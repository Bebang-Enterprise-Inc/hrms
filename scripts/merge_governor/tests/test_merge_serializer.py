"""Integration tests for merge serializer with mocked gh commands."""
from __future__ import annotations

import asyncio
import json

import pytest

from scripts.merge_governor.ai_backend_base import ReviewBackend, ReviewResult
from scripts.merge_governor.merge_serializer import MergeSerializer
from scripts.merge_governor.port_allocator import PortAllocator
from scripts.merge_governor.reviewer import Reviewer
from scripts.merge_governor.staging_manager import StagingManager
from scripts.merge_governor.state_manager import PRRecord, StateManager


class MockBackend(ReviewBackend):
    def __init__(self, decision="APPROVE"):
        self._decision = decision

    async def review(self, pr_number, diff_text, merge_context, timeout_s=120):
        return ReviewResult(decision=self._decision, reasoning="mock", confidence=0.9)

    async def chat(self, message, state):
        return "mock"

    async def health_check(self):
        return True


@pytest.fixture
def setup(tmp_path):
    mgr = StateManager(tmp_path / "state")
    mgr.state.production_head = "abc123"
    mgr.state.active_prs["100"] = PRRecord(
        number=100, title="Test PR", head_ref="feature/test",
        head_sha="sha100", updated_at="2026-03-22",
        staging_port=8001, review_decision="APPROVE",
    )
    mgr.state.merge_queue = [100]
    mgr.save()

    port_alloc = PortAllocator(mgr, port_min=8001, port_max=8003)
    port_alloc.allocate(100)

    backend = MockBackend("APPROVE")
    reviewer = Reviewer(backend=backend, state_mgr=mgr)
    staging = StagingManager(mgr, port_alloc, dry_run=True)
    serializer = MergeSerializer(mgr, reviewer, staging, dry_run=True)

    return mgr, serializer, reviewer


class TestMergeSerializerDryRun:
    @pytest.mark.asyncio
    async def test_process_queue_dry_run(self, setup):
        mgr, serializer, _ = setup
        await serializer.process_queue()
        # In dry-run, PR should be removed from queue
        assert 100 not in mgr.state.merge_queue

    @pytest.mark.asyncio
    async def test_paused_skips_processing(self, setup):
        mgr, serializer, _ = setup
        mgr.state.paused = True
        await serializer.process_queue()
        assert 100 in mgr.state.merge_queue  # Still in queue

    @pytest.mark.asyncio
    async def test_unapproved_pr_waits(self, setup):
        mgr, serializer, _ = setup
        mgr.state.active_prs["100"].review_decision = "REJECT"
        await serializer.process_queue()
        assert 100 in mgr.state.merge_queue  # Still waiting

    @pytest.mark.asyncio
    async def test_empty_queue_noop(self, setup):
        mgr, serializer, _ = setup
        mgr.state.merge_queue = []
        await serializer.process_queue()  # Should not error

    @pytest.mark.asyncio
    async def test_missing_pr_removed_from_queue(self, setup):
        mgr, serializer, _ = setup
        del mgr.state.active_prs["100"]
        await serializer.process_queue()
        assert 100 not in mgr.state.merge_queue


class TestL1SmokeLogic:
    def test_check_url_mock(self):
        """Verify _check_url exists and is async."""
        serializer = MergeSerializer.__new__(MergeSerializer)
        assert asyncio.iscoroutinefunction(serializer._check_url)

    def test_l1_smoke_is_async(self):
        serializer = MergeSerializer.__new__(MergeSerializer)
        assert asyncio.iscoroutinefunction(serializer._l1_smoke_test)


class TestStagingManager:
    @pytest.mark.asyncio
    async def test_should_no_cache(self, tmp_path):
        mgr = StateManager(tmp_path / "state")
        port_alloc = PortAllocator(mgr)
        staging = StagingManager(mgr, port_alloc, dry_run=True)

        assert staging.should_no_cache(["hrms/api/store.py"]) is True
        assert staging.should_no_cache(["hrms/hr/doctype/bei_po/bei_po.json"]) is True
        assert staging.should_no_cache(["frontend/src/App.vue"]) is False
        assert staging.should_no_cache(["README.md"]) is False

    @pytest.mark.asyncio
    async def test_dry_run_deploy(self, tmp_path):
        mgr = StateManager(tmp_path / "state")
        port_alloc = PortAllocator(mgr)
        staging = StagingManager(mgr, port_alloc, dry_run=True)

        pr = PRRecord(
            number=200, title="Test", head_ref="feature/test",
            head_sha="abc", updated_at="now",
        )
        result = await staging.deploy_branch(pr)
        assert result is True
        assert pr.staging_port is not None

    @pytest.mark.asyncio
    async def test_dry_run_teardown(self, tmp_path):
        mgr = StateManager(tmp_path / "state")
        port_alloc = PortAllocator(mgr)
        staging = StagingManager(mgr, port_alloc, dry_run=True)

        pr = PRRecord(
            number=200, title="Test", head_ref="feature/test",
            head_sha="abc", updated_at="now", staging_port=8001,
        )
        port_alloc.allocate(200)
        result = await staging.teardown_branch(pr)
        assert result is True
        assert port_alloc.get_port(200) is None
