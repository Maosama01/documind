from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List

class DocumentResponse(BaseModel):
    """Returned after uploading or fetching a document"""
    # from_attributes lets Pydantic read a SQLAlchemy Document object directly
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    filename: str
    status: str
    error_message: Optional[str] = None  # why processing failed; None otherwise
    page_count: Optional[int] = None
    content_preview: Optional[str] = None
    created_at: datetime

class DocumentListResponse(BaseModel):
    """Returned when listing all documents"""
    documents: List[DocumentResponse]
    total: int

class ChunkResponse(BaseModel):
    """A single text chunk with its source info"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    chunk_index: int
    page_number: Optional[int] = None
    document_id: int
