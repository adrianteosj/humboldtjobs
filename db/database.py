"""
Database connection and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL
from .models import Base

# Create engine
engine = create_engine(DATABASE_URL, echo=False)

# Session factory
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Create all tables in the database"""
    Base.metadata.create_all(engine)


def get_session():
    """Get a new database session"""
    return SessionLocal()
