"""
Retrieval evaluation: does semantic_search find the pages that answer each question?

Run from backend/ (needs backend/.env with SECRET_KEY and DATABASE_URL, like the app):

    .venv/bin/python -m scripts.eval_retrieval data/golden.jsonl [--k 5]

Golden set: a JSONL file, one JSON object per line, written by hand:

    {"question": "When are invoices due?", "document_id": 1, "expected_pages": [3]}

document_id is the id of an uploaded, processed document in the database the
app uses. expected_pages are the pages (1-based) that answer the question.

Metrics are counted in pages, not chunks: several retrieved chunks from the
same page count once.
- recall@k: per question, (expected pages found among the pages of the top k
  chunks) / (number of expected pages), averaged over all questions.
- hit@k: share of questions with at least one expected page in the top k.
- faithfulness: RESULT PENDING. Not implemented: it needs each claim in a
  generated answer checked against the text it cites.

The script reads the database directly and ignores document ownership: it is
a local tool, not an API.
"""
import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple

FIELDS = {"question", "document_id", "expected_pages"}
FAITHFULNESS = "RESULT PENDING (not implemented: needs each claim checked against the text it cites)"


class GoldenSetError(ValueError):
    """The golden set (or the documents it names) cannot be evaluated. Lists every problem found."""


@dataclass
class GoldenRow:
    line: int
    question: str
    document_id: int
    expected_pages: List[int]


@dataclass
class QuestionResult:
    row: GoldenRow
    retrieved_pages: List[int]  # page of each top-k chunk, most similar first
    recall: float
    hit: bool


def recall_at_k(expected_pages: Sequence[int], retrieved_pages: Sequence[int]) -> float:
    expected = set(expected_pages)
    return len(expected & set(retrieved_pages)) / len(expected)


def hit_at_k(expected_pages: Sequence[int], retrieved_pages: Sequence[int]) -> bool:
    return bool(set(expected_pages) & set(retrieved_pages))


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def load_golden_set(path: Path) -> List[GoldenRow]:
    """Parse and check every line; raise GoldenSetError listing all problems at once."""
    rows, errors = [], []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as error:
            errors.append(f"line {number}: not valid JSON ({error.msg})")
            continue
        if not isinstance(data, dict):
            errors.append(f"line {number}: expected a JSON object")
            continue
        if data.get("example"):
            errors.append(
                f'line {number}: marked "example": true. The example file only shows the format: '
                "copy it, write real questions about your own document, and delete the example field"
            )
            continue

        unknown = set(data) - FIELDS - {"example"}  # catches typos such as "expected_page"
        missing = FIELDS - set(data)
        if unknown or missing:
            if unknown:
                errors.append(f"line {number}: unknown field(s) {sorted(unknown)}")
            if missing:
                errors.append(f"line {number}: missing field(s) {sorted(missing)}")
            continue

        question, document_id, pages = data["question"], data["document_id"], data["expected_pages"]
        line_errors = []
        if not isinstance(question, str) or not question.strip():
            line_errors.append("question must be a non-empty string")
        if not _is_int(document_id):
            line_errors.append("document_id must be an integer")
        if not isinstance(pages, list) or not pages or not all(_is_int(p) and p >= 1 for p in pages):
            line_errors.append("expected_pages must be a non-empty list of page numbers (1 or more)")
        elif len(set(pages)) != len(pages):
            line_errors.append("expected_pages lists a page twice")
        if line_errors:
            errors.extend(f"line {number}: {message}" for message in line_errors)
            continue
        rows.append(GoldenRow(number, question.strip(), document_id, pages))

    if errors:
        raise GoldenSetError("\n".join(errors))
    if not rows:
        raise GoldenSetError("the golden set has no questions")
    return rows


def evaluate(db, rows: List[GoldenRow], k: int) -> Tuple[List[QuestionResult], dict]:
    """Search every question and score it. Checks the named documents first."""
    from app.models import Document
    from app.services.document_service import semantic_search

    # A missing or unprocessed document is an error, never a score of 0.
    errors, documents = [], {}
    for document_id in sorted({row.document_id for row in rows}):
        document = db.get(Document, document_id)
        if document is None:
            errors.append(f"document {document_id} does not exist")
        elif document.status != "processed":
            errors.append(f"document {document_id} is not processed (status: {document.status})")
        else:
            documents[document_id] = document
    # An expected page past the end of the document is a typo that would cap recall.
    for row in rows:
        document = documents.get(row.document_id)
        if document is not None and document.page_count:
            too_high = [page for page in row.expected_pages if page > document.page_count]
            if too_high:
                errors.append(
                    f"line {row.line}: expected page(s) {too_high} but document {row.document_id} "
                    f"has {document.page_count} pages"
                )
    if errors:
        raise GoldenSetError("\n".join(errors))

    results = []
    for row in rows:
        chunks = semantic_search(db, row.question, row.document_id, k)
        retrieved = [chunk.page_number for chunk in chunks]
        results.append(QuestionResult(
            row, retrieved,
            recall_at_k(row.expected_pages, retrieved),
            hit_at_k(row.expected_pages, retrieved),
        ))
    summary = {
        "questions": len(results),
        "k": k,
        "recall_at_k": sum(r.recall for r in results) / len(results),
        "hit_at_k": sum(r.hit for r in results) / len(results),
    }
    return results, summary


def format_report(results: List[QuestionResult], summary: dict, golden_path: Path) -> str:
    k = summary["k"]
    lines = [
        f"Retrieval evaluation: {summary['questions']} questions from {golden_path}, k={k}",
        "",
        f"{'line':>4}  {'doc':>4}  {'expected':<12} {'retrieved pages (top ' + str(k) + ')':<26} {'recall':>6}  hit  question",
    ]
    for r in results:
        question = r.row.question if len(r.row.question) <= 60 else r.row.question[:57] + "..."
        lines.append(
            f"{r.row.line:>4}  {r.row.document_id:>4}  {str(r.row.expected_pages):<12} "
            f"{str(r.retrieved_pages):<26} {r.recall:>6.2f}  {'yes' if r.hit else 'no ':<3}  {question}"
        )
    lines += [
        "",
        f"recall@{k}: {summary['recall_at_k']:.2f}  "
        f"(mean over questions of: expected pages found in the top {k} / expected pages)",
        f"hit@{k}:    {summary['hit_at_k']:.2f}  "
        f"(share of questions with at least one expected page in the top {k})",
        f"faithfulness: {FAITHFULNESS}",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Measure recall@k of DocuMind's retrieval on a golden set.")
    parser.add_argument("golden_set", type=Path, help="JSONL file: question, document_id, expected_pages")
    parser.add_argument("--k", type=int, default=5, help="number of chunks retrieved per question (default 5)")
    args = parser.parse_args(argv)
    if not 1 <= args.k <= 50:
        parser.error("--k must be between 1 and 50")

    try:
        rows = load_golden_set(args.golden_set)
    except (GoldenSetError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    # Imported only now: importing the app needs SECRET_KEY and the database
    # settings, which checking the golden set above does not.
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        results, summary = evaluate(db, rows, args.k)
    except GoldenSetError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    finally:
        db.close()

    print(format_report(results, summary, args.golden_set))
    return 0


if __name__ == "__main__":
    sys.exit(main())
