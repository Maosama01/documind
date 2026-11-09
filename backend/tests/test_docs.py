"""
The README describes what the code does today (CLAUDE.md, integrity rule 1).

These tests catch the drift that can be checked mechanically: an endpoint or a
setting missing from the README, an endpoint the app does not have, and
features that were once claimed but do not exist.
"""
import re
from pathlib import Path

import pytest
from fastapi.routing import APIRoute

from app.config import Settings
from app.main import app

README = (Path(__file__).resolve().parents[2] / "README.md").read_text(encoding="utf-8")

# The README claimed these before Phase 6; none of them exist in this repository.
NOT_BUILT = ["AWS", "S3", "EC2", "React", "Ollama", "LLaMA"]


def readme_endpoints() -> set:
    """(method, path) pairs from the README's API table rows: | `GET` | `/path` | ..."""
    rows = re.findall(r"^\|\s*`(GET|POST|PUT|PATCH|DELETE)`\s*\|\s*`([^`]+)`", README, flags=re.MULTILINE)
    return set(rows)


def app_endpoints() -> set:
    return {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }


def test_readme_api_table_matches_the_app_exactly():
    assert readme_endpoints() == app_endpoints()


def test_readme_documents_every_setting():
    missing = [name for name in Settings.model_fields if f"`{name}`" not in README]
    assert missing == []


@pytest.mark.parametrize("term", NOT_BUILT)
def test_readme_does_not_mention_features_that_do_not_exist(term):
    assert not re.search(rf"\b{re.escape(term)}\b", README, flags=re.IGNORECASE)
