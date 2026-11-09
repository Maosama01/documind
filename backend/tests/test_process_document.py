"""
process_document against the test database.

PDF reading and the embedding model are replaced by fakes, so these tests
check the pipeline's wiring and failure handling, not pypdf or MiniLM.
"""
import logging

import pytest
from pypdf.errors import PdfReadError

from app.config import settings
from app.database import SessionLocal
from app.models import Chunk, Document, User
from app.services import document_service
from app.services.document_service import (
    INTERNAL_ERROR,
    MODEL_UNAVAILABLE,
    NO_TEXT,
    UNREADABLE_PDF,
)

pytestmark = pytest.mark.db


def raise_(error):
    raise error


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
    monkeypatch.setattr(document_service, "get_model", lambda: object())
    monkeypatch.setattr(document_service, "count_over_token_limit", lambda texts: pdf["over_limit"])
    monkeypatch.setattr(
        document_service, "create_embeddings_batch", lambda texts: [[0.0] * 384 for _ in texts]
    )
    return pdf


def new_document(db, status="pending", error_message=None) -> int:
    user = User(email="owner@example.com", full_name="Owner", hashed_password="not-a-real-hash")
    db.add(user)
    db.flush()
    document = Document(title="Doc", filename="doc.pdf", status=status,
                        error_message=error_message, owner_id=user.id)
    db.add(document)
    db.commit()
    return document.id


def page_text(n_words: int) -> str:
    return " ".join(f"w{i}" for i in range(n_words))


def reloaded(db, document_id: int) -> Document:
    """The document as processing (in its own session) left it."""
    db.expire_all()
    return db.get(Document, document_id)


def chunk_sizes(db, document_id: int) -> list:
    chunks = db.query(Chunk).filter(Chunk.document_id == document_id).order_by(Chunk.chunk_index)
    return [len(chunk.content.split()) for chunk in chunks]


# ---- the happy path ---------------------------------------------------------

def test_chunks_use_the_size_and_overlap_settings(db_session, fake_pdf):
    fake_pdf["pages"] = [{"page_number": 1, "text": page_text(400)}]
    document_id = new_document(db_session)

    document_service.process_document(document_id, "unused.pdf")

    assert chunk_sizes(db_session, document_id) == [180, 180, 100]
    document = reloaded(db_session, document_id)
    assert document.status == "processed"
    assert document.error_message is None


def test_changing_the_settings_changes_the_chunks(db_session, fake_pdf, monkeypatch):
    monkeypatch.setattr(settings, "CHUNK_SIZE_WORDS", 100)
    monkeypatch.setattr(settings, "CHUNK_OVERLAP_WORDS", 20)
    fake_pdf["pages"] = [{"page_number": 1, "text": page_text(400)}]
    document_id = new_document(db_session)

    document_service.process_document(document_id, "unused.pdf")

    assert chunk_sizes(db_session, document_id) == [100, 100, 100, 100, 80]


def test_chunks_over_the_token_limit_are_logged(db_session, fake_pdf, caplog):
    fake_pdf["pages"] = [{"page_number": 1, "text": page_text(400)}]
    fake_pdf["over_limit"] = 2
    document_id = new_document(db_session)

    with caplog.at_level(logging.WARNING, logger="app.services.document_service"):
        document_service.process_document(document_id, "unused.pdf")

    assert f"Document {document_id}: 2 of 3 chunks exceed" in caplog.text


def test_nothing_is_logged_when_every_chunk_fits(db_session, fake_pdf, caplog):
    fake_pdf["pages"] = [{"page_number": 1, "text": page_text(400)}]
    document_id = new_document(db_session)

    with caplog.at_level(logging.WARNING, logger="app.services.document_service"):
        document_service.process_document(document_id, "unused.pdf")

    assert "exceed" not in caplog.text


def test_successful_processing_clears_an_old_error(db_session, fake_pdf):
    fake_pdf["pages"] = [{"page_number": 1, "text": page_text(50)}]
    document_id = new_document(db_session, status="failed", error_message="an older failure")

    document_service.process_document(document_id, "unused.pdf")

    document = reloaded(db_session, document_id)
    assert (document.status, document.error_message) == ("processed", None)


# ---- its own session --------------------------------------------------------

@pytest.mark.parametrize("fails", [False, True])
def test_processing_opens_and_closes_its_own_session(db_session, fake_pdf, monkeypatch, fails):
    fake_pdf["pages"] = [{"page_number": 1, "text": page_text(50)}]
    if fails:
        monkeypatch.setattr(document_service, "create_embeddings_batch",
                            lambda texts: raise_(RuntimeError("boom")))
    document_id = new_document(db_session)
    opened, closed = [], []

    def session_factory():
        session = SessionLocal()
        opened.append(session)
        original_close = session.close
        session.close = lambda: (closed.append(session), original_close())
        return session

    document_service.process_document(document_id, "unused.pdf", session_factory=session_factory)

    assert len(opened) == 1
    assert closed == opened


# ---- failures say why ------------------------------------------------------

@pytest.mark.parametrize(
    "break_it,expected",
    [
        (lambda pdf, mp: mp.setattr(document_service, "extract_text_from_pdf",
                                    lambda path: raise_(PdfReadError("EOF marker not found"))),
         UNREADABLE_PDF),
        (lambda pdf, mp: pdf.update(pages=[]), NO_TEXT),
        (lambda pdf, mp: pdf.update(pages=[{"page_number": 1, "text": "only five words on here"}]), NO_TEXT),
        (lambda pdf, mp: mp.setattr(document_service, "get_model",
                                    lambda: raise_(PermissionError("[Errno 13] Permission denied: '/Volumes/X'"))),
         MODEL_UNAVAILABLE),
        (lambda pdf, mp: mp.setattr(document_service, "create_embeddings_batch",
                                    lambda texts: raise_(RuntimeError("boom at /srv/secret/path"))),
         INTERNAL_ERROR),
    ],
    ids=["unreadable-pdf", "no-text", "only-short-pages", "model-unavailable", "unexpected-error"],
)
def test_failures_are_recorded_with_a_safe_reason(db_session, fake_pdf, monkeypatch, caplog, break_it, expected):
    fake_pdf["pages"] = [{"page_number": 1, "text": page_text(50)}]
    break_it(fake_pdf, monkeypatch)
    document_id = new_document(db_session)

    with caplog.at_level(logging.ERROR, logger="app.services.document_service"):
        document_service.process_document(document_id, "unused.pdf")  # does not raise

    document = reloaded(db_session, document_id)
    assert document.status == "failed"
    assert document.error_message == expected
    assert chunk_sizes(db_session, document_id) == []  # nothing half-saved
    assert f"Document {document_id} failed" in caplog.text  # the full error goes to the log


def test_the_raw_error_reaches_the_log_but_not_the_user(db_session, fake_pdf, monkeypatch, caplog):
    fake_pdf["pages"] = [{"page_number": 1, "text": page_text(50)}]
    monkeypatch.setattr(document_service, "create_embeddings_batch",
                        lambda texts: raise_(RuntimeError("boom at /srv/secret/path")))
    document_id = new_document(db_session)

    with caplog.at_level(logging.ERROR, logger="app.services.document_service"):
        document_service.process_document(document_id, "unused.pdf")

    assert "/srv/secret/path" in caplog.text
    assert "/srv/secret/path" not in reloaded(db_session, document_id).error_message


def test_a_deleted_document_is_skipped(db_session, fake_pdf, caplog):
    with caplog.at_level(logging.WARNING, logger="app.services.document_service"):
        document_service.process_document(999_999, "unused.pdf")

    assert "Document 999999 was deleted before processing started" in caplog.text
