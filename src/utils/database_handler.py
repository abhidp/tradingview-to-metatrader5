from typing import Dict, Any, Optional
from contextlib import contextmanager
import logging
from datetime import datetime
from sqlalchemy import update
from sqlalchemy.orm import Session
from src.models.database import Base, Trade, SessionLocal

logger = logging.getLogger('DatabaseHandler')

class DatabaseHandler:
    def __init__(self):
        self.SessionLocal = SessionLocal
    
    @contextmanager
    def get_db(self):
        """Get database session."""
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    def save_trade(self, trade_data: Dict[str, Any]) -> None:
        """Save trade to database."""
        print(f"\n💾 DatabaseHandler: Saving trade {trade_data.get('trade_id')}")
        
        with self.get_db() as db:
            try:
                trade = Trade(
                    trade_id=trade_data['trade_id'],
                    order_id=trade_data['order_id'],
                    instrument=trade_data['instrument'],
                    side=trade_data['side'],
                    quantity=trade_data['quantity'],
                    type=trade_data['type'],
                    ask_price=trade_data['ask_price'],
                    bid_price=trade_data['bid_price'],
                    status=trade_data['status'],
                    tv_request=trade_data['tv_request'],
                    tv_response=trade_data['tv_response'],
                    created_at=trade_data['created_at']
                )
                
                db.add(trade)
                db.commit()
                print("✅ Trade saved successfully")
                
            except Exception as e:
                db.rollback()
                print(f"❌ Error saving trade: {e}")
                logger.error(f"Database error: {e}", exc_info=True)
                raise
    
    def update_trade_status(self, trade_id: str, status: str, update_data: Dict[str, Any]) -> None:
        """Update trade status and details."""
        print(f"\n💾 DatabaseHandler: Updating trade {trade_id}")
        
        with self.get_db() as db:
            try:
                # Prepare update data with status
                data_to_update = {
                    'status': status,
                    'updated_at': datetime.utcnow(),
                    **update_data
                }
                
                # Update the trade
                result = db.query(Trade).filter(
                    Trade.trade_id == trade_id
                ).update(data_to_update)
                
                if result == 0:
                    raise Exception(f"Trade not found: {trade_id}")
                
                db.commit()
                print("✅ Trade updated successfully")
                
            except Exception as e:
                db.rollback()
                print(f"❌ Error updating trade: {e}")
                logger.error(f"Database error: {e}", exc_info=True)
                raise
    
    def get_trade(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """Get trade by ID."""
        with self.get_db() as db:
            trade = db.query(Trade).filter(Trade.trade_id == trade_id).first()
            if trade:
                return {
                    'trade_id': trade.trade_id,
                    'order_id': trade.order_id,
                    'instrument': trade.instrument,
                    'side': trade.side,
                    'quantity': str(trade.quantity),
                    'status': trade.status
                }
            return None
        
    def get_trade_by_position(self, position_id: str) -> Optional[Dict[str, Any]]:
        """Get trade by position ID."""
        with self.get_db() as db:
            try:
                trade = db.query(Trade).filter(Trade.position_id == position_id).first()
                if trade:
                    print(f"\n📋 Found trade for position {position_id}:")
                    print(f"Trade ID: {trade.trade_id}")
                    print(f"MT5 Ticket: {trade.mt5_ticket}")
                    print(f"Status: {trade.status}")
                    
                    return {
                        'trade_id': trade.trade_id,
                        'order_id': trade.order_id,
                        'position_id': trade.position_id,
                        'instrument': trade.instrument,
                        'side': trade.side,
                        'quantity': str(trade.quantity),
                        'type': trade.type,
                        'status': trade.status,
                        'mt5_ticket': trade.mt5_ticket,  # Make sure this is included
                        'mt5_position': trade.mt5_position
                    }
                else:
                    print(f"❌ No trade found for position {position_id}")
                return None
                
            except Exception as e:
                logger.error(f"Error getting trade by position: {e}")
                print(f"❌ Database error: {e}")
                return None