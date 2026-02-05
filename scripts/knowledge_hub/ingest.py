"""Document ingestion pipeline for Knowledge Hub.

This module provides the main entry points for ingesting documents into the
Knowledge Hub. It coordinates extraction, chunking, embedding generation,
and storage.
"""

from pathlib import Path
from typing import Dict, Any, Optional

from .chunker import chunk_text
from .embeddings import generate_embeddings_batch
from .extractors import pptx_to_text
from .storage import (
    store_document,
    store_chunks,
    update_document_status,
    document_exists,
)


# MIME type mapping for supported file extensions
MIME_TYPES = {
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# Supported extensions for text extraction
SUPPORTED_EXTENSIONS = {".pptx", ".txt", ".md"}


def _get_mime_type(suffix: str) -> str:
    """Get MIME type for a file extension.

    Args:
        suffix: File extension including dot (e.g., ".pptx")

    Returns:
        MIME type string, or "application/octet-stream" for unknown extensions
    """
    return MIME_TYPES.get(suffix.lower(), "application/octet-stream")


def extract_content(file_path: str) -> str:
    """Extract text content from a file based on its extension.

    Args:
        file_path: Path to the file to extract content from

    Returns:
        Extracted text content

    Raises:
        ValueError: If file type is not supported
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pptx":
        return pptx_to_text(file_path)
    elif suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8")
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def ingest_local_file(
    file_path: str,
    category: str = None,
    metadata: Dict[str, Any] = None,
    title: str = None,
) -> Dict[str, Any]:
    """Ingest a local file into the Knowledge Hub.

    This is the main entry point for local file ingestion. It performs:
    1. Content extraction based on file type
    2. Text chunking
    3. Embedding generation
    4. Storage in Supabase

    Args:
        file_path: Path to the local file
        category: Optional document category (e.g., "mancom", "training")
        metadata: Optional additional metadata dictionary
        title: Optional document title (defaults to filename stem)

    Returns:
        Dictionary containing:
        - document_id: UUID of the created document
        - chunks_created: Number of chunks created
        - error: Error message if ingestion failed (None on success)
    """
    path = Path(file_path)
    doc_title = title or path.stem
    mime_type = _get_mime_type(path.suffix)
    file_size = path.stat().st_size if path.exists() else None

    # Create document record first (status: processing)
    doc_id = store_document(
        title=doc_title,
        source_type="local",
        source_path=str(path.absolute()),
        mime_type=mime_type,
        file_size_bytes=file_size,
        category=category,
        metadata=metadata,
    )

    try:
        # Extract content
        content = extract_content(file_path)

        # Chunk the content
        chunks = chunk_text(content)

        # Generate embeddings for all chunks
        chunk_texts = [c["content"] for c in chunks]
        embeddings = generate_embeddings_batch(chunk_texts)

        # Store chunks with embeddings
        chunk_ids = store_chunks(doc_id, chunks, embeddings)

        # Update status to completed
        update_document_status(doc_id, "completed", None)

        return {
            "document_id": doc_id,
            "chunks_created": len(chunk_ids),
            "error": None,
        }

    except Exception as e:
        # Update status to failed
        update_document_status(doc_id, "failed", str(e))
        return {
            "document_id": doc_id,
            "chunks_created": 0,
            "error": str(e),
        }


def ingest_drive_file(
    file_id: str,
    title: str,
    content: str = None,
    category: str = None,
    mime_type: str = None,
    file_size_bytes: int = None,
    owner_email: str = None,
    metadata: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Ingest a Google Drive file into the Knowledge Hub.

    This function handles Google Drive files that have already been exported/
    extracted. It includes deduplication check via file_id.

    Args:
        file_id: Google Drive file ID (used for deduplication)
        title: Document title
        content: Pre-extracted text content from the Drive file
        category: Optional document category
        mime_type: Optional MIME type from Drive
        file_size_bytes: Optional file size
        owner_email: Optional owner email from Drive
        metadata: Optional additional metadata

    Returns:
        Dictionary containing:
        - document_id: UUID of the created document (None if skipped)
        - chunks_created: Number of chunks created
        - skipped: True if file was already ingested
        - reason: Reason for skipping (if skipped)
        - error: Error message if ingestion failed
    """
    # Check for duplicates
    if document_exists(file_id):
        return {
            "document_id": None,
            "chunks_created": 0,
            "skipped": True,
            "reason": f"Document with file_id '{file_id}' already exists",
            "error": None,
        }

    # Create document record (status: processing)
    doc_id = store_document(
        title=title,
        source_type="gdrive",
        source_path=f"https://drive.google.com/file/d/{file_id}",
        file_id=file_id,
        mime_type=mime_type,
        file_size_bytes=file_size_bytes,
        owner_email=owner_email,
        category=category,
        metadata=metadata,
    )

    try:
        # Chunk the content
        chunks = chunk_text(content or "")

        # Generate embeddings for all chunks
        chunk_texts = [c["content"] for c in chunks]
        embeddings = generate_embeddings_batch(chunk_texts) if chunk_texts else []

        # Store chunks with embeddings
        chunk_ids = store_chunks(doc_id, chunks, embeddings) if chunks else []

        # Update status to completed
        update_document_status(doc_id, "completed", None)

        return {
            "document_id": doc_id,
            "chunks_created": len(chunk_ids),
            "skipped": False,
            "reason": None,
            "error": None,
        }

    except Exception as e:
        # Update status to failed
        update_document_status(doc_id, "failed", str(e))
        return {
            "document_id": doc_id,
            "chunks_created": 0,
            "skipped": False,
            "reason": None,
            "error": str(e),
        }
