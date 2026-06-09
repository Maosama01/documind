from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
from app.models.document import Document
from app.models.chunk import Chunk
from app.services.pdf_service import extract_text_from_pdf, get_pdf_metadata, get_file_size
from app.services.chunking_service import split_text_into_chunks
from app.services.embedding_service import create_embeddings_batch, create_embedding

def process_document(db: Session, document_id: int, file_path: str) -> Document:
    """
    Full pipeline: PDF → Text → Chunks → Embeddings → Database
    
    This function:
    1. Extracts text from the PDF
    2. Updates document metadata (page count, preview)
    3. Splits text into chunks
    4. Creates embeddings for all chunks in one batch
    5. Saves all chunks + embeddings to database
    6. Updates document status to "processed"
    """
    
    # Step 1: Get the document from database
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise ValueError(f"Document {document_id} not found")
    
    # Update status to "processing" so user knows it's working
    document.status = "processing"
    db.commit()
    
    try:
        # Step 2: Extract text from PDF pages
        pages = extract_text_from_pdf(file_path)
        
        # Step 3: Update document metadata
        metadata = get_pdf_metadata(file_path)
        document.page_count = metadata["page_count"]
        document.content_preview = metadata["content_preview"]
        document.file_size = get_file_size(file_path)
        db.commit()
        
        # Step 4: Split into chunks
        chunks_data = split_text_into_chunks(pages, chunk_size=500, chunk_overlap=50)
        
        if not chunks_data:
            document.status = "failed"
            db.commit()
            raise ValueError("No text could be extracted from this PDF")
        
        # Step 5: Create embeddings for ALL chunks at once (batch processing)
        # This is much faster than embedding one chunk at a time
        chunk_texts = [chunk["content"] for chunk in chunks_data]
        print(f"Creating embeddings for {len(chunk_texts)} chunks...")
        embeddings = create_embeddings_batch(chunk_texts)
        print("Embeddings created successfully!")
        
        # Step 6: Save chunks to database
        for i, (chunk_data, embedding) in enumerate(zip(chunks_data, embeddings)):
            chunk = Chunk(
                content=chunk_data["content"],
                chunk_index=chunk_data["chunk_index"],
                page_number=chunk_data["page_number"],
                embedding=embedding,
                document_id=document_id
            )
            db.add(chunk)
        
        # Commit all chunks at once (more efficient than one by one)
        db.commit()
        
        # Step 7: Mark document as processed
        document.status = "processed"
        db.commit()
        
        print(f"Document {document_id} processed: {len(chunks_data)} chunks created")
        return document
        
    except Exception as e:
        # If anything goes wrong, mark document as failed
        document.status = "failed"
        db.commit()
        raise e


def semantic_search(
    db: Session,
    query: str,
    document_id: int,
    top_k: int = 5
) -> List[Chunk]:
    """
    Find the most relevant chunks for a given query.
    
    1. Convert the query to an embedding
    2. Use pgvector to find the most similar chunk embeddings
    3. Return the top_k most relevant chunks
    
    This is the core of RAG — Retrieval Augmented Generation.
    """
    
    # Convert question to embedding
    query_embedding = create_embedding(query)
    
    # pgvector's <=> operator calculates cosine distance
    # (1 - cosine similarity, so lower = more similar)
    # We order by distance ascending to get most similar first
    results = db.query(Chunk).filter(
        Chunk.document_id == document_id
    ).order_by(
        Chunk.embedding.op("<=>")(query_embedding)
        # This is pgvector's cosine distance operator
        # It finds chunks whose embeddings are closest to the query embedding
    ).limit(top_k).all()
    
    return results


def get_documents_for_user(db: Session, user_id: int) -> List[Document]:
    """Get all documents belonging to a specific user"""
    return db.query(Document).filter(Document.owner_id == user_id).all()


def get_document_by_id(db: Session, document_id: int, user_id: int):
    """Get a specific document, verifying it belongs to the user"""
    return db.query(Document).filter(
        Document.id == document_id,
        Document.owner_id == user_id
    ).first()