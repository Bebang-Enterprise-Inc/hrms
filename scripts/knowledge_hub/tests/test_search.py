"""Tests for search interface."""

import pytest
from unittest.mock import Mock, patch, MagicMock, call


def test_search_returns_formatted_results():
    """Search should return formatted results with citations."""
    from scripts.knowledge_hub.search import search

    mock_chunks = [
        {
            "document_title": "Test Doc",
            "section_title": "Introduction",
            "content": "relevant content here",
            "source_path": "/path/to/doc.pptx",
            "similarity": 0.85
        }
    ]

    with patch("scripts.knowledge_hub.search.generate_embedding") as mock_embed, \
         patch("scripts.knowledge_hub.search.search_chunks") as mock_search:

        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = mock_chunks

        results = search("test query")

        assert len(results) == 1
        assert results[0]["title"] == "Test Doc"
        assert results[0]["section"] == "Introduction"
        assert results[0]["content"] == "relevant content here"
        assert results[0]["source"] == "/path/to/doc.pptx"
        assert results[0]["score"] == 0.85
        mock_embed.assert_called_with("test query", task_type="RETRIEVAL_QUERY")


def test_search_with_no_results():
    """Search with no matches should return empty list."""
    from scripts.knowledge_hub.search import search

    with patch("scripts.knowledge_hub.search.generate_embedding") as mock_embed, \
         patch("scripts.knowledge_hub.search.search_chunks") as mock_search:

        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = []

        results = search("obscure query")

        assert results == []


def test_search_passes_top_k_parameter():
    """Search should pass top_k as match_count to search_chunks."""
    from scripts.knowledge_hub.search import search

    with patch("scripts.knowledge_hub.search.generate_embedding") as mock_embed, \
         patch("scripts.knowledge_hub.search.search_chunks") as mock_search:

        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = []

        search("test query", top_k=10)

        mock_search.assert_called_once()
        call_kwargs = mock_search.call_args[1]
        assert call_kwargs["match_count"] == 10


def test_search_passes_threshold_parameter():
    """Search should pass threshold as match_threshold to search_chunks."""
    from scripts.knowledge_hub.search import search

    with patch("scripts.knowledge_hub.search.generate_embedding") as mock_embed, \
         patch("scripts.knowledge_hub.search.search_chunks") as mock_search:

        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = []

        search("test query", threshold=0.7)

        mock_search.assert_called_once()
        call_kwargs = mock_search.call_args[1]
        assert call_kwargs["match_threshold"] == 0.7


def test_search_handles_missing_section_title():
    """Search should handle chunks without section_title."""
    from scripts.knowledge_hub.search import search

    mock_chunks = [
        {
            "document_title": "Test Doc",
            "section_title": None,
            "content": "content without section",
            "source_path": "/path/to/doc.pptx",
            "similarity": 0.80
        }
    ]

    with patch("scripts.knowledge_hub.search.generate_embedding") as mock_embed, \
         patch("scripts.knowledge_hub.search.search_chunks") as mock_search:

        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = mock_chunks

        results = search("test query")

        assert len(results) == 1
        assert results[0]["section"] is None


def test_search_with_context_returns_formatted_string():
    """search_with_context should return formatted context with citations."""
    from scripts.knowledge_hub.search import search_with_context

    mock_chunks = [
        {
            "document_title": "Doc A",
            "section_title": "Section 1",
            "content": "First relevant content.",
            "source_path": "/path/to/docA.pptx",
            "similarity": 0.90
        },
        {
            "document_title": "Doc B",
            "section_title": "Section 2",
            "content": "Second relevant content.",
            "source_path": "/path/to/docB.pdf",
            "similarity": 0.85
        }
    ]

    with patch("scripts.knowledge_hub.search.generate_embedding") as mock_embed, \
         patch("scripts.knowledge_hub.search.search_chunks") as mock_search:

        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = mock_chunks

        context = search_with_context("test query", top_k=5)

        # Should contain numbered citations
        assert "[1]" in context
        assert "[2]" in context
        # Should contain content
        assert "First relevant content." in context
        assert "Second relevant content." in context
        # Should contain source references
        assert "Doc A" in context
        assert "Doc B" in context


def test_search_with_context_empty_results():
    """search_with_context should handle no results gracefully."""
    from scripts.knowledge_hub.search import search_with_context

    with patch("scripts.knowledge_hub.search.generate_embedding") as mock_embed, \
         patch("scripts.knowledge_hub.search.search_chunks") as mock_search:

        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = []

        context = search_with_context("obscure query")

        assert context == ""


def test_search_with_context_includes_citations_footer():
    """search_with_context should include a citations footer with sources."""
    from scripts.knowledge_hub.search import search_with_context

    mock_chunks = [
        {
            "document_title": "Policy Manual",
            "section_title": "Leave Policy",
            "content": "Employees are entitled to 15 days leave.",
            "source_path": "/docs/policy.pptx",
            "similarity": 0.92
        }
    ]

    with patch("scripts.knowledge_hub.search.generate_embedding") as mock_embed, \
         patch("scripts.knowledge_hub.search.search_chunks") as mock_search:

        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = mock_chunks

        context = search_with_context("leave policy")

        # Should have a sources/citations section
        assert "Sources:" in context or "Citations:" in context or "References:" in context
        assert "Policy Manual" in context
        assert "/docs/policy.pptx" in context


def test_search_multiple_results_ordered_by_score():
    """Search results should be returned in order by similarity score."""
    from scripts.knowledge_hub.search import search

    # Storage returns results already sorted, but we verify our formatting preserves order
    mock_chunks = [
        {
            "document_title": "Best Match",
            "section_title": None,
            "content": "best content",
            "source_path": "/path/best.pptx",
            "similarity": 0.95
        },
        {
            "document_title": "Good Match",
            "section_title": None,
            "content": "good content",
            "source_path": "/path/good.pptx",
            "similarity": 0.85
        },
        {
            "document_title": "Fair Match",
            "section_title": None,
            "content": "fair content",
            "source_path": "/path/fair.pptx",
            "similarity": 0.75
        }
    ]

    with patch("scripts.knowledge_hub.search.generate_embedding") as mock_embed, \
         patch("scripts.knowledge_hub.search.search_chunks") as mock_search:

        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = mock_chunks

        results = search("test query")

        assert len(results) == 3
        assert results[0]["title"] == "Best Match"
        assert results[0]["score"] == 0.95
        assert results[1]["title"] == "Good Match"
        assert results[2]["title"] == "Fair Match"


def test_search_with_recency_returns_formatted_results():
    """search_with_recency should return results with similarity, recency, and score."""
    from scripts.knowledge_hub.search import search_with_recency

    mock_rpc_response = Mock()
    mock_rpc_response.data = [
        {
            "chunk_id": "chunk-uuid-1",
            "document_title": "Recent Doc",
            "section_title": "Section A",
            "content": "recent content here",
            "source_path": "/path/to/recent.pptx",
            "similarity": 0.85,
            "recency_score": 0.95,
            "final_score": 0.88,
            "document_date": "2026-02-01"
        },
        {
            "chunk_id": "chunk-uuid-2",
            "document_title": "Older Doc",
            "section_title": None,
            "content": "older content here",
            "source_path": "/path/to/older.pdf",
            "similarity": 0.90,
            "recency_score": 0.50,
            "final_score": 0.78,
            "document_date": "2025-01-15"
        }
    ]

    mock_supabase = Mock()
    mock_rpc = Mock(return_value=Mock(execute=Mock(return_value=mock_rpc_response)))
    mock_supabase.rpc = mock_rpc

    with patch("scripts.knowledge_hub.search.generate_embedding") as mock_embed, \
         patch("scripts.knowledge_hub.search.get_supabase_client") as mock_get_client:

        mock_embed.return_value = [0.1] * 768
        mock_get_client.return_value = mock_supabase

        results = search_with_recency("test query", top_k=5, threshold=0.5)

        # Verify results format
        assert len(results) == 2
        assert results[0]["title"] == "Recent Doc"
        assert results[0]["section"] == "Section A"
        assert results[0]["content"] == "recent content here"
        assert results[0]["source"] == "/path/to/recent.pptx"
        assert results[0]["similarity"] == 0.85
        assert results[0]["recency"] == 0.95
        assert results[0]["score"] == 0.88
        assert results[0]["date"] == "2026-02-01"

        # Verify embedding was called correctly
        mock_embed.assert_called_with("test query", task_type="RETRIEVAL_QUERY")


def test_search_with_recency_calls_correct_rpc():
    """search_with_recency should call match_chunks_with_recency with correct params."""
    from scripts.knowledge_hub.search import search_with_recency

    mock_rpc_response = Mock()
    mock_rpc_response.data = []

    mock_supabase = Mock()
    mock_rpc = Mock(return_value=Mock(execute=Mock(return_value=mock_rpc_response)))
    mock_supabase.rpc = mock_rpc

    with patch("scripts.knowledge_hub.search.generate_embedding") as mock_embed, \
         patch("scripts.knowledge_hub.search.get_supabase_client") as mock_get_client:

        mock_embed.return_value = [0.1] * 768
        mock_get_client.return_value = mock_supabase

        search_with_recency(
            "test query",
            top_k=10,
            threshold=0.6,
            decay_rate=0.02,
            recency_weight=0.4
        )

        # Verify RPC was called with correct parameters
        mock_rpc.assert_called_with(
            "match_chunks_with_recency",
            {
                "query_embedding": [0.1] * 768,
                "match_threshold": 0.6,
                "match_count": 10,
                "decay_rate": 0.02,
                "recency_weight": 0.4
            }
        )


def test_search_with_recency_tracks_chunk_access():
    """search_with_recency should call track_chunk_access for returned chunks."""
    from scripts.knowledge_hub.search import search_with_recency

    mock_rpc_response = Mock()
    mock_rpc_response.data = [
        {
            "chunk_id": "chunk-1",
            "document_title": "Doc",
            "content": "content",
            "source_path": "/path",
            "similarity": 0.8,
            "recency_score": 0.9,
            "final_score": 0.85
        },
        {
            "chunk_id": "chunk-2",
            "document_title": "Doc 2",
            "content": "content 2",
            "source_path": "/path2",
            "similarity": 0.7,
            "recency_score": 0.8,
            "final_score": 0.75
        }
    ]

    mock_track_response = Mock()
    mock_track_response.data = None

    mock_supabase = Mock()
    rpc_calls = []

    def mock_rpc_side_effect(name, params):
        rpc_calls.append((name, params))
        if name == "match_chunks_with_recency":
            return Mock(execute=Mock(return_value=mock_rpc_response))
        elif name == "track_chunk_access":
            return Mock(execute=Mock(return_value=mock_track_response))
        return Mock(execute=Mock(return_value=Mock(data=[])))

    mock_supabase.rpc = Mock(side_effect=mock_rpc_side_effect)

    with patch("scripts.knowledge_hub.search.generate_embedding") as mock_embed, \
         patch("scripts.knowledge_hub.search.get_supabase_client") as mock_get_client:

        mock_embed.return_value = [0.1] * 768
        mock_get_client.return_value = mock_supabase

        search_with_recency("test query")

        # Verify track_chunk_access was called with the chunk IDs
        track_call = [c for c in rpc_calls if c[0] == "track_chunk_access"]
        assert len(track_call) == 1
        assert track_call[0][1] == {"chunk_ids": ["chunk-1", "chunk-2"]}


def test_search_with_recency_no_tracking_on_empty_results():
    """search_with_recency should not call track_chunk_access when no results."""
    from scripts.knowledge_hub.search import search_with_recency

    mock_rpc_response = Mock()
    mock_rpc_response.data = []

    mock_supabase = Mock()
    rpc_calls = []

    def mock_rpc_side_effect(name, params):
        rpc_calls.append((name, params))
        return Mock(execute=Mock(return_value=mock_rpc_response))

    mock_supabase.rpc = Mock(side_effect=mock_rpc_side_effect)

    with patch("scripts.knowledge_hub.search.generate_embedding") as mock_embed, \
         patch("scripts.knowledge_hub.search.get_supabase_client") as mock_get_client:

        mock_embed.return_value = [0.1] * 768
        mock_get_client.return_value = mock_supabase

        results = search_with_recency("test query")

        assert results == []
        # Only match_chunks_with_recency should be called, not track_chunk_access
        assert len(rpc_calls) == 1
        assert rpc_calls[0][0] == "match_chunks_with_recency"


def test_search_with_recency_handles_missing_optional_fields():
    """search_with_recency should handle chunks with missing optional fields."""
    from scripts.knowledge_hub.search import search_with_recency

    mock_rpc_response = Mock()
    mock_rpc_response.data = [
        {
            "chunk_id": "chunk-1",
            # Missing document_title, section_title, document_date
            "content": "minimal content",
            "source_path": "/path/minimal.txt",
            "similarity": 0.75
            # Missing recency_score, final_score
        }
    ]

    mock_supabase = Mock()
    mock_supabase.rpc = Mock(return_value=Mock(execute=Mock(return_value=mock_rpc_response)))

    with patch("scripts.knowledge_hub.search.generate_embedding") as mock_embed, \
         patch("scripts.knowledge_hub.search.get_supabase_client") as mock_get_client:

        mock_embed.return_value = [0.1] * 768
        mock_get_client.return_value = mock_supabase

        results = search_with_recency("test query")

        assert len(results) == 1
        assert results[0]["title"] == "Unknown"  # Default value
        assert results[0]["section"] is None
        assert results[0]["content"] == "minimal content"
        assert results[0]["similarity"] == 0.75
        assert results[0]["recency"] == 1.0  # Default value
        assert results[0]["score"] == 0.0  # Default value
        assert results[0]["date"] is None
