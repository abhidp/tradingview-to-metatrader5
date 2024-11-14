import asyncio
import logging
from datetime import datetime
from typing import Any, Dict

import MetaTrader5 as mt5

from src.utils.database_handler import DatabaseHandler
from src.utils.queue_handler import RedisQueue

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('TradeHandler')

class TradeHandler:
    def __init__(self):
        self.db = DatabaseHandler()
        self.queue = RedisQueue()
        self.pending_orders = {}  # Track order->execution mapping
        self.loop = asyncio.get_event_loop()
    
    async def process_order(self, request_data: Dict[str, Any], response_data: Dict[str, Any]) -> None:
        """Process new order from TradingView asynchronously."""
        try:
            trade_id = f"TV_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{response_data['d']['orderId']}"
            
            # Convert TP/SL to float if present
            take_profit = float(request_data['takeProfit']) if 'takeProfit' in request_data else None
            stop_loss = float(request_data['stopLoss']) if 'stopLoss' in request_data else None
            
            # Store the order ID for TP/SL separately
            tp_order_id = response_data['d'].get('takeProfitOrderId')
            sl_order_id = response_data['d'].get('stopLossOrderId')
            
            trade_data = {
                'trade_id': trade_id,
                'order_id': response_data['d']['orderId'],
                'tp_order_id': tp_order_id,
                'sl_order_id': sl_order_id,
                'instrument': request_data['instrument'],
                'side': request_data['side'],
                'quantity': request_data['qty'],
                'type': request_data['type'],
                'ask_price': request_data['currentAsk'],
                'bid_price': request_data['currentBid'],
                'take_profit': take_profit,
                'stop_loss': stop_loss,
                'status': 'pending',
                'tv_request': request_data,
                'tv_response': response_data,
                'created_at': datetime.utcnow()
            }
            
            # Get direction emoji
            direction_emoji = "🔼" if request_data['side'].lower() == 'buy' else "🔻"
            
            # Log new order with improved format
            print(f"\n{direction_emoji} New {request_data['side'].upper()} order: {request_data['instrument']} x {request_data['qty']}")
            if take_profit or stop_loss:
                print(f"🎯 TP: {take_profit} | SL: {stop_loss}")
            
            # Store in database asynchronously
            await self.db.async_save_trade(trade_data)
            self.pending_orders[response_data['d']['orderId']] = trade_id
            
            if tp_order_id:
                self.pending_orders[tp_order_id] = trade_id
            if sl_order_id:
                self.pending_orders[sl_order_id] = trade_id
            
        except Exception as e:
            logger.error(f"Error processing order: {e}")
            print(f"❌ Order failed: {e}")

    async def process_execution(self, execution_data: Dict[str, Any]) -> None:
        """Process execution update from TradingView asynchronously."""
        try:
            executions = execution_data.get('d', [])
            for execution in executions:
                order_id = execution.get('orderId')
                if order_id and order_id in self.pending_orders:
                    trade_id = self.pending_orders[order_id]
                    position_id = execution.get('positionId')
                    
                    # Get original trade data asynchronously
                    original_trade = await self.db.async_get_trade(trade_id)
                    if not original_trade:
                        logger.error(f"Trade not found: {trade_id}")
                        continue
                    
                    # Prepare trade data
                    trade_data = {
                        'trade_id': trade_id,
                        'execution_data': execution,
                        'position_id': position_id,
                        'instrument': original_trade.get('instrument'),
                        'side': original_trade.get('side'),
                        'qty': original_trade.get('quantity'),
                        'type': original_trade.get('type'),
                        'take_profit': original_trade.get('take_profit'),
                        'stop_loss': original_trade.get('stop_loss')
                    }

                    # Update database asynchronously
                    update_data = {
                        'position_id': position_id,
                        'execution_price': execution.get('price'),
                        'execution_data': execution,
                        'executed_at': datetime.utcnow(),
                        'is_closed': execution.get('isClose', False)
                    }
                    
                    await self.db.async_update_trade_status(trade_id, 'executed', update_data)
                    
                    # Publish trade for execution asynchronously
                    await self.queue.async_push_trade(trade_data)
                    print(f"✔  Trade executed - TV PositionID#: {position_id}")
                    print(f"💲 Average Fill Price - {update_data['execution_price']}")

                    
                    del self.pending_orders[order_id]
                    
        except Exception as e:
            logger.error(f"Error processing execution: {e}")

    async def process_position_close(self, position_id: str, close_data: Dict[str, Any] = None) -> None:
        """Process position close request from TradingView asynchronously."""
        try:
            close_data = close_data or {}  # Ensure close_data is dict
            print(f"\n📤 Closing PositionID#: {position_id}")
            
            # Get trade data asynchronously
            trade = await self.db.async_get_trade_by_position(position_id)
            if not trade:
                logger.error(f"No trade found for position {position_id}")
                return           
            
            mt5_ticket = trade.get('mt5_ticket')
            if not mt5_ticket:
                logger.error(f"No MT5 ticket found for trade {trade['trade_id']}")
                return

            try:
                # Initialize MT5 connection if needed
                if not mt5.initialize():
                    logger.error("Failed to initialize MT5")
                    return

                # Get specific position
                positions = mt5.positions_get(ticket=int(mt5_ticket))

                if not positions:
                    # If position not found in MT5, add the closing log here
                    direction_emoji = "BUY🔼" if trade['side'].lower() == 'buy' else "SELL🔻"
                    print(f"📌 Closed {direction_emoji} {trade['instrument']} x {trade['quantity']}")
                    return
                    
            except Exception as e:
                logger.error(f"Error getting MT5 position: {e}")
                logger.error(f"MT5 last error: {mt5.last_error()}")
                return
            
            current_volume = float(positions[0].volume)
            
            # Get direction emoji
            direction_emoji = "BUY🔼" if trade['side'].lower() == 'buy' else "SELL🔻"

            # Handle partial close
            try:
                close_amount = float(close_data.get('amount', current_volume))
                
                # Validate close amount
                if close_amount <= 0 or close_amount > current_volume:
                    logger.error(f"Invalid close amount: {close_amount} (current volume: {current_volume})")
                    return
                    
                # Check if this closes the entire remaining position
                is_partial = close_amount < current_volume
            except Exception as e:
                logger.error(f"Error processing close amount: {e}")
                return

            # Prepare close data
            close_request = {
                'trade_id': trade['trade_id'],
                'mt5_ticket': mt5_ticket,
                'instrument': trade['instrument'],
                'type': 'market',
                'qty': str(close_amount),
                'is_partial': is_partial,
                'side': 'sell' if trade['side'] == 'buy' else 'buy',
                'execution_data': {
                    'instrument': trade['instrument'],
                    'positionId': position_id,
                    'qty': str(close_amount),
                    'side': 'sell' if trade['side'] == 'buy' else 'buy',
                    'isClose': True
                }
            }
            
            # Publish close request asynchronously
            await self.queue.async_push_trade(close_request)
            
            # Update status asynchronously
            close_status = 'closing' if is_partial else 'closed'
            status_update = {
                'close_requested_at': datetime.utcnow().isoformat(),
                'is_closed': not is_partial  # Only mark as closed for full closes
            }
            await self.db.async_update_trade_status(
                trade['trade_id'], 
                close_status, 
                status_update
            )
            
            # Log close action with consistent format
            if is_partial:
                print(f"⭕ Partially closing {direction_emoji} {trade['instrument']} x {close_amount}")
            else:
                print(f"📌 Closed {direction_emoji} {trade['instrument']} x {close_amount}")

        except Exception as e:
            logger.error(f"Error processing position close: {e}")

    async def process_position_update(self, position_id: str, update_data: Dict[str, Any] = None) -> None:
        """Process position update from TradingView asynchronously."""
        try:
            # Check for TradingView error response first
            if isinstance(update_data, dict) and ('s' in update_data or 'errmsg' in update_data):
                error_msg = update_data.get('errmsg') or update_data.get('error', 'Unknown error')
                if 's' in update_data and update_data['s'] == 'error':
                    print(f"\n❌ TP/SL Update Failed - PositionID#: {position_id}")
                    print(f"⚠  Error: {error_msg}")
                    return


            update_data = update_data or {}  # Ensure update_data is dict
            
            # Get trade data asynchronously
            trade = await self.db.async_get_trade_by_position(position_id)
            if not trade:
                logger.error(f"No trade found for position {position_id}")
                return
            
            # Convert TP/SL to float if present
            take_profit = float(update_data.get('takeProfit')) if 'takeProfit' in update_data else None
            stop_loss = float(update_data.get('stopLoss')) if 'stopLoss' in update_data else None
            
            if not take_profit and not stop_loss:
                logger.error(f"No TP/SL update found in request data")
                return
                    
            # Get current TP/SL values from trade
            current_tp = trade.get('take_profit')
            current_sl = trade.get('stop_loss')
                    
            # Prepare update data for queue
            update_trade_data = {
                'trade_id': trade['trade_id'],
                'mt5_ticket': trade.get('mt5_ticket'),
                'instrument': trade['instrument'],
                'position_id': position_id,
                'take_profit': take_profit if take_profit is not None else current_tp,
                'stop_loss': stop_loss if stop_loss is not None else current_sl,
                'type': 'update'
            }
            
            # Log the update request with previous and new values
            print(f"\n💱 Updating TP/SL for PositionID#: {position_id}")
            if take_profit is not None:
                print(f"🟢 TP: {current_tp} → {take_profit}")
            if stop_loss is not None:
                print(f"🛑 SL: {current_sl} → {stop_loss}")
            print()

            # Publish update request asynchronously
            await self.queue.async_push_trade(update_trade_data)
            
            # Update database with new TP/SL values
            update_data = {
                'take_profit': take_profit if take_profit is not None else current_tp,
                'stop_loss': stop_loss if stop_loss is not None else current_sl,
                'updated_at': datetime.utcnow()
            }
            await self.db.async_update_trade_status(trade['trade_id'], 'updated', update_data)
            
        except Exception as e:
            logger.error(f"Error processing position update: {e}")

    async def process_tpsl_delete(self, order_id: str, level_type: str) -> None:
        """Process deletion of TP or SL level."""
        try:
            # Get active trades from database
            trade = await self.db.async_get_latest_active_trade()
            if not trade:
                logger.error("No active trades found")
                return

            position_id = trade.get('position_id')
            print(f"🗑  Removing {level_type} for Position #{position_id}")
            
            # Prepare update data
            update_data = {
                'trade_id': trade['trade_id'],
                'mt5_ticket': trade.get('mt5_ticket'),
                'instrument': trade['instrument'],
                'position_id': position_id,
                'type': 'update'
            }

            # Set which level to remove while keeping the other level
            current_tp = trade.get('take_profit')
            current_sl = trade.get('stop_loss')
            
            if level_type == 'TP':
                update_data['take_profit'] = 0  # Remove TP
                update_data['stop_loss'] = current_sl  # Keep existing SL
                print(f"🟢 TP: {current_tp} → None")
            else:  # SL
                update_data['stop_loss'] = 0  # Remove SL
                update_data['take_profit'] = current_tp  # Keep existing TP
                print(f"🛑 SL: {current_sl} → None")

            # Push to queue for MT5 processing
            await self.queue.async_push_trade(update_data)

            # Update database
            db_update = {
                'take_profit': None if level_type == 'TP' else current_tp,
                'stop_loss': None if level_type == 'SL' else current_sl,
                'updated_at': datetime.utcnow()
            }
            await self.db.async_update_trade_status(trade['trade_id'], 'updated', db_update)

        except Exception as e:
            logger.error(f"Error processing {level_type} deletion: {e}")

    def cleanup(self):
        """Cleanup resources."""
        self.db.cleanup()