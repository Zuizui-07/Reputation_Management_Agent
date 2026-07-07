"""
================================================
  Document Processor — Full ingestion pipeline
================================================
Orchestrates: parse → chunk → embed → index
for both PDFs and URLs.
"""

import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models.knowledge_document import KnowledgeDocument, KnowledgeChunk
from app.services.knowledge.pdf_parser import parse_pdf
from app.services.knowledge.url_scraper import crawl_website
from app.services.knowledge.chunker import chunk_documents
from app.services.knowledge.embedder import embed_texts
from app.services.knowledge import vector_store

logger = logging.getLogger(__name__)


async def process_document(
    document: KnowledgeDocument,
    session: AsyncSession,
    max_depth: int = None,
    max_pages: int = None,
) -> bool:
    """
    Process a knowledge document through the full RAG pipeline.

    Flow:
        1. Parse (PDF) or Crawl (URL) → raw text pages
        2. Chunk the text into overlapping segments
        3. Generate embeddings for all chunks
        4. Index embeddings into ChromaDB
        5. Save chunks to DB for audit/debugging
        6. Update document status

    Args:
        document: The KnowledgeDocument ORM record.
        session: Active database session.
        max_depth: For URLs, max crawl depth.
        max_pages: For URLs, max pages to crawl.

    Returns:
        True if processing succeeded, False otherwise.
    """
    if max_depth is None:
        max_depth = settings.RAG_MAX_CRAWL_DEPTH
    if max_pages is None:
        max_pages = settings.RAG_MAX_CRAWL_PAGES

    logger.info(f"═══ Processing document {document.id}: {document.filename} ({document.doc_type}) ═══")

    # Update status to processing
    document.status = "processing"
    await session.flush()

    try:
        # ── Step 1: Extract raw text ──
        if document.doc_type == "pdf":
            raw_pages = parse_pdf(document.file_path)
        elif document.doc_type == "url":
            raw_pages = await crawl_website(
                root_url=document.filename,
                max_depth=max_depth,
                max_pages=max_pages,
            )
            document.total_pages_crawled = len(raw_pages)
        else:
            raise ValueError(f"Unknown document type: {document.doc_type}")

        if not raw_pages:
            raise ValueError("No text could be extracted from the document")

        logger.info(f"Extracted {len(raw_pages)} raw pages/sections")

        # ── Step 2: Chunk the text ──
        chunks = chunk_documents(
            raw_pages,
            chunk_size=settings.RAG_CHUNK_SIZE,
            chunk_overlap=settings.RAG_CHUNK_OVERLAP,
        )

        if not chunks:
            raise ValueError("No chunks generated from the extracted text")

        logger.info(f"Generated {len(chunks)} chunks")

        # ── Step 3: Generate embeddings ──
        chunk_texts = [c["text"] for c in chunks]
        embeddings = embed_texts(chunk_texts)
        logger.info(f"Generated {len(embeddings)} embeddings")

        # ── Step 4: Index into ChromaDB ──
        # First, remove any existing vectors for this doc (in case of re-index)
        vector_store.delete_document(document.id)
        vector_store.add_chunks(document.id, chunks, embeddings)

        # ── Step 5: Save chunks to DB ──
        for i, chunk in enumerate(chunks):
            db_chunk = KnowledgeChunk(
                document_id=document.id,
                chunk_index=i,
                content=chunk["text"],
                metadata_json=chunk.get("metadata"),
            )
            session.add(db_chunk)

        # ── Step 6: Update document status ──
        document.status = "ready"
        document.total_chunks = len(chunks)
        document.processed_at = datetime.now(timezone.utc)
        document.error_message = None

        await session.commit()
        logger.info(f"═══ Document {document.id} processed successfully: {len(chunks)} chunks indexed ═══")
        return True

    except Exception as e:
        logger.error(f"Document processing failed for {document.id}: {e}", exc_info=True)

        # Update status to failed
        document.status = "failed"
        document.error_message = str(e)[:2000]
        document.processed_at = datetime.now(timezone.utc)
        await session.commit()
        return False
