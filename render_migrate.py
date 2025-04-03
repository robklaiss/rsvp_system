#!/usr/bin/env python
"""
Database migration script for Render.com deployment
This script will create all necessary tables in the PostgreSQL database
"""
import os
import sys
import logging
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def migrate_database():
    """Create all tables in the database"""
    try:
        # Get database URL from environment
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            logger.error("DATABASE_URL environment variable not set")
            sys.exit(1)
            
        logger.info(f"Connecting to database: {database_url}")
        
        # Create database engine
        engine = create_engine(database_url)
        
        # Import models after engine creation
        from app.models.database import Base
        
        # Create all tables
        logger.info("Creating database tables...")
        Base.metadata.create_all(engine)
        
        logger.info("Database migration completed successfully")
        return True
    except SQLAlchemyError as e:
        logger.error(f"Database migration failed: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during migration: {str(e)}")
        return False

if __name__ == "__main__":
    success = migrate_database()
    sys.exit(0 if success else 1)
