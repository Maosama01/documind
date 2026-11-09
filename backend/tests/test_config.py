import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings

BACKEND_DIR = Path(__file__).resolve().parent.parent


def test_secret_key_is_required(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(_env_file=None)


@pytest.mark.parametrize("value", ["", "too-short"])
def test_short_or_empty_secret_key_is_rejected(monkeypatch, value):
    monkeypatch.setenv("SECRET_KEY", value)
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(_env_file=None)


def test_debug_defaults_to_false(monkeypatch):
    monkeypatch.delenv("DEBUG", raising=False)
    assert Settings(_env_file=None).DEBUG is False


def test_chunk_settings_default_to_180_and_30(monkeypatch):
    monkeypatch.delenv("CHUNK_SIZE_WORDS", raising=False)
    monkeypatch.delenv("CHUNK_OVERLAP_WORDS", raising=False)
    loaded = Settings(_env_file=None)
    assert (loaded.CHUNK_SIZE_WORDS, loaded.CHUNK_OVERLAP_WORDS) == (180, 30)


def test_chunk_settings_can_be_set_from_the_environment(monkeypatch):
    monkeypatch.setenv("CHUNK_SIZE_WORDS", "120")
    monkeypatch.setenv("CHUNK_OVERLAP_WORDS", "25")
    loaded = Settings(_env_file=None)
    assert (loaded.CHUNK_SIZE_WORDS, loaded.CHUNK_OVERLAP_WORDS) == (120, 25)


@pytest.mark.parametrize("size,overlap", [("180", "10"), ("180", "180"), ("100", "150")])
def test_app_refuses_unsafe_chunk_settings(monkeypatch, size, overlap):
    monkeypatch.setenv("CHUNK_SIZE_WORDS", size)
    monkeypatch.setenv("CHUNK_OVERLAP_WORDS", overlap)
    with pytest.raises(ValidationError, match="chunk overlap"):
        Settings(_env_file=None)


def test_fastapi_debug_follows_the_setting():
    from app.main import app

    assert app.debug is False


def test_app_refuses_to_start_without_secret_key(tmp_path):
    """Importing app.main is what uvicorn does on start; it must fail without SECRET_KEY."""
    env = {key: value for key, value in os.environ.items() if key != "SECRET_KEY"}
    env["PYTHONPATH"] = str(BACKEND_DIR)
    # cwd=tmp_path so no backend/.env file can supply a key.
    result = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "SECRET_KEY" in result.stderr
