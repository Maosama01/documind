from typing import Callable, Dict, List

MAX_CHUNK_TOKENS = 254
# all-MiniLM-L6-v2 embeds at most 256 tokens per text (max_seq_length in its
# sentence_bert_config.json), and the tokenizer adds two of its own: [CLS] at
# the start and [SEP] at the end. That leaves 254 for the chunk's text.

MIN_PAGE_WORDS = 20
# A page with fewer words than this is skipped: these are usually page numbers,
# headers or footers. It also skips a page that holds one short sentence.

TokenCounter = Callable[[List[str]], List[int]]
# Given a page's words, returns how many tokens each word costs.
# embedding_service.count_word_tokens is the real one.


def validate_chunk_settings(chunk_size: int, chunk_overlap: int) -> None:
    """Raise ValueError unless 1 <= chunk_size <= MAX_CHUNK_TOKENS and 0 <= chunk_overlap < chunk_size."""
    if not 1 <= chunk_size <= MAX_CHUNK_TOKENS:
        raise ValueError(
            f"chunk size must be between 1 and {MAX_CHUNK_TOKENS} tokens, got {chunk_size}: "
            "the embedding model reads 256 tokens, two of which it uses itself"
        )
    if not 0 <= chunk_overlap < chunk_size:
        raise ValueError(
            f"chunk overlap must be at least 0 and smaller than chunk size "
            f"({chunk_size} tokens), got {chunk_overlap}"
        )


def split_text_into_chunks(
    pages: List[Dict],
    chunk_size: int,
    chunk_overlap: int,
    count_tokens: TokenCounter,
    min_page_words: int = MIN_PAGE_WORDS
) -> List[Dict]:
    """
    Split document pages into overlapping chunks of whole words, measured in tokens.

    For each page, words are added to a chunk while the chunk's token count
    stays within chunk_size. The next chunk starts with the last words of the
    previous one, as many as fit in chunk_overlap tokens, so a sentence cut at
    a boundary keeps its context.

    A chunk's token count is the sum of its words' token counts. That holds
    for the embedding model's tokenizer because it splits text on whitespace
    before cutting words into pieces.

    Guarantees:
    - A chunk never mixes words from two pages, so its page_number is exact.
    - A chunk has at most chunk_size tokens, except a single word that is
      longer than chunk_size on its own: it becomes a chunk by itself (the
      model will still cut it off; the token-limit warning reports it).
    - Every chunk adds at least one word the previous chunk did not have.
    - Every word of a page with at least min_page_words words is in some
      chunk, including the last word. Shorter pages produce no chunk.

    Splitting is on whitespace, so paragraph breaks and newlines are not kept.

    Returns:
        List of {"content": str, "chunk_index": int, "page_number": int},
        with chunk_index counting 0, 1, 2, ... across the whole document.
    """
    validate_chunk_settings(chunk_size, chunk_overlap)

    chunks = []
    chunk_index = 0

    for page in pages:
        words = page["text"].split()
        if len(words) < min_page_words:
            continue
        costs = count_tokens(words)

        start = 0
        while True:
            # Add words while they fit. The first word always goes in, so a
            # word longer than chunk_size still makes progress as its own chunk.
            end, used = start, 0
            while end < len(words) and (end == start or used + costs[end] <= chunk_size):
                used += costs[end]
                end += 1

            chunks.append({
                "content": " ".join(words[start:end]),
                "chunk_index": chunk_index,
                "page_number": page["page_number"]
            })
            chunk_index += 1

            if end >= len(words):  # this chunk reached the last word of the page
                break

            # Step back over the last words of this chunk while they fit in the
            # overlap AND still leave room for the next new word (words[end]),
            # so the next chunk always contains at least one new word. Never
            # step back to `start`: that would repeat this chunk.
            next_start, overlap_used = end, 0
            while (
                next_start - 1 > start
                and overlap_used + costs[next_start - 1] <= chunk_overlap
                and overlap_used + costs[next_start - 1] + costs[end] <= chunk_size
            ):
                next_start -= 1
                overlap_used += costs[next_start]
            start = next_start

    return chunks
