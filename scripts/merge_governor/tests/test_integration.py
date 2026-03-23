"""Integration test: mock both backends, simulate review → approve → merge flow."""
from __future__ import annotations

import asyncio

import pytest

from scripts.merge_governor.ai_backend_base import ReviewBackend, ReviewResult
from scripts.merge_governor.conflict_detector import ConflictDetector
from scripts.merge_governor.reviewer import Reviewer
from scripts.merge_governor.state_manager import PRRecord, StateManager


class MockBackend(ReviewBackend):
    """Mock backend that always approves."""

    def __init__(self, decision: str = "APPROVE"):
        self._decision = decision
        self.review_calls = 0

    async def review(self, pr_number, diff_text, merge_context, timeout_s=120):
        self.review_calls += 1
        return ReviewResult(
            decision=self._decision,
            reasoning=f"Mock {self._decision}",
            confidence=0.95,
        )

    async def chat(self, message, state):
        return f"Mock response to: {message}"

    async def health_check(self):
        return True


class TestReviewApproveFlow:
    @pytest.fixture
    def mgr(self, tmp_path):
        mgr = StateManager(tmp_path / "state")
        # Simulate a PR in state
        mgr.state.active_prs["100"] = PRRecord(
            number=100,
            title="Add new feature",
            head_ref="feature/new",
            head_sha="abc123",
            updated_at="2026-03-22",
        )
        mgr.state.merge_history = [
            {"number": 99, "touched_files": ["hrms/api/store.py", "hrms/utils/scm_roles.py"]},
        ]
        mgr.save()
        return mgr

    @pytest.mark.asyncio
    async def test_approve_flow(self, mgr):
        backend = MockBackend("APPROVE")
        reviewer = Reviewer(backend=backend, state_mgr=mgr)

        result = await reviewer.review_pr(
            pr_number=100,
            head_sha="abc123",
            diff_text="diff --git a/new_file.py b/new_file.py\n+# new content",
        )

        assert result.decision == "APPROVE"
        assert backend.review_calls == 1

        # Verify state updated
        pr = mgr.state.active_prs["100"]
        assert pr.review_decision == "APPROVE"
        assert pr.review_sha == "abc123"

    @pytest.mark.asyncio
    async def test_reject_flow(self, mgr):
        backend = MockBackend("REJECT")
        reviewer = Reviewer(backend=backend, state_mgr=mgr)

        result = await reviewer.review_pr(
            pr_number=100,
            head_sha="abc123",
            diff_text="diff --git a/hrms/api/store.py b/hrms/api/store.py\n-old\n+new",
        )

        assert result.decision == "REJECT"
        pr = mgr.state.active_prs["100"]
        assert pr.review_decision == "REJECT"

    @pytest.mark.asyncio
    async def test_full_cycle_approve_then_merge(self, mgr):
        """Simulate: detect PR → review → approve → queue → (merge would happen in Phase 3)."""
        backend = MockBackend("APPROVE")
        reviewer = Reviewer(backend=backend, state_mgr=mgr)

        # Step 1: Review
        result = await reviewer.review_pr(100, "abc123", "trivial diff")
        assert result.is_approved

        # Step 2: Add to merge queue
        mgr.state.merge_queue.append(100)
        mgr.save()
        assert 100 in mgr.state.merge_queue

        # Step 3: Merge would be handled by merge_serializer (Phase 3)
        # Simulate post-merge cleanup
        mgr.add_to_merge_history(100, ["new_file.py"])
        mgr.state.merge_queue.remove(100)
        del mgr.state.active_prs["100"]
        mgr.save()

        assert 100 not in mgr.state.merge_queue
        assert "100" not in mgr.state.active_prs
        assert len(mgr.state.merge_history) == 2  # 99 + 100

    @pytest.mark.asyncio
    async def test_stale_review_invalidation(self, mgr):
        """If PR SHA changes after review, cached review should not be used."""
        backend = MockBackend("APPROVE")
        reviewer = Reviewer(backend=backend, state_mgr=mgr)

        # Review at sha1
        await reviewer.review_pr(100, "sha1", "diff v1")
        assert backend.review_calls == 1

        # Force push changes SHA
        await reviewer.review_pr(100, "sha2", "diff v2")
        assert backend.review_calls == 2  # New review triggered


class TestConflictDetectorUnit:
    """Unit tests for conflict report without git calls."""

    def test_conflict_report_construction(self):
        from scripts.merge_governor.conflict_detector import ConflictReport

        report = ConflictReport(
            pr_number=42,
            has_conflicts=True,
            conflicting_files=["hrms/api/store.py"],
            pr_files=["hrms/api/store.py", "hrms/api/new.py"],
            recent_merge_files={99: ["hrms/api/store.py"]},
        )
        assert report.has_conflicts
        assert len(report.conflicting_files) == 1
