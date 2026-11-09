# DocuMind: rules for every session

DocuMind is a FastAPI + PostgreSQL/pgvector RAG API. The Python package lives in `backend/app`
(imports are `app.…`), so run the server and the tests from `backend/`.

## Running the tests

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
docker compose up -d db          # from the repo root: the pgvector Postgres
.venv/bin/pytest
```

- `tests/conftest.py` sets a test `SECRET_KEY` and points `DATABASE_URL` at `TEST_DATABASE_URL`
  (default `postgresql://documind_user:documind_pass@localhost:5432/documind_test`). It creates that
  database if missing and refuses to run unless the name ends in `_test`, because it drops tables.
- Tests marked `db` are skipped, with the reason printed, when that Postgres is unreachable.
  A run with skips has not verified the database behaviour; say so when reporting.
- On the user's Mac a Homebrew `postgresql@16` service owns `localhost:5432` (both `::1` and
  `127.0.0.1`), so `localhost` never reaches the Docker container and the `db` tests skip. Phase 1
  was verified with a throwaway container:
  `docker run -d --rm --name documind_pytest_pg -e POSTGRES_USER=documind_user -e POSTGRES_PASSWORD=documind_pass -e POSTGRES_DB=documind -p 127.0.0.1:55432:5432 pgvector/pgvector:pg16`
  then `TEST_DATABASE_URL=postgresql://documind_user:documind_pass@127.0.0.1:55432/documind_test .venv/bin/pytest`.

## Integrity rules (override everything)

1. Never claim a capability the code does not have. README, docstrings, comments and API
   descriptions describe what runs today.
2. Never commit secrets or user files. `.env` and `uploads/` stay ignored. The app must refuse to
   start without `SECRET_KEY`.
3. Every change ships with a test. `pytest` must pass before every commit. Commit at the end of each
   phase with a message that says what works, what is mocked and what is missing.
4. Never fabricate a metric. If an evaluation has not been run, write RESULT PENDING.
5. Explain each phase to the user in plain language before committing: what changed, why, and the
   one question an interviewer would ask about it. The user will defend this code line by line.

Working style: one phase at a time, stop after each phase for the user's review. Before writing
code for a phase, list the files to be touched and ask all questions in one batch.

## Known state (verified by audit, do not re-derive)

- pypdf extraction per page; word-based chunking 500/50 in `chunking_service.py`;
  all-MiniLM-L6-v2 embeddings (384 dims) in a pgvector `Vector(384)` column; search orders by
  `Chunk.embedding.op("<=>")` with no index; python-jose HS256 JWT, 30 min; upload uses FastAPI
  `BackgroundTasks`; `docker-compose.yml` runs only `pgvector/pgvector:pg16`.
- Bugs:
  - `POST /query/` returns a hardcoded placeholder with fake sources and no auth.
  - `/auth/login` reuses `UserCreate`, so it demands `full_name`.
  - `config.py` has a hardcoded default `SECRET_KEY` and `DEBUG=True`.
  - Chunk→Document has no cascade, so deleting a processed document raises `IntegrityError`.
  - No `CREATE EXTENSION vector` anywhere.
  - 500-word chunks exceed MiniLM's 256-token window, so chunk tails are silently truncated.
  - A user PDF is committed under `backend/uploads/`.
  - Zero tests, no CI.
  - README claims AWS, React, Ollama and GitHub Actions that do not exist.

## Additional findings (2026-11-09)

Resolved in Phase 1:
- The folder was not a git repo. It is now attached to `origin` = public `Maosama01/documind`.
  Local `main` rewrote GitHub's `e536266` as `861ceac` without the user PDF; the user force-pushes.
  Until then (and until GitHub garbage-collects or support purges it) `e536266` still serves the PDF.
- Importing `app.main` ran `create_all` and loaded the embedding model. Now `init_db()` runs in the
  FastAPI lifespan hook and `embedding_service.get_model()` loads the model on first use.
- Root `requirements.txt` (bcrypt 5.0.0 + passlib 1.7.4) was deleted; `backend/requirements.txt`
  is the only one, plus `backend/requirements-dev.txt` for pytest.

Still open (not in any phase yet):
- `upload_document` hands the request-scoped DB session (closed by `get_db`) to the background task.
- `delete_document` does not delete the PDF from disk (its docstring now says so).
- Swagger's Authorize button cannot log in: `OAuth2PasswordBearer(tokenUrl="/auth/login")` makes it
  send form fields `username`/`password`, but `/auth/login` takes JSON `{email, password}`.
- `backend/requirements.txt` includes `boto3`, which no code uses (README claims S3; Phase 6).
- `datetime.utcnow()` in `auth_service.py` and class-based pydantic `Config` in schemas are
  deprecated (warnings in pytest output).
- No migrations: `create_all` never alters an existing table, so schema changes reach an old
  database only after the table is recreated.
- Phase 4 note: an HNSW index combined with `WHERE document_id = …` filters after the approximate
  search, so a document can get fewer than `top_k` results. The `pgvector/pgvector:pg16` image
  ships pgvector 0.8.7, which has `hnsw.iterative_scan`; test it before claiming results are kept.

## Phases (one at a time, stop after each for review)

- [x] **Phase 1, hygiene** (committed 2026-11-09; 25 tests pass against pgvector):
  remove the committed PDF from git, ignore `uploads/`, make `SECRET_KEY`
  required with no default, `DEBUG` default false, add `backend/.env.example`, fix login to use
  `UserLogin`, add cascade delete (`ondelete="CASCADE"` + `delete-orphan`), run
  `CREATE EXTENSION IF NOT EXISTS vector` before `create_all`. Add `pytest.ini` with
  `pythonpath = .` and a conftest that sets a test `SECRET_KEY`.
- [ ] **Phase 2, chunking:** chunk size and overlap become settings (default 180/30 words) with a
  comment explaining the 256-token limit. Tests: overlap shared between neighbours, nothing lost at
  the end, chunks never cross pages, tiny tails dropped.
- [ ] **Phase 3, generation:** new `services/llm_service.py` with `build_prompt` (sources labelled
  `[p.N]`, answer only from sources, cite pages, reply exactly "Not found in the document."
  otherwise), a cited-pages parser, and `generate_answer` returning answer, provider, cited_pages
  and a `grounded` flag that is false when a cited page was not retrieved. Providers by env:
  `LLM_PROVIDER=gemini` (`GEMINI_API_KEY`, REST via httpx), `anthropic` (`ANTHROPIC_API_KEY`), or
  `none` → an extractive fallback that returns the best matching sentences with citations and
  labels itself. Rewrite `routes/query.py`: JWT required, verify document ownership and processed
  status, `semantic_search`, then `generate_answer`; return question, answer, cited_pages,
  grounded, provider, sources. Tests mock the provider call; cover grounded true/false, not found,
  fallback.
- [ ] **Phase 4, index and CI:** `CREATE INDEX IF NOT EXISTS … USING hnsw (embedding
  vector_cosine_ops)` at startup; `.github/workflows/tests.yml` running pytest on push and
  pull_request.
- [ ] **Phase 5, evaluation:** `scripts/eval_retrieval.py` takes a JSONL golden set (question,
  document_id, expected_pages) and reports recall@5 and a faithfulness placeholder;
  `data/golden.example.jsonl` holds the format and 3 rows marked as examples; the README section
  says RESULT PENDING until the user runs it on a real document.
- [ ] **Phase 6, README:** rewrite to describe exactly what the code does, how to run it, and what
  is still missing (OCR, token-based chunking, deployment).
