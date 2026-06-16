import asyncio
import logging
import signal
import time
from datetime import datetime, timezone
from typing import Any, Dict, Set
import MetaTrader5 as mt5

from src.config.mt5_config import get_mt5_config
from src.services.mt5_service import MT5Service, find_mt5_terminals
from src.services.tradingview_service import TradingViewService
from src.utils.database_handler import DatabaseHandler
from app.queue.inproc_queue import InProcQueue
from src.utils.number_format import fmt_num
from src.utils.token_manager import GLOBAL_TOKEN_MANAGER

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
        self._monitor_task = None
        # Serialises MT5 access: trade execution, the position-check loop, and a
        # broker-profile hot-swap (reconnect_mt5) all drive the process-global
        # MetaTrader5 connection, so they must never overlap across awaits.
        self._mt5_lock = asyncio.Lock()

    def initialize(self):
        """Initialize all services with shared event loop."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # Check MT5 terminal path before initialization
        mt5_config = get_mt5_config()
        terminal_path = mt5_config['terminal_path']
        if not terminal_path:
            print("\n⚠️  MT5 terminal path not configured")
            print("Available MT5 terminals:")
            terminals = find_mt5_terminals()
            for i, path in enumerate(terminals, 1):
                print(f"{i}. {path}")
            print("\nConfigure the terminal path in Settings (or .env until then).")
        
        # Initialize services
        self.queue = InProcQueue()
        self.queue.loop = self.loop
        
        self.db = DatabaseHandler()
        
        self.mt5 = MT5Service(
            account=mt5_config['account'],
            password=mt5_config['password'],
            server=mt5_config['server'],
            db_handler=self.db
        )
        self.mt5.set_loop(self.loop)

        self.tv_service = TradingViewService(
            token_manager=GLOBAL_TOKEN_MANAGER
        )

    def init_inproc(self, loop, queue, db):
        """Initialize the worker to share an existing event loop, queue, and db.

        Used by app/engine.py so the proxy and worker run on one loop. Unlike
        initialize(), this does NOT create a new event loop or its own queue/db.
        """
        self.loop = loop
        self.queue = queue
        self.db = db

        mt5_config = get_mt5_config()
        self.mt5 = MT5Service(
            account=mt5_config['account'],
            password=mt5_config['password'],
            server=mt5_config['server'],
            db_handler=self.db,
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
                    print(f"\n📊 Initialized {len(self.open_positions)} open positions\n")
        except Exception as e:
            logger.error(f"❌ Error initializing positions: {e}")

    def _start_trailing_monitor(self) -> None:
        """Start the trailing-stop monitor (assumes any previous one was stopped)."""
        if self.mt5 and self.mt5.initialized:
            self._monitor_task = self.loop.create_task(self.mt5.monitor_trailing_stops())

    async def _stop_trailing_monitor(self) -> None:
        """Cancel the trailing-stop monitor and WAIT for it to finish, so it can't
        still be mid-call against the global MT5 connection when we swap it out."""
        task = self._monitor_task
        self._monitor_task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as e:  # noqa: BLE001
                logger.error(f"❌ Trailing monitor error during shutdown: {e}")

    async def reconnect_mt5(self) -> None:
        """Switch the MT5 connection to the current (active-profile) config WITHOUT
        restarting the proxy.

        Used when a broker profile is activated: only the MT5 side needs to change
        (account/server/terminal/password), so we close the existing MT5 session
        and rebuild MT5Service from the latest settings. The proxy on its port keeps
        running untouched, avoiding a Windows port-rebind failure.

        Held under _mt5_lock so an in-flight trade or the position-check loop can't
        interleave with the teardown/rebuild of the shared global MT5 connection.
        """
        logger.info("🔄 Switching MT5 connection to the active profile…")
        async with self._mt5_lock:
            # Stop the old monitor first and wait for it, so it isn't mid-call on
            # the connection we're about to shut down.
            await self._stop_trailing_monitor()
            try:
                if self.mt5 is not None:
                    self.mt5.cleanup()
            except Exception as e:
                logger.error(f"❌ Error closing previous MT5 connection: {e}")
            mt5_config = get_mt5_config()
            self.mt5 = MT5Service(
                account=mt5_config['account'],
                password=mt5_config['password'],
                server=mt5_config['server'],
                db_handler=self.db,
            )
            self.mt5.set_loop(self.loop)
            # Positions belong to the new broker — reset and re-read.
            self.open_positions = set()
            await self._initialize_positions()
            self._start_trailing_monitor()

    async def handle_message(self, msg_type: str, data: Dict[str, Any]) -> None:
        """Handle messages from Redis channels asynchronously."""
        try:
            if msg_type == 'trade':
                await self.process_trade(data['data'])
            # elif msg_type == 'status':
                # print(f"📡 Status: {data['message']}")
            elif msg_type == 'error':
                logger.error(f"❌ Queue error: {data['error']}")
        except Exception as e:
            logger.error(f"❌ Error handling message: {e}")

    async def process_trade(self, trade_data: Dict[str, Any]) -> None:
        """Process a single trade, serialised against MT5 reconnects/position checks."""
        async with self._mt5_lock:
            await self._process_trade_locked(trade_data)

    async def _process_trade_locked(self, trade_data: Dict[str, Any]) -> None:
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
                        'closed_at': datetime.now(timezone.utc)
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
            execution_price = result.get('price') or trade_data.get('execution_data', {}).get('price', 0.0)

            print(f"✔  Position OPENED: {direction_emoji} {result.get('symbol')} x {fmt_num(result.get('volume'))} @ {fmt_num(execution_price)}")
            print(f"🔗 References: TV# {position_id} --> MT5# {mt5_ticket}")
            
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
        try:
            position_id = trade_data.get('execution_data', {}).get('positionId', 'N/A')
            mt5_ticket = trade_data.get('mt5_ticket', 'Pending')
            is_partial = trade_data.get('is_partial', False)
            close_amount = float(trade_data.get('qty', 0))
                        
            # Send close request
            result = await self.mt5.async_close_position(trade_data)
            
            if 'error' in result:
                status = 'failed'
                update_data = {
                    'error_message': result['error'],
                    'mt5_response': result,
                    'execution_time_ms': int(time.time() * 1000) - start_time
                }
                print(f"❌ Close Failed: {result['error']} (TV #{position_id} --> MT5 #{mt5_ticket})")
            else:
                status = 'closed' if not is_partial else 'updated'
                update_data = {
                    'mt5_response': result,
                    'execution_time_ms': int(time.time() * 1000) - start_time,
                    'is_closed': not is_partial,
                    'closed_at': datetime.now(timezone.utc) if not is_partial else None
                }
                
                mt5_ticket = str(trade_data.get('mt5_ticket'))
                if not is_partial:
                    self.open_positions.discard(mt5_ticket)
                
                direction = trade_data.get('execution_data', {}).get('side', '').lower()
                direction_emoji = "SELL🔻" if direction == 'buy' else "BUY🔼"
                execution_price = result.get('price') or trade_data.get('execution_data', {}).get('price', 0.0)

                print(f"{'🛡  Position partially closed' if is_partial else '📌 Position CLOSED'}: {direction_emoji} {result.get('symbol')} {fmt_num(result.get('volume'))} @ {fmt_num(execution_price)}")
                print(f"🔗 References: TV# {position_id} --> MT5# {mt5_ticket}")
                
                if is_partial:
                    remaining = result.get('remaining_volume', 0)
                    print(f"🔳 Remaining volume: {fmt_num(remaining)}")
                    
                    
                print(f"⚡ Execution time: {update_data['execution_time_ms']}ms\n")
            
            await self.db.async_update_trade_status(trade_id, status, update_data)
            
        except Exception as e:
            logger.error(f"❌ Error in _handle_position_close: {e}")
            if 'trade_id' in trade_data:
                await self.db.async_update_trade_status(
                    trade_data['trade_id'],
                    'failed',
                    {
                        'error_message': str(e),
                        'closed_at': datetime.now(timezone.utc)
                    }
                )

    async def _handle_position_update(self, trade_data: Dict[str, Any], trade_id: str, start_time: int) -> None:
        """Handle updating TP/SL for an existing position."""
        try:
            position_id = trade_data.get('position_id', 'N/A')
            mt5_ticket = trade_data.get('mt5_ticket', 'N/A')
            
            # Get current trade data
            trade = await self.db.async_get_trade_by_mt5_ticket(mt5_ticket)
            if not trade:
                logger.error(f"No trade found for MT5 ticket {mt5_ticket}")
                return
                
            if trade.get('is_closed'):
                logger.info(f"Position {mt5_ticket} is already closed, skipping update")
                return
            
            result = await self.mt5.async_update_position(trade_data)
            
            if 'error' not in result:
                status = 'updated'
                update_data = {
                    'mt5_response': result,
                    'execution_time_ms': int(time.time() * 1000) - start_time,
                    'take_profit': result.get('take_profit'),
                    'stop_loss': result.get('stop_loss')
                }

                print(f"💱 Position updated for {result.get('symbol')} x {fmt_num(trade.get('quantity'))} @ {fmt_num(trade.get('execution_price'))}")
                print(f"🔗 References: TV# {position_id} --> MT5# {mt5_ticket}")
                
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
                print(f"❌ Update Failed: {result['error']} (TV #{position_id} --> MT5# {mt5_ticket})")
            
            await self.db.async_update_trade_status(trade_id, status, update_data)
            
        except Exception as e:
            logger.error(f"❌ Error in _handle_position_update: {e}")
            await self.db.async_update_trade_status(
                trade_id,
                'failed',
                {
                    'error_message': str(e),
                    'closed_at': datetime.now(timezone.utc)
                }
            )

    async def check_mt5_positions(self) -> None:
        """Monitor MT5 positions for manual closes, serialised against reconnects."""
        async with self._mt5_lock:
            await self._check_mt5_positions_locked()

    async def _check_mt5_positions_locked(self) -> None:
        try:
            if not await self.mt5.async_initialize():
                return

            positions = await self.loop.run_in_executor(None, mt5.positions_get)
            if positions is None:
                return

            current_position_tickets = {str(pos.ticket) for pos in positions}

            for ticket in self.open_positions.copy():
                # Check if position exists in current positions
                if ticket not in current_position_tickets:
                    await self.handle_mt5_close(ticket)
                    self.open_positions.discard(ticket)

            self.open_positions = current_position_tickets

        except Exception as e:
            logger.error(f"❌ Error checking positions: {e}")

    async def handle_mt5_close(self, ticket: str) -> None:
        """Handle position closed in MT5 asynchronously."""
        try:            
            print(f"📤 Processing MT5-initiated close for Ticket#: {ticket}")
                
            # Get trade data from database
            trade = await self.db.async_get_trade_by_mt5_ticket(ticket)
            if not trade:
                logger.info(f"ℹ️ No trade found for MT5 ticket {ticket}\n")
                return
                    
            if trade.get('is_closed'):
                print()
                return

            position_id = trade.get('position_id')
            if not position_id:
                logger.error(f"❌ No position ID for trade {trade['trade_id']}\n")
                return

            # First update database status
            await self.db.async_update_trade_status(trade['trade_id'], 'closed', {
                'is_closed': True,
                'closed_at': datetime.now(timezone.utc)
            })

            # Log position details
            direction = trade.get('side', '').lower()
            direction_emoji = "BUY🔼" if direction == 'buy' else "SELL🔻"
            
            # Send close request to TradingView
            result = await self.tv_service.async_close_position(position_id)
            
            if result.get('error'):
                if not '404' in str(result['error']):
                    logger.error(f"❌ Failed to close TV position: {result['error']}\n")
                return

            print(f"📌 Closed {direction_emoji} {trade['instrument']} x {fmt_num(trade['quantity'])}")
            print(f"🔗 References: TV# {position_id} <-- MT5# {ticket}\n")

        except Exception as e:
            logger.error(f"❌ Error handling MT5 close: {e}\n")
            if 'trade' in locals() and trade:
                await self.db.async_update_trade_status(trade['trade_id'], 'failed', {
                    'error_message': str(e),
                    'closed_at': datetime.now(timezone.utc)
                })
    
    async def run_async(self):
        """Run the worker service asynchronously."""
        print("\n🚀 MT5 Worker Started")
        print("👀 Watching for trades...\n")
        
        try:
            # Initialize positions
            await self._initialize_positions()

            # Start trailing stop monitor as a task
            self._start_trailing_monitor()

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