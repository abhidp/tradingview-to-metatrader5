from typing import Dict, Any, Optional
from contextlib import contextmanager
import logging
from datetime import datetime
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker
from src.models.database import Base, Trade

logger = logging.getLogger('DatabaseHandler')

class DatabaseHandler:
    def __init__(self):
        """Initialize database handler."""
        from src.models.database import engine, SessionLocal
        self.engine = engine
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
                # Create new trade
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
                
                # Add to database
                db.add(trade)
                db.commit()
                print("✅ Trade saved successfully")
                
            except Exception as e:
                db.rollback()
                print(f"❌ Error saving trade: {e}")
                logger.error(f"Database error: {e}", exc_info=True)
                raise
    
    def update_trade(self, trade_id: str, update_data: Dict[str, Any]) -> None:
        """Update existing trade."""
        print(f"\n💾 DatabaseHandler: Updating trade {trade_id}")
        
        with self.get_db() as db:
            try:
                # Update trade
                result = db.query(Trade).filter(Trade.trade_id == trade_id).update(update_data)
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
                    'position_id': trade.position_id,
                    'instrument': trade.instrument,
                    'side': trade.side,
                    'quantity': str(trade.quantity),
                    'status': trade.status,
                    'created_at': trade.created_at.isoformat() if trade.created_at else None
                }
            return None