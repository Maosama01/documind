"""
Token-based chunking, checked over many page lengths and word costs.

Every word is unique ("p3w17" is word 17 of page 3) and its token cost comes
from a counter the test controls, so a test can check exact chunk sizes.
The real counter (the model's tokenizer) is checked separately, by hand.
"""
import random

import pytest

from app.services.chunking_service import (
    MAX_CHUNK_TOKENS,
    MIN_PAGE_WORDS,
    split_text_into_chunks,
    validate_chunk_settings,
)

SIZE, OVERLAP = 240, 40  # the defaults in config.py
# Other valid settings, including no overlap and an overlap of size - 1
SETTINGS = [(SIZE, OVERLAP), (50, 10), (10, 0), (60, 59)]
PAGE_LENGTHS = list(range(0, 120)) + list(range(120, 1000, 37))


def page(number: int, n_words: int) -> dict:
    return {"page_number": number, "text": " ".join(f"p{number}w{i}" for i in range(n_words))}


def one_token_each(words):
    return [1] * len(words)


def random_costs(seed: int, giant_share: float = 0.0):
    """Each word costs 1-6 tokens (fixed per word); a share of words cost 300, more than any chunk."""
    rng, costs = random.Random(seed), {}

    def count(words):
        for word in words:
            if word not in costs:
                costs[word] = 300 if rng.random() < giant_share else rng.randint(1, 6)
        return [costs[word] for word in words]
    return count


def words(chunk) -> list:
    return chunk["content"].split()


def chunk(pages, size=SIZE, overlap=OVERLAP, count=one_token_each):
    return split_text_into_chunks(pages, size, overlap, count)


@pytest.mark.parametrize("size,overlap", SETTINGS)
@pytest.mark.parametrize("giant_share", [0.0, 0.02])
def test_no_chunk_exceeds_the_budget_except_a_single_giant_word(size, overlap, giant_share):
    count = random_costs(seed=size * 1000 + overlap, giant_share=giant_share)
    for n_words in PAGE_LENGTHS:
        for c in chunk([page(1, n_words)], size, overlap, count):
            cost = sum(count(words(c)))
            assert cost <= size or len(words(c)) == 1, (n_words, cost)


@pytest.mark.parametrize("size,overlap", SETTINGS)
@pytest.mark.parametrize("giant_share", [0.0, 0.02])
def test_nothing_lost_at_the_end_of_a_page(size, overlap, giant_share):
    count = random_costs(seed=size * 1000 + overlap, giant_share=giant_share)
    for n_words in range(MIN_PAGE_WORDS, max(PAGE_LENGTHS) + 1, 7):
        expected = page(1, n_words)["text"].split()
        chunks = chunk([page(1, n_words)], size, overlap, count)

        assert {word for c in chunks for word in words(c)} == set(expected), n_words
        assert words(chunks[-1])[-1] == expected[-1], n_words


@pytest.mark.parametrize("size,overlap", SETTINGS)
def test_neighbours_share_a_run_of_words_that_fits_in_the_overlap(size, overlap):
    count = random_costs(seed=7)
    for n_words in PAGE_LENGTHS:
        chunks = chunk([page(1, n_words)], size, overlap, count)
        for before, after in zip(chunks, chunks[1:]):
            shared = len(set(words(before)) & set(words(after)))
            assert words(before)[len(words(before)) - shared:] == words(after)[:shared]
            assert sum(count(words(after)[:shared])) <= overlap
            assert len(words(after)) > shared  # every chunk adds at least one new word


def test_with_one_token_per_word_the_overlap_is_exact():
    chunks = chunk([page(1, 400)], size=100, overlap=20)

    assert [len(words(c)) for c in chunks] == [100, 100, 100, 100, 80]
    for before, after in zip(chunks, chunks[1:]):
        assert words(before)[-20:] == words(after)[:20]


def test_default_windows_with_one_token_per_word():
    """Spelled out once by hand: 240 tokens per chunk, the next starting 40 tokens back."""
    chunks = chunk([page(1, 600)])

    spans = [(words(c)[0], words(c)[-1]) for c in chunks]
    assert spans == [("p1w0", "p1w239"), ("p1w200", "p1w439"), ("p1w400", "p1w599")]


def test_a_word_longer_than_the_budget_gets_a_chunk_of_its_own():
    giant = "p1w10"
    chunks = chunk([page(1, 30)], size=12, overlap=4,
                   count=lambda ws: [300 if w == giant else 1 for w in ws])

    assert [giant] in [words(c) for c in chunks]
    assert all(giant not in words(c) for c in chunks if words(c) != [giant])
    assert {w for c in chunks for w in words(c)} == set(page(1, 30)["text"].split())


def test_chunks_never_cross_pages():
    pages = [page(1, 400), page(2, 25), page(3, 241), page(4, 0), page(5, 333)]

    chunks = chunk(pages, count=random_costs(seed=3))

    assert {c["page_number"] for c in chunks} == {1, 2, 3, 5}
    for c in chunks:
        assert all(word.startswith(f"p{c['page_number']}w") for word in words(c))


def test_page_shorter_than_the_minimum_is_dropped():
    assert chunk([page(1, MIN_PAGE_WORDS - 1)]) == []
    assert chunk([page(1, 0)]) == []
    assert len(chunk([page(1, MIN_PAGE_WORDS)])) == 1


def test_chunk_index_counts_across_pages_without_gaps():
    pages = [page(1, 400), page(2, MIN_PAGE_WORDS - 1), page(3, 300)]

    chunks = chunk(pages)

    assert [c["chunk_index"] for c in chunks] == list(range(len(chunks)))


def test_the_budget_leaves_room_for_the_models_own_two_tokens():
    assert MAX_CHUNK_TOKENS == 256 - 2


@pytest.mark.parametrize(
    "size,overlap,reason",
    [
        (0, 0, "between 1 and 254"),
        (255, 40, "between 1 and 254"),           # the model would cut the end off
        (240, 240, "smaller than chunk size"),    # the chunker could not move forward
        (240, -1, "at least 0"),
    ],
)
def test_unsafe_settings_are_rejected(size, overlap, reason):
    with pytest.raises(ValueError, match=reason):
        validate_chunk_settings(size, overlap)
    with pytest.raises(ValueError, match=reason):
        split_text_into_chunks([page(1, 500)], size, overlap, one_token_each)
