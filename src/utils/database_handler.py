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
                    take_profit=trade_data.get('take_profit'),
                    stop_loss=trade_data.get('stop_loss'),
                    status=trade_data['status'],
                    tv_request=trade_data['tv_request'],
                    tv_response=trade_data['tv_response'],
                    created_at=trade_data['created_at']
                )
                
                db.add(trade)
                db.commit()
                
            except Exception as e:
                db.rollback()
                logger.error(f"Error saving trade: {e}", exc_info=True)
                raise
    
    def update_trade_status(self, trade_id: str, status: str, update_data: Dict[str, Any]) -> None:
        """Update trade status and details."""        
        with self.get_db() as db:
            try:
                data_to_update = {
                    'status': status,
                    'updated_at': datetime.utcnow(),
                    **update_data
                }
                
                result = db.query(Trade).filter(
                    Trade.trade_id == trade_id
                ).update(data_to_update)
                
                if result == 0:
                    raise Exception(f"Trade not found: {trade_id}")
                
                db.commit()
                
            except Exception as e:
                db.rollback()
                logger.error(f"Error updating trade: {e}", exc_info=True)
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
                    'type': trade.type,
                    'take_profit': float(trade.take_profit) if trade.take_profit is not None else None,
                    'stop_loss': float(trade.stop_loss) if trade.stop_loss is not None else None,
                    'status': trade.status
                }
            return None
    
    def get_trade_by_position(self, position_id: str) -> Optional[Dict[str, Any]]:
        """Get trade by position ID."""
        with self.get_db() as db:
            trade = db.query(Trade).filter(Trade.position_id == position_id).first()
            if trade:
                return {
                    'trade_id': trade.trade_id,
                    'order_id': trade.order_id,
                    'position_id': trade.position_id,
                    'instrument': trade.instrument,
                    'side': trade.side,
                    'quantity': str(trade.quantity),
                    'type': trade.type,
                    'status': trade.status,
                    'mt5_ticket': trade.mt5_ticket,
                    'mt5_position': trade.mt5_position
                }
            return None
            
    def get_trade_by_mt5_ticket(self, mt5_ticket: str) -> Optional[Dict[str, Any]]:
        """Get trade by MT5 ticket."""
        with self.get_db() as db:
            trade = db.query(Trade).filter(Trade.mt5_ticket == mt5_ticket).first()
            if trade:
                return {
                    'trade_id': trade.trade_id,
                    'position_id': trade.position_id,
                    'mt5_ticket': trade.mt5_ticket,
                    'instrument': trade.instrument,
                    'side': trade.side,
                    'quantity': str(trade.quantity),
                    'status': trade.status
                }
            return None