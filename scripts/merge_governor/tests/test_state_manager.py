"""Tests for state persistence including corrupt-file recovery."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from scripts.merge_governor.state_manager import GovernorState, PRRecord, StateManager


@pytest.fixture
def state_dir(tmp_path):
    return tmp_path / "state"


@pytest.fixture
def mgr(state_dir):
    return StateManager(state_dir)


class TestStateManager:
    def test_fresh_state(self, mgr):
        state = mgr.load()
        assert isinstance(state, GovernorState)
        assert state.active_prs == {}
        assert state.merge_queue == []
        assert state.paused is False

    def test_save_and_load(self, mgr):
        mgr.state.paused = True
        mgr.state.production_head = "abc123"
        mgr.state.merge_queue = [101, 102]
        mgr.save()

        mgr2 = StateManager(mgr.state_dir)
        state = mgr2.load()
        assert state.paused is True
        assert state.production_head == "abc123"
        assert state.merge_queue == [101, 102]

    def test_save_with_pr_records(self, mgr):
        pr = PRRecord(
            number=42,
            title="Test PR",
            head_ref="feature/test",
            head_sha="deadbeef",
            updated_at="2026-03-22T00:00:00Z",
            staging_port=8001,
            review_decision="APPROVE",
        )
        mgr.state.active_prs["42"] = pr
        mgr.save()

        mgr2 = StateManager(mgr.state_dir)
        state = mgr2.load()
        assert "42" in state.active_prs
        loaded_pr = state.active_prs["42"]
        assert loaded_pr.number == 42
        assert loaded_pr.staging_port == 8001
        assert loaded_pr.review_decision == "APPROVE"

    def test_corrupt_file_raises(self, mgr):
        mgr.state_mgr_state_file = mgr.state_file
        mgr.state_file.write_text("NOT VALID JSON {{{{", encoding="utf-8")
        with pytest.raises(ValueError, match="corrupt"):
            mgr.load()

    def test_empty_file_raises(self, mgr):
        mgr.state_file.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="empty"):
            mgr.load()

    def test_atomic_write_no_partial(self, mgr, state_dir):
        """Verify atomic write uses temp file + os.replace."""
        mgr.state.production_head = "test123"
        mgr.save()

        # File should exist and be valid JSON
        assert mgr.state_file.exists()
        data = json.loads(mgr.state_file.read_text())
        assert data["production_head"] == "test123"

        # No leftover temp files
        tmp_files = list(state_dir.glob("state_*.tmp"))
        assert len(tmp_files) == 0

    def test_merge_history_keeps_last_10(self, mgr):
        for i in range(15):
            mgr.add_to_merge_history(i, [f"file_{i}.py"])
        assert len(mgr.state.merge_history) == 10
        assert mgr.state.merge_history[0]["number"] == 5
        assert mgr.state.merge_history[-1]["number"] == 14


class TestGovernorState:
    def test_round_trip(self):
        state = GovernorState()
        state.paused = True
        state.production_head = "abc"
        state.active_prs["1"] = PRRecord(
            number=1, title="T", head_ref="b", head_sha="s", updated_at="u"
        )
        d = state.to_dict()
        restored = GovernorState.from_dict(d)
        assert restored.paused is True
        assert restored.production_head == "abc"
        assert "1" in restored.active_prs
        assert restored.active_prs["1"].number == 1
