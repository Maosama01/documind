from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
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


def init_db(bind: Engine = engine) -> None:
    """
    Prepare the database at startup: pgvector extension first, then tables,
    then the index on chunks.document_id.

    Order matters: chunks.embedding is a vector(384) column, and Postgres
    rejects the vector type until the extension exists in this database.
    Both statements run in one transaction, so a failure leaves nothing
    half-created.

    create_all only creates tables that are missing. It never alters an
    existing table, so a schema change (like the ON DELETE CASCADE on
    chunks.document_id) reaches an existing database only after the table
    is recreated. There are no migrations yet.

    CREATE EXTENSION needs a role allowed to create extensions; the
    docker-compose user is a superuser, so it works locally.
    """
    import app.models  # noqa: F401  registers User, Document and Chunk on Base.metadata

    with bind.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(bind=connection)
        # create_all adds a table's indexes only when it creates the table, so a
        # chunks table created before this index existed gets it here.
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_chunks_document_id ON chunks (document_id)"
        ))


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
