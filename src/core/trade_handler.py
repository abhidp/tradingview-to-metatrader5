import logging
import json
import asyncio
from datetime import datetime
from typing import Dict, Any
from src.utils.database_handler import DatabaseHandler
from src.utils.queue_handler import RedisQueue

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
            
            print(f"📤 Trade sent to queue - TradeId#: {trade_id}")
            
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
                    
                    del self.pending_orders[order_id]
                    
        except Exception as e:
            logger.error(f"Error processing execution: {e}")

    async def process_position_close(self, position_id: str) -> None:
        """Process position close request from TradingView asynchronously."""
        try:
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
            
            # Get direction emoji
            direction_emoji = "BUY🔼" if trade['side'].lower() == 'buy' else "SELL🔻"
            
            # Prepare close data
            close_data = {
                'trade_id': trade['trade_id'],
                'mt5_ticket': mt5_ticket,
                'instrument': trade['instrument'],
                'type': 'market',
                'qty': trade['quantity'],
                'side': 'sell' if trade['side'] == 'buy' else 'buy',
                'execution_data': {
                    'instrument': trade['instrument'],
                    'positionId': position_id,
                    'qty': trade['quantity'],
                    'side': 'sell' if trade['side'] == 'buy' else 'buy',
                    'isClose': True
                }
            }
            
            # Publish close request asynchronously
            await self.queue.async_push_trade(close_data)
            
            # Update status asynchronously
            await self.db.async_update_trade_status(
                trade['trade_id'], 
                'closing', 
                {
                    'close_requested_at': datetime.utcnow().isoformat()
                }
            )
            print(f"📌 Closed {direction_emoji} {trade['instrument']} x {trade['quantity']}")
            
        except Exception as e:
            logger.error(f"Error processing position close: {e}")

    def cleanup(self):
        """Cleanup resources."""
        self.db.cleanup()