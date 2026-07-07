"""
================================================
  Vector Store — ChromaDB collection management
================================================
Manages persistent ChromaDB collection for storing
and retrieving document embeddings.
"""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.config import settings

logger = logging.getLogger(__name__)

_client = None
_collection = None

COLLECTION_NAME = "company_knowledge"


def _ensure_client():
    """Initialize ChromaDB persistent client."""
    global _client, _collection
    if _client is None:
        persist_dir = Path(settings.CHROMA_PERSIST_DIR)
        persist_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Initializing ChromaDB at: {persist_dir}")
        _client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"ChromaDB collection '{COLLECTION_NAME}' ready ({_collection.count()} existing vectors)")
    return _client, _collection


def get_vector_store():
    """Get the ChromaDB collection instance."""
    _, collection = _ensure_client()
    return collection


def add_chunks(
    document_id: int,
    chunks: List[Dict[str, Any]],
    embeddings: List[List[float]],
) -> int:
    """
    Add document chunks with embeddings to the vector store.

    Args:
        document_id: Database ID of the parent document.
        chunks: List of { "text": str, "metadata": dict }.
        embeddings: Corresponding embedding vectors.

    Returns:
        Number of chunks added.
    """
    _, collection = _ensure_client()

    if not chunks or not embeddings:
        return 0

    ids = [f"doc{document_id}_chunk{i}" for i in range(len(chunks))]
    documents = [c["text"] for c in chunks]
    metadatas = []
    for c in chunks:
        meta = {**c.get("metadata", {})}
        meta["document_id"] = str(document_id)
        # ChromaDB only allows str, int, float, bool in metadata
        for key, value in list(meta.items()):
            if value is None:
                meta[key] = ""
            elif not isinstance(value, (str, int, float, bool)):
                meta[key] = str(value)
        metadatas.append(meta)

    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    logger.info(f"Added {len(chunks)} chunks for document {document_id} to vector store")
    return len(chunks)


def delete_document(document_id: int) -> int:
    """
    Remove all chunks for a specific document from the vector store.

    Args:
        document_id: Database ID of the document to remove.

    Returns:
        Number of chunks removed.
    """
    _, collection = _ensure_client()

    # Find all chunk IDs for this document
    results = collection.get(
        where={"document_id": str(document_id)},
    )

    if results and results["ids"]:
        collection.delete(ids=results["ids"])
        count = len(results["ids"])
        logger.info(f"Deleted {count} chunks for document {document_id}")
        return count

    logger.info(f"No chunks found for document {document_id}")
    return 0


def query(
    query_embedding: List[float],
    n_results: int = 5,
) -> List[Dict[str, Any]]:
    """
    Query the vector store for similar chunks.

    Args:
        query_embedding: The query embedding vector.
        n_results: Number of results to return.

    Returns:
        List of { "content": str, "metadata": dict, "distance": float }
    """
    _, collection = _ensure_client()

    if collection.count() == 0:
        return []

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, collection.count()),
    )

    output = []
    if results and results["documents"] and results["documents"][0]:
        for i in range(len(results["documents"][0])):
            output.append({
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else 0.0,
            })

    return output


def get_stats() -> Dict[str, Any]:
    """Get vector store statistics."""
    _, collection = _ensure_client()
    return {
        "total_vectors": collection.count(),
        "collection_name": COLLECTION_NAME,
    }
