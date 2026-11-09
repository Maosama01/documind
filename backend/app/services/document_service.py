import logging
from sqlalchemy.orm import Session
from typing import List
# pyrefly: ignore [missing-import]
from pypdf.errors import PyPdfError
from app.config import settings
from app.database import SessionLocal
from app.models.document import Document
from app.models.chunk import Chunk
from app.services.pdf_service import extract_text_from_pdf, get_pdf_metadata, get_file_size
from app.services.chunking_service import MIN_CHUNK_WORDS, split_text_into_chunks
from app.services.embedding_service import (
    count_over_token_limit,
    create_embeddings_batch,
    create_embedding,
    get_model
)

logger = logging.getLogger(__name__)

# Failure reasons stored in documents.error_message and shown to the user.
# They never include the underlying exception text, which can contain file
# paths or SQL; that goes to the server log instead.
UNREADABLE_PDF = "The file could not be read as a PDF. It may be damaged or password-protected."
NO_TEXT = (
    "No text could be extracted. Scanned PDFs need OCR, which is not supported, "
    "and pages with fewer than 20 words are skipped."
)
MODEL_UNAVAILABLE = "The embedding model could not be loaded."
INTERNAL_ERROR = "Processing failed because of an internal error. The server log has the details."
INTERRUPTED = "Processing was interrupted by a server restart. Upload the file again."


class ProcessingError(Exception):
    """A processing failure whose message is safe to show the user."""


def process_document(document_id: int, file_path: str, session_factory=SessionLocal) -> None:
    """
    Full pipeline: PDF → Text → Chunks → Embeddings → Database

    Runs as a background task after an upload, so it opens its own database
    session instead of borrowing the request's: the request's session would
    otherwise keep a pooled connection checked out for the whole run.

    On failure the document ends as "failed" with error_message set, and the
    exception is logged, not raised: nothing above a background task could
    handle it.
    """
    db = session_factory()
    try:
        _process(db, document_id, file_path)
    finally:
        db.close()


def _process(db: Session, document_id: int, file_path: str) -> None:
    document = db.get(Document, document_id)
    if document is None:
        logger.warning("Document %s was deleted before processing started", document_id)
        return

    # Update status to "processing" so the user knows it's working
    document.status = "processing"
    document.error_message = None
    db.commit()

    try:
        # Step 1: Extract text and metadata from the PDF pages
        try:
            pages = extract_text_from_pdf(file_path)
            metadata = get_pdf_metadata(file_path)
        except PyPdfError as error:  # not a PDF, damaged, or encrypted
            raise ProcessingError(UNREADABLE_PDF) from error
        document.page_count = metadata["page_count"]
        document.content_preview = metadata["content_preview"]
        document.file_size = get_file_size(file_path)
        db.commit()

        # Step 2: Split into chunks
        chunks_data = split_text_into_chunks(
            pages,
            chunk_size=settings.CHUNK_SIZE_WORDS,
            chunk_overlap=settings.CHUNK_OVERLAP_WORDS,
            min_chunk_words=MIN_CHUNK_WORDS
        )
        if not chunks_data:
            raise ProcessingError(NO_TEXT)

        # Step 3: Load the model explicitly, so a missing download or an
        # unwritable model cache is reported as such, not as an internal error
        try:
            get_model()
        except Exception as error:
            raise ProcessingError(MODEL_UNAVAILABLE) from error

        chunk_texts = [chunk["content"] for chunk in chunks_data]

        # Word-based chunk sizes only estimate the token count, so measure it:
        # text past the model's token limit is not embedded and cannot be found.
        over_limit = count_over_token_limit(chunk_texts)
        if over_limit:
            logger.warning(
                "Document %s: %d of %d chunks exceed the embedding model's token "
                "limit; the text past the limit is not embedded",
                document_id, over_limit, len(chunk_texts)
            )

        # Step 4: Create embeddings for ALL chunks at once (batch processing)
        # This is much faster than embedding one chunk at a time
        embeddings = create_embeddings_batch(chunk_texts)

        # Step 5: Save the chunks and mark the document processed, in one commit
        for chunk_data, embedding in zip(chunks_data, embeddings):
            db.add(Chunk(
                content=chunk_data["content"],
                chunk_index=chunk_data["chunk_index"],
                page_number=chunk_data["page_number"],
                embedding=embedding,
                document_id=document_id
            ))
        document.status = "processed"
        db.commit()
        logger.info("Document %s processed: %d chunks", document_id, len(chunks_data))

    except Exception as error:
        # Undo anything uncommitted (e.g. half-added chunks) before writing the failure
        db.rollback()
        reason = str(error) if isinstance(error, ProcessingError) else INTERNAL_ERROR
        logger.exception("Document %s failed: %s", document_id, reason)
        document = db.get(Document, document_id)
        if document is not None:  # None if the user deleted it meanwhile
            document.status = "failed"
            document.error_message = reason
            db.commit()


def fail_interrupted_documents(db: Session) -> int:
    """
    Mark documents left "pending" or "processing" by an earlier server process
    as failed, and return how many there were.

    Called once at startup, before the server accepts uploads, so no document
    can be legitimately in progress yet. This assumes a single server process:
    with several workers, one that starts while another is processing would
    mark that work as failed.
    """
    count = (
        db.query(Document)
        .filter(Document.status.in_(["pending", "processing"]))
        .update({"status": "failed", "error_message": INTERRUPTED}, synchronize_session=False)
    )
    db.commit()
    return count


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
    #
    # This search is exact: Postgres uses the index on chunks.document_id to
    # fetch this document's chunks, computes the distance to every one of them,
    # and sorts. A document has at most a few hundred chunks, so that is cheap.
    #
    # There is deliberately no HNSW (approximate vector) index. Measured on
    # pgvector 0.8.7 with 200 documents x 100 chunks of random vectors, an HNSW
    # index made this exact query shape return 0 rows instead of 5: Postgres
    # took the 40 nearest chunks across ALL documents (hnsw.ef_search) and only
    # then removed the ones from other documents. With hnsw.iterative_scan it
    # returned 5 rows, but not the same 5 as the exact search. HNSW pays off for
    # searching across every document, which this API does not offer.
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