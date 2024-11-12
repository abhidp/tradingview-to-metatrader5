import logging
import MetaTrader5 as mt5
import asyncio
from datetime import datetime
from typing import Dict, Any
from src.utils.database_handler import DatabaseHandler
from src.utils.queue_handler import RedisQueue

import logging
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
            
            trade_data = {
                'trade_id': trade_id,
                'order_id': response_data['d']['orderId'],
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
            
            # print(f"📤 Trade sent to queue - TradeId#: {trade_id}")
            
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

                # Query all positions first for debugging
                all_positions = mt5.positions_get()

                # Get specific position
                positions = mt5.positions_get(ticket=int(mt5_ticket))

                if not positions:
                    logger.info(f"Position {mt5_ticket} not found in MT5")
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

            # Use mapped symbol
            instrument = trade['instrument']
            mt5_symbol = f"{instrument}.r"  # Add proper suffix

            # Prepare close data
            close_request = {
                'trade_id': trade['trade_id'],
                'mt5_ticket': mt5_ticket,
                'instrument': trade['instrument'],  # Use original instrument name without suffix
                'type': 'market',
                'qty': str(close_amount),
                'is_partial': is_partial,
                'side': 'sell' if trade['side'] == 'buy' else 'buy',
                'execution_data': {
                    'instrument': trade['instrument'],  # Use original instrument name without suffix
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
            
            operation_type = "⭕ Partially closed" if is_partial else "📌 Closed"
            print(f"{operation_type} {direction_emoji} {trade['instrument']} x {close_amount}")
            
        except Exception as e:
            logger.error(f"Error processing position close: {e}")
            logger.error(f"Close data was: {close_data}")

    async def process_position_update(self, position_id: str, update_data: Dict[str, Any]) -> None:
        """Process position update from TradingView asynchronously."""
        try:
            close_data = close_data or {}
            print(f"\n📤 Closing PositionID#: {position_id}")
            
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
            
            # Log the update request only if values are changing
            if take_profit is not None:
                print(f"🎯 TP: {current_tp} → {take_profit}")
            if stop_loss is not None:
                print(f"🛑 SL: {current_sl} → {stop_loss}")
                
            # Publish update request asynchronously
            await self.queue.async_push_trade(update_trade_data)
                
        except Exception as e:
            logger.error(f"Error processing position update: {e}")
            
    def cleanup(self):
        """Cleanup resources."""
        self.db.cleanup()