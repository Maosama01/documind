"""
process_document with the chunk settings, against the test database.

The PDF reading and the embedding model are replaced by fakes, so these tests
check the pipeline's wiring (settings → chunks → rows → log), not pypdf or MiniLM.
"""
import logging

import pytest

from app.config import settings
from app.models import Chunk, Document, User
from app.services import document_service

pytestmark = pytest.mark.db


@pytest.fixture
def fake_pdf(monkeypatch):
    """Replace PDF reading and embedding. Returns a dict the test fills with pages."""
    pdf = {"pages": [], "over_limit": 0}
    monkeypatch.setattr(document_service, "extract_text_from_pdf", lambda path: pdf["pages"])
    monkeypatch.setattr(
        document_service, "get_pdf_metadata",
        lambda path: {"page_count": len(pdf["pages"]), "content_preview": ""},
    )
    monkeypatch.setattr(document_service, "get_file_size", lambda path: 1234)
    monkeypatch.setattr(document_service, "count_over_token_limit", lambda texts: pdf["over_limit"])
    monkeypatch.setattr(
        document_service, "create_embeddings_batch", lambda texts: [[0.0] * 384 for _ in texts]
    )
    return pdf


def new_document(db) -> int:
    user = User(email="owner@example.com", full_name="Owner", hashed_password="not-a-real-hash")
    db.add(user)
    db.flush()
    document = Document(title="Doc", filename="doc.pdf", status="pending", owner_id=user.id)
    db.add(document)
    db.commit()
    return document.id


def page_text(n_words: int) -> str:
    return " ".join(f"w{i}" for i in range(n_words))


def test_chunks_use_the_size_and_overlap_settings(db_session, fake_pdf):
    fake_pdf["pages"] = [{"page_number": 1, "text": page_text(400)}]
    document_id = new_document(db_session)

    document_service.process_document(db_session, document_id, "unused.pdf")

    chunks = db_session.query(Chunk).filter(Chunk.document_id == document_id).order_by(Chunk.chunk_index).all()
    assert [len(c.content.split()) for c in chunks] == [180, 180, 100]
    assert db_session.get(Document, document_id).status == "processed"


def test_changing_the_settings_changes_the_chunks(db_session, fake_pdf, monkeypatch):
    monkeypatch.setattr(settings, "CHUNK_SIZE_WORDS", 100)
    monkeypatch.setattr(settings, "CHUNK_OVERLAP_WORDS", 20)
    fake_pdf["pages"] = [{"page_number": 1, "text": page_text(400)}]
    document_id = new_document(db_session)

    document_service.process_document(db_session, document_id, "unused.pdf")

    sizes = [len(c.content.split()) for c in db_session.query(Chunk).order_by(Chunk.chunk_index)]
    assert sizes == [100, 100, 100, 100, 80]


def test_chunks_over_the_token_limit_are_logged(db_session, fake_pdf, caplog):
    fake_pdf["pages"] = [{"page_number": 1, "text": page_text(400)}]
    fake_pdf["over_limit"] = 2
    document_id = new_document(db_session)

    with caplog.at_level(logging.WARNING, logger="app.services.document_service"):
        document_service.process_document(db_session, document_id, "unused.pdf")

    assert f"Document {document_id}: 2 of 3 chunks exceed" in caplog.text


def test_nothing_is_logged_when_every_chunk_fits(db_session, fake_pdf, caplog):
    fake_pdf["pages"] = [{"page_number": 1, "text": page_text(400)}]
    document_id = new_document(db_session)

    with caplog.at_level(logging.WARNING, logger="app.services.document_service"):
        document_service.process_document(db_session, document_id, "unused.pdf")

    assert "exceed" not in caplog.text
