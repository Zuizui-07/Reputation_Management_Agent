"""
================================================
  Embedder — Generate text embeddings
================================================
Uses sentence-transformers for local embedding generation.
Lazy-loads the model on first call to avoid slow startup.
"""

import logging
from typing import List
from app.config import settings

logger = logging.getLogger(__name__)

_model = None


def _load_model():
    """Lazy-load the sentence-transformer model."""
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
        logger.info(f"Embedding model loaded (dim={_model.get_sentence_embedding_dimension()})")
    return _model


def get_embedder():
    """Get the loaded embedding model instance."""
    return _load_model()


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for a list of texts.

    Args:
        texts: List of text strings to embed.

    Returns:
        List of embedding vectors (list of floats).
    """
    if not texts:
        return []

    model = _load_model()
    logger.debug(f"Embedding {len(texts)} texts")

    # sentence-transformers returns numpy arrays, convert to list
    embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return [emb.tolist() for emb in embeddings]


def embed_query(query: str) -> List[float]:
    """
    Generate embedding for a single query text.

    Args:
        query: The query text to embed.

    Returns:
        Embedding vector as a list of floats.
    """
    model = _load_model()
    embedding = model.encode([query], show_progress_bar=False, convert_to_numpy=True)
    return embedding[0].tolist()
