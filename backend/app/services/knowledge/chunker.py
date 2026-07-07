"""
================================================
  Text Chunker — Split text into semantic chunks
================================================
Implements recursive character splitting with overlap
for optimal RAG retrieval.
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Hierarchical split separators — try each in order
SEPARATORS = ["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " "]


def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    """
    Recursively split text using hierarchical separators.
    Ensures chunks don't exceed chunk_size and overlap for context continuity.
    """
    # If text fits in one chunk, return it
    if len(text) <= chunk_size:
        return [text]

    # Find the best separator
    best_sep = " "
    for sep in SEPARATORS:
        if sep in text:
            best_sep = sep
            break

    # Split by the separator
    parts = text.split(best_sep)
    chunks = []
    current_chunk = ""

    for part in parts:
        candidate = current_chunk + (best_sep if current_chunk else "") + part

        if len(candidate) <= chunk_size:
            current_chunk = candidate
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = part

            # If a single part exceeds chunk_size, force-split it
            if len(current_chunk) > chunk_size:
                while len(current_chunk) > chunk_size:
                    chunks.append(current_chunk[:chunk_size].strip())
                    current_chunk = current_chunk[chunk_size - chunk_overlap:]

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    # Add overlap between consecutive chunks
    if chunk_overlap > 0 and len(chunks) > 1:
        overlapped_chunks = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_tail = chunks[i - 1][-chunk_overlap:]
            overlapped_chunks.append(prev_tail + " " + chunks[i])
        chunks = overlapped_chunks

    return chunks


def chunk_text(
    text: str,
    metadata: Dict[str, Any],
    chunk_size: int = 2000,
    chunk_overlap: int = 200,
) -> List[Dict[str, Any]]:
    """
    Split text into overlapping chunks with metadata.

    Args:
        text: The full text to chunk.
        metadata: Metadata to attach to each chunk (page, url, etc.).
        chunk_size: Maximum characters per chunk (default: 2000 ≈ ~500 tokens).
        chunk_overlap: Overlap between consecutive chunks (default: 200).

    Returns:
        List of dicts: [{ "text": str, "metadata": { ...original_metadata, "chunk_index": int } }]
    """
    if not text or not text.strip():
        return []

    raw_chunks = _split_text(text.strip(), chunk_size, chunk_overlap)

    # Filter out tiny chunks (< 30 chars are usually noise)
    chunks = [c for c in raw_chunks if len(c) >= 30]

    result = []
    for i, chunk in enumerate(chunks):
        result.append({
            "text": chunk,
            "metadata": {
                **metadata,
                "chunk_index": i,
                "chunk_length": len(chunk),
            },
        })

    logger.debug(f"Chunked {len(text)} chars → {len(result)} chunks")
    return result


def chunk_documents(
    documents: List[Dict[str, Any]],
    chunk_size: int = 2000,
    chunk_overlap: int = 200,
) -> List[Dict[str, Any]]:
    """
    Chunk a list of documents (from PDF parser or URL scraper).

    Args:
        documents: List of { "text": str, "metadata": dict }
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Overlap between chunks.

    Returns:
        Flat list of all chunks across all documents.
    """
    all_chunks = []
    for doc in documents:
        chunks = chunk_text(doc["text"], doc["metadata"], chunk_size, chunk_overlap)
        all_chunks.extend(chunks)

    logger.info(f"Chunked {len(documents)} documents → {len(all_chunks)} total chunks")
    return all_chunks
