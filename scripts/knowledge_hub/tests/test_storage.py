"""Tests for Supabase storage."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import uuid


@pytest.fixture
def mock_supabase():
    """Create a mock Supabase client."""
    mock_client = MagicMock()
    with patch("scripts.knowledge_hub.storage.get_supabase_client", return_value=mock_client):
        yield mock_client


def test_store_document_returns_id(mock_supabase):
    """Storing document should return UUID."""
    from scripts.knowledge_hub.storage import store_document

    doc_uuid = str(uuid.uuid4())
    mock_response = MagicMock()
    mock_response.data = [{"id": doc_uuid}]
    mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_response

    doc_id = store_document(
        title="Test Doc",
        source_type="local",
        source_path="/test/path.txt"
    )

    assert doc_id is not None
    assert isinstance(doc_id, str)
    assert doc_id == doc_uuid


def test_store_document_with_all_fields(mock_supabase):
    """Should store document with all optional fields."""
    from scripts.knowledge_hub.storage import store_document

    doc_uuid = str(uuid.uuid4())
    mock_response = MagicMock()
    mock_response.data = [{"id": doc_uuid}]
    mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_response

    doc_id = store_document(
        title="Full Doc",
        source_type="gdrive",
        source_path="/path/to/doc.pdf",
        file_id="drive-abc123",
        mime_type="application/pdf",
        file_size_bytes=1024,
        owner_email="user@bebang.ph",
        category="policy",
        metadata={"tags": ["hr", "policy"]}
    )

    assert doc_id == doc_uuid
    # Verify insert was called with correct data
    call_args = mock_supabase.table.return_value.insert.call_args[0][0]
    assert call_args["title"] == "Full Doc"
    assert call_args["source_type"] == "gdrive"
    assert call_args["file_id"] == "drive-abc123"
    assert call_args["status"] == "processing"


def test_store_chunks_with_embeddings(mock_supabase):
    """Should store chunks with their embeddings."""
    from scripts.knowledge_hub.storage import store_chunks

    mock_response = MagicMock()
    mock_response.data = [{"id": str(uuid.uuid4())}, {"id": str(uuid.uuid4())}]
    mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_response

    chunks = [
        {"content": "chunk 1", "chunk_index": 0, "char_count": 7},
        {"content": "chunk 2", "chunk_index": 1, "char_count": 7}
    ]
    embeddings = [[0.1] * 768, [0.2] * 768]

    chunk_ids = store_chunks("doc-123", chunks, embeddings)

    assert len(chunk_ids) == 2


def test_store_chunks_includes_content_hash(mock_supabase):
    """Chunks should include content hash for deduplication."""
    from scripts.knowledge_hub.storage import store_chunks
    import hashlib

    mock_response = MagicMock()
    mock_response.data = [{"id": str(uuid.uuid4())}]
    mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_response

    chunks = [{"content": "test content", "chunk_index": 0, "char_count": 12}]
    embeddings = [[0.1] * 768]

    store_chunks("doc-123", chunks, embeddings)

    # Verify content hash was computed
    call_args = mock_supabase.table.return_value.insert.call_args[0][0]
    expected_hash = hashlib.sha256("test content".encode()).hexdigest()
    assert call_args[0]["content_hash"] == expected_hash


def test_store_chunks_with_section_title(mock_supabase):
    """Chunks can include optional section title."""
    from scripts.knowledge_hub.storage import store_chunks

    mock_response = MagicMock()
    mock_response.data = [{"id": str(uuid.uuid4())}]
    mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_response

    chunks = [
        {
            "content": "chunk content",
            "chunk_index": 0,
            "char_count": 13,
            "section_title": "Introduction"
        }
    ]
    embeddings = [[0.1] * 768]

    store_chunks("doc-123", chunks, embeddings)

    call_args = mock_supabase.table.return_value.insert.call_args[0][0]
    assert call_args[0]["section_title"] == "Introduction"


def test_document_exists_by_file_id(mock_supabase):
    """Should check if document already exists."""
    from scripts.knowledge_hub.storage import document_exists

    mock_response = MagicMock()
    mock_response.data = [{"id": "existing-id"}]
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

    exists = document_exists(file_id="drive-file-123")

    assert exists is True


def test_document_not_exists(mock_supabase):
    """Should return False when document doesn't exist."""
    from scripts.knowledge_hub.storage import document_exists

    mock_response = MagicMock()
    mock_response.data = []
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

    exists = document_exists(file_id="non-existent-file")

    assert exists is False


def test_update_document_status(mock_supabase):
    """Should update document processing status."""
    from scripts.knowledge_hub.storage import update_document_status

    update_document_status("doc-123", "completed")

    mock_supabase.table.assert_called_with("kb_documents")
    mock_supabase.table.return_value.update.assert_called()


def test_update_document_status_with_error(mock_supabase):
    """Should update status with error message."""
    from scripts.knowledge_hub.storage import update_document_status

    update_document_status("doc-123", "failed", error_message="Parse error")

    call_args = mock_supabase.table.return_value.update.call_args[0][0]
    assert call_args["status"] == "failed"
    assert call_args["error_message"] == "Parse error"


def test_search_returns_results(mock_supabase):
    """Search should return matching chunks."""
    from scripts.knowledge_hub.storage import search_chunks

    mock_response = MagicMock()
    mock_response.data = [
        {
            "chunk_id": str(uuid.uuid4()),
            "document_title": "Test Doc",
            "content": "relevant content",
            "similarity": 0.85
        }
    ]
    mock_supabase.rpc.return_value.execute.return_value = mock_response

    results = search_chunks([0.1] * 768)

    assert len(results) == 1
    assert results[0]["similarity"] == 0.85


def test_search_uses_default_params(mock_supabase):
    """Search should use default match count and threshold."""
    from scripts.knowledge_hub.storage import search_chunks
    from scripts.knowledge_hub.config import config

    mock_response = MagicMock()
    mock_response.data = []
    mock_supabase.rpc.return_value.execute.return_value = mock_response

    search_chunks([0.1] * 768)

    # Verify RPC was called with default params
    mock_supabase.rpc.assert_called_once()
    call_args = mock_supabase.rpc.call_args[0]
    assert call_args[0] == "match_chunks"
    call_params = mock_supabase.rpc.call_args[0][1]
    assert call_params["match_count"] == config.default_match_count
    assert call_params["match_threshold"] == config.default_match_threshold


def test_search_with_custom_params(mock_supabase):
    """Search should accept custom match count and threshold."""
    from scripts.knowledge_hub.storage import search_chunks

    mock_response = MagicMock()
    mock_response.data = []
    mock_supabase.rpc.return_value.execute.return_value = mock_response

    search_chunks([0.1] * 768, match_count=10, match_threshold=0.7)

    call_params = mock_supabase.rpc.call_args[0][1]
    assert call_params["match_count"] == 10
    assert call_params["match_threshold"] == 0.7


def test_search_empty_results(mock_supabase):
    """Search should handle empty results gracefully."""
    from scripts.knowledge_hub.storage import search_chunks

    mock_response = MagicMock()
    mock_response.data = []
    mock_supabase.rpc.return_value.execute.return_value = mock_response

    results = search_chunks([0.1] * 768)

    assert results == []
    assert isinstance(results, list)
