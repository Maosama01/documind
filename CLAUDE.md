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
- The user's `~/.zshrc` used to set `HF_HOME=/Volumes/DevDrive/Models/huggingface`; with that drive
  unmounted the embedding model could not load and every upload ended as `failed`. At the user's
  request (2026-11-09) it now uses the DevDrive only when `/Volumes/DevDrive` exists, otherwise
  `~/.cache/huggingface` (where MiniLM is cached). Backup: `~/.zshrc.backup-2026-11-09`. Shells
  started before the change still have the old value. Change the user's shell config only when asked.

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

- pypdf extraction per page; word-based chunking 500/50 in `chunking_service.py` (Phase 2: now
  180/30 from settings);
  all-MiniLM-L6-v2 embeddings (384 dims) in a pgvector `Vector(384)` column; search orders by
  `Chunk.embedding.op("<=>")` with no index (Phase 4: exact search via a btree index on
  `chunks.document_id`; deliberately no HNSW, see below); python-jose HS256 JWT, 30 min; upload uses FastAPI
  `BackgroundTasks`; `docker-compose.yml` runs only `pgvector/pgvector:pg16`.
- Bugs:
  - `POST /query/` returns a hardcoded placeholder with fake sources and no auth. (Fixed in Phase 3.)
  - `/auth/login` reuses `UserCreate`, so it demands `full_name`.
  - `config.py` has a hardcoded default `SECRET_KEY` and `DEBUG=True`.
  - Chunk→Document has no cascade, so deleting a processed document raises `IntegrityError`.
  - No `CREATE EXTENSION vector` anywhere.
  - 500-word chunks exceed MiniLM's 256-token window, so chunk tails are silently truncated.
    (Phase 2: measured on the one local PDF, 2 of 3 500-word chunks were over, at 565 and 660
    tokens; at 180 words 0 of 7 were over, the largest at 255. Still word-based, so dense text can
    exceed 256; `process_document` logs how many chunks do.)
  - A user PDF is committed under `backend/uploads/`.
  - Zero tests, no CI. (Tests since Phase 1; CI in `.github/workflows/tests.yml` since Phase 4.)
  - README claims AWS, React, Ollama and GitHub Actions that do not exist.

## Additional findings (2026-11-09)

Resolved in Phase 1:
- The folder was not a git repo. It is now attached to `origin` = public `Maosama01/documind`.
  `e536266` was rewritten as `861ceac` without the user PDF, and the user force-pushed `main`
  (`e536266...de0120f`). Checked on 2026-11-09: GitHub `main` has no `uploads/` or PDF, the repo
  has 0 forks. `e536266` (with the PDF) is still served by its SHA; the user confirmed the PDF is
  not sensitive, so no GitHub Support purge is needed. The rule still stands: user files never get
  committed.
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
- A failed upload records no reason: the status endpoint only says "Processing failed. Please try
  again."; the cause is only in the server log.
- Gemini and Anthropic have never been called for real (no API keys in this session). Their
  request shapes follow the docs read on 2026-11-09 and are tested against a fake HTTP layer only.
- Extractive fallback limits: summary questions ("What is this document about?") match no single
  sentence and get "Not found"; sentences split only on . ! ? so text using "…" yields very long
  "sentences"; `FALLBACK_MIN_SIMILARITY = 0.35` is untuned (on the one local PDF, 2 answerable
  questions scored 0.62/0.67, a summary question 0.23, an unrelated one 0.11; 4 questions are a
  sanity check, not an evaluation).
- HNSW decision (Phase 4, measured 2026-11-09 on pgvector 0.8.7, 200 documents x 100 chunks of
  random vectors, query `WHERE document_id = 7 ORDER BY embedding <=> q LIMIT 5`): no index → 5 exact
  rows; HNSW only → 0 rows (40 nearest across all documents, then filtered); HNSW +
  `hnsw.iterative_scan = strict_order` → 5 rows, not the same 5 as exact; HNSW + btree on
  `document_id` → planner used the btree, 5 exact rows. The user chose btree only, no HNSW.
  `test_chunks_has_no_approximate_vector_index` guards this; the `test_search.py` tests alone do
  NOT catch an added HNSW index at test data size (checked by adding one: they still passed).
  Revisit HNSW only if the API ever searches across all documents.

## Phases (one at a time, stop after each for review)

- [x] **Phase 1, hygiene** (committed 2026-11-09; 25 tests pass against pgvector):
  remove the committed PDF from git, ignore `uploads/`, make `SECRET_KEY`
  required with no default, `DEBUG` default false, add `backend/.env.example`, fix login to use
  `UserLogin`, add cascade delete (`ondelete="CASCADE"` + `delete-orphan`), run
  `CREATE EXTENSION IF NOT EXISTS vector` before `create_all`. Add `pytest.ini` with
  `pythonpath = .` and a conftest that sets a test `SECRET_KEY`.
- [x] **Phase 2, chunking** (committed 2026-11-09; 55 tests pass against pgvector).
  Decisions: overlap must be >= `MIN_CHUNK_WORDS` (20) and < size or the app refuses to start;
  pages under 20 words are skipped; `split_text_simple` (unused) deleted. Spec: chunk size and overlap become settings (default 180/30 words) with a
  comment explaining the 256-token limit. Tests: overlap shared between neighbours, nothing lost at
  the end, chunks never cross pages, tiny tails dropped.
- [x] **Phase 3, generation** (done 2026-11-09, 96 tests pass against pgvector, plus one real
  end-to-end run with `LLM_PROVIDER=none`; committed 2026-11-09). Decisions: grounded is also false when
  nothing is cited, true for the not-found reply; httpx for both providers, no SDK; defaults
  `LLM_PROVIDER=none`, `gemini-3.8-flash`, `claude-opus-5-5`; provider failure → 502, no silent
  fallback; no sampling parameters sent. Spec: new `services/llm_service.py` with `build_prompt` (sources labelled
  `[p.N]`, answer only from sources, cite pages, reply exactly "Not found in the document."
  otherwise), a cited-pages parser, and `generate_answer` returning answer, provider, cited_pages
  and a `grounded` flag that is false when a cited page was not retrieved. Providers by env:
  `LLM_PROVIDER=gemini` (`GEMINI_API_KEY`, REST via httpx), `anthropic` (`ANTHROPIC_API_KEY`), or
  `none` → an extractive fallback that returns the best matching sentences with citations and
  labels itself. Rewrite `routes/query.py`: JWT required, verify document ownership and processed
  status, `semantic_search`, then `generate_answer`; return question, answer, cited_pages,
  grounded, provider, sources. Tests mock the provider call; cover grounded true/false, not found,
  fallback.
- [x] **Phase 4, index and CI** (committed 2026-11-09; 104 tests pass locally and in a Linux
  container running the workflow's steps). Decisions: btree index on
  `chunks.document_id` instead of HNSW (measured, see above); CI sets `REQUIRE_TEST_DB=1` so an
  unreachable database fails the run; CI installs CPU-only torch from PyTorch's index. First GitHub
  run (id 42599895463, commit 6586d8d, 2026-11-09) passed: 104 tests, torch 2.12.0+cpu, no NVIDIA
  packages. Git pushes now authenticate through `gh` (`gh auth setup-git`), whose token has the
  `workflow` scope needed to change files under `.github/workflows/`. Spec was: `CREATE INDEX IF NOT EXISTS … USING hnsw (embedding
  vector_cosine_ops)` at startup; `.github/workflows/tests.yml` running pytest on push and
  pull_request.
- [x] **Phase 5, evaluation** (committed 2026-11-09; 129 tests pass against pgvector).
  Decisions: files live in `backend/scripts/` and `backend/data/` (run
  `cd backend && .venv/bin/python -m scripts.eval_retrieval data/golden.jsonl`); recall@k = mean per
  question of expected pages found in the pages of the top-k chunks / expected pages, plus hit@k;
  rows with `"example": true` are refused; real golden sets are gitignored; faithfulness prints
  RESULT PENDING, no LLM calls. The README result stays RESULT PENDING until the user runs it on a
  real, long document. A CLI smoke run with the real model on the 2-page local PDF and 2 questions
  written by Claude worked (1.00/1.00, meaningless at 7 chunks; not a result). Spec was:
  `scripts/eval_retrieval.py` takes a JSONL golden set (question,
  document_id, expected_pages) and reports recall@5 and a faithfulness placeholder;
  `data/golden.example.jsonl` holds the format and 3 rows marked as examples; the README section
  says RESULT PENDING until the user runs it on a real document.
- [ ] **Phase 6, README:** rewrite to describe exactly what the code does, how to run it, and what
  is still missing (OCR, token-based chunking, deployment).
