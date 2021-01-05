from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import DB_URI


def get_db_session():
    """
    Get a new create a new database session.

    Returns:
        Session -- New database session.
    """

    try:
        session = Session()
        return session
    finally:
        session.close()


# Create ORM engine and session
engine = create_engine(DB_URI)
Session = sessionmaker(bind=engine)
database_session = get_db_session()

# Construct a base class for declarative class definitions
Base = declarative_base()
