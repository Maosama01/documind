"""
POST /query/ end to end against the test database.

The question's embedding and the LLM are faked; retrieval (pgvector ordering),
auth, ownership checks and the response shape are real.
"""
import httpx
import pytest

from app.config import settings
from app.models import Chunk, Document, User
from app.services import document_service, llm_service

pytestmark = pytest.mark.db

PASSWORD = "correct horse battery staple"


def unit_vector(index: int) -> list:
    vector = [0.0] * 384
    vector[index] = 1.0
    return vector


def login(client, email: str) -> dict:
    client.post("/auth/signup", json={"email": email, "full_name": "User", "password": PASSWORD})
    token = client.post("/auth/login", json={"email": email, "password": PASSWORD}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def add_document(db, email: str, status: str = "processed") -> int:
    owner = db.query(User).filter(User.email == email).one()
    document = Document(title="Contract", filename="contract.pdf", status=status, owner_id=owner.id)
    db.add(document)
    db.flush()
    db.add_all([
        # The question's fake embedding is unit_vector(0), so page 2 ranks first.
        Chunk(content="Invoices are due within 30 days.", chunk_index=0, page_number=2,
              embedding=unit_vector(0), document_id=document.id),
        Chunk(content="The contract renews every year.", chunk_index=1, page_number=4,
              embedding=unit_vector(1), document_id=document.id),
    ])
    db.commit()
    return document.id


@pytest.fixture
def fake_question_embedding(monkeypatch):
    monkeypatch.setattr(document_service, "create_embedding", lambda text: unit_vector(0))


def fake_gemini(monkeypatch, status_code=200, text="Invoices are due within 30 days [p.2]."):
    reply = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(
        llm_service, "_new_client",
        lambda: httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(status_code, json=reply))),
    )


def test_query_requires_a_token(client):
    response = client.post("/query/", json={"question": "When?", "document_id": 1})

    assert response.status_code == 401


def test_query_answers_from_retrieved_chunks(client, db_session, monkeypatch, fake_question_embedding):
    headers = login(client, "owner@example.com")
    document_id = add_document(db_session, "owner@example.com")
    fake_gemini(monkeypatch)

    response = client.post(
        "/query/",
        json={"question": "When are invoices due?", "document_id": document_id, "max_results": 2},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["question"] == "When are invoices due?"
    assert body["answer"] == "Invoices are due within 30 days [p.2]."
    assert body["cited_pages"] == [2]
    assert body["grounded"] is True
    assert body["provider"] == f"gemini:{settings.GEMINI_MODEL}"
    assert [(s["rank"], s["page_number"]) for s in body["sources"]] == [(1, 2), (2, 4)]
    assert body["sources"][0]["content"] == "Invoices are due within 30 days."
    assert "confidence" not in body  # the old placeholder's made-up number is gone


def test_max_results_limits_the_sources(client, db_session, monkeypatch, fake_question_embedding):
    headers = login(client, "owner@example.com")
    document_id = add_document(db_session, "owner@example.com")
    fake_gemini(monkeypatch)

    response = client.post(
        "/query/", json={"question": "Due?", "document_id": document_id, "max_results": 1}, headers=headers
    )

    assert [s["page_number"] for s in response.json()["sources"]] == [2]


def test_someone_elses_document_is_not_found(client, db_session, fake_question_embedding):
    login(client, "owner@example.com")
    document_id = add_document(db_session, "owner@example.com")
    stranger = login(client, "stranger@example.com")

    response = client.post("/query/", json={"question": "Due?", "document_id": document_id}, headers=stranger)

    assert response.status_code == 404


def test_unprocessed_document_is_rejected(client, db_session, fake_question_embedding):
    headers = login(client, "owner@example.com")
    document_id = add_document(db_session, "owner@example.com", status="processing")

    response = client.post("/query/", json={"question": "Due?", "document_id": document_id}, headers=headers)

    assert response.status_code == 400
    assert "processing" in response.json()["detail"]


def test_provider_failure_returns_502(client, db_session, monkeypatch, fake_question_embedding):
    headers = login(client, "owner@example.com")
    document_id = add_document(db_session, "owner@example.com")
    fake_gemini(monkeypatch, status_code=500)

    response = client.post("/query/", json={"question": "Due?", "document_id": document_id}, headers=headers)

    assert response.status_code == 502
    assert response.json()["detail"] == "Answer generation failed: gemini returned HTTP 500"


@pytest.mark.parametrize(
    "payload",
    [
        {"question": "   ", "document_id": 1},
        {"question": "Due?", "document_id": 1, "max_results": 0},
        {"question": "Due?", "document_id": 1, "max_results": 11},
    ],
)
def test_invalid_requests_are_rejected(client, payload):
    headers = login(client, "owner@example.com")

    response = client.post("/query/", json=payload, headers=headers)

    assert response.status_code == 422
