# pyrefly: ignore [missing-import]
from sentence_transformers import SentenceTransformer
from typing import List
import numpy as np

# Load the model once when the module is imported
# This happens at server startup — not on every request
# The model is ~90MB and downloads automatically on first run
# all-MiniLM-L6-v2 is fast, accurate, and produces 384-dimension embeddings
print("Loading embedding model... (first time may take a minute)")
model = SentenceTransformer('all-MiniLM-L6-v2')
print("Embedding model loaded successfully!")

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
    embedding = model.encode(text)
    return embedding.tolist()

def create_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Create embeddings for multiple texts at once.
    Much faster than calling create_embedding() in a loop
    because the model processes batches efficiently.
    
    Input:  ["text1", "text2", "text3"]
    Output: [[...384 numbers...], [...384 numbers...], [...384 numbers...]]
    """
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=True)
    # batch_size=32 means process 32 texts at a time
    # show_progress_bar=True shows a progress bar in the terminal
    
    return [emb.tolist() for emb in embeddings]

def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate how similar two vectors are.
    Returns a value between -1 and 1:
    - 1.0 = identical meaning
    - 0.0 = unrelated
    - -1.0 = opposite meaning
    
    We use this to find the chunks most relevant to a question.
    """
    a = np.array(vec1)
    b = np.array(vec2)
    
    # Cosine similarity formula: (A · B) / (|A| × |B|)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))