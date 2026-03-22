"""Tests for maintenance/forgetting module."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
import uuid


@pytest.fixture
def mock_supabase():
    """Create a mock Supabase client."""
    mock_client = MagicMock()
    with patch("scripts.knowledge_hub.maintenance.get_supabase_client", return_value=mock_client):
        yield mock_client


class TestCleanupUnusedChunks:
    """Tests for cleanup_unused_chunks function."""

    def test_dry_run_does_not_delete(self, mock_supabase):
        """Dry run should find candidates but not delete them."""
        from scripts.knowledge_hub.maintenance import cleanup_unused_chunks

        # Mock response with 3 old, unused chunks
        mock_response = MagicMock()
        mock_response.data = [
            {"id": str(uuid.uuid4()), "document_id": "doc-1", "access_count": 0, "created_at": "2025-01-01T00:00:00"},
            {"id": str(uuid.uuid4()), "document_id": "doc-2", "access_count": 0, "created_at": "2025-01-02T00:00:00"},
            {"id": str(uuid.uuid4()), "document_id": "doc-3", "access_count": 0, "created_at": "2025-01-03T00:00:00"},
        ]
        mock_supabase.table.return_value.select.return_value.lt.return_value.lte.return_value.execute.return_value = mock_response

        result = cleanup_unused_chunks(min_age_days=90, min_access_count=0, dry_run=True)

        assert result["candidates_found"] == 3
        assert result["dry_run"] is True
        assert result["deleted"] == 0
        # Verify delete was NOT called
        mock_supabase.table.return_value.delete.assert_not_called()

    def test_actual_delete_removes_chunks(self, mock_supabase):
        """With dry_run=False, should actually delete chunks."""
        from scripts.knowledge_hub.maintenance import cleanup_unused_chunks

        chunk_ids = [str(uuid.uuid4()) for _ in range(2)]
        mock_response = MagicMock()
        mock_response.data = [
            {"id": chunk_ids[0], "document_id": "doc-1", "access_count": 0, "created_at": "2025-01-01T00:00:00"},
            {"id": chunk_ids[1], "document_id": "doc-2", "access_count": 0, "created_at": "2025-01-02T00:00:00"},
        ]
        mock_supabase.table.return_value.select.return_value.lt.return_value.lte.return_value.execute.return_value = mock_response

        result = cleanup_unused_chunks(min_age_days=90, min_access_count=0, dry_run=False)

        assert result["candidates_found"] == 2
        assert result["dry_run"] is False
        assert result["deleted"] == 2
        # Verify delete was called with correct IDs
        mock_supabase.table.return_value.delete.return_value.in_.assert_called_once_with("id", chunk_ids)

    def test_no_candidates_found(self, mock_supabase):
        """Should handle case with no old unused chunks."""
        from scripts.knowledge_hub.maintenance import cleanup_unused_chunks

        mock_response = MagicMock()
        mock_response.data = []
        mock_supabase.table.return_value.select.return_value.lt.return_value.lte.return_value.execute.return_value = mock_response

        result = cleanup_unused_chunks(min_age_days=90, min_access_count=0, dry_run=False)

        assert result["candidates_found"] == 0
        assert result["deleted"] == 0


class TestCleanupLowQualityChunks:
    """Tests for cleanup_low_quality_chunks function."""

    def test_dry_run_finds_low_quality(self, mock_supabase):
        """Dry run should find low-quality chunks but not delete."""
        from scripts.knowledge_hub.maintenance import cleanup_low_quality_chunks

        mock_response = MagicMock()
        mock_response.data = [
            {"id": str(uuid.uuid4()), "quality_score": 0.1},
            {"id": str(uuid.uuid4()), "quality_score": 0.2},
        ]
        mock_supabase.table.return_value.select.return_value.lt.return_value.execute.return_value = mock_response

        result = cleanup_low_quality_chunks(quality_threshold=0.3, dry_run=True)

        assert result["candidates_found"] == 2
        assert result["dry_run"] is True
        assert result["deleted"] == 0
        mock_supabase.table.return_value.delete.assert_not_called()

    def test_actual_delete_low_quality(self, mock_supabase):
        """With dry_run=False, should delete low-quality chunks."""
        from scripts.knowledge_hub.maintenance import cleanup_low_quality_chunks

        chunk_ids = [str(uuid.uuid4())]
        mock_response = MagicMock()
        mock_response.data = [{"id": chunk_ids[0], "quality_score": 0.15}]
        mock_supabase.table.return_value.select.return_value.lt.return_value.execute.return_value = mock_response

        result = cleanup_low_quality_chunks(quality_threshold=0.3, dry_run=False)

        assert result["candidates_found"] == 1
        assert result["deleted"] == 1
        mock_supabase.table.return_value.delete.return_value.in_.assert_called_once_with("id", chunk_ids)


class TestGetForgettingStats:
    """Tests for get_forgetting_stats function."""

    def test_returns_statistics(self, mock_supabase):
        """Should return comprehensive forgetting statistics."""
        from scripts.knowledge_hub.maintenance import get_forgetting_stats

        # Mock total count
        mock_total = MagicMock()
        mock_total.count = 100

        # Mock never accessed count
        mock_never_accessed = MagicMock()
        mock_never_accessed.count = 25

        # Mock low quality count
        mock_low_quality = MagicMock()
        mock_low_quality.count = 10

        # Set up mock chain for each call
        mock_select = MagicMock()
        mock_select.execute.side_effect = [mock_total, mock_never_accessed, mock_low_quality]
        mock_select.eq.return_value = mock_select
        mock_select.lt.return_value = mock_select
        mock_supabase.table.return_value.select.return_value = mock_select

        stats = get_forgetting_stats()

        assert stats["total_chunks"] == 100
        assert stats["never_accessed"] == 25
        assert stats["low_quality"] == 10
        assert stats["never_accessed_pct"] == 25.0
        assert stats["low_quality_pct"] == 10.0

    def test_handles_empty_database(self, mock_supabase):
        """Should handle case with no chunks gracefully."""
        from scripts.knowledge_hub.maintenance import get_forgetting_stats

        mock_empty = MagicMock()
        mock_empty.count = 0

        mock_select = MagicMock()
        mock_select.execute.return_value = mock_empty
        mock_select.eq.return_value = mock_select
        mock_select.lt.return_value = mock_select
        mock_supabase.table.return_value.select.return_value = mock_select

        stats = get_forgetting_stats()

        assert stats["total_chunks"] == 0
        assert stats["never_accessed"] == 0
        assert stats["low_quality"] == 0
        assert stats["never_accessed_pct"] == 0
        assert stats["low_quality_pct"] == 0
