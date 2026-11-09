import logging
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.document import Document
from app.schemas.document import DocumentResponse, DocumentListResponse
from app.services.dependencies import get_current_user
from fastapi.responses import FileResponse
from app.services.pdf_service import delete_upload_file, save_upload_file, upload_path
from app.services.document_service import (
    process_document,
    get_documents_for_user,
    get_document_by_id,
    semantic_search
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/documents",
    tags=["documents"]
)

@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload a PDF document.
    
    The file is saved immediately and processing happens in the background.
    This means the API responds fast (doesn't make user wait for embeddings).
    
    BackgroundTasks is FastAPI's built-in background job system.
    """
    
    # Validate it's actually a PDF
    if not file.filename.endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported"
        )
    
    # Validate file size (max 10MB for now)
    MAX_SIZE = 10 * 1024 * 1024  # 10MB in bytes
    file_content = await file.read()
    if len(file_content) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 10MB"
        )
    
    # Reset file pointer after reading
    # (we read it to check size, now we need to read it again to save)
    await file.seek(0)
    
    # Create a unique filename to avoid conflicts
    # uuid4() generates a random unique ID like "550e8400-e29b-41d4-a716"
    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    
    # Save the file locally
    file_path = await save_upload_file(file, unique_filename)
    
    # Create database record
    document = Document(
        title=file.filename.replace(".pdf", "").replace("_", " ").title(),
        filename=unique_filename,
        status="pending",
        owner_id=current_user.id
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    
    # Process in background (extract text + create embeddings)
    # The user gets a response immediately while this runs. The task opens
    # its own database session; this request's session is not passed on.
    background_tasks.add_task(
        process_document,
        document.id,
        file_path
    )
    
    return document


@router.get("/", response_model=DocumentListResponse)
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all documents for the current user"""
    documents = get_documents_for_user(db, current_user.id)
    return {
        "documents": documents,
        "total": len(documents)
    }


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific document by ID"""
    document = get_document_by_id(db, document_id, current_user.id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    return document


@router.get("/{document_id}/status")
def get_document_status(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Check processing status of a document.
    Poll this endpoint after uploading to know when processing is done.
    When the status is "failed", error_message says why.
    """
    document = get_document_by_id(db, document_id, current_user.id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        "id": document.id,
        "status": document.status,
        "title": document.title,
        "page_count": document.page_count,
        "error_message": document.error_message,
        "message": {
            "pending": "Document queued for processing",
            "processing": "Extracting text and creating embeddings...",
            "processed": "Ready! You can now ask questions.",
            "failed": f"Processing failed: {document.error_message or 'reason not recorded'}"
        }.get(document.status, "Unknown status")
    }


@router.get("/{document_id}/file")
def get_document_file(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    The uploaded PDF of one of your documents, sent inline so a browser can
    show it (the frontend opens it at a cited page).
    """
    document = get_document_by_id(db, document_id, current_user.id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    path = upload_path(document.filename)
    if path is None or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="The PDF file for this document is missing")

    # Stored as "<uuid>_<original name>"; send the original name back
    original_name = document.filename.split("_", 1)[-1]
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=original_name,
        content_disposition_type="inline"
    )


@router.get("/{document_id}/search")
def search_document(
    document_id: int,
    q: str,
    top_k: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Semantic search within a document.
    
    ?q=your question here
    ?top_k=5 (how many chunks to return)
    
    This is the retrieval part of RAG; POST /query/ adds answer
    generation on top of it.
    """
    document = get_document_by_id(db, document_id, current_user.id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status != "processed":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not ready yet. Status: {document.status}"
        )
    
    # Find relevant chunks using vector similarity
    chunks = semantic_search(db, q, document_id, top_k)
    
    return {
        "query": q,
        "document_id": document_id,
        "results": [
            {
                "chunk_index": chunk.chunk_index,
                "page_number": chunk.page_number,
                "content": chunk.content,
                "relevance_rank": i + 1
            }
            for i, chunk in enumerate(chunks)
        ],
        "total_results": len(chunks)
    }


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a document, its chunks and its uploaded PDF file.
    """
    document = get_document_by_id(db, document_id, current_user.id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Chunks are deleted too: Document.chunks has cascade="all, delete-orphan",
    # and chunks.document_id has ON DELETE CASCADE in the database.
    filename = document.filename
    db.delete(document)
    db.commit()

    # The file goes after the commit: if the commit failed, the document
    # would still exist without its file. A file left behind is only logged.
    if not delete_upload_file(filename):
        logger.warning("Document %s deleted, but no file %r was removed", document_id, filename)

    return None  # 204 No Content