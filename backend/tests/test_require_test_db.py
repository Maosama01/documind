"""
REQUIRE_TEST_DB=1 (set in CI) turns "test database unreachable" from a skip
into a failure, so CI cannot pass without running the database tests.

Each test runs one database test in a separate pytest process, pointed at a
port where nothing listens.
"""
import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
UNREACHABLE_DATABASE = "postgresql://nobody:nothing@127.0.0.1:1/documind_test"
ONE_DB_TEST = "tests/test_init_db.py::test_init_db_can_run_on_every_start"


def run_one_db_test(require_db: bool) -> subprocess.CompletedProcess:
    env = dict(os.environ, TEST_DATABASE_URL=UNREACHABLE_DATABASE)
    env.pop("REQUIRE_TEST_DB", None)
    if require_db:
        env["REQUIRE_TEST_DB"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", ONE_DB_TEST],
        cwd=BACKEND_DIR, env=env, capture_output=True, text=True,
    )


def test_unreachable_database_skips_by_default():
    result = run_one_db_test(require_db=False)

    assert result.returncode == 0, result.stdout
    assert "1 skipped" in result.stdout


def test_unreachable_database_fails_when_required():
    result = run_one_db_test(require_db=True)

    assert result.returncode != 0, result.stdout
    assert "REQUIRE_TEST_DB=1 and Could not connect" in result.stdout
