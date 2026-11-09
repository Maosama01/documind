import pytest
from sqlalchemy import text

from app.database import Base, init_db

pytestmark = pytest.mark.db


def test_init_db_creates_the_extension_before_the_tables(db_engine):
    """
    Starts from a database with no vector extension and no tables.
    If create_all ran before CREATE EXTENSION, Postgres would reject the
    vector(384) column with: type "vector" does not exist.
    """
    Base.metadata.drop_all(db_engine)
    with db_engine.begin() as connection:
        connection.execute(text("DROP EXTENSION IF EXISTS vector"))

    init_db(db_engine)

    with db_engine.connect() as connection:
        has_extension = connection.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        ).scalar()
        tables = set(connection.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        ).scalars())
        embedding_type = connection.execute(text(
            "SELECT udt_name FROM information_schema.columns "
            "WHERE table_name = 'chunks' AND column_name = 'embedding'"
        )).scalar()
    assert has_extension == 1
    assert {"users", "documents", "chunks"} <= tables
    assert embedding_type == "vector"


def test_init_db_can_run_on_every_start(db_engine):
    init_db(db_engine)
    init_db(db_engine)
