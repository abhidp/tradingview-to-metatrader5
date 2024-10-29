from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Numeric, JSON, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from src.config.database import DB_CONFIG

# Create database URL
DATABASE_URL = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for declarative models
Base = declarative_base()

class Trade(Base):
    """Model for trades table."""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    trade_id = Column(String(50), unique=True, index=True)  # Our custom trade ID
    order_id = Column(String(50), index=True)  # TradingView order ID
    position_id = Column(String(50), index=True)  # Position ID from execution
    mt5_ticket = Column(String(50))  # MT5 order ticket
    
    # Trade details
    instrument = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)
    quantity = Column(Numeric, nullable=False)
    type = Column(String(20), nullable=False)
    
    # Prices
    ask_price = Column(Numeric)
    bid_price = Column(Numeric)
    execution_price = Column(Numeric)
    
    # Status
    status = Column(String(20), nullable=False, default='new')  # new, pending, executed, failed
    error_message = Column(Text)
    is_closed = Column(Boolean, default=False)
    
    # Raw data
    tv_request = Column(JSON)  # TradingView request data
    tv_response = Column(JSON)  # TradingView response data
    execution_data = Column(JSON)  # Execution response data
    mt5_response = Column(JSON)  # MT5 execution response
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)
    executed_at = Column(DateTime(timezone=True))

# Create all tables
Base.metadata.create_all(bind=engine)