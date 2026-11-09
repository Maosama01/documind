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
    
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    # Every chunk belongs to a document.
    # ondelete="CASCADE" puts ON DELETE CASCADE on the foreign key in Postgres,
    # so deleting a document row deletes its chunks even outside SQLAlchemy
    # (e.g. a raw SQL DELETE).
    # index=True creates ix_chunks_document_id: every search is limited to one
    # document, and this index finds that document's chunks without reading
    # the whole table (see semantic_search for why there is no vector index).

    document = relationship("Document", back_populates="chunks")
    # chunk.document → gives you the parent Document
    # The other side (Document.chunks) is defined in document.py
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<Chunk id={self.id} doc_id={self.document_id} index={self.chunk_index}>"