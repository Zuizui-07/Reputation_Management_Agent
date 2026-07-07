"""
================================================
  Knowledge Base Router — Superadmin API endpoints
================================================
Upload PDFs, add URLs, manage knowledge documents.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, BackgroundTasks
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import require_superadmin
from app.database import AsyncSessionLocal
from app.config import settings
from app.models.knowledge_document import KnowledgeDocument, KnowledgeChunk
from app.schemas.knowledge import (
    URLUploadRequest, DocumentOut, DocumentDetailOut, SearchResult,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ──────────────────────────────────────────────
#  Dependency: get DB session
# ──────────────────────────────────────────────
async def get_session():
    async with AsyncSessionLocal() as session:
        yield session


# ──────────────────────────────────────────────
#  POST /upload-pdf — Upload a PDF file
# ──────────────────────────────────────────────
@router.post("/upload-pdf", response_model=DocumentOut)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    admin: dict = Depends(require_superadmin),
    session: AsyncSession = Depends(get_session),
):
    """Upload a PDF document to the knowledge base."""
    # Validate file type
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    if file.size and file.size > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    # Ensure upload directory exists
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Save file
    import uuid
    unique_name = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = upload_dir / unique_name

    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    logger.info(f"PDF saved: {file_path} ({len(content)} bytes)")

    # Create DB record
    document = KnowledgeDocument(
        doc_type="pdf",
        filename=file.filename,
        file_path=str(file_path),
        status="pending",
        uploaded_by=None,  # Could resolve from admin email if needed
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)

    # Process in background
    background_tasks.add_task(_process_document_bg, document.id)

    return document


# ──────────────────────────────────────────────
#  POST /add-url — Submit a URL for crawling
# ──────────────────────────────────────────────
@router.post("/add-url", response_model=DocumentOut)
async def add_url(
    body: URLUploadRequest,
    background_tasks: BackgroundTasks,
    admin: dict = Depends(require_superadmin),
    session: AsyncSession = Depends(get_session),
):
    """Submit a website URL for full-site crawling and indexing."""
    # Basic URL validation
    url = body.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    # Create DB record
    document = KnowledgeDocument(
        doc_type="url",
        filename=url,
        status="pending",
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)

    # Process in background
    background_tasks.add_task(
        _process_document_bg,
        document.id,
        max_depth=body.max_depth,
        max_pages=body.max_pages,
    )

    return document


# ──────────────────────────────────────────────
#  GET /documents — List all knowledge documents
# ──────────────────────────────────────────────
@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    status: Optional[str] = Query(None, description="Filter by status"),
    doc_type: Optional[str] = Query(None, description="Filter by type (pdf/url)"),
    admin: dict = Depends(require_superadmin),
    session: AsyncSession = Depends(get_session),
):
    """List all knowledge base documents."""
    query = select(KnowledgeDocument).order_by(KnowledgeDocument.uploaded_at.desc())

    if status:
        query = query.where(KnowledgeDocument.status == status)
    if doc_type:
        query = query.where(KnowledgeDocument.doc_type == doc_type)

    result = await session.execute(query)
    documents = result.scalars().all()
    return documents


# ──────────────────────────────────────────────
#  GET /documents/{id} — Get document details
# ──────────────────────────────────────────────
@router.get("/documents/{doc_id}", response_model=DocumentDetailOut)
async def get_document(
    doc_id: int,
    admin: dict = Depends(require_superadmin),
    session: AsyncSession = Depends(get_session),
):
    """Get document details including chunks."""
    result = await session.execute(
        select(KnowledgeDocument)
        .options(selectinload(KnowledgeDocument.chunks))
        .where(KnowledgeDocument.id == doc_id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return document


# ──────────────────────────────────────────────
#  DELETE /documents/{id} — Delete document
# ──────────────────────────────────────────────
@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: int,
    admin: dict = Depends(require_superadmin),
    session: AsyncSession = Depends(get_session),
):
    """Delete a document and its vectors from the knowledge base."""
    result = await session.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove vectors from ChromaDB
    from app.services.knowledge.vector_store import delete_document as delete_vectors
    deleted_vectors = delete_vectors(doc_id)

    # Remove uploaded file if it exists
    if document.file_path and os.path.exists(document.file_path):
        os.remove(document.file_path)

    # Delete from DB (cascades to chunks)
    await session.delete(document)
    await session.commit()

    return {
        "message": f"Document '{document.filename}' deleted",
        "vectors_removed": deleted_vectors,
    }


# ──────────────────────────────────────────────
#  POST /documents/{id}/reindex — Re-process
# ──────────────────────────────────────────────
@router.post("/documents/{doc_id}/reindex", response_model=DocumentOut)
async def reindex_document(
    doc_id: int,
    background_tasks: BackgroundTasks,
    admin: dict = Depends(require_superadmin),
    session: AsyncSession = Depends(get_session),
):
    """Re-process and re-index a document."""
    result = await session.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete existing chunks
    await session.execute(
        delete(KnowledgeChunk).where(KnowledgeChunk.document_id == doc_id)
    )
    document.status = "pending"
    document.total_chunks = 0
    document.error_message = None
    await session.commit()
    await session.refresh(document)

    # Re-process in background
    background_tasks.add_task(_process_document_bg, doc_id)

    return document


# ──────────────────────────────────────────────
#  GET /search — Test semantic search
# ──────────────────────────────────────────────
@router.get("/search", response_model=list[SearchResult])
async def search_knowledge(
    q: str = Query(..., description="Search query"),
    top_k: int = Query(5, ge=1, le=20, description="Number of results"),
    admin: dict = Depends(require_superadmin),
):
    """Test semantic search against the knowledge base (debug/preview endpoint)."""
    from app.services.knowledge.retriever import retrieve_context
    from app.services.knowledge.embedder import embed_query
    from app.services.knowledge.vector_store import query as vector_query

    query_embedding = embed_query(q)
    raw_results = vector_query(query_embedding, n_results=top_k)

    results = []
    for r in raw_results:
        results.append(SearchResult(
            chunk_content=r["content"],
            document_name=r["metadata"].get("source", r["metadata"].get("url", "Unknown")),
            similarity_score=round(1 - r["distance"], 4),  # Convert distance to similarity
            metadata=r["metadata"],
        ))

    return results


# ──────────────────────────────────────────────
#  GET /stats — Knowledge base statistics
# ──────────────────────────────────────────────
@router.get("/stats")
async def get_stats(
    admin: dict = Depends(require_superadmin),
    session: AsyncSession = Depends(get_session),
):
    """Get knowledge base statistics."""
    from app.services.knowledge.vector_store import get_stats as get_vector_stats

    # Count documents by status
    doc_counts = await session.execute(
        select(
            KnowledgeDocument.status,
            func.count(KnowledgeDocument.id),
        ).group_by(KnowledgeDocument.status)
    )
    status_counts = {row[0]: row[1] for row in doc_counts.all()}

    # Total chunks
    chunk_count = await session.execute(
        select(func.count(KnowledgeChunk.id))
    )
    total_chunks = chunk_count.scalar() or 0

    # Vector store stats
    vector_stats = get_vector_stats()

    return {
        "documents": status_counts,
        "total_chunks_in_db": total_chunks,
        "vector_store": vector_stats,
    }


# ──────────────────────────────────────────────
#  Background processor helper
# ──────────────────────────────────────────────
async def _process_document_bg(
    document_id: int,
    max_depth: int = None,
    max_pages: int = None,
):
    """Background task to process a document through the RAG pipeline."""
    from app.services.knowledge.processor import process_document

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
        )
        document = result.scalar_one_or_none()

        if not document:
            logger.error(f"Document {document_id} not found for background processing")
            return

        await process_document(
            document=document,
            session=session,
            max_depth=max_depth,
            max_pages=max_pages,
        )
