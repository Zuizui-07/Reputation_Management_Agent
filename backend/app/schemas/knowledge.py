"""
================================================
  Knowledge Base — Pydantic Schemas
================================================
"""

from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from datetime import datetime


# ── Requests ──

class URLUploadRequest(BaseModel):
    url: str
    max_depth: int = 3
    max_pages: int = 50


# ── Responses ──

class ChunkOut(BaseModel):
    id: int
    chunk_index: int
    content: str
    metadata_json: Optional[dict] = None

    class Config:
        from_attributes = True


class DocumentOut(BaseModel):
    id: int
    doc_type: str
    filename: str
    status: str
    total_chunks: int
    total_pages_crawled: int
    uploaded_at: datetime
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class DocumentDetailOut(DocumentOut):
    chunks: List[ChunkOut] = []

    class Config:
        from_attributes = True


class SearchResult(BaseModel):
    chunk_content: str
    document_name: str
    similarity_score: float
    metadata: Optional[dict] = None
