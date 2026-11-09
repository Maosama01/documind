# DocuMind: rules for every session

DocuMind is a FastAPI + PostgreSQL/pgvector RAG API. The Python package lives in `backend/app`
(imports are `app.…`), so run the server and the tests from `backend/`.

## Running the tests

Frontend (`frontend/`, Node 22.13+): `npm ci && npm run typecheck && npm test` (Vitest + MSW, no
server needed). End to end: `docker compose up --build` (needs `backend/.env`), then
`npx playwright install chromium && npm run e2e`. After any change to a route or schema, run
`cd backend && .venv/bin/python -m scripts.export_openapi` and `cd frontend && npm run api:types`;
CI fails if `frontend/openapi.json` or `frontend/src/api/schema.d.ts` is stale.

Backend:

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
  180/30 from settings; Phase 8: token-based, 240/40 model tokens of whole words);
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
    tokens; at 180 words 0 of 7 were over, the largest at 255. Phase 8 fixed it: chunks are packed
    by exact per-word token counts, so only a single word longer than 254 tokens can exceed it.)
  - A user PDF is committed under `backend/uploads/`.
  - Zero tests, no CI. (Tests since Phase 1; CI in `.github/workflows/tests.yml` since Phase 4.)
  - README claims AWS, React, Ollama and GitHub Actions that do not exist. (Fixed in Phase 6;
    `tests/test_docs.py` keeps the README's endpoint and settings tables in sync with the app and
    fails if AWS, S3, EC2, React, Ollama or LLaMA reappear.)

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

Still open (not in any phase; the README's "Not built yet" and "Known issues" sections list them
for readers, so update both places when one is fixed):
- No migrations: `create_all` never alters an existing table. Additions to existing tables go in
  `init_db` as SQL that is safe to run on every start (`CREATE INDEX IF NOT EXISTS`, `ALTER TABLE ...
  ADD COLUMN IF NOT EXISTS`). Switch to Alembic (installed, never set up) before changes that need
  data migration or column changes.
- Startup marks every `pending`/`processing` document as failed (`fail_interrupted_documents`). This
  assumes a single server process; with several uvicorn workers it would fail another worker's
  in-progress upload.
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
- [x] **Phase 7, processing reliability** (committed 2026-11-09; 160 tests pass against pgvector,
  50 of them marked db, plus a real-server check). `process_document(document_id, file_path)` opens its own
  session (FastAPI 0.136.3 closed the request session only after the task, holding a pooled
  connection for the whole run); failures set `documents.error_message` to a safe category
  (unreadable PDF, no text, model unavailable, internal) and log the full error; startup fails
  interrupted documents; DELETE removes the PDF (path checked to stay in `uploads/`);
  `datetime.utcnow` and pydantic class `Config` replaced, and `pytest.ini` turns DeprecationWarnings
  from `app.` modules into errors.
- [x] **Phase 8, token-based chunking** (committed 2026-11-09; 178 tests pass against pgvector, 51
  marked db). `CHUNK_SIZE_TOKENS=240` / `CHUNK_OVERLAP_TOKENS=40` replace the word
  settings (an old `.env` with the word names stops startup; an exported env var is ignored); the
  app refuses unless `0 <= overlap < size <= 254`. Chunks pack whole words using
  `embedding_service.count_word_tokens` (the model's tokenizer, per word, no special tokens); a run
  of words costs the sum of its words because BertPreTokenizer splits on whitespace first (0
  mismatches on the local PDF). A word longer than the budget gets its own chunk. Real-tokenizer
  check on the local PDF: 240/40 gave 7 chunks, max 242 full tokens; 254/0 gave max exactly 256.
  The overlap is now "as many trailing words as fit in 40 tokens and leave room for the next word",
  not an exact word count. Pages under `MIN_PAGE_WORDS` (20) are still skipped, checked before the
  model loads so a scanned PDF reports "no text" even when the model is missing.
- [x] **Phase 9, Docker** (committed 2026-11-09; 185 tests pass against pgvector, 51 marked db, plus
  a real stack run). `backend/Dockerfile` (python:3.13-slim, CPU torch, MiniLM
  downloaded at build, then `HF_HUB_OFFLINE=1`, non-root uid 1000) and `.dockerignore` (keeps
  `.env`, uploads, venv, tests out). Compose `api` service waits for a healthy db, reads secrets
  from `backend/.env` (required: starting api without it errors; `up -d db` alone still works,
  checked on Compose 5.3.0), overrides `DATABASE_URL` to `db:5432`, stores uploads in a named
  volume, has a /health healthcheck. CI job "docker" runs `docker compose up --build --wait` and
  `backend/scripts/smoke_test.py` (stdlib only; `make_pdf` there is shared with the route tests).
  Measured on Apple silicon (arm64): build about 5 min; image 2.05 GB unpacked (pip layer 1.33 GB,
  model 92 MB, app 152 kB), about 474 MB compressed; stack healthy in 14 s; smoke test passed.
  First GitHub run (id 42651298749, commit 1a90e7f): pytest job 185 passed; docker job built the
  image on x86_64, both containers healthy, smoke test passed; whole docker job 2 min 14 s. To
  verify without touching the user's dev volume, use another Compose project
  (`-p documind-verify`) with an override that renames the containers.
- [x] **Phase 10, web app** (committed 2026-11-10). React 19 + TypeScript + Vite in
  `frontend/`, React Router 7, TanStack Query, openapi-fetch with types generated from the API's
  OpenAPI schema. Served by nginx (`web` service, http://localhost:3000) which forwards `/api` to the
  API and sends a strict CSP (`frontend/security-headers.conf`). Token in sessionStorage (user's
  choice; CSP is the mitigation; httpOnly cookies would need backend changes). Questions are kept per
  tab in sessionStorage; the API stores none. New backend route `GET /documents/{id}/file` (owner
  only, inline PDF, path checked via `pdf_service.upload_path`). Design: the design skill's
  "achromatic ledger" app style (seed 721301883, sheet in `.taste-skill/`, gitignored); the face is
  one hue, `--cite` #1d5fbf, used only for "where the answer came from"; the signature element is the
  page strip (cited / read-not-cited / cited-never-read). Checked with the skill's lint and inspector
  at 1440/768/390: 0 FAIL on every screen; WARNs defended: ragged rows and empty space come from a
  two-document account and a viewport-tall PDF viewer; `--allow placeholder-data` because the
  inspected account's email was example.com (the backend rejects reserved test domains like .test).
  Version notes: TypeScript 5.9 (openapi-typescript does not support TS 7), React Router 7 and jsdom
  29 (the newer majors need Node 22.22+; the user's Node is 22.17.1). openapi-fetch gets
  `fetch: (r) => globalThis.fetch(r)` so mocks installed later still see calls. Dev-only
  `?dev-token=` hook (`auth/session.ts`) lets the inspector open signed-in screens; it is absent from
  the production bundle (checked). Verified: 36 frontend tests, 188 backend tests (55 db), the smoke test
  through nginx, and the Playwright e2e against the full Docker stack all pass locally.
- [x] **Follow-up, Swagger login** (2026-11-09): `POST /auth/token` takes the OAuth2 password form
  (`username` = email) and the bearer scheme's `tokenUrl` points to it, so Swagger's Authorize
  button works; JSON `/auth/login` is unchanged; `/auth/me` uses `get_current_user` instead of its
  own second scheme.
- [x] **Phase 6, README** (committed 2026-11-09; 137 tests pass against pgvector).
  Also fixed 7 outdated comments (S3, "Week N", frontend, compose health check) and removed the
  unused boto3, botocore, s3transfer, jmespath, python-dateutil and urllib3 from requirements.
  Spec was: rewrite to describe exactly what the code does, how to run it, and what
  is still missing (OCR, token-based chunking, deployment).
