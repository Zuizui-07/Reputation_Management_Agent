"""
================================================
  Knowledge Document & Chunk Models
================================================
"""

from sqlalchemy import (
    Column, Integer, String, Text, Enum, DateTime, ForeignKey, JSON,
    func,
)
from sqlalchemy.orm import relationship
from app.database import Base


class KnowledgeDocument(Base):
    """Tracks uploaded company documents (PDFs and scraped URLs)."""

    __tablename__ = "knowledge_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_type = Column(Enum("pdf", "url", name="doc_type_enum"), nullable=False)
    filename = Column(String(500), nullable=False, comment="Original filename or root URL")
    file_path = Column(String(1000), nullable=True, comment="Server-side storage path (PDFs only)")
    status = Column(
        Enum("pending", "processing", "ready", "failed", name="doc_status_enum"),
        nullable=False,
        default="pending",
    )
    total_chunks = Column(Integer, default=0)
    total_pages_crawled = Column(Integer, default=0, comment="For URLs: number of pages crawled")
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    uploaded_at = Column(DateTime, nullable=False, server_default=func.now())
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    chunks = relationship("KnowledgeChunk", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<KnowledgeDocument id={self.id} type={self.doc_type} status={self.status}>"


class KnowledgeChunk(Base):
    """Individual text chunks extracted from documents, stored for audit/debugging."""

    __tablename__ = "knowledge_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    metadata_json = Column(JSON, nullable=True, comment="Page number, URL, section heading, etc.")
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    document = relationship("KnowledgeDocument", back_populates="chunks")

    def __repr__(self):
        return f"<KnowledgeChunk id={self.id} doc={self.document_id} idx={self.chunk_index}>"
