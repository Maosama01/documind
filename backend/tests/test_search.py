"""
semantic_search returns the exact nearest chunks of one document.

The set-up is the case that breaks a filtered approximate (HNSW) search:
another document's chunks are all closer to the question than any chunk of the
document being searched.
"""
import math

import pytest
from sqlalchemy import text

from app.models import Chunk, Document, User
from app.services import document_service
from app.services.document_service import semantic_search

pytestmark = pytest.mark.db


def at_angle(theta: float) -> list:
    """A 384-d unit vector at angle theta from QUESTION: cosine distance = 1 - cos(theta)."""
    vector = [0.0] * 384
    vector[0], vector[1] = math.cos(theta), math.sin(theta)
    return vector


QUESTION = at_angle(0.0)


@pytest.fixture
def target_document(db_session, monkeypatch) -> int:
    monkeypatch.setattr(document_service, "create_embedding", lambda question: QUESTION)
    user = User(email="owner@example.com", full_name="Owner", hashed_password="not-a-real-hash")
    db_session.add(user)
    db_session.flush()
    target = Document(title="Target", filename="t.pdf", status="processed", owner_id=user.id)
    other = Document(title="Other", filename="o.pdf", status="processed", owner_id=user.id)
    db_session.add_all([target, other])
    db_session.flush()
    # Target chunk i sits at angle 0.1 * (i + 1), so the exact order is target 0, 1, 2, ...
    db_session.add_all(
        Chunk(content=f"target {i}", chunk_index=i, page_number=1,
              embedding=at_angle(0.1 * (i + 1)), document_id=target.id)
        for i in range(8)
    )
    # Every chunk of the other document is closer to the question than any target chunk.
    db_session.add_all(
        Chunk(content=f"other {i}", chunk_index=i, page_number=1,
              embedding=at_angle(0.001 * (i + 1)), document_id=other.id)
        for i in range(30)
    )
    db_session.commit()
    return target.id


def contents(chunks) -> list:
    return [chunk.content for chunk in chunks]


def test_returns_the_closest_chunks_of_the_document_in_order(db_session, target_document):
    results = semantic_search(db_session, "question", target_document, top_k=5)

    assert contents(results) == [f"target {i}" for i in range(5)]


def test_never_returns_chunks_of_another_document(db_session, target_document):
    results = semantic_search(db_session, "question", target_document, top_k=50)

    assert contents(results) == [f"target {i}" for i in range(8)]


def test_same_results_when_postgres_has_to_use_the_document_index(db_session, target_document):
    """
    With sequential scans switched off, Postgres must reach the rows through an
    index. The plan shows it uses ix_chunks_document_id, and the results stay exact.
    """
    db_session.execute(text("SET LOCAL enable_seqscan = off"))  # this transaction only
    question = "[" + ",".join(str(x) for x in QUESTION) + "]"
    plan = "\n".join(db_session.execute(
        text(
            "EXPLAIN SELECT id FROM chunks WHERE document_id = :document_id "
            "ORDER BY embedding <=> CAST(:question AS vector) LIMIT 5"
        ),
        {"document_id": target_document, "question": question},
    ).scalars())
    results = contents(semantic_search(db_session, "question", target_document, top_k=5))
    db_session.rollback()

    assert "ix_chunks_document_id" in plan
    assert results == [f"target {i}" for i in range(5)]
