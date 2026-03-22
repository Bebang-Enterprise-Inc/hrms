"""Text chunking for Knowledge Hub."""

from typing import List, Dict, Any
from .config import config


def chunk_text(
    text: str,
    chunk_size: int = None,
    overlap: int = None,
    separators: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Split text into overlapping chunks.

    Args:
        text: The text to split into chunks.
        chunk_size: Maximum size of each chunk in characters. Defaults to config.chunk_size.
        overlap: Number of characters to overlap between chunks. Defaults to config.chunk_overlap.
        separators: List of separators to prefer for splitting, in order of preference.
            Defaults to ["\n\n", "\n", ". ", " "].

    Returns:
        List of chunk dictionaries, each containing:
            - content: The chunk text
            - chunk_index: Zero-based index of the chunk
            - char_count: Character count of the chunk content
    """
    chunk_size = chunk_size or config.chunk_size
    overlap = overlap or config.chunk_overlap
    separators = separators or ["\n\n", "\n", ". ", " "]

    # Handle empty text
    if not text or not text.strip():
        return []

    # If text fits in one chunk, return it directly
    if len(text) <= chunk_size:
        return [{"content": text, "chunk_index": 0, "char_count": len(text)}]

    chunks = []
    start = 0
    chunk_index = 0

    while start < len(text):
        # Calculate the end position for this chunk
        end = min(start + chunk_size, len(text))

        # If we're not at the end of the text, try to find a good break point
        if end < len(text):
            best_break = end
            # Search for separators in the latter half of the chunk
            for sep in separators:
                search_start = max(start + chunk_size // 2, start)
                last_sep = text.rfind(sep, search_start, end)
                if last_sep != -1:
                    best_break = last_sep + len(sep)
                    break
            end = best_break

        # Extract and clean the chunk content
        chunk_content = text[start:end].strip()

        if chunk_content:
            chunks.append({
                "content": chunk_content,
                "chunk_index": chunk_index,
                "char_count": len(chunk_content)
            })
            chunk_index += 1

        # Move start position, accounting for overlap
        if end >= len(text):
            break

        start = end - overlap
        # Ensure we make forward progress
        if start <= chunks[-1]["chunk_index"] if chunks else 0:
            start = end

    return chunks
