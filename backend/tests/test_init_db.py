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


def chunk_indexes(engine) -> dict:
    """{index name: CREATE INDEX statement} for the chunks table."""
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'chunks'")
        )
        return dict(rows.all())


def test_init_db_creates_the_document_id_index(db_engine):
    init_db(db_engine)

    assert "ix_chunks_document_id" in chunk_indexes(db_engine)


def test_init_db_adds_the_index_to_a_chunks_table_created_without_it(db_engine):
    """A database created before this index existed: create_all would not add it."""
    with db_engine.begin() as connection:
        connection.execute(text("DROP INDEX ix_chunks_document_id"))
    assert "ix_chunks_document_id" not in chunk_indexes(db_engine)

    init_db(db_engine)

    assert "ix_chunks_document_id" in chunk_indexes(db_engine)


def test_init_db_adds_error_message_to_a_documents_table_created_without_it(db_engine):
    """A database created before Phase 7: create_all would not add the column."""
    def has_column():
        with db_engine.connect() as connection:
            return connection.execute(text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'documents' AND column_name = 'error_message'"
            )).scalar() == 1

    with db_engine.begin() as connection:
        connection.execute(text("ALTER TABLE documents DROP COLUMN error_message"))
    assert not has_column()

    init_db(db_engine)

    assert has_column()


def test_chunks_has_no_approximate_vector_index(db_engine):
    init_db(db_engine)

    definitions = " ".join(chunk_indexes(db_engine).values()).lower()
    assert "hnsw" not in definitions and "ivfflat" not in definitions, (
        "An approximate vector index changes semantic_search results (it returned 0 of 5 "
        "rows with a document filter when measured); read the comment in semantic_search first."
    )
