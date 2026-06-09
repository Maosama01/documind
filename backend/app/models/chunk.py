from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
# pyrefly: ignore [missing-import]
from pgvector.sqlalchemy import Vector
from app.database import Base

class Chunk(Base):
    __tablename__ = "chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    
    content = Column(Text, nullable=False)
    # The actual text of this chunk
    # e.g., "The payment terms are net 30 days from invoice date..."
    
    chunk_index = Column(Integer, nullable=False)
    # Which chunk number within the document (0, 1, 2, ...)
    # Useful for ordering chunks and showing context
    
    page_number = Column(Integer, nullable=True)
    # Which page of the PDF this chunk came from
    # Used for citations ("Answer found on page 3")
    
    embedding = Column(Vector(384), nullable=True)
    # Vector(384) stores a list of 384 floating point numbers
    # 384 is the dimension of all-MiniLM-L6-v2 embeddings
    # This is what makes semantic search possible
    
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    # Every chunk belongs to a document
    
    document = relationship("Document", backref="chunks")
    # chunk.document → gives you the parent Document
    # document.chunks → gives you all chunks for that document
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<Chunk id={self.id} doc_id={self.document_id} index={self.chunk_index}>"