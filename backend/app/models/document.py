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
    # Where the file is stored in AWS S3 (Week 6)
    # Nullable for now since we don't have S3 yet
    
    file_size = Column(Integer, nullable=True)
    # Size in bytes
    
    status = Column(String, default="pending")
    # Tracks processing state:
    # "pending" → just uploaded
    # "processing" → being chunked and embedded
    # "processed" → ready for querying
    # "failed" → something went wrong
    
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
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<Document id={self.id} title={self.title} status={self.status}>"