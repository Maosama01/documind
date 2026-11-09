"""
End-to-end smoke test against a running DocuMind API.

    python3 backend/scripts/smoke_test.py [base_url]     (default http://localhost:8000)

Signs up a throwaway user, uploads a generated one-page PDF, waits until it
is processed, asks a question and checks that the answer cites page 1.
Uses only the standard library, so it runs wherever Python 3 does (CI uses it
against the Docker image). Exits 0 on success, 1 on any failure.

It expects LLM_PROVIDER=none (the extractive fallback); with a real provider
the answer depends on that model.
"""
import json
import secrets
import sys
import time
import urllib.error
import urllib.request

QUESTION = "When are invoices due?"
PDF_TEXT = (
    "Invoices are due within thirty days of receipt. Late payments incur a fee of two "
    "percent per month. The contract renews every year unless either party cancels it in writing."
)


def make_pdf(text: str) -> bytes:
    """A minimal one-page PDF showing `text` in Helvetica, with correct byte offsets.

    `text` must not contain parentheses or backslashes (PDF string syntax).
    """
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_offset = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    pdf += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    pdf += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode()
    return bytes(pdf)


def call(method: str, url: str, body: bytes = None, headers: dict = None):
    """Send a request; return (status, decoded JSON or None)."""
    request = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, raw = error.code, error.read()
    return status, (json.loads(raw) if raw else None)


def post_json(url: str, payload: dict, token: str = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return call("POST", url, json.dumps(payload).encode(), headers)


def upload_pdf(url: str, token: str, filename: str, content: bytes):
    boundary = secrets.token_hex(16)
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: application/pdf\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}", "Authorization": f"Bearer {token}"}
    return call("POST", url, body, headers)


class SmokeTestFailure(Exception):
    pass


def check(condition: bool, message: str):
    if not condition:
        raise SmokeTestFailure(message)


def run(base_url: str, timeout_seconds: int = 180) -> dict:
    email, password = f"smoke-{secrets.token_hex(4)}@example.com", secrets.token_hex(16)

    status, _ = call("GET", f"{base_url}/health")
    check(status == 200, f"/health returned {status}")

    status, body = post_json(f"{base_url}/auth/signup", {"email": email, "full_name": "Smoke Test", "password": password})
    check(status == 201, f"signup returned {status}: {body}")
    status, body = post_json(f"{base_url}/auth/login", {"email": email, "password": password})
    check(status == 200, f"login returned {status}: {body}")
    token = body["access_token"]

    status, document = upload_pdf(f"{base_url}/documents/upload", token, "smoke.pdf", make_pdf(PDF_TEXT))
    check(status == 201, f"upload returned {status}: {document}")

    deadline = time.monotonic() + timeout_seconds
    while True:
        status, state = call("GET", f"{base_url}/documents/{document['id']}/status",
                             headers={"Authorization": f"Bearer {token}"})
        check(status == 200, f"status returned {status}: {state}")
        if state["status"] in ("processed", "failed"):
            break
        check(time.monotonic() < deadline, f"still {state['status']} after {timeout_seconds}s")
        time.sleep(1)
    check(state["status"] == "processed", f"processing failed: {state.get('error_message')}")

    status, answer = post_json(f"{base_url}/query/", {"question": QUESTION, "document_id": document["id"]}, token)
    check(status == 200, f"query returned {status}: {answer}")
    check(answer["cited_pages"] == [1] and answer["grounded"] is True,
          f"expected a grounded answer citing page 1, got {answer}")
    return {"document_id": document["id"], "provider": answer["provider"], "answer": answer["answer"]}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    base_url = (argv[0] if argv else "http://localhost:8000").rstrip("/")
    try:
        result = run(base_url)
    except (SmokeTestFailure, urllib.error.URLError, KeyError, ValueError) as error:
        print(f"SMOKE TEST FAILED: {error}", file=sys.stderr)
        return 1
    print(f"smoke test passed against {base_url}: document {result['document_id']} processed; "
          f"{result['provider']} answered: {result['answer'][:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
