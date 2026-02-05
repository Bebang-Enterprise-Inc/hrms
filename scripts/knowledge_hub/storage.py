"""Supabase storage for Knowledge Hub."""

import hashlib
from typing import List, Dict, Any, Optional

from supabase import create_client

from .config import config

# Lazy-initialized Supabase client (allows mocking in tests)
_supabase_client = None


def get_supabase_client():
    """Get or create Supabase client (lazy initialization).

    This function is designed to be easily mockable in tests.
    """
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(config.supabase_url, config.supabase_key)
    return _supabase_client


def store_document(
    title: str,
    source_type: str,
    source_path: str,
    file_id: str = None,
    mime_type: str = None,
    file_size_bytes: int = None,
    owner_email: str = None,
    category: str = None,
    metadata: Dict = None
) -> str:
    """Store a document record.

    Args:
        title: Document title
        source_type: Source type ('local', 'gdrive', 'url')
        source_path: Path or URL to the source
        file_id: Optional unique file identifier (e.g., Google Drive file ID)
        mime_type: Optional MIME type
        file_size_bytes: Optional file size in bytes
        owner_email: Optional owner email
        category: Optional document category
        metadata: Optional additional metadata dict

    Returns:
        Document UUID as string
    """
    doc_data = {
        "title": title,
        "source_type": source_type,
        "source_path": source_path,
        "file_id": file_id,
        "mime_type": mime_type,
        "file_size_bytes": file_size_bytes,
        "owner_email": owner_email,
        "category": category,
        "metadata": metadata or {},
        "status": "processing"
    }

    client = get_supabase_client()
    response = client.table("kb_documents").insert(doc_data).execute()
    return response.data[0]["id"]


def store_chunks(
    document_id: str,
    chunks: List[Dict[str, Any]],
    embeddings: List[List[float]]
) -> List[str]:
    """Store chunks with their embeddings.

    Args:
        document_id: Parent document UUID
        chunks: List of chunk dicts with 'content', 'chunk_index', 'char_count',
                and optional 'section_title'
        embeddings: List of embedding vectors (must match chunks length)

    Returns:
        List of chunk UUIDs
    """
    chunk_records = []
    for chunk, embedding in zip(chunks, embeddings):
        content_hash = hashlib.sha256(chunk["content"].encode()).hexdigest()
        chunk_records.append({
            "document_id": document_id,
            "chunk_index": chunk["chunk_index"],
            "section_title": chunk.get("section_title"),
            "content": chunk["content"],
            "content_hash": content_hash,
            "char_count": chunk["char_count"],
            "embedding": embedding
        })

    client = get_supabase_client()
    response = client.table("kb_chunks").insert(chunk_records).execute()
    return [r["id"] for r in response.data]


def update_document_status(document_id: str, status: str, error_message: str = None) -> None:
    """Update document processing status.

    Args:
        document_id: Document UUID
        status: New status ('processing', 'completed', 'failed')
        error_message: Optional error message (for failed status)
    """
    update_data = {"status": status}
    if error_message:
        update_data["error_message"] = error_message

    client = get_supabase_client()
    client.table("kb_documents").update(update_data).eq("id", document_id).execute()


def document_exists(file_id: str) -> bool:
    """Check if document already exists by file_id.

    Args:
        file_id: Unique file identifier to check

    Returns:
        True if document exists, False otherwise
    """
    client = get_supabase_client()
    response = client.table("kb_documents").select("id").eq("file_id", file_id).execute()
    return len(response.data) > 0


def search_chunks(
    query_embedding: List[float],
    match_count: int = None,
    match_threshold: float = None
) -> List[Dict[str, Any]]:
    """Search for similar chunks using vector similarity.

    Args:
        query_embedding: Query vector (768 dimensions for Gemini)
        match_count: Max number of results (default from config)
        match_threshold: Minimum similarity threshold (default from config)

    Returns:
        List of matching chunks with similarity scores
    """
    match_count = match_count or config.default_match_count
    match_threshold = match_threshold or config.default_match_threshold

    client = get_supabase_client()
    response = client.rpc(
        "match_chunks",
        {
            "query_embedding": query_embedding,
            "match_count": match_count,
            "match_threshold": match_threshold
        }
    ).execute()

    return response.data
