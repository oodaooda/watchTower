"""SQLAlchemy engine/session setup for watchTower.

Provides:
- `engine`: SQLAlchemy Engine
- `SessionLocal`: session factory
- `Base`: Declarative base
- `get_db()`: FastAPI dependency yielding a session
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

# Create engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
    echo=True,
)

# Session factory
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

qa_engine = create_engine(
    settings.qa_database_url or settings.database_url,
    pool_pre_ping=True,
    future=True,
    echo=True,
)
QASessionLocal = sessionmaker(bind=qa_engine, autoflush=False, autocommit=False, future=True)


Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and ensures it's closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_qa_db():
    """FastAPI dependency for read-only QA DB session."""
    db = QASessionLocal()
    try:
        yield db
    finally:
        db.close()
