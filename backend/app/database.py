from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

# create_engine creates the connection to PostgreSQL
# It uses the DATABASE_URL from our config
# pool_pre_ping=True means it tests the connection before using it
# (prevents errors if DB was restarted)
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True
)

# SessionLocal is a factory for database sessions
# A "session" is like a conversation with the database
# autocommit=False means we manually control when changes are saved
# autoflush=False means changes aren't sent to DB until we say so
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base is the parent class all our database models will inherit from
# SQLAlchemy uses it to track all models and create tables
Base = declarative_base()


# This is a "dependency" — FastAPI will call this function
# for every request that needs database access
# It creates a session, gives it to the route, then closes it
# The "yield" makes this a generator function
# Code after yield runs after the request is done (cleanup)
def get_db():
    db = SessionLocal()
    try:
        yield db          # Give the session to the route handler
    finally:
        db.close()        # Always close, even if an error occurred
