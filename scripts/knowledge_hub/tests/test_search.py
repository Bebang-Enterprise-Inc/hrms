"""Tests for search interface."""

import pytest
from unittest.mock import Mock, patch, MagicMock


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
