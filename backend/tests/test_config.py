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


def test_chunk_settings_default_to_240_and_40_tokens(monkeypatch):
    monkeypatch.delenv("CHUNK_SIZE_TOKENS", raising=False)
    monkeypatch.delenv("CHUNK_OVERLAP_TOKENS", raising=False)
    loaded = Settings(_env_file=None)
    assert (loaded.CHUNK_SIZE_TOKENS, loaded.CHUNK_OVERLAP_TOKENS) == (240, 40)


def test_chunk_settings_can_be_set_from_the_environment(monkeypatch):
    monkeypatch.setenv("CHUNK_SIZE_TOKENS", "120")
    monkeypatch.setenv("CHUNK_OVERLAP_TOKENS", "25")
    loaded = Settings(_env_file=None)
    assert (loaded.CHUNK_SIZE_TOKENS, loaded.CHUNK_OVERLAP_TOKENS) == (120, 25)


@pytest.mark.parametrize(
    "size,overlap,reason",
    [("255", "40", "between 1 and 254"), ("240", "240", "smaller than chunk size"),
     ("240", "-1", "at least 0"), ("0", "0", "between 1 and 254")],
)
def test_app_refuses_unsafe_chunk_settings(monkeypatch, size, overlap, reason):
    monkeypatch.setenv("CHUNK_SIZE_TOKENS", size)
    monkeypatch.setenv("CHUNK_OVERLAP_TOKENS", overlap)
    with pytest.raises(ValidationError, match=reason):
        Settings(_env_file=None)


def test_an_old_env_file_with_word_settings_stops_startup(tmp_path):
    """The word-based settings were replaced; a .env still setting them is rejected, not ignored."""
    env_file = tmp_path / ".env"
    env_file.write_text("CHUNK_SIZE_WORDS=180\nCHUNK_OVERLAP_WORDS=30\n")
    with pytest.raises(ValidationError, match="(?i)chunk_size_words"):
        Settings(_env_file=env_file)


def test_an_old_exported_word_setting_is_ignored(monkeypatch):
    """Unlike .env entries, unknown environment variables are not checked."""
    monkeypatch.setenv("CHUNK_SIZE_WORDS", "180")
    assert Settings(_env_file=None).CHUNK_SIZE_TOKENS == 240


def test_llm_provider_defaults_to_none(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert Settings(_env_file=None).LLM_PROVIDER == "none"


@pytest.mark.parametrize("provider,key_name", [("gemini", "GEMINI_API_KEY"), ("anthropic", "ANTHROPIC_API_KEY")])
def test_app_refuses_a_provider_without_its_api_key(monkeypatch, provider, key_name):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.setenv(key_name, "")
    with pytest.raises(ValidationError, match=key_name):
        Settings(_env_file=None)


@pytest.mark.parametrize("provider,key_name", [("gemini", "GEMINI_API_KEY"), ("anthropic", "ANTHROPIC_API_KEY")])
def test_provider_with_its_api_key_is_accepted(monkeypatch, provider, key_name):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.setenv(key_name, "some-key")
    assert Settings(_env_file=None).LLM_PROVIDER == provider


def test_unknown_llm_provider_is_rejected(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    with pytest.raises(ValidationError, match="LLM_PROVIDER"):
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
