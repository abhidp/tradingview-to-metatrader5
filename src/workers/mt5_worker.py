import logging
import signal
import time
import asyncio
from typing import Dict, Any, Set
from datetime import datetime, timezone
import MetaTrader5 as mt5
from src.utils.token_manager import GLOBAL_TOKEN_MANAGER
from src.utils.queue_handler import RedisQueue
from src.services.mt5_service import MT5Service
from src.services.tradingview_service import TradingViewService
from src.utils.database_handler import DatabaseHandler
from src.config.mt5_config import MT5_CONFIG

logger = logging.getLogger('MT5Worker')

class MT5Worker:
    def __init__(self):
        self.running = True
        self.shutdown_event = asyncio.Event()
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
                    print(f"📊 Initialized {len(self.open_positions)} open positions\n")
                    # logger.info(f"Initialized {len(self.open_positions)} open positions\n")
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
            
            # Get common reference IDs
            position_id = trade_data.get('execution_data', {}).get('positionId', 'N/A')
            mt5_ticket = trade_data.get('mt5_ticket', 'Pending')
            
            # Handle TP/SL updates
            if trade_data.get('type') == 'update':
                await self._handle_position_update(trade_data, trade_id, start_time)
                return
                
            # Handle position close
            if trade_data.get('execution_data', {}).get('isClose', False):
                await self._handle_position_close(trade_data, trade_id, start_time)
                return
                
            # Handle new position
            await self._handle_new_position(trade_data, trade_id, start_time)
            
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

    async def _handle_new_position(self, trade_data: Dict[str, Any], trade_id: str, start_time: int) -> None:
        """Handle opening a new position."""
        position_id = trade_data.get('execution_data', {}).get('positionId', 'N/A')
        result = await self.mt5.async_execute_market_order(trade_data)
        
        if 'error' not in result:
            status = 'completed'
            update_data = {
                'mt5_ticket': result['mt5_ticket'],
                'mt5_response': result,
                'execution_time_ms': int(time.time() * 1000) - start_time
            }
            
            mt5_ticket = str(result['mt5_ticket'])
            self.open_positions.add(mt5_ticket)
            
            # Log success
            direction = trade_data.get('execution_data', {}).get('side', '').lower()
            direction_emoji = "BUY🔼" if direction == 'buy' else "SELL🔻"
            print(f"✔  Position OPENED: {direction_emoji} {result.get('symbol')} x {result.get('volume')} @ {result.get('price')}")
            print(f"🔗 References: TV #{position_id} --> MT5 #{mt5_ticket}")
            
            if result.get('take_profit') or result.get('stop_loss'):
                print(f"🎯 TP: {result.get('take_profit')} | SL: {result.get('stop_loss')}")
            print(f"⚡ Execution time: {update_data['execution_time_ms']}ms\n")
        else:
            status = 'failed'
            update_data = {
                'error_message': result['error'],
                'mt5_response': result,
                'execution_time_ms': int(time.time() * 1000) - start_time
            }
            print(f"❌ Open Failed: {result['error']} (TV #{position_id})")
        
        await self.db.async_update_trade_status(trade_id, status, update_data)

    async def _handle_position_close(self, trade_data: Dict[str, Any], trade_id: str, start_time: int) -> None:
        """Handle closing an existing position."""
        position_id = trade_data.get('execution_data', {}).get('positionId', 'N/A')
        mt5_ticket = trade_data.get('mt5_ticket', 'Pending')
        
        # print(f"📤 Processing CLOSE TradeId#: {trade_id}")
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
            
            direction = trade_data.get('execution_data', {}).get('side', '').lower()
            direction_emoji = "SELL🔻" if direction == 'buy' else "BUY🔼"
            print(f"📌 Position CLOSED: {direction_emoji} {result.get('symbol')} {result.get('volume')} @ {result.get('price')}")
            print(f"🔗 References: TV #{position_id} --> MT5 #{mt5_ticket}")
            print(f"⚡ Execution time: {update_data['execution_time_ms']}ms\n")
            
        else:
            status = 'failed'
            update_data = {
                'error_message': result['error'],
                'mt5_response': result,
                'execution_time_ms': int(time.time() * 1000) - start_time
            }
            print(f"❌ Close Failed: {result['error']} (TV #{position_id} --> MT5 #{mt5_ticket})")
        
        await self.db.async_update_trade_status(trade_id, status, update_data)

    async def _handle_position_update(self, trade_data: Dict[str, Any], trade_id: str, start_time: int) -> None:
        """Handle updating TP/SL for an existing position."""
        position_id = trade_data.get('position_id', 'N/A')
        mt5_ticket = trade_data.get('mt5_ticket', 'N/A')
        
        # print(f"📝 Processing UPDATE TradeId#: {trade_id}")
        result = await self.mt5.async_update_position(trade_data)
        
        if 'error' not in result:
            status = 'updated'
            update_data = {
                'mt5_response': result,
                'execution_time_ms': int(time.time() * 1000) - start_time
            }
            
            print(f"🔄 Position updated in MT5: #{mt5_ticket}")
            print(f"🔗 References: TV #{position_id} --> MT5 #{mt5_ticket}")
            
            if result.get('take_profit') or result.get('stop_loss'):
                print(f"🎯 New TP: {result.get('take_profit')} | SL: {result.get('stop_loss')}")
            print(f"⚡ Execution time: {update_data['execution_time_ms']}ms\n")
            
        else:
            status = 'failed'
            update_data = {
                'error_message': result['error'],
                'mt5_response': result,
                'execution_time_ms': int(time.time() * 1000) - start_time
            }
            print(f"❌ Update Failed: {result['error']} (TV #{position_id} --> MT5 #{mt5_ticket})")
        
        await self.db.async_update_trade_status(trade_id, status, update_data)

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
            # Add initial logging
            print(f"📤 Processing MT5-initiated close for Ticket#: {mt5_ticket}")
                
            trade = await self.db.async_get_trade_by_mt5_ticket(mt5_ticket)
            if not trade:
                logger.info(f"ℹ️ No trade found for MT5 ticket {mt5_ticket}\n")
                return
                    
            if trade.get('is_closed'):
                print()
                return

            position_id = trade.get('position_id')
            if not position_id:
                logger.error(f"❌ No position ID for trade {trade['trade_id']}\n")
                return

            # Log position details
            direction = trade.get('side', '').lower()
            direction_emoji = "BUY🔼" if direction == 'buy' else "SELL🔻"
            
            # Close in TradingView
            result = await self.tv_service.async_close_position(position_id)
            
            if result.get('error'):
                if '404' in str(result['error']):
                    await self.db.async_update_trade_status(trade['trade_id'], 'closed', {
                        'is_closed': True,
                        'closed_at': datetime.now(timezone.utc).isoformat()
                    })
                else:
                    logger.error(f"❌ Failed to close TV position: {result['error']}\n")
                return

            print(f"📌 Position CLOSED in TV: {direction_emoji} {trade['instrument']} {trade['quantity']}")
            print(f"🔗 References: TV #{position_id} <-- MT5 #{mt5_ticket}\n" )

            await self.db.async_update_trade_status(trade['trade_id'], 'closed', {
                'is_closed': True,
                'closed_at': datetime.now(timezone.utc).isoformat()
            })

            # Add summary log
            # print(f"💱 Close sync completed: {direction_emoji} {trade['instrument']} {trade['quantity']}")

        except Exception as e:
            logger.error(f"❌ Error handling MT5 close: {e}\n")
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

    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info("\n⛔ Shutdown requested...")
        self.running = False
        if self.loop:
            self.loop.call_soon_threadsafe(self.shutdown_event.set)

    async def shutdown(self):
        """Perform async shutdown tasks."""
        logger.info("🛑 Initiating shutdown sequence...")
        self.running = False
        
        # Wait a bit for ongoing operations to complete
        await asyncio.sleep(0.5)
        
        # Cleanup resources
        self.cleanup()
        logger.info("✅ Shutdown completed")

    def run(self):
        """Run the worker service with proper signal handling."""
        try:
            # Initialize services
            self.initialize()
            
            # Set up signal handlers
            signal.signal(signal.SIGINT, self.handle_shutdown)
            signal.signal(signal.SIGTERM, self.handle_shutdown)
            
            # Subscribe to Redis channels
            self.queue.subscribe(self.handle_message)
            
            # Run the main async loop
            self.loop.run_until_complete(self.run_async())
            
        except KeyboardInterrupt:
            logger.info("\n⛔ Keyboard interrupt received...")
        except Exception as e:
            logger.error(f"❌ Fatal error: {e}")
        finally:
            # Run shutdown sequence
            self.loop.run_until_complete(self.shutdown())
            self.loop.close()
    
    def cleanup(self):
        """Cleanup resources in correct order."""
        logger.info("🧹 Cleaning up resources...")
        
        # Clean up MT5 first
        if self.mt5:
            self.mt5.cleanup()
        
        # Then database
        if self.db:
            self.db.cleanup()
        
        # Redis cleanup last (after all other operations are done)
        if self.queue:
            self.queue.cleanup()
        
        logger.info("✨ All resources cleaned up")