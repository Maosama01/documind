"""
Chunking properties, checked over many page lengths.

Every word is unique ("p3w17" is word 17 of page 3), so a test can tell exactly
which page and position each word in a chunk came from.
"""
import pytest

from app.services.chunking_service import (
    MIN_CHUNK_WORDS,
    split_text_into_chunks,
    validate_chunk_settings,
)

SIZE, OVERLAP = 180, 30  # the defaults in config.py
# Other valid settings, including the tightest one allowed (overlap == MIN_CHUNK_WORDS)
SETTINGS = [(SIZE, OVERLAP), (50, MIN_CHUNK_WORDS), (40, MIN_CHUNK_WORDS), (100, 80)]
PAGE_LENGTHS = range(0, 700)


def page(number: int, n_words: int) -> dict:
    return {"page_number": number, "text": " ".join(f"p{number}w{i}" for i in range(n_words))}


def chunk(pages, size=SIZE, overlap=OVERLAP):
    return split_text_into_chunks(pages, size, overlap, MIN_CHUNK_WORDS)


def words(c) -> list:
    return c["content"].split()


@pytest.mark.parametrize("size,overlap", SETTINGS)
def test_neighbouring_chunks_share_exactly_the_overlap(size, overlap):
    for n_words in PAGE_LENGTHS:
        chunks = chunk([page(1, n_words)], size, overlap)
        for before, after in zip(chunks, chunks[1:]):
            assert words(before)[-overlap:] == words(after)[:overlap], n_words


@pytest.mark.parametrize("size,overlap", SETTINGS)
def test_nothing_lost_at_the_end_of_a_page(size, overlap):
    for n_words in range(MIN_CHUNK_WORDS, max(PAGE_LENGTHS) + 1):
        expected = page(1, n_words)["text"].split()
        chunks = chunk([page(1, n_words)], size, overlap)

        covered = {word for c in chunks for word in words(c)}
        assert covered == set(expected), n_words
        assert words(chunks[-1])[-1] == expected[-1], n_words


@pytest.mark.parametrize("size,overlap", SETTINGS)
def test_no_chunk_is_longer_than_chunk_size_or_shorter_than_the_minimum(size, overlap):
    for n_words in PAGE_LENGTHS:
        for c in chunk([page(1, n_words)], size, overlap):
            assert MIN_CHUNK_WORDS <= len(words(c)) <= size, n_words


def test_chunks_never_cross_pages():
    pages = [page(1, 400), page(2, 25), page(3, 181), page(4, 0), page(5, 333)]

    chunks = chunk(pages)

    assert {c["page_number"] for c in chunks} == {1, 2, 3, 5}
    for c in chunks:
        assert all(word.startswith(f"p{c['page_number']}w") for word in words(c))


def test_page_shorter_than_the_minimum_is_dropped():
    short = MIN_CHUNK_WORDS - 1
    assert chunk([page(1, short)]) == []
    assert chunk([page(1, 0)]) == []
    assert len(chunk([page(1, MIN_CHUNK_WORDS)])) == 1


def test_chunk_index_counts_across_pages_without_gaps():
    pages = [page(1, 400), page(2, MIN_CHUNK_WORDS - 1), page(3, 200)]

    chunks = chunk(pages)

    assert [c["chunk_index"] for c in chunks] == list(range(len(chunks)))


def test_default_windows_on_a_400_word_page():
    """Spelled out once by hand: windows start every 180 - 30 = 150 words."""
    chunks = chunk([page(1, 400)])

    spans = [(words(c)[0], words(c)[-1]) for c in chunks]
    assert spans == [("p1w0", "p1w179"), ("p1w150", "p1w329"), ("p1w300", "p1w399")]


@pytest.mark.parametrize(
    "size,overlap,reason",
    [
        (180, MIN_CHUNK_WORDS - 1, "at least 20"),  # a short tail could hold new words and be dropped
        (180, 180, "smaller than chunk size"),      # the window would never move forward
        (180, 200, "smaller than chunk size"),      # the window would move backwards: no chunks
    ],
)
def test_unsafe_settings_are_rejected(size, overlap, reason):
    with pytest.raises(ValueError, match=reason):
        validate_chunk_settings(size, overlap, MIN_CHUNK_WORDS)
    with pytest.raises(ValueError, match=reason):
        split_text_into_chunks([page(1, 500)], size, overlap, MIN_CHUNK_WORDS)
