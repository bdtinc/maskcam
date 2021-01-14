from typing import Generator, Union

from app.core.config import DB_URI

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker


def get_db_session() -> Session:
    """
    Get a new create a new database session.

    Returns:
        Session -- New database session.
    """
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()


def get_db_generator() -> Generator:
    """
    Get a new create a new database generator.

    Returns:
        Union[Session, Generator] -- New database generator.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Create ORM engine and session
engine = create_engine(DB_URI)
SessionLocal = sessionmaker(bind=engine)

# Construct a base class for declarative class definitions
Base = declarative_base()
