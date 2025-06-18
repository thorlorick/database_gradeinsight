# ==============================================================================
# utils/database.py - Database utilities
# ==============================================================================

import logging
from sqlalchemy.orm import Session
from database import Base, engine, SessionLocal

logger = logging.getLogger(__name__)


def init_database() -> None:
    """Initialize database tables with error handling"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise


def get_db() -> Session:
    """Database dependency for FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def reset_database() -> None:
    """Reset the database (drop and recreate all tables)"""
    try:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        logger.info("Database reset successfully")
    except Exception as e:
        logger.error(f"Error resetting database: {e}")
        raise
