import logging
import time
import asyncio
from typing import Dict, Any, Set
from datetime import datetime, timezone
import MetaTrader5 as mt5
from src.core.interceptor import GLOBAL_TOKEN_MANAGER
from src.utils.queue_handler import RedisQueue
from src.services.mt5_service import MT5Service
from src.services.tradingview_service import TradingViewService
from src.utils.database_handler import DatabaseHandler
from src.config.mt5_config import MT5_CONFIG

logger = logging.getLogger('MT5Worker')

class MT5Worker:
    def __init__(self):
        self.running = True
        self.open_positions: Set[str] = set()
        self.loop = None
        self.queue = None
        self.db = None
        self.mt5 = None
        self.tv_service = None

    def initialize(self):
        """Initialize all services with shared event loop."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # Initialize services
        self.queue = RedisQueue()
        self.queue.loop = self.loop
        
        self.db = DatabaseHandler()
        
        self.mt5 = MT5Service(
            account=MT5_CONFIG['account'],
            password=MT5_CONFIG['password'],
            server=MT5_CONFIG['server']
        )
        self.mt5.set_loop(self.loop)
        
        self.tv_service = TradingViewService(
            token_manager=GLOBAL_TOKEN_MANAGER
        )

    async def _initialize_positions(self) -> None:
        """Initialize open positions set on startup."""
        try:
            if await self.mt5.async_initialize():
                positions = await self.loop.run_in_executor(None, mt5.positions_get)
                if positions is not None:
                    self.open_positions = {str(pos.ticket) for pos in positions}
                    print(f"📊 Initialized {len(self.open_positions)} open positions")
                    logger.info(f"Initialized {len(self.open_positions)} open positions")
        except Exception as e:
            logger.error(f"❌ Error initializing positions: {e}")

    async def handle_message(self, msg_type: str, data: Dict[str, Any]) -> None:
        """Handle messages from Redis channels asynchronously."""
        try:
            if msg_type == 'trade':
                await self.process_trade(data['data'])
            elif msg_type == 'status':
                print(f"📡 Status: {data['message']}")
            elif msg_type == 'error':
                logger.error(f"❌ Queue error: {data['error']}")
        except Exception as e:
            logger.error(f"❌ Error handling message: {e}")

    async def process_trade(self, trade_data: Dict[str, Any]) -> None:
        """Process a single trade asynchronously."""
        try:
            trade_id = trade_data['trade_id']
            start_time = int(time.time() * 1000)
            
            # Different emojis for new trade vs close
            operation = "CLOSE" if trade_data.get('execution_data', {}).get('isClose', False) else "NEW"
            trade_emoji = "📤" if operation == "CLOSE" else "📥"
            print(f"\n{trade_emoji} Processing {operation} trade: {trade_id}")
            
            # Execute or close based on isClose flag
            if trade_data.get('execution_data', {}).get('isClose', False):
                result = await self.mt5.async_close_position(trade_data)
                
                if 'error' in result and 'No position found' in result['error']:
                    status = 'closed'
                    update_data = {
                        'mt5_response': result,
                        'execution_time_ms': int(time.time() * 1000) - start_time,
                        'is_closed': True,
                        'closed_at': datetime.now(timezone.utc).isoformat()
                    }
                    mt5_ticket = str(trade_data.get('mt5_ticket'))
                    self.open_positions.discard(mt5_ticket)
                    
                elif 'error' not in result:
                    status = 'closed'
                    update_data = {
                        'mt5_response': result,
                        'execution_time_ms': int(time.time() * 1000) - start_time,
                        'is_closed': True,
                        'closed_at': datetime.now(timezone.utc).isoformat()
                    }
                    mt5_ticket = str(trade_data.get('mt5_ticket'))
                    self.open_positions.discard(mt5_ticket)
                    await self.db.async_update_trade_status(trade_id, status, update_data)
                    
                    direction = trade_data.get('execution_data', {}).get('side', '').lower()
                    direction_emoji = "SHORT🔻" if direction == 'buy' else "LONG🔼"
                    print(f"📍 Position CLOSED: {direction_emoji} {result.get('symbol')} {result.get('volume')} @ {result.get('price')}")
                    print(f"⚡ Execution time: {update_data['execution_time_ms']}ms")
                    return
                    
                else:
                    status = 'failed'
                    update_data = {
                        'error_message': result['error'],
                        'mt5_response': result,
                        'execution_time_ms': int(time.time() * 1000) - start_time
                    }
                    print(f"❌ Close Failed: {result['error']}")
            else:
                result = await self.mt5.async_execute_market_order(trade_data)
                
                if 'error' not in result:
                    status = 'completed'
                    update_data = {
                        'mt5_ticket': result['mt5_ticket'],
                        'mt5_response': result,
                        'execution_time_ms': int(time.time() * 1000) - start_time
                    }
                    self.open_positions.add(str(result['mt5_ticket']))
                    direction = trade_data.get('execution_data', {}).get('side', '').lower()
                    direction_emoji = "LONG🔼" if direction == 'buy' else "SHORT🔻"
                    print(f"✔  Position OPENED: {direction_emoji} {result.get('symbol')} x {result.get('volume')} @ {result.get('price')}")
                else:
                    status = 'failed'
                    update_data = {
                        'error_message': result['error'],
                        'mt5_response': result,
                        'execution_time_ms': int(time.time() * 1000) - start_time
                    }
                    print(f"❌ Open Failed: {result['error']}")
            
            await self.db.async_update_trade_status(trade_id, status, update_data)
            
            if 'error' not in result and not trade_data.get('execution_data', {}).get('isClose', False):
                print(f"⚡ Execution time: {update_data['execution_time_ms']}ms")
                if result.get('take_profit') or result.get('stop_loss'):
                    print(f"🎯 TP: {result.get('take_profit')} | SL: {result.get('stop_loss')}")

        except Exception as e:
            logger.error(f"❌ Error processing trade: {e}")
            if 'trade_id' in trade_data:
                await self.db.async_update_trade_status(
                    trade_data['trade_id'],
                    'failed',
                    {
                        'error_message': str(e),
                        'closed_at': datetime.now(timezone.utc).isoformat()
                    }
                )

    async def check_mt5_positions(self) -> None:
        """Monitor MT5 positions for manual closes asynchronously."""
        try:
            if not await self.mt5.async_initialize():
                return

            positions = await self.loop.run_in_executor(None, mt5.positions_get)
            if positions is None:
                return

            current_position_tickets = {str(pos.ticket) for pos in positions}

            for ticket in self.open_positions.copy():
                if ticket not in current_position_tickets:
                    await self.handle_mt5_close(ticket)
                    self.open_positions.discard(ticket)

            self.open_positions = current_position_tickets

        except Exception as e:
            logger.error(f"❌ Error checking positions: {e}")

    async def handle_mt5_close(self, mt5_ticket: str) -> None:
        """Handle position closed in MT5 asynchronously."""
        try:            
            trade = await self.db.async_get_trade_by_mt5_ticket(mt5_ticket)
            if not trade:
                logger.info(f"ℹ️ No trade found for MT5 ticket {mt5_ticket}")
                return
                
            if trade.get('is_closed'):
                return

            position_id = trade.get('position_id')
            if not position_id:
                logger.error(f"❌ No position ID for trade {trade['trade_id']}")
                return

            result = await self.tv_service.async_close_position(position_id)
            
            if result.get('error'):
                if '404' in str(result['error']):
                    await self.db.async_update_trade_status(trade['trade_id'], 'closed', {
                        'is_closed': True,
                        'closed_at': datetime.now(timezone.utc).isoformat()
                    })
                else:
                    logger.error(f"❌ Failed to close TV position: {result['error']}")
                return

            direction = trade.get('side', '').lower()
            direction_emoji = "LONG🔼" if direction == 'buy' else "SHORT🔻"
            print(f"\n📍 Position CLOSED in TV: {direction_emoji} {trade['instrument']} {trade['quantity']}") 

            await self.db.async_update_trade_status(trade['trade_id'], 'closed', {
                'is_closed': True,
                'closed_at': datetime.now(timezone.utc).isoformat()
            })

        except Exception as e:
            logger.error(f"❌ Error handling MT5 close: {e}")
            if 'trade' in locals() and trade:
                await self.db.async_update_trade_status(trade['trade_id'], 'failed', {
                    'error_message': str(e),
                    'closed_at': datetime.now(timezone.utc).isoformat()
                })

    async def run_async(self):
        """Run the worker service asynchronously."""
        print("\n🚀 MT5 Worker Started")
        print("👀 Watching for trades...\n")
        
        try:
            # Initialize positions
            await self._initialize_positions()
            
            # Main loop for position checking
            while self.running:
                try:
                    await self.check_mt5_positions()
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"❌ Error in position check: {e}")
                    await asyncio.sleep(1)
                    
        except Exception as e:
            logger.error(f"❌ Fatal error: {e}")
        finally:
            self.running = False
            print("\n🛑 Worker stopped")

    def run(self):
        """Run the worker service."""
        try:
            # Initialize services
            self.initialize()
            
            # Subscribe to Redis channels
            self.queue.subscribe(self.handle_message)
            
            # Run the main async loop
            self.loop.run_until_complete(self.run_async())
            
        except KeyboardInterrupt:
            print("\n⛔ Shutdown requested...")
        except Exception as e:
            logger.error(f"❌ Fatal error: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup resources."""
        logger.info("🧹 Cleaning up resources...")
        if self.mt5:
            self.mt5.cleanup()
        if self.db:
            self.db.cleanup()
        if self.queue:
            self.queue.cleanup()
        if self.loop:
            self.loop.close()