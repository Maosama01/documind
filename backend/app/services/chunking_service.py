from typing import List, Dict

def split_text_into_chunks(
    pages: List[Dict],
    chunk_size: int = 500,
    chunk_overlap: int = 50
) -> List[Dict]:
    """
    Split document pages into overlapping text chunks.
    
    Why overlap? Imagine a sentence is cut right at a chunk boundary:
    "The payment terms are net 30 days" gets split as:
    Chunk 1: "...The payment terms are"
    Chunk 2: "net 30 days from invoice..."
    
    With overlap, chunk 2 starts 50 words before the boundary,
    so it includes "...The payment terms are net 30 days..."
    This prevents losing context at boundaries.
    
    Args:
        pages: List of {"page_number": int, "text": str}
        chunk_size: Target number of words per chunk
        chunk_overlap: Number of words to repeat between chunks
    
    Returns:
        List of {"content": str, "chunk_index": int, "page_number": int}
    """
    chunks = []
    chunk_index = 0
    
    for page in pages:
        page_number = page["page_number"]
        text = page["text"]
        
        # Split text into individual words
        words = text.split()
        
        if not words:
            continue
        
        # Slide a window of chunk_size words across the page
        # Step size = chunk_size - chunk_overlap
        # This creates the overlapping effect
        step = chunk_size - chunk_overlap
        
        for start in range(0, len(words), step):
            end = start + chunk_size
            chunk_words = words[start:end]
            
            # Skip very short chunks (less than 20 words)
            # They're usually page headers/footers with no real content
            if len(chunk_words) < 20:
                continue
            
            # Join words back into a string
            chunk_text = " ".join(chunk_words)
            
            chunks.append({
                "content": chunk_text,
                "chunk_index": chunk_index,
                "page_number": page_number
            })
            
            chunk_index += 1
            
            # If we've reached the end of the page, stop
            if end >= len(words):
                break
    
    return chunks


def split_text_simple(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
    """
    Simpler version — splits a single text string into chunks.
    Used for quick processing without page tracking.
    """
    words = text.split()
    chunks = []
    step = chunk_size - chunk_overlap
    
    for start in range(0, len(words), step):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        if len(chunk.split()) >= 20:
            chunks.append(chunk)
        if end >= len(words):
            break
    
    return chunks