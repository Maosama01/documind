"""
llm_service without any real LLM.

Gemini and Anthropic calls go through httpx.MockTransport: the test sees the
exact request (URL, headers, JSON body) and decides the reply. The fallback's
embeddings are replaced by small hand-made vectors.
"""
import json
import re
from types import SimpleNamespace

import httpx
import pytest

from app.config import settings
from app.services import llm_service
from app.services.llm_service import (
    NOT_FOUND,
    SYSTEM_PROMPT,
    LLMProviderError,
    build_prompt,
    generate_answer,
    parse_cited_pages,
)

GEMINI_KEY = "test-gemini-key"
ANTHROPIC_KEY = "test-anthropic-key"


def chunk(page_number, content, chunk_index=0):
    return SimpleNamespace(page_number=page_number, content=content, chunk_index=chunk_index)


CHUNKS = [
    chunk(3, "Invoices are due within 30 days of receipt. Late payments incur a fee."),
    chunk(5, "The contract renews every year unless cancelled in writing."),
]


class FakeProvider:
    """Answers every request with `reply` and remembers the requests it saw."""

    def __init__(self, reply=None, status_code=200, error=None, raw_body=None):
        self.reply, self.status_code, self.error, self.raw_body = reply, status_code, error, raw_body
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.error:
            raise self.error
        if self.raw_body is not None:
            return httpx.Response(self.status_code, content=self.raw_body)
        return httpx.Response(self.status_code, json=self.reply)

    @property
    def body(self):
        return json.loads(self.requests[-1].content)


def use_provider(monkeypatch, name, fake):
    monkeypatch.setattr(settings, "LLM_PROVIDER", name)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", GEMINI_KEY)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", ANTHROPIC_KEY)
    monkeypatch.setattr(
        llm_service, "_new_client", lambda: httpx.Client(transport=httpx.MockTransport(fake))
    )


def gemini_reply(text, thought=None):
    parts = ([{"text": thought, "thought": True}] if thought else []) + [{"text": text}]
    return {"candidates": [{"content": {"role": "model", "parts": parts}, "finishReason": "STOP"}]}


def anthropic_reply(text):
    return {"content": [{"type": "text", "text": text}], "stop_reason": "end_turn"}


# ---- prompt and citations -------------------------------------------------

def test_prompt_labels_each_source_with_its_page_and_ends_with_the_question():
    system_prompt, user_prompt = build_prompt("When are invoices due?", CHUNKS)

    assert system_prompt == SYSTEM_PROMPT
    assert f"reply with exactly: {NOT_FOUND}" in system_prompt
    assert "[p.3]\nInvoices are due within 30 days" in user_prompt
    assert "[p.5]\nThe contract renews" in user_prompt
    assert user_prompt.endswith("Question: When are invoices due?")


@pytest.mark.parametrize(
    "answer,pages",
    [
        ("Due in 30 days [p.3].", [3]),
        ("Due in 30 days [p. 3]. Renews yearly [p.5].", [3, 5]),
        ("Both [p.5, p.3] and again [p.3].", [3, 5]),
        ("No citation here.", []),
        ("Not counted: page 3, (p.3), [p.3-5], [Extractive answer: ...]", []),
    ],
)
def test_parse_cited_pages(answer, pages):
    assert parse_cited_pages(answer) == pages


# ---- grounded flag and not found (Gemini) ---------------------------------

def test_answer_citing_only_retrieved_pages_is_grounded(monkeypatch):
    use_provider(monkeypatch, "gemini", FakeProvider(gemini_reply("Invoices are due within 30 days [p.3].")))

    result = generate_answer("When are invoices due?", CHUNKS)

    assert result.answer == "Invoices are due within 30 days [p.3]."
    assert result.cited_pages == [3]
    assert result.grounded is True
    assert result.provider == f"gemini:{settings.GEMINI_MODEL}"


def test_answer_citing_a_page_that_was_not_retrieved_is_not_grounded(monkeypatch):
    use_provider(monkeypatch, "gemini", FakeProvider(gemini_reply("Due in 30 days [p.3]. Fee is 5% [p.9].")))

    result = generate_answer("When are invoices due?", CHUNKS)

    assert result.cited_pages == [3, 9]
    assert result.grounded is False


def test_answer_with_no_citation_is_not_grounded(monkeypatch):
    use_provider(monkeypatch, "gemini", FakeProvider(gemini_reply("Invoices are due within 30 days.")))

    result = generate_answer("When are invoices due?", CHUNKS)

    assert result.cited_pages == []
    assert result.grounded is False


@pytest.mark.parametrize("reply", [NOT_FOUND, "not found in the document", "  Not found in the document.\n"])
def test_not_found_reply_is_returned_exactly_and_counts_as_grounded(monkeypatch, reply):
    use_provider(monkeypatch, "gemini", FakeProvider(gemini_reply(reply)))

    result = generate_answer("Who is the CEO?", CHUNKS)

    assert result.answer == NOT_FOUND
    assert result.cited_pages == []
    assert result.grounded is True


def test_no_retrieved_chunks_answers_not_found_without_calling_the_provider(monkeypatch):
    fake = FakeProvider(gemini_reply("should not be used"))
    use_provider(monkeypatch, "gemini", fake)

    result = generate_answer("Anything?", [])

    assert result.answer == NOT_FOUND
    assert fake.requests == []


# ---- exact provider requests ----------------------------------------------

def test_gemini_request_shape(monkeypatch):
    fake = FakeProvider(gemini_reply("Due in 30 days [p.3].", thought="Let me look at page 3."))
    use_provider(monkeypatch, "gemini", fake)

    result = generate_answer("When are invoices due?", CHUNKS)

    request = fake.requests[0]
    assert request.method == "POST"
    assert str(request.url) == (
        f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent"
    )
    assert request.headers["x-goog-api-key"] == GEMINI_KEY
    assert fake.body["systemInstruction"] == {"parts": [{"text": SYSTEM_PROMPT}]}
    assert fake.body["contents"] == [
        {"role": "user", "parts": [{"text": build_prompt("When are invoices due?", CHUNKS)[1]}]}
    ]
    assert "generationConfig" not in fake.body  # no sampling settings sent
    assert result.answer == "Due in 30 days [p.3]."  # the thought part is not part of the answer


def test_anthropic_request_shape(monkeypatch):
    fake = FakeProvider(anthropic_reply("Renews every year [p.5]."))
    use_provider(monkeypatch, "anthropic", fake)

    result = generate_answer("Does it renew?", CHUNKS)

    request = fake.requests[0]
    assert str(request.url) == "https://api.anthropic.com/v1/messages"
    assert request.headers["x-api-key"] == ANTHROPIC_KEY
    assert request.headers["anthropic-version"] == "2023-06-01"
    assert fake.body == {
        "model": settings.ANTHROPIC_MODEL,
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": build_prompt("Does it renew?", CHUNKS)[1]}],
    }
    assert result.answer == "Renews every year [p.5]."
    assert result.grounded is True
    assert result.provider == f"anthropic:{settings.ANTHROPIC_MODEL}"


# ---- provider failures ----------------------------------------------------

@pytest.mark.parametrize(
    "name,fake,message",
    [
        ("gemini", FakeProvider({"error": {"message": "quota"}}, status_code=429), "gemini returned HTTP 429"),
        ("anthropic", FakeProvider({"error": {"type": "overloaded_error"}}, status_code=529), "anthropic returned HTTP 529"),
        ("gemini", FakeProvider(error=httpx.ReadTimeout("timed out")), "gemini request failed: ReadTimeout"),
        ("anthropic", FakeProvider(error=httpx.ConnectError("refused")), "anthropic request failed: ConnectError"),
        ("gemini", FakeProvider(raw_body=b"<html>bad gateway</html>"), "not JSON"),
        ("gemini", FakeProvider({"promptFeedback": {"blockReason": "SAFETY"}}), "no answer text (SAFETY)"),
        ("gemini", FakeProvider({"candidates": [{"finishReason": "MAX_TOKENS"}]}), "no answer text (MAX_TOKENS)"),
        ("anthropic", FakeProvider({"content": [], "stop_reason": "refusal"}), "stop_reason=refusal"),
    ],
)
def test_provider_failures_raise_without_leaking_the_api_key(monkeypatch, name, fake, message):
    use_provider(monkeypatch, name, fake)

    with pytest.raises(LLMProviderError, match=re.escape(message)) as error:
        generate_answer("When are invoices due?", CHUNKS)

    assert GEMINI_KEY not in str(error.value)
    assert ANTHROPIC_KEY not in str(error.value)


# ---- extractive fallback (LLM_PROVIDER=none) ------------------------------

def fake_embeddings(monkeypatch, keyword):
    """Sentences containing `keyword` point the same way as the question; the rest are orthogonal."""
    def vector(text):
        return [1.0, 0.0] if keyword in text.lower() else [0.0, 1.0]

    monkeypatch.setattr(llm_service, "create_embedding", lambda text: [1.0, 0.0])
    monkeypatch.setattr(
        llm_service, "create_embeddings_batch",
        lambda texts, show_progress_bar=True: [vector(text) for text in texts],
    )


def no_http_allowed():
    raise AssertionError("the fallback must not make an HTTP call")


def test_fallback_returns_matching_sentences_with_citations_and_a_label(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "none")
    monkeypatch.setattr(llm_service, "_new_client", no_http_allowed)
    fake_embeddings(monkeypatch, keyword="due")

    result = generate_answer("When are invoices due?", CHUNKS)

    assert result.provider == "none:extractive"
    assert result.answer.startswith(llm_service.FALLBACK_LABEL)
    assert "Invoices are due within 30 days of receipt. [p.3]" in result.answer
    assert "renews" not in result.answer  # similarity 0 is below the cutoff
    assert result.cited_pages == [3]
    assert result.grounded is True


def test_fallback_says_not_found_when_no_sentence_is_similar_enough(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "none")
    monkeypatch.setattr(llm_service, "_new_client", no_http_allowed)
    fake_embeddings(monkeypatch, keyword="no sentence contains this")

    result = generate_answer("Who is the CEO?", CHUNKS)

    assert result.answer == NOT_FOUND
    assert result.grounded is True


def test_fallback_skips_short_fragments_and_repeated_sentences(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "none")
    fake_embeddings(monkeypatch, keyword="due")
    overlapping = [
        chunk(3, "Page 3. Invoices are due within 30 days of receipt."),
        chunk(3, "Invoices are due within 30 days of receipt. Payment is due by bank transfer only."),
    ]

    result = generate_answer("When are invoices due?", overlapping)

    body = result.answer[len(llm_service.FALLBACK_LABEL):]
    assert body.count("Invoices are due within 30 days of receipt.") == 1
    assert "Page 3." not in body
    assert "Payment is due by bank transfer only. [p.3]" in body
