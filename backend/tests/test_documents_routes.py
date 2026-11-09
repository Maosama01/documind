"""
Upload, status and delete through the API, with a real PDF and real pypdf.

Uploads go to a temporary folder (pdf_service.UPLOAD_DIR is redirected) and
the embedding model is faked. TestClient runs the background processing task
before the upload request returns, so the status is final when it is read.
"""
from pathlib import Path

import pytest

from app.services import document_service, pdf_service
from app.services.document_service import UNREADABLE_PDF
from app.services.pdf_service import delete_upload_file

EMAIL = "owner@example.com"
PASSWORD = "correct horse battery staple"
SENTENCE = " ".join(f"word{i}" for i in range(40))  # 40 words: enough for one chunk


def make_pdf(text: str) -> bytes:
    """A minimal one-page PDF showing `text` in Helvetica, with correct byte offsets."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_offset = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    pdf += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    pdf += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode()
    return bytes(pdf)


@pytest.fixture
def upload_dir(tmp_path, monkeypatch) -> Path:
    folder = tmp_path / "uploads"
    folder.mkdir()
    monkeypatch.setattr(pdf_service, "UPLOAD_DIR", str(folder))
    return folder


@pytest.fixture
def fake_model(monkeypatch):
    monkeypatch.setattr(document_service, "get_model", lambda: object())
    monkeypatch.setattr(document_service, "count_over_token_limit", lambda texts: 0)
    monkeypatch.setattr(
        document_service, "create_embeddings_batch", lambda texts: [[0.1] * 384 for _ in texts]
    )


def login(client) -> dict:
    client.post("/auth/signup", json={"email": EMAIL, "full_name": "Owner", "password": PASSWORD})
    token = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def upload(client, headers, content: bytes, name="contract.pdf") -> dict:
    response = client.post("/documents/upload", files={"file": (name, content, "application/pdf")}, headers=headers)
    assert response.status_code == 201
    return response.json()


@pytest.mark.db
def test_a_real_pdf_is_processed(client, upload_dir, fake_model):
    headers = login(client)

    document = upload(client, headers, make_pdf(SENTENCE))

    status = client.get(f"/documents/{document['id']}/status", headers=headers).json()
    assert status["status"] == "processed"
    assert status["page_count"] == 1
    assert status["error_message"] is None
    assert (upload_dir / document["filename"]).exists()


@pytest.mark.db
def test_a_file_that_is_not_a_pdf_fails_with_a_reason(client, upload_dir, fake_model):
    headers = login(client)

    document = upload(client, headers, b"this is plain text, not a PDF", name="notes.pdf")

    status = client.get(f"/documents/{document['id']}/status", headers=headers).json()
    assert status["status"] == "failed"
    assert status["error_message"] == UNREADABLE_PDF
    assert status["message"] == f"Processing failed: {UNREADABLE_PDF}"
    fetched = client.get(f"/documents/{document['id']}", headers=headers).json()
    assert fetched["error_message"] == UNREADABLE_PDF


@pytest.mark.db
def test_deleting_a_document_deletes_its_file(client, upload_dir, fake_model):
    headers = login(client)
    document = upload(client, headers, make_pdf(SENTENCE))
    saved = upload_dir / document["filename"]
    assert saved.exists()

    response = client.delete(f"/documents/{document['id']}", headers=headers)

    assert response.status_code == 204
    assert not saved.exists()


@pytest.mark.db
def test_deleting_works_when_the_file_is_already_gone(client, upload_dir, fake_model):
    headers = login(client)
    document = upload(client, headers, make_pdf(SENTENCE))
    (upload_dir / document["filename"]).unlink()

    response = client.delete(f"/documents/{document['id']}", headers=headers)

    assert response.status_code == 204
    assert client.get(f"/documents/{document['id']}", headers=headers).status_code == 404


def test_delete_upload_file_stays_inside_the_upload_folder(upload_dir):
    outside = upload_dir.parent / "outside.pdf"
    outside.write_bytes(b"not yours")
    inside = upload_dir / "mine.pdf"
    inside.write_bytes(b"yours")

    assert delete_upload_file("../outside.pdf") is False
    assert outside.exists()
    assert delete_upload_file("mine.pdf") is True
    assert not inside.exists()
    assert delete_upload_file("mine.pdf") is False  # already gone: not an error
