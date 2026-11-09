"""User files and secrets stay out of git."""
import shutil
import subprocess
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent

needs_git = pytest.mark.skipif(
    shutil.which("git") is None or not (REPO_ROOT / ".git").exists(),
    reason="not running inside a git checkout",
)


def git(*args):
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)


@needs_git
@pytest.mark.parametrize("path", ["backend/uploads/example.pdf", "uploads/example.pdf", "backend/.env"])
def test_uploads_and_env_files_are_ignored(path):
    assert git("check-ignore", "--quiet", path).returncode == 0


@needs_git
def test_no_uploaded_file_is_tracked():
    assert git("ls-files", "backend/uploads").stdout.strip() == ""


def test_env_example_contains_no_secret_value():
    lines = (BACKEND_DIR / ".env.example").read_text().splitlines()
    secret_lines = [line for line in lines if line.split("=")[0].endswith("_KEY")]
    assert secret_lines == ["SECRET_KEY=", "GEMINI_API_KEY=", "ANTHROPIC_API_KEY="]
