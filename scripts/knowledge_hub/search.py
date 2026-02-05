"""Search interface for Knowledge Hub with RAG context formatting."""

from typing import List, Dict, Any, Optional

from .embeddings import generate_embedding
from .storage import search_chunks


def search(
    query: str,
    top_k: int = None,
    threshold: float = None
) -> List[Dict[str, Any]]:
    """
    Search for relevant chunks using semantic similarity.

    Args:
        query: Search query text
        top_k: Maximum number of results to return (default from config)
        threshold: Minimum similarity threshold (default from config)

    Returns:
        List of formatted results with keys:
        - title: Document title
        - section: Section title (may be None)
        - content: Chunk content text
        - source: Source file path
        - score: Similarity score (0-1)
    """
    # Generate query embedding using RETRIEVAL_QUERY task type
    query_embedding = generate_embedding(query, task_type="RETRIEVAL_QUERY")

    # Search for similar chunks
    kwargs = {}
    if top_k is not None:
        kwargs["match_count"] = top_k
    if threshold is not None:
        kwargs["match_threshold"] = threshold

    raw_results = search_chunks(query_embedding, **kwargs)

    # Format results
    formatted_results = []
    for chunk in raw_results:
        formatted_results.append({
            "title": chunk.get("document_title"),
            "section": chunk.get("section_title"),
            "content": chunk.get("content"),
            "source": chunk.get("source_path"),
            "score": chunk.get("similarity")
        })

    return formatted_results


def search_with_context(
    query: str,
    top_k: int = None,
    threshold: float = None
) -> str:
    """
    Search and format results for RAG context with numbered citations.

    Args:
        query: Search query text
        top_k: Maximum number of results to return (default from config)
        threshold: Minimum similarity threshold (default from config)

    Returns:
        Formatted context string with numbered citations [1], [2], etc.
        Returns empty string if no results found.
    """
    # Generate query embedding using RETRIEVAL_QUERY task type
    query_embedding = generate_embedding(query, task_type="RETRIEVAL_QUERY")

    # Search for similar chunks
    kwargs = {}
    if top_k is not None:
        kwargs["match_count"] = top_k
    if threshold is not None:
        kwargs["match_threshold"] = threshold

    raw_results = search_chunks(query_embedding, **kwargs)

    if not raw_results:
        return ""

    # Build context with numbered citations
    context_parts = []
    sources = []

    for i, chunk in enumerate(raw_results, start=1):
        title = chunk.get("document_title", "Unknown")
        section = chunk.get("section_title")
        content = chunk.get("content", "")
        source_path = chunk.get("source_path", "")

        # Build citation header
        if section:
            header = f"[{i}] {title} - {section}"
        else:
            header = f"[{i}] {title}"

        context_parts.append(f"{header}\n{content}")
        sources.append({
            "index": i,
            "title": title,
            "source": source_path
        })

    # Join context parts
    context_body = "\n\n".join(context_parts)

    # Build sources/citations footer
    sources_lines = ["Sources:"]
    for src in sources:
        sources_lines.append(f"[{src['index']}] {src['title']} ({src['source']})")

    sources_footer = "\n".join(sources_lines)

    return f"{context_body}\n\n{sources_footer}"
