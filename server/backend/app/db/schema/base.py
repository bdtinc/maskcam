from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import DB_URI


# Create ORM engine and session
engine = create_engine(DB_URI)
Session = sessionmaker(bind=engine)
database_session = Session()

# Construct a base class for declarative class definitions
Base = declarative_base()
