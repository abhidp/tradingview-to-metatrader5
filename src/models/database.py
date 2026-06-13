import logging
from datetime import datetime

from sqlalchemy import (JSON, Boolean, Column, DateTime, Integer, Numeric,
                        String, Text)
from sqlalchemy.orm import declarative_base

from src.config.database import get_engine, get_session_factory

logger = logging.getLogger(__name__)

# Shared SQLite engine + session factory (see src/config/database.py).
engine = get_engine()
SessionLocal = get_session_factory()

# Create base class for declarative models
Base = declarative_base()

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    trade_id = Column(String(50), unique=True, index=True)
    order_id = Column(String(50), index=True)
    position_id = Column(String(50), index=True)
    mt5_ticket = Column(String(50))
    mt5_position = Column(String(50))

    # Trade details
    instrument = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)
    quantity = Column(Numeric, nullable=False)
    type = Column(String(20), nullable=False)
    
    # Prices
    ask_price = Column(Numeric)
    bid_price = Column(Numeric)
    execution_price = Column(Numeric)
    take_profit = Column(Numeric)
    stop_loss = Column(Numeric)
    tp_order_id = Column(String(50)) 
    sl_order_id = Column(String(50))
    trailing_stop_pips = Column(Numeric)

    
    # Status
    status = Column(String(20), nullable=False, default='new')
    error_message = Column(Text)
    is_closed = Column(Boolean, default=False)
    close_requested_at = Column(DateTime(timezone=True))
    execution_time_ms = Column(Integer)
    
    # JSON data
    tv_request = Column(JSON)
    tv_response = Column(JSON)
    execution_data = Column(JSON)
    mt5_response = Column(JSON)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)
    executed_at = Column(DateTime(timezone=True))
    closed_at = Column(DateTime(timezone=True))
    
    def __repr__(self):
        return f"<Trade(trade_id='{self.trade_id}', instrument='{self.instrument}', status='{self.status}')>"

def init_db():
    """Initialize database tables."""
    try:
        Base.metadata.create_all(bind=get_engine())
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise

# Initialize tables if this file is run directly
if __name__ == "__main__":
    init_db()