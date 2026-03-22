"""Tests for embedding generation."""

import pytest
from unittest.mock import Mock, patch


def test_generate_embedding_returns_768_dimensions():
    """Embedding should return 768-dimensional vector."""
    from scripts.knowledge_hub.embeddings import generate_embedding

    # Mock the Gemini API response
    mock_response = Mock()
    mock_response.embeddings = [Mock(values=[0.1] * 768)]

    with patch("scripts.knowledge_hub.embeddings.client") as mock_client:
        mock_client.models.embed_content.return_value = mock_response

        result = generate_embedding("test text", task_type="RETRIEVAL_DOCUMENT")

        assert len(result) == 768
        assert all(isinstance(v, float) for v in result)


def test_generate_embedding_uses_correct_task_type():
    """Should pass task_type to Gemini API."""
    from scripts.knowledge_hub.embeddings import generate_embedding

    mock_response = Mock()
    mock_response.embeddings = [Mock(values=[0.1] * 768)]

    with patch("scripts.knowledge_hub.embeddings.client") as mock_client:
        mock_client.models.embed_content.return_value = mock_response

        generate_embedding("test", task_type="RETRIEVAL_QUERY")

        call_args = mock_client.models.embed_content.call_args
        assert call_args.kwargs["config"]["task_type"] == "RETRIEVAL_QUERY"


def test_batch_embeddings_returns_list():
    """Batch embedding should return list of vectors."""
    from scripts.knowledge_hub.embeddings import generate_embeddings_batch

    mock_response = Mock()
    mock_response.embeddings = [Mock(values=[0.1] * 768), Mock(values=[0.2] * 768)]

    with patch("scripts.knowledge_hub.embeddings.client") as mock_client:
        mock_client.models.embed_content.return_value = mock_response

        result = generate_embeddings_batch(["text1", "text2"])

        assert len(result) == 2
        assert len(result[0]) == 768
