import threading
from typing import List
import numpy as np

MODEL_NAME = "all-MiniLM-L6-v2"
# all-MiniLM-L6-v2 is fast and produces 384-dimension embeddings
# (matches the Vector(384) column on Chunk).

_model = None
_model_lock = threading.Lock()


def get_model():
    """
    Load the embedding model on first use and reuse it afterwards.

    Importing this module no longer loads the model (~90MB, downloaded on the
    first run). The first upload or search after startup pays the load time
    instead. The lock stops two concurrent first requests from loading it twice:
    FastAPI runs sync routes in a thread pool, so that can happen.
    """
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                # Imported here so that importing this module does not import torch.
                # pyrefly: ignore [missing-import]
                from sentence_transformers import SentenceTransformer
                print("Loading embedding model... (first time may take a minute)")
                _model = SentenceTransformer(MODEL_NAME)
                print("Embedding model loaded successfully!")
    return _model


def create_embedding(text: str) -> List[float]:
    """
    Convert a single text string into a vector embedding.

    Input:  "What are the payment terms?"
    Output: [0.123, -0.456, 0.789, ...] (384 numbers)

    The output is a list of floats that represents the MEANING of the text.
    Similar texts will have similar vectors.
    """
    # model.encode returns a numpy array
    # .tolist() converts it to a plain Python list
    # pgvector needs a plain list, not numpy array
    embedding = get_model().encode(text)
    return embedding.tolist()

def create_embeddings_batch(texts: List[str], show_progress_bar: bool = True) -> List[List[float]]:
    """
    Create embeddings for multiple texts at once.
    Much faster than calling create_embedding() in a loop
    because the model processes batches efficiently.

    Input:  ["text1", "text2", "text3"]
    Output: [[...384 numbers...], [...384 numbers...], [...384 numbers...]]
    """
    embeddings = get_model().encode(texts, batch_size=32, show_progress_bar=show_progress_bar)
    # batch_size=32 means process 32 texts at a time
    # show_progress_bar prints a progress bar in the terminal; the per-question
    # extractive fallback turns it off

    return [emb.tolist() for emb in embeddings]

def count_over_token_limit(texts: List[str]) -> int:
    """
    Count how many texts are longer than the model's token limit.

    The limit is the model's max_seq_length: 256 tokens for all-MiniLM-L6-v2,
    including the [CLS] and [SEP] tokens the tokenizer adds. encode() cuts off
    everything past it, so the end of an over-limit text is not in its embedding.
    Uses the model's own tokenizer, so the count is measured, not estimated.
    """
    if not texts:
        return 0
    model = get_model()
    limit = model.max_seq_length
    # verbose=False: the tokenizer otherwise warns for every text over 512 tokens
    token_ids = model.tokenizer(texts, verbose=False)["input_ids"]
    return sum(1 for ids in token_ids if len(ids) > limit)


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate how similar two vectors are.
    Returns a value between -1 and 1:
    - 1.0 = identical meaning
    - 0.0 = unrelated
    - -1.0 = opposite meaning

    Used by the extractive fallback in llm_service to rank sentences.
    Search itself does not use it: semantic_search lets pgvector compute
    cosine distance in SQL with the <=> operator.
    """
    a = np.array(vec1)
    b = np.array(vec2)

    # Cosine similarity formula: (A · B) / (|A| × |B|)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
