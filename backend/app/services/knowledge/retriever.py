"""
================================================
  Retriever — RAG context retrieval agent
================================================
Takes a user message, embeds it, searches the vector store,
and returns formatted context for LLM injection.
"""

import logging
from typing import Optional, List, Dict, Any
from app.config import settings
from app.services.knowledge.embedder import embed_query
from app.services.knowledge.vector_store import query as vector_query

logger = logging.getLogger(__name__)


async def retrieve_context(
    message: str,
    top_k: int = None,
) -> Optional[str]:
    """
    Retrieve relevant company knowledge for a given message.

    Args:
        message: The user's message to find relevant context for.
        top_k: Number of results to retrieve (default: from config).

    Returns:
        Formatted context string for LLM injection, or None if no relevant context found.
    """
    if top_k is None:
        top_k = settings.RAG_TOP_K

    try:
        # Embed the query
        query_embedding = embed_query(message)

        # Search vector store
        results = vector_query(query_embedding, n_results=top_k)

        if not results:
            logger.debug("No RAG context found for message")
            return None

        # Filter out low-relevance results (cosine distance > 0.7 means low similarity)
        relevant_results = [r for r in results if r["distance"] < 0.7]

        if not relevant_results:
            logger.debug("All RAG results were below relevance threshold")
            return None

        # Format context for LLM
        context_parts = []
        for i, result in enumerate(relevant_results, 1):
            source = result["metadata"].get("source", result["metadata"].get("url", "Unknown"))
            context_parts.append(
                f"[Source {i}: {source}]\n{result['content']}"
            )

        context = "\n\n---\n\n".join(context_parts)

        logger.info(
            f"Retrieved {len(relevant_results)} relevant chunks for RAG context "
            f"(best distance: {relevant_results[0]['distance']:.3f})"
        )

        return context

    except Exception as e:
        logger.error(f"RAG retrieval error: {e}", exc_info=True)
        return None  # Graceful degradation — don't break reply drafting


def format_rag_context_for_prompt(context: Optional[str]) -> str:
    """
    Format RAG context as a section to inject into the LLM system prompt.

    Args:
        context: Raw context string from retrieve_context(), or None.

    Returns:
        Formatted string to insert into the system prompt.
    """
    if not context:
        return ""

    return f"""
## Company Knowledge Base (use this information to give accurate, specific answers):

{context}

IMPORTANT: Use the above company knowledge to provide specific, accurate information in your reply.
If the knowledge base contains relevant details (products, services, processes, eligibility, rates, etc.),
reference them naturally in your response. Do NOT make up information not found in the knowledge base.
""".strip()
