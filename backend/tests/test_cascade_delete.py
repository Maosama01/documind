"""
Deleting a document must delete its chunks.

Before Phase 1 there was no cascade, so deleting a processed document raised
IntegrityError (its chunks still pointed at it).
"""
import pytest
from sqlalchemy import text

from app.models import Chunk, Document, User

EMAIL = "owner@example.com"
PASSWORD = "correct horse battery staple"


def add_document_with_chunks(db, owner_id: int, n_chunks: int = 3) -> int:
    document = Document(title="Doc", filename="doc.pdf", status="processed", owner_id=owner_id)
    db.add(document)
    db.flush()
    for i in range(n_chunks):
        db.add(Chunk(
            content=f"chunk {i}",
            chunk_index=i,
            page_number=1,
            embedding=[0.1] * 384,
            document_id=document.id,
        ))
    db.commit()
    return document.id


def add_user(db) -> int:
    user = User(email=EMAIL, full_name="Owner", hashed_password="not-a-real-hash")
    db.add(user)
    db.commit()
    return user.id


def chunk_count(db, document_id: int) -> int:
    return db.query(Chunk).filter(Chunk.document_id == document_id).count()


def test_chunk_foreign_key_declares_on_delete_cascade():
    (foreign_key,) = Chunk.__table__.c.document_id.foreign_keys
    assert foreign_key.ondelete == "CASCADE"


def test_document_chunks_relationship_cascades_delete_and_orphans():
    cascade = Document.chunks.property.cascade
    assert cascade.delete
    assert cascade.delete_orphan


@pytest.mark.db
def test_orm_delete_removes_chunks(db_session):
    document_id = add_document_with_chunks(db_session, add_user(db_session))

    db_session.delete(db_session.get(Document, document_id))
    db_session.commit()

    assert chunk_count(db_session, document_id) == 0


@pytest.mark.db
def test_raw_sql_delete_removes_chunks_through_the_foreign_key(db_session):
    """Bypasses SQLAlchemy's cascade, so only ON DELETE CASCADE in Postgres can pass this."""
    document_id = add_document_with_chunks(db_session, add_user(db_session))

    db_session.execute(text("DELETE FROM documents WHERE id = :id"), {"id": document_id})
    db_session.commit()

    assert chunk_count(db_session, document_id) == 0


@pytest.mark.db
def test_chunk_removed_from_document_is_deleted(db_session):
    document_id = add_document_with_chunks(db_session, add_user(db_session), n_chunks=3)
    document = db_session.get(Document, document_id)

    document.chunks.remove(document.chunks[0])
    db_session.commit()

    assert chunk_count(db_session, document_id) == 2


@pytest.mark.db
def test_delete_endpoint_removes_processed_document_and_chunks(client, db_session):
    client.post("/auth/signup", json={"email": EMAIL, "full_name": "Owner", "password": PASSWORD})
    token = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}).json()["access_token"]
    owner_id = db_session.query(User).filter(User.email == EMAIL).one().id
    document_id = add_document_with_chunks(db_session, owner_id)

    response = client.delete(f"/documents/{document_id}", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 204
    assert db_session.query(Document).filter(Document.id == document_id).count() == 0
    assert chunk_count(db_session, document_id) == 0
