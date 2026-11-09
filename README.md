# DocuMind

[![tests](https://github.com/Maosama01/documind/actions/workflows/tests.yml/badge.svg)](https://github.com/Maosama01/documind/actions/workflows/tests.yml)

A FastAPI backend that answers questions about your own PDFs. You upload a PDF; the API splits it
into chunks, embeds them with a local sentence-transformer model, and stores them in PostgreSQL with
pgvector. When you ask a question, it retrieves the most similar chunks from that document and
returns an answer that cites its pages as `[p.N]`, written by Gemini, by Claude, or (with no API key)
by an extractive fallback that quotes the document's own sentences.

It is an API only: there is no frontend and no deployment. The sections below describe what the code
does today and what is still missing.

## What it does

- **Accounts:** sign up and log in with email and password (bcrypt hashes); every document route
  needs a JWT (HS256, 30 minutes).
- **Upload:** `POST /documents/upload` accepts a PDF up to 10 MB, saves it to `backend/uploads/`, and
  processes it in the background. If processing fails, the document's `error_message` says why
  (for example, the file is not a readable PDF, or it has no extractable text).
- **Processing:** pypdf extracts the text of each page; the text is split into chunks of whole words
  of at most 240 tokens, counted with the embedding model's own tokenizer, with a 40-token overlap
  and never crossing a page; `all-MiniLM-L6-v2` turns each chunk into a 384-number vector; chunks
  and vectors go into the `chunks` table.
- **Search:** `GET /documents/{id}/search` returns the chunks of one document closest to a question
  (cosine distance, exact).
- **Answers:** `POST /query/` retrieves the top chunks and asks the configured provider to answer
  only from them, citing pages, or to reply exactly `Not found in the document.`. The response says
  which provider answered and whether the answer is `grounded` (see Design decisions).
- **Evaluation:** a script measures retrieval recall on a hand-written question set (no result yet,
  see Evaluation).

## How a question is answered

```
upload PDF ──► saved to backend/uploads/ ──► background task:
                 pypdf text per page
                 → chunks of whole words, ≤ 240 model tokens, 40-token overlap, never across pages
                 → all-MiniLM-L6-v2 embeddings (384 numbers each)
                 → chunks table (pgvector column)

POST /query/ ──► embed the question with the same model
             ──► exact cosine search within that one document (top 5 by default)
             ──► LLM_PROVIDER = gemini | anthropic: answer only from the sources, cite [p.N]
                 LLM_PROVIDER = none: the 2 most similar sentences, labelled as extractive
             ──► grounded = at least one citation and every cited page was retrieved
```

## API

Interactive docs run at `http://localhost:8000/docs`. To call protected routes there, click
**Authorize** and log in with your email in the `username` field; Swagger then sends the token for
you. Other clients send it as `Authorization: Bearer <token>`.

| Method | Path | Auth | What it does |
|---|---|---|---|
| `GET` | `/` | no | Welcome message and version |
| `GET` | `/health` | no | Returns `{"status": "healthy"}` |
| `POST` | `/auth/signup` | no | Create an account: JSON `email`, `full_name`, `password` |
| `POST` | `/auth/login` | no | JSON `email`, `password` → `access_token` |
| `POST` | `/auth/token` | no | The same login as an OAuth2 form (`username` = email, `password`); used by Swagger's Authorize button |
| `GET` | `/auth/me` | yes | The logged-in user |
| `POST` | `/documents/upload` | yes | Upload a PDF (multipart field `file`); processing runs in the background |
| `GET` | `/documents/` | yes | Your documents |
| `GET` | `/documents/{document_id}` | yes | One of your documents |
| `GET` | `/documents/{document_id}/status` | yes | `pending`, `processing`, `processed` or `failed`, with `error_message` saying why it failed |
| `GET` | `/documents/{document_id}/search` | yes | `?q=...&top_k=5`: the closest chunks of a processed document |
| `DELETE` | `/documents/{document_id}` | yes | Delete a document, its chunks and its PDF file |
| `POST` | `/query/` | yes | JSON `question`, `document_id`, `max_results` (1-10, default 5) → answer |

A document that is not yours returns 404, as if it did not exist. `POST /query/` returns 400 while a
document is still processing and 502 if the LLM provider fails. Example requests for most endpoints
are in the Bruno collection in `bruno/DocuMind API/`.

## Running it locally

You need Python 3.13 and Docker.

```bash
git clone https://github.com/Maosama01/documind.git
cd documind
docker compose up -d db
```

Docker runs only PostgreSQL with pgvector, on `localhost:5432`. If another PostgreSQL already listens
on port 5432, `localhost` may reach that one instead; stop it first.

```bash
cd backend
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Edit `backend/.env` and set `SECRET_KEY` (generate one with
`python3 -c "import secrets; print(secrets.token_hex(32))"`). Then start the API from `backend/`,
because `.env` and `uploads/` are found relative to the current directory:

```bash
.venv/bin/uvicorn app.main:app
```

On startup the app creates the `vector` extension, the tables, the `document_id` index and the
`error_message` column if they are missing, and marks any document an earlier run left unfinished
as `failed`. The first upload downloads the embedding model (about 90 MB) into the Hugging Face
cache.

A full round trip with curl:

```bash
curl -X POST localhost:8000/auth/signup -H 'Content-Type: application/json' \
  -d '{"email": "me@example.com", "full_name": "Me", "password": "a long password"}'
curl -X POST localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d '{"email": "me@example.com", "password": "a long password"}'
# copy access_token from the reply
TOKEN=...
curl -X POST localhost:8000/documents/upload -H "Authorization: Bearer $TOKEN" -F file=@my.pdf
curl localhost:8000/documents/1/status -H "Authorization: Bearer $TOKEN"
curl -X POST localhost:8000/query/ -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"question": "What are the payment terms?", "document_id": 1}'
```

## Configuration

Settings come from environment variables or `backend/.env` (see `backend/.env.example`). The app
refuses to start when a required value is missing or unsafe.

| Setting | Default | Meaning |
|---|---|---|
| `SECRET_KEY` | none, required | Signs the JWTs. At least 32 characters |
| `DATABASE_URL` | `postgresql://documind_user:documind_pass@localhost:5432/documind` | Matches `docker-compose.yml` |
| `DEBUG` | `false` | Passed to FastAPI; `true` returns tracebacks in error responses |
| `ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Token lifetime |
| `CHUNK_SIZE_TOKENS` | `240` | Most tokens per chunk, counted with the embedding model's tokenizer. At most 254 |
| `CHUNK_OVERLAP_TOKENS` | `40` | Most tokens of text shared by neighbouring chunks. Smaller than the chunk size |
| `LLM_PROVIDER` | `none` | `none`, `gemini` or `anthropic` |
| `GEMINI_API_KEY` | empty | Required when `LLM_PROVIDER=gemini` |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Gemini model for answers |
| `ANTHROPIC_API_KEY` | empty | Required when `LLM_PROVIDER=anthropic` |
| `ANTHROPIC_MODEL` | `claude-opus-5-5` | Claude model for answers (`claude-haiku-5-5` costs less) |
| `LLM_TIMEOUT_SECONDS` | `30` | Timeout for one provider request |
| `APP_NAME`, `APP_VERSION` | `DocuMind`, `1.0.0` | Defined but not used by the app |

## Design decisions

Each decision has a longer explanation next to the code it describes.

- **Chunks sized in the model's own tokens** (`config.py`, `chunking_service.py`).
  `all-MiniLM-L6-v2` embeds at most 256 tokens, two of which it uses itself, and silently drops the
  rest. On the one PDF measured, the original 500-word chunks ran to 565-660 tokens, so most of each
  chunk was never searchable, and even 180-word chunks reached 255. Chunks are now built from whole
  words, adding words while the total stays within 240 tokens. The count is exact before embedding:
  the tokenizer splits on whitespace before cutting words into pieces, so a run of words costs the
  sum of its words (checked on that PDF: no mismatches). The one exception is a single word longer
  than the whole budget; it gets a chunk of its own and the over-limit warning reports it.
- **Exact search, no approximate vector index** (`document_service.semantic_search`). Every query is
  limited to one document, which a normal index on `chunks.document_id` finds directly. In a test
  with pgvector 0.8.7 and random vectors (200 documents, 100 chunks each), adding an HNSW index made
  this query return 0 results instead of 5: it took the 40 nearest chunks across all documents and
  only then removed the other documents' chunks. A test fails if an HNSW or IVFFlat index is added.
- **`grounded` checks page numbers only** (`llm_service.generate_answer`). It is true when the answer
  cites at least one page and every cited page was among the retrieved chunks, or when the answer is
  `Not found in the document.`. It does not check that the cited text supports the answer.
- **The no-LLM fallback labels itself** (`llm_service._extractive_answer`). With `LLM_PROVIDER=none`
  the answer starts with `[Extractive answer: no LLM is configured ...]` and quotes the two most
  similar sentences with their pages. Below a similarity of 0.35 it replies `Not found in the
  document.`; that cutoff was chosen by hand and has not been tuned.
- **Provider failures return 502** (`routes/query.py`). A timeout, HTTP error or empty reply from
  Gemini or Anthropic is reported as an error, not silently replaced by the fallback.

## Tests

The tests live in `backend/tests/` and run with pytest from `backend/`. Tests marked `db` need a
PostgreSQL with pgvector; they use a separate database whose name must end in `_test`, which they
create and empty.

```bash
docker compose up -d db          # from the repository root, if it is not already running
cd backend
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
```

`TEST_DATABASE_URL` points the tests at another server (default
`postgresql://documind_user:documind_pass@localhost:5432/documind_test`). If it cannot be reached,
the `db` tests are skipped and pytest prints why; with `REQUIRE_TEST_DB=1` they fail instead. No test
calls a real LLM or downloads the embedding model: provider calls go through a fake HTTP layer and
embeddings are hand-made vectors.

GitHub Actions (`.github/workflows/tests.yml`) runs the whole suite on every push and pull request,
on Python 3.13 with a `pgvector/pgvector:pg16` service and `REQUIRE_TEST_DB=1`.

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

## Not built yet

- **OCR.** Text comes from pypdf only. Scanned pages have no text and are skipped; a PDF with no text
  at all ends as `failed`.
- **Deployment.** No Dockerfile for the API and no hosting: Docker Compose runs only PostgreSQL, and
  uploads are stored on the local disk.
- **Migrations.** Tables are created with SQLAlchemy `create_all`, which never changes an existing
  table. The two later additions (an index and the `error_message` column) are applied at startup
  with SQL that is safe to run every time; there are no versioned migrations.
- **Real LLM calls are unverified.** The Gemini and Anthropic requests follow their documentation
  and are tested against a fake HTTP layer, but have not been sent to the real APIs.
- **Faithfulness evaluation**, and a recall@5 result on a real document.
- **Search across documents.** Every search and question is limited to one document.

## Known issues

- Background processing runs inside the API process (FastAPI `BackgroundTasks`), so a restart
  interrupts it. On the next start those documents are marked `failed` with a message asking to
  upload again. That startup step assumes one server process: with several workers
  (`uvicorn --workers N`), a worker that starts while another is processing would mark that upload
  as failed.
- The upload check is a case-sensitive `.pdf` filename suffix, not a check of the file's contents.
- Tokens cannot be revoked or refreshed; they expire after 30 minutes.

## Tech stack

Python 3.13, FastAPI, SQLAlchemy 2, PostgreSQL 16 with pgvector, pypdf, sentence-transformers
(`all-MiniLM-L6-v2`), httpx, python-jose, passlib with bcrypt, pytest, GitHub Actions.

## Author

Tanishq Khandelwal — [GitHub](https://github.com/Maosama01)
