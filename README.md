# DocuMind 🧠

An AI-powered document intelligence platform that lets users upload PDFs and ask questions in plain English — getting precise answers with source citations.

## Tech Stack

- **Backend:** FastAPI (Python)
- **Database:** PostgreSQL + pgvector
- **AI/ML:** HuggingFace Sentence Transformers, Ollama (LLaMA)
- **Cloud:** AWS EC2, S3
- **DevOps:** Docker, GitHub Actions

## Architecture

User → React Frontend → FastAPI Backend → PostgreSQL + pgvector → Ollama LLM

## Features

- Upload PDF documents
- Semantic search using vector embeddings
- RAG-powered Q&A with source citations
- JWT authentication
- REST API with full documentation

## Evaluation

**Retrieval recall@5: RESULT PENDING.** No evaluation has been run on a real document yet.
**Faithfulness: RESULT PENDING.** Not implemented.

`backend/scripts/eval_retrieval.py` measures whether search finds the pages that answer a question.
It reads a hand-written golden set (JSONL, one question per line) and runs the app's own search
against the database with the real embedding model.

1. Upload a PDF and wait until its status is `processed`. Note its document id.
2. Copy `backend/data/golden.example.jsonl` to `backend/data/golden.jsonl`. Replace the example rows
   with real questions about your document and the pages that answer them, and delete the
   `"example"` field: the script refuses to score rows marked as examples. Real golden sets are
   gitignored.
3. From `backend/` (with `backend/.env` set up as for the server), run:

   ```bash
   .venv/bin/python -m scripts.eval_retrieval data/golden.jsonl
   ```

Metrics are counted in pages, not chunks:
- **recall@5**: for each question, the share of its expected pages found among the pages of the top
  5 chunks, averaged over all questions.
- **hit@5**: the share of questions with at least one expected page in the top 5.
- **faithfulness**: whether each claim in a generated answer is supported by the text it cites. Not
  implemented, so the script prints RESULT PENDING.

`--k` changes the number of chunks retrieved per question (default 5).

Use a long document. A short one has few chunks, so the top 5 already covers most of it and
recall@5 is high whatever the search does: a 2-page PDF splits into about 7 chunks, so the top 5
is most of the document.

## Status

🚧 Currently in development

## Author

Tanishq Khandelwal — [GitHub](https://github.com/Maosama01)
