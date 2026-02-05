"""Tests for LLM-powered metadata generation."""

import pytest
from unittest.mock import Mock, patch


def test_generate_chunk_metadata_returns_expected_fields():
    """Chunk metadata should include summary, keywords, questions, and quality score."""
    from scripts.knowledge_hub.metadata import generate_chunk_metadata

    # Mock Gemini API response with valid JSON
    mock_response = Mock()
    mock_response.text = '''{
        "summary": "This chunk discusses employee onboarding procedures.",
        "keywords": ["onboarding", "employee", "hr", "procedures", "training"],
        "potential_questions": [
            "What are the onboarding steps?",
            "How long does onboarding take?"
        ],
        "quality_score": 0.85
    }'''

    with patch("scripts.knowledge_hub.metadata.model") as mock_model:
        mock_model.generate_content.return_value = mock_response

        result = generate_chunk_metadata("Employee onboarding procedures include...")

        assert "summary" in result
        assert "keywords" in result
        assert "potential_questions" in result
        assert "quality_score" in result
        assert isinstance(result["keywords"], list)
        assert isinstance(result["quality_score"], float)
        assert 0.0 <= result["quality_score"] <= 1.0


def test_generate_chunk_metadata_handles_empty_content():
    """Empty content should return default metadata without API call."""
    from scripts.knowledge_hub.metadata import generate_chunk_metadata

    with patch("scripts.knowledge_hub.metadata.model") as mock_model:
        result = generate_chunk_metadata("")

        # Should not call API for empty content
        mock_model.generate_content.assert_not_called()

        assert result["summary"] == ""
        assert result["keywords"] == []
        assert result["potential_questions"] == []
        assert result["quality_score"] == 0.0


def test_generate_chunk_metadata_handles_markdown_wrapped_json():
    """Should parse JSON even when wrapped in markdown code blocks."""
    from scripts.knowledge_hub.metadata import generate_chunk_metadata

    mock_response = Mock()
    mock_response.text = '''```json
{
    "summary": "Policy document summary.",
    "keywords": ["policy", "compliance"],
    "potential_questions": ["What is the policy?"],
    "quality_score": 0.7
}
```'''

    with patch("scripts.knowledge_hub.metadata.model") as mock_model:
        mock_model.generate_content.return_value = mock_response

        result = generate_chunk_metadata("Some policy content here...")

        assert result["summary"] == "Policy document summary."
        assert result["quality_score"] == 0.7


def test_generate_chunk_metadata_clamps_quality_score():
    """Quality score should be clamped between 0.0 and 1.0."""
    from scripts.knowledge_hub.metadata import generate_chunk_metadata

    # Test score > 1.0
    mock_response = Mock()
    mock_response.text = '{"summary": "", "keywords": [], "potential_questions": [], "quality_score": 1.5}'

    with patch("scripts.knowledge_hub.metadata.model") as mock_model:
        mock_model.generate_content.return_value = mock_response

        result = generate_chunk_metadata("Some content")
        assert result["quality_score"] == 1.0

    # Test score < 0.0
    mock_response.text = '{"summary": "", "keywords": [], "potential_questions": [], "quality_score": -0.5}'

    with patch("scripts.knowledge_hub.metadata.model") as mock_model:
        mock_model.generate_content.return_value = mock_response

        result = generate_chunk_metadata("Some content")
        assert result["quality_score"] == 0.0


def test_generate_chunk_metadata_handles_malformed_json():
    """Should return defaults when API returns invalid JSON."""
    from scripts.knowledge_hub.metadata import generate_chunk_metadata

    mock_response = Mock()
    mock_response.text = "This is not valid JSON at all"

    with patch("scripts.knowledge_hub.metadata.model") as mock_model:
        mock_model.generate_content.return_value = mock_response

        result = generate_chunk_metadata("Some content")

        assert result["summary"] == ""
        assert result["keywords"] == []
        assert result["potential_questions"] == []
        assert result["quality_score"] == 0.5  # Default fallback


def test_generate_document_metadata_returns_expected_fields():
    """Document metadata should include summary, keywords, and entities."""
    from scripts.knowledge_hub.metadata import generate_document_metadata

    mock_response = Mock()
    mock_response.text = '''{
        "summary": "A comprehensive guide to BEI employee policies.",
        "keywords": ["bei", "employee", "policies", "hr", "handbook"],
        "entities": {
            "organizations": ["BEI", "Bebang Enterprise Inc"],
            "people": [],
            "topics": ["HR policies", "Employee handbook"]
        }
    }'''

    with patch("scripts.knowledge_hub.metadata.model") as mock_model:
        mock_model.generate_content.return_value = mock_response

        result = generate_document_metadata(
            "This handbook covers all BEI employee policies...",
            "BEI Employee Handbook"
        )

        assert "summary" in result
        assert "keywords" in result
        assert "entities" in result
        assert isinstance(result["entities"], dict)


def test_batch_generate_chunk_metadata_processes_multiple_chunks():
    """Batch function should process multiple chunks and return list."""
    from scripts.knowledge_hub.metadata import batch_generate_chunk_metadata

    mock_response = Mock()
    mock_response.text = '{"summary": "Test", "keywords": ["test"], "potential_questions": [], "quality_score": 0.5}'

    with patch("scripts.knowledge_hub.metadata.model") as mock_model:
        mock_model.generate_content.return_value = mock_response

        chunks = ["Chunk 1 content", "Chunk 2 content", "Chunk 3 content"]
        results = batch_generate_chunk_metadata(chunks)

        assert len(results) == 3
        assert all("summary" in r for r in results)
        assert all("quality_score" in r for r in results)
