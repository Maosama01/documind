# pyrefly: ignore [missing-import]
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import relationship
# pyrefly: ignore [missing-import]
from sqlalchemy.sql import func
from app.database import Base

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    
    title = Column(String, nullable=False)
    # The display name of the document
    
    filename = Column(String, nullable=False)
    # Original filename when uploaded
    
    s3_key = Column(String, nullable=True)
    # Not used: nothing stores files in S3. Uploaded PDFs are saved to the
    # local uploads/ folder (see pdf_service.py). The column stays so existing
    # databases still match the model; there are no migrations to drop it.
    
    file_size = Column(Integer, nullable=True)
    # Size in bytes
    
    status = Column(String, default="pending")
    # Tracks processing state:
    # "pending" → just uploaded
    # "processing" → being chunked and embedded
    # "processed" → ready for querying
    # "failed" → something went wrong
    
    error_message = Column(Text, nullable=True)
    # Why processing failed, in words safe to show the user (the full error is
    # in the server log). None unless status is "failed".

    page_count = Column(Integer, nullable=True)
    
    content_preview = Column(Text, nullable=True)
    # First 500 characters of the document
    # Useful for showing previews without loading full content
    
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # ForeignKey links this to the users table
    # Every document belongs to a user
    # "users.id" means the "id" column of the "users" table
    
    owner = relationship("User", backref="documents")
    # This creates a Python relationship:
    # document.owner → gives you the User object
    # user.documents → gives you all documents for that user
    # backref="documents" creates the reverse relationship automatically

    chunks = relationship(
        "Chunk",
        back_populates="document",
        cascade="all, delete-orphan"
    )
    # document.chunks → gives you all chunks for that document
    # cascade="all, delete-orphan": db.delete(document) also deletes its chunks,
    # and a chunk removed from document.chunks is deleted instead of being left
    # with no parent. SQLAlchemy loads and deletes the chunks itself, so this works
    # even on a database whose foreign key was created before ON DELETE CASCADE.

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<Document id={self.id} title={self.title} status={self.status}>"