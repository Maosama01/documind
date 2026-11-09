"""
The Docker setup keeps secrets and user files out of the image and starts the
API the way the README says.

These tests read the files; CI's "docker" job builds the image, starts the
stack and runs scripts/smoke_test.py against it.
"""
from pathlib import Path

import yaml

from app.services.embedding_service import MODEL_NAME
from app.services.pdf_service import extract_text_from_pdf
from scripts.smoke_test import PDF_TEXT, make_pdf

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
DOCKERFILE = (BACKEND_DIR / "Dockerfile").read_text()
DOCKERFILE_LINES = [line.strip() for line in DOCKERFILE.splitlines()]
DOCKERIGNORE = {
    line.strip()
    for line in (BACKEND_DIR / ".dockerignore").read_text().splitlines()
    if line.strip() and not line.startswith("#")
}
COMPOSE = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text())


def test_secrets_and_user_files_are_kept_out_of_the_build():
    assert {".env", ".env.*", "uploads/", ".venv/"} <= DOCKERIGNORE


def test_the_dockerfile_copies_only_requirements_and_app():
    copied = [line.split()[1] for line in DOCKERFILE_LINES if line.startswith("COPY ")]
    assert copied == ["requirements.txt", "app"]


def test_the_container_does_not_run_as_root():
    users = [line.split()[1] for line in DOCKERFILE_LINES if line.startswith("USER ")]
    assert users and users[-1] not in ("root", "0")


def test_the_image_has_the_apps_model_and_then_stays_offline():
    assert f"SentenceTransformer('{MODEL_NAME}')" in DOCKERFILE
    assert DOCKERFILE.index("SentenceTransformer(") < DOCKERFILE.index("ENV HF_HUB_OFFLINE=1")


def test_the_image_installs_cpu_only_torch():
    assert "--extra-index-url https://download.pytorch.org/whl/cpu" in DOCKERFILE


def test_the_api_service_waits_for_the_database_and_reads_secrets_at_runtime():
    api = COMPOSE["services"]["api"]
    assert api["depends_on"]["db"]["condition"] == "service_healthy"
    assert api["env_file"] == ["backend/.env"]
    assert "@db:5432/" in api["environment"]["DATABASE_URL"]
    assert "uploads:/app/uploads" in api["volumes"]
    assert "healthcheck" in api


def test_the_smoke_test_pdf_is_readable_by_pypdf(tmp_path):
    path = tmp_path / "smoke.pdf"
    path.write_bytes(make_pdf(PDF_TEXT))

    pages = extract_text_from_pdf(str(path))

    assert [page["page_number"] for page in pages] == [1]
    assert pages[0]["text"].split() == PDF_TEXT.split()
