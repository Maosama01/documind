"""
scripts/eval_retrieval.py: metric maths, golden-set checks, and full runs
against the test database with hand-made embeddings (never the real model).
"""
import json
import math
from pathlib import Path

import pytest

from app.models import Chunk, Document, User
from app.services import document_service
from scripts.eval_retrieval import (
    GoldenRow,
    GoldenSetError,
    evaluate,
    hit_at_k,
    load_golden_set,
    main,
    recall_at_k,
)

EXAMPLE_FILE = Path(__file__).resolve().parent.parent / "data" / "golden.example.jsonl"


def write_jsonl(path: Path, rows) -> Path:
    path.write_text("\n".join(row if isinstance(row, str) else json.dumps(row) for row in rows) + "\n")
    return path


def row(**overrides) -> dict:
    return {"question": "When are invoices due?", "document_id": 1, "expected_pages": [3], **overrides}


# ---- metric maths -----------------------------------------------------------

@pytest.mark.parametrize(
    "expected,retrieved,recall,hit",
    [
        ([3], [3, 3, 4, 1, 2], 1.0, True),   # a page counts once however many chunks come from it
        ([3, 5], [5, 1, 1, 2, 2], 0.5, True),
        ([3, 5], [1, 2, 4, 6, 7], 0.0, False),
        ([2, 3, 4], [4, 3, 2], 1.0, True),   # order inside the top k does not matter
    ],
)
def test_recall_and_hit(expected, retrieved, recall, hit):
    assert recall_at_k(expected, retrieved) == recall
    assert hit_at_k(expected, retrieved) is hit


# ---- golden-set checks ------------------------------------------------------

def test_valid_golden_set_is_loaded_and_blank_lines_are_skipped(tmp_path):
    path = write_jsonl(tmp_path / "golden.jsonl", [row(), "", row(question="  Renewal?  ", expected_pages=[5, 6])])

    rows = load_golden_set(path)

    assert rows == [
        GoldenRow(1, "When are invoices due?", 1, [3]),
        GoldenRow(3, "Renewal?", 1, [5, 6]),
    ]


def test_the_committed_example_file_is_refused():
    with pytest.raises(GoldenSetError) as error:
        load_golden_set(EXAMPLE_FILE)

    assert [f"line {n}: marked \"example\": true" in str(error.value) for n in (1, 2, 3)] == [True] * 3


def test_the_example_file_is_valid_once_the_example_flag_is_removed(tmp_path):
    lines = EXAMPLE_FILE.read_text().splitlines()
    unflagged = [{k: v for k, v in json.loads(line).items() if k != "example"} for line in lines]

    rows = load_golden_set(write_jsonl(tmp_path / "golden.jsonl", unflagged))

    assert len(rows) == 3


@pytest.mark.parametrize(
    "bad_line,message",
    [
        ("{not json", "not valid JSON"),
        ("[1, 2]", "expected a JSON object"),
        (json.dumps({"question": "Q", "document_id": 1}), "missing field(s) ['expected_pages']"),
        (json.dumps(row(expected_page=[3])), "unknown field(s) ['expected_page']"),
        (json.dumps(row(question="  ")), "question must be a non-empty string"),
        (json.dumps(row(document_id="1")), "document_id must be an integer"),
        (json.dumps(row(document_id=True)), "document_id must be an integer"),
        (json.dumps(row(expected_pages=[])), "expected_pages must be a non-empty list"),
        (json.dumps(row(expected_pages=[0])), "expected_pages must be a non-empty list"),
        (json.dumps(row(expected_pages=["3"])), "expected_pages must be a non-empty list"),
        (json.dumps(row(expected_pages=[3, 3])), "expected_pages lists a page twice"),
    ],
)
def test_bad_lines_are_reported_with_their_line_number(tmp_path, bad_line, message):
    path = write_jsonl(tmp_path / "golden.jsonl", [row(), bad_line])

    with pytest.raises(GoldenSetError) as error:
        load_golden_set(path)

    assert f"line 2: {message}" in str(error.value)


def test_every_problem_is_reported_at_once(tmp_path):
    path = write_jsonl(tmp_path / "golden.jsonl", ["{bad", row(document_id="x"), row(expected_pages=[])])

    with pytest.raises(GoldenSetError) as error:
        load_golden_set(path)

    assert [line.split(":")[0] for line in str(error.value).splitlines()] == ["line 1", "line 2", "line 3"]


def test_empty_golden_set_is_refused(tmp_path):
    with pytest.raises(GoldenSetError, match="no questions"):
        load_golden_set(write_jsonl(tmp_path / "golden.jsonl", [""]))


def test_main_refuses_the_example_file_before_touching_the_database(capsys):
    assert main([str(EXAMPLE_FILE)]) == 2
    assert 'marked "example": true' in capsys.readouterr().err


def test_main_reports_a_missing_file(tmp_path, capsys):
    assert main([str(tmp_path / "nope.jsonl")]) == 2
    assert "error:" in capsys.readouterr().err


# ---- full runs against the test database ------------------------------------

def at_angle(theta: float) -> list:
    vector = [0.0] * 384
    vector[0], vector[1] = math.cos(theta), math.sin(theta)
    return vector


# One chunk per page; page p sits at angle 0.1 * p. A question at angle a
# retrieves the pages whose angles are closest to a.
QUESTION_VECTORS = {
    "near page 1": at_angle(0.0),   # top 2: pages 1, 2
    "near page 4": at_angle(0.4),   # top 2: pages 4, 3
}


@pytest.fixture
def processed_document(db_session, monkeypatch) -> int:
    monkeypatch.setattr(document_service, "create_embedding", lambda question: QUESTION_VECTORS[question])
    user = User(email="owner@example.com", full_name="Owner", hashed_password="not-a-real-hash")
    db_session.add(user)
    db_session.flush()
    document = Document(title="Doc", filename="doc.pdf", status="processed", page_count=4, owner_id=user.id)
    pending = Document(title="Pending", filename="p.pdf", status="processing", owner_id=user.id)
    db_session.add_all([document, pending])
    db_session.flush()
    db_session.add_all(
        Chunk(content=f"page {page}", chunk_index=page - 1, page_number=page,
              embedding=at_angle(0.1 * page), document_id=document.id)
        for page in range(1, 5)
    )
    db_session.commit()
    return document.id


def golden_rows(document_id: int):
    return [
        GoldenRow(1, "near page 1", document_id, [2]),      # retrieved [1, 2]: recall 1.0, hit
        GoldenRow(2, "near page 4", document_id, [1, 4]),   # retrieved [4, 3]: recall 0.5, hit
        GoldenRow(3, "near page 1", document_id, [4]),      # retrieved [1, 2]: recall 0.0, miss
    ]


@pytest.mark.db
def test_evaluate_scores_each_question_and_averages(db_session, processed_document):
    results, summary = evaluate(db_session, golden_rows(processed_document), k=2)

    assert [r.retrieved_pages for r in results] == [[1, 2], [4, 3], [1, 2]]
    assert [r.recall for r in results] == [1.0, 0.5, 0.0]
    assert [r.hit for r in results] == [True, True, False]
    assert summary == {"questions": 3, "k": 2, "recall_at_k": 0.5, "hit_at_k": 2 / 3}


@pytest.mark.db
def test_documents_that_cannot_be_scored_are_errors_not_zeros(db_session, processed_document):
    pending_id = db_session.query(Document).filter(Document.status == "processing").one().id
    rows = [
        GoldenRow(1, "near page 1", 999_999, [1]),
        GoldenRow(2, "near page 1", pending_id, [1]),
        GoldenRow(3, "near page 1", processed_document, [9]),
    ]

    with pytest.raises(GoldenSetError) as error:
        evaluate(db_session, rows, k=2)

    message = str(error.value)
    assert "document 999999 does not exist" in message
    assert f"document {pending_id} is not processed (status: processing)" in message
    assert f"line 3: expected page(s) [9] but document {processed_document} has 4 pages" in message


@pytest.mark.db
def test_main_prints_the_report(db_session, processed_document, tmp_path, capsys):
    path = write_jsonl(tmp_path / "golden.jsonl", [
        {"question": r.question, "document_id": r.document_id, "expected_pages": r.expected_pages}
        for r in golden_rows(processed_document)
    ])

    assert main([str(path), "--k", "2"]) == 0

    report = capsys.readouterr().out
    assert "3 questions" in report
    assert "recall@2: 0.50" in report
    assert "hit@2:    0.67" in report
    assert "faithfulness: RESULT PENDING" in report
