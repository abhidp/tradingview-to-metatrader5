import logging
import time
from datetime import datetime

from sqlalchemy import (JSON, Boolean, Column, DateTime, Integer, Numeric,
                        String, Text, create_engine, text)
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from src.config.database import DATABASE_URL

logger = logging.getLogger(__name__)

# Create SQLAlchemy engine with retries
def create_db_engine(retries=5, delay=2):
    """Create database engine with retry logic."""
    for attempt in range(retries):
        try:
            engine = create_engine(
                DATABASE_URL,
                pool_size=20,
                max_overflow=10,
                pool_timeout=30,
                pool_recycle=1800,
                pool_pre_ping=True  # Add connection health check
            )
            # Test connection using proper SQLAlchemy syntax
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                conn.commit()
            return engine
        except OperationalError as e:
            if attempt == retries - 1:
                logger.error(f"Failed to connect to database after {retries} attempts: {e}")
                raise
            logger.warning(f"Database connection attempt {attempt + 1} failed, retrying in {delay} seconds...")
            time.sleep(delay)
            
# Create engine with retry logic
engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise

# Initialize tables if this file is run directly
if __name__ == "__main__":
    init_db()