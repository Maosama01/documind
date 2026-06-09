from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class DocumentResponse(BaseModel):
    """Returned after uploading or fetching a document"""
    id: int
    title: str
    filename: str
    status: str
    page_count: Optional[int] = None
    content_preview: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class DocumentListResponse(BaseModel):
    """Returned when listing all documents"""
    documents: List[DocumentResponse]
    total: int

class ChunkResponse(BaseModel):
    """A single text chunk with its source info"""
    id: int
    content: str
    chunk_index: int
    page_number: Optional[int] = None
    document_id: int
    
    class Config:
        from_attributes = True
        