"""
Shared test setup.

The environment variables are set at the top of this file, before any test
imports `app`: app.config builds Settings() at import time (and refuses to
start without SECRET_KEY), and app.database builds its engine from
DATABASE_URL at import time.
"""
import os

TEST_SECRET_KEY = "test-secret-key-for-pytest-only-0123456789abcdef"
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://documind_user:documind_pass@localhost:5432/documind_test",
)
REQUIRE_TEST_DB = os.environ.get("REQUIRE_TEST_DB") == "1"
# CI sets REQUIRE_TEST_DB=1: an unreachable database then fails the run instead
# of skipping the database tests, so CI cannot pass without running them.

os.environ["SECRET_KEY"] = TEST_SECRET_KEY
os.environ["DATABASE_URL"] = TEST_DATABASE_URL  # the app under test never sees the dev database
os.environ["DEBUG"] = "false"
os.environ["LLM_PROVIDER"] = "none"  # no test calls a real LLM; tests opt into a fake provider

import pytest  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402


def _create_database_if_missing(url) -> None:
    """Connect to the server's maintenance database and create the test database once."""
    admin_engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": url.database},
            ).scalar()
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        admin_engine.dispose()


def _truncate_all(engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE users, documents, chunks RESTART IDENTITY CASCADE"))


@pytest.fixture(scope="session")
def db_engine():
    """
    The app's own engine, pointed at a fresh schema in the test database.

    Skips (with the reason printed) when Postgres is not reachable.
    """
    url = make_url(TEST_DATABASE_URL)
    if not (url.database or "").endswith("_test"):
        pytest.exit(
            f"TEST_DATABASE_URL must name a database ending in _test (got {url.database!r}). "
            "These tests drop its tables."
        )
    try:
        _create_database_if_missing(url)
    except OperationalError as error:
        message = (
            f"Could not connect to the test Postgres at {url.render_as_string(hide_password=True)}: "
            f"{str(error.orig).strip()} -- start it with `docker compose up -d db`, "
            "or point TEST_DATABASE_URL at a pgvector Postgres"
        )
        if REQUIRE_TEST_DB:
            pytest.fail(f"REQUIRE_TEST_DB=1 and {message}", pytrace=False)
        pytest.skip(message)

    import app.models  # noqa: F401  registers every table on Base.metadata
    from app.database import Base, engine, init_db

    assert engine.url.database == url.database, "app engine is not pointed at the test database"
    Base.metadata.drop_all(engine)
    init_db(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """A session on the test database. Every table is emptied after the test."""
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        # Close first: an open transaction would block TRUNCATE.
        session.close()
        _truncate_all(db_engine)


@pytest.fixture
def client(db_session):
    """
    HTTP client for the app, backed by the test database.

    Not used as a context manager, so the startup hook (init_db) does not run
    again; db_engine has already prepared the schema.
    """
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app)
