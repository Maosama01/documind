"""
At startup, documents a previous server process left "pending" or
"processing" are marked failed, so they do not show as in progress forever.
"""
import pytest
from fastapi.testclient import TestClient

from app.models import Document, User
from app.services.document_service import INTERRUPTED, fail_interrupted_documents

pytestmark = pytest.mark.db


def add_documents(db, statuses) -> dict:
    user = User(email="owner@example.com", full_name="Owner", hashed_password="not-a-real-hash")
    db.add(user)
    db.flush()
    ids = {}
    for status in statuses:
        document = Document(title=status, filename=f"{status}.pdf", status=status, owner_id=user.id,
                            error_message="its own reason" if status == "failed" else None)
        db.add(document)
        db.flush()
        ids[status] = document.id
    db.commit()
    return ids


def state(db, document_id):
    db.expire_all()
    document = db.get(Document, document_id)
    return document.status, document.error_message


def test_unfinished_documents_are_marked_failed(db_session):
    ids = add_documents(db_session, ["pending", "processing", "processed", "failed"])

    assert fail_interrupted_documents(db_session) == 2

    assert state(db_session, ids["pending"]) == ("failed", INTERRUPTED)
    assert state(db_session, ids["processing"]) == ("failed", INTERRUPTED)
    assert state(db_session, ids["processed"]) == ("processed", None)
    assert state(db_session, ids["failed"]) == ("failed", "its own reason")


def test_the_server_does_it_on_startup(db_session):
    ids = add_documents(db_session, ["processing"])
    from app.main import app

    with TestClient(app):  # entering runs the lifespan startup: init_db, then the recovery
        pass

    assert state(db_session, ids["processing"]) == ("failed", INTERRUPTED)
