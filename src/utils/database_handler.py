# utils/database_handler.py

import asyncio
import logging
import os
import traceback
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, text, update
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import QueuePool

from src.models.database import Trade

logger = logging.getLogger('DatabaseHandler')

class DatabaseHandler:
    def __init__(self):
        try:
            # Load environment variables
            load_dotenv()
            
            # Construct database URL
            db_url = (
                f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
                f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
            )
            
            # Create engine with connection pooling
            self.engine = create_engine(
                db_url,
                poolclass=QueuePool,
                pool_size=20,
                max_overflow=10,
                pool_timeout=30,
                pool_recycle=1800,
                pool_pre_ping=True,
                connect_args={
                    "connect_timeout": 10,
                    "application_name": "TradingView Copier"
                }
            )
            
            # Create scoped session factory
            self.SessionLocal = scoped_session(
                sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            )
            
            # Initialize thread pool for async operations
            self.loop = asyncio.get_event_loop()
            
            # Test connection
            self._test_connection()
            
        except Exception as e:
            logger.error(f"Error initializing DatabaseHandler: {e}")
            logger.error(traceback.format_exc())
            raise
    
    def _test_connection(self):
        """Test database connection."""
        try:
            with self.get_db() as db:
                db.execute(text("SELECT 1"))
                # logger.info("Database connection test passed")
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            logger.error(traceback.format_exc())
            raise
    
    @contextmanager
    def get_db(self):
        """Get database session with improved error handling."""
        session = self.SessionLocal()
        try:
            logger.debug("Database session created")
            yield session
        except Exception as e:
            logger.error(f"Error in database session: {e}")
            logger.error(traceback.format_exc())
            session.rollback()
            raise
        finally:
            session.close()
            self.SessionLocal.remove()
            logger.debug("Database session closed")
    
    def save_trade(self, trade_data: Dict[str, Any]) -> None:
        """Save trade to database with enhanced error handling."""
        try:
            logger.info(f"Saving trade {trade_data.get('trade_id')}")
            logger.debug(f"Trade data: {trade_data}")
            
            with self.get_db() as db:
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
                
                logger.debug("Adding trade to session")
                db.add(trade)
                
                logger.debug("Committing transaction")
                db.commit()
                
                logger.info(f"Trade {trade_data['trade_id']} saved successfully")
                
        except Exception as e:
            logger.error(f"Error saving trade: {e}")
            logger.error(f"Trade data: {trade_data}")
            logger.error(traceback.format_exc())
            raise
    
    def update_trade_status(self, trade_id: str, status: str, update_data: Dict[str, Any]) -> None:
        """Update trade status with enhanced error handling."""
        try:
            logger.info(f"Updating trade {trade_id} status to {status}")
            logger.debug(f"Update data: {update_data}")
            
            with self.get_db() as db:
                data_to_update = {
                    'status': status,
                    'updated_at': datetime.utcnow(),
                    **update_data
                }
                
                stmt = (
                    update(Trade)
                    .where(Trade.trade_id == trade_id)
                    .values(data_to_update)
                    .execution_options(synchronize_session=False)
                )
                
                result = db.execute(stmt)
                if result.rowcount == 0:
                    logger.error(f"No trade found with ID: {trade_id}")
                    raise Exception(f"Trade not found: {trade_id}")
                
                db.commit()
                # logger.info(f"Trade {trade_id} status updated successfully")
                
        except Exception as e:
            logger.error(f"Error updating trade status: {e}")
            logger.error(f"Trade ID: {trade_id}, Status: {status}, Update data: {update_data}")
            logger.error(traceback.format_exc())
            raise
    
    def get_trade(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """Get trade by ID with enhanced error handling."""
        try:
            logger.info(f"Fetching trade {trade_id}")
            
            with self.get_db() as db:
                trade = (
                    db.query(Trade)
                    .filter(Trade.trade_id == trade_id)
                    .first()
                )
                
                if trade:
                    logger.info(f"Trade {trade_id} found")
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
                logger.info(f"Trade {trade_id} not found")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching trade: {e}")
            logger.error(f"Trade ID: {trade_id}")
            logger.error(traceback.format_exc())
            raise
    
    def cleanup(self):
        """Cleanup database connections."""
        try:
            logger.info("Cleaning up database connections")
            self.engine.dispose()
            logger.info("Database connections cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            logger.error(traceback.format_exc())

    async def async_save_trade(self, trade_data: Dict[str, Any]) -> None:
        """Save trade to database asynchronously."""
        def _save_trade():
            with self.get_db() as db:
                try:
                    logger.info(f"Async saving trade {trade_data.get('trade_id')}")
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
                    logger.info(f"Trade {trade_data['trade_id']} saved successfully")
                except Exception as e:
                    logger.error(f"Error in async save trade: {e}")
                    logger.error(traceback.format_exc())
                    raise

        await self.loop.run_in_executor(None, _save_trade)

    async def async_update_trade_status(self, trade_id: str, status: str, update_data: Dict[str, Any]) -> None:
        """Update trade status asynchronously."""
        def _update_trade():
            with self.get_db() as db:
                try:
                    # logger.info(f"Async updating trade {trade_id} status to {status}")
                    data_to_update = {
                        'status': status,
                        'updated_at': datetime.utcnow(),
                        **update_data
                    }
                    
                    stmt = (
                        update(Trade)
                        .where(Trade.trade_id == trade_id)
                        .values(data_to_update)
                        .execution_options(synchronize_session=False)
                    )
                    
                    result = db.execute(stmt)
                    if result.rowcount == 0:
                        raise Exception(f"Trade not found: {trade_id}")
                    
                    db.commit()
                    # logger.info(f"Trade {trade_id} status updated successfully")
                except Exception as e:
                    logger.error(f"Error in async update trade: {e}")
                    logger.error(traceback.format_exc())
                    raise

        await self.loop.run_in_executor(None, _update_trade)

    async def async_get_trade(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """Get trade by ID asynchronously."""
        def _get_trade():
            with self.get_db() as db:
                try:
                    logger.info(f"Async fetching trade {trade_id}")
                    trade = (
                        db.query(Trade)
                        .filter(Trade.trade_id == trade_id)
                        .first()
                    )
                    
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
                except Exception as e:
                    logger.error(f"Error in async get trade: {e}")
                    logger.error(traceback.format_exc())
                    raise

        return await self.loop.run_in_executor(None, _get_trade)

    async def async_get_trade_by_position(self, position_id: str) -> Optional[Dict[str, Any]]:
        """Get trade by position ID asynchronously."""
        def _get_trade():
            with self.get_db() as db:
                try:
                    trade = (
                        db.query(Trade)
                        .filter(Trade.position_id == position_id)
                        .first()
                    )
                    
                    if trade:
                        return {
                            'trade_id': trade.trade_id,
                            'position_id': trade.position_id,
                            'mt5_ticket': trade.mt5_ticket,
                            'instrument': trade.instrument,
                            'side': trade.side,
                            'quantity': str(trade.quantity),
                            'status': trade.status,
                            'type': trade.type,
                            'take_profit': float(trade.take_profit) if trade.take_profit is not None else None,
                            'stop_loss': float(trade.stop_loss) if trade.stop_loss is not None else None
                        }
                    return None
                except Exception as e:
                    logger.error(f"Error in async get trade by position: {e}")
                    raise

        return await self.loop.run_in_executor(None, _get_trade)

    async def async_get_trade_by_mt5_ticket(self, mt5_ticket: str) -> Optional[Dict[str, Any]]:
        """Get trade by MT5 ticket asynchronously."""
        def _get_trade():
            with self.get_db() as db:
                try:
                    trade = (
                        db.query(Trade)
                        .filter(Trade.mt5_ticket == mt5_ticket)
                        .first()
                    )
                    
                    if trade:
                        return {
                            'trade_id': trade.trade_id,
                            'position_id': trade.position_id,
                            'mt5_ticket': trade.mt5_ticket,
                            'instrument': trade.instrument,
                            'side': trade.side,
                            'quantity': str(trade.quantity),
                            'status': trade.status,
                            'is_closed': trade.is_closed
                        }
                    return None
                except Exception as e:
                    logger.error(f"Error in async get trade by MT5 ticket: {e}")
                    logger.error(traceback.format_exc())
                    raise

        return await self.loop.run_in_executor(None, _get_trade)