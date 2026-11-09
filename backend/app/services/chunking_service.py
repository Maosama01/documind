from typing import List, Dict

MIN_CHUNK_WORDS = 20
# A page with fewer words than this is skipped: these are usually page numbers,
# headers or footers. It also skips a page that holds one short sentence.


def validate_chunk_settings(chunk_size: int, chunk_overlap: int, min_chunk_words: int) -> None:
    """
    Raise ValueError unless 0 < min_chunk_words <= chunk_overlap < chunk_size.

    - chunk_overlap < chunk_size: the window moves forward by chunk_size - chunk_overlap
      words. At 0 the loop would never advance; below 0 it would produce no chunks.
    - chunk_overlap >= min_chunk_words: this is what makes dropping short pieces safe.
      After the first window on a page, every window starts with chunk_overlap words
      already seen plus at least one new word, so it is never shorter than
      min_chunk_words and never dropped. The only piece that can be dropped is a whole
      page shorter than min_chunk_words.
    """
    if min_chunk_words < 1:
        raise ValueError(f"min_chunk_words must be at least 1, got {min_chunk_words}")
    if chunk_overlap < min_chunk_words:
        raise ValueError(
            f"chunk overlap ({chunk_overlap} words) must be at least {min_chunk_words} words; "
            "with less, the end of a page can be dropped as a short tail and lost"
        )
    if chunk_overlap >= chunk_size:
        raise ValueError(
            f"chunk overlap ({chunk_overlap} words) must be smaller than "
            f"chunk size ({chunk_size} words)"
        )


def split_text_into_chunks(
    pages: List[Dict],
    chunk_size: int,
    chunk_overlap: int,
    min_chunk_words: int
) -> List[Dict]:
    """
    Split document pages into overlapping word windows, one page at a time.

    Why overlap? Imagine a sentence is cut right at a chunk boundary:
    "The payment terms are net 30 days" gets split as:
    Chunk 1: "...The payment terms are"
    Chunk 2: "net 30 days from invoice..."

    With overlap, chunk 2 starts chunk_overlap words before the boundary,
    so it includes "...The payment terms are net 30 days..."

    Guarantees (see validate_chunk_settings):
    - A chunk never mixes words from two pages, so its page_number is exact.
    - No chunk is longer than chunk_size words.
    - Neighbouring chunks on the same page share exactly chunk_overlap words.
    - Every word of a page with at least min_chunk_words words is in some chunk,
      including the last word. Pages with fewer words produce no chunk.

    Splitting is on whitespace, so paragraph breaks and newlines are not kept.

    Args:
        pages: List of {"page_number": int, "text": str}
        chunk_size: Maximum number of words per chunk
        chunk_overlap: Number of words repeated between neighbouring chunks
        min_chunk_words: Pages with fewer words than this are skipped

    Returns:
        List of {"content": str, "chunk_index": int, "page_number": int},
        with chunk_index counting 0, 1, 2, ... across the whole document.
    """
    validate_chunk_settings(chunk_size, chunk_overlap, min_chunk_words)

    chunks = []
    chunk_index = 0
    step = chunk_size - chunk_overlap

    for page in pages:
        page_number = page["page_number"]
        words = page["text"].split()

        # Slide a window of chunk_size words across the page, moving `step` words
        # at a time, so each window repeats the last chunk_overlap words of the one before
        for start in range(0, len(words), step):
            end = start + chunk_size
            chunk_words = words[start:end]

            # Only the first window of a page can be this short (the whole page
            # is shorter than min_chunk_words); later windows always hold
            # chunk_overlap >= min_chunk_words words plus at least one new one
            if len(chunk_words) < min_chunk_words:
                break

            chunks.append({
                "content": " ".join(chunk_words),
                "chunk_index": chunk_index,
                "page_number": page_number
            })
            chunk_index += 1

            # This window reached the last word of the page
            if end >= len(words):
                break

    return chunks
