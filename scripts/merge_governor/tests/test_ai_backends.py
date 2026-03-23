"""Tests for AI backend interface, CLI output parser, and review caching."""
from __future__ import annotations

import json

import pytest

from scripts.merge_governor.ai_backend_base import ReviewBackend, ReviewResult
from scripts.merge_governor.ai_backend_cli import CLIBackend
from scripts.merge_governor.reviewer import Reviewer
from scripts.merge_governor.state_manager import PRRecord, StateManager


class TestReviewResult:
    def test_approved(self):
        r = ReviewResult(decision="APPROVE", reasoning="ok", confidence=0.9)
        assert r.is_approved

    def test_rejected(self):
        r = ReviewResult(decision="REJECT", reasoning="bad", confidence=0.8)
        assert not r.is_approved


class TestCLIParser:
    def setup_method(self):
        self.backend = CLIBackend()

    def test_clean_json(self):
        raw = json.dumps({
            "decision": "APPROVE",
            "reasoning": "Clean PR",
            "confidence": 0.95,
            "conflicting_files": [],
            "suggested_fix": None,
        })
        result = self.backend._parse_response(raw, 42)
        assert result.decision == "APPROVE"
        assert result.confidence == 0.95

    def test_json_with_preamble(self):
        raw = 'Here is my review:\n\n{"decision": "REJECT", "reasoning": "Conflict", "confidence": 0.8, "conflicting_files": ["foo.py"], "suggested_fix": null}'
        result = self.backend._parse_response(raw, 42)
        assert result.decision == "REJECT"
        assert "foo.py" in result.conflicting_files

    def test_json_with_ansi_codes(self):
        raw = '\x1b[32m{"decision": "APPROVE", "reasoning": "ok", "confidence": 0.9, "conflicting_files": [], "suggested_fix": null}\x1b[0m'
        result = self.backend._parse_response(raw, 42)
        assert result.decision == "APPROVE"

    def test_no_json_raises(self):
        with pytest.raises(ValueError, match="No JSON"):
            self.backend._parse_response("This is just text with no JSON", 42)

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Invalid JSON"):
            self.backend._parse_response('{"broken": }', 42)

    def test_invalid_decision_defaults_reject(self):
        raw = '{"decision": "MAYBE", "reasoning": "unsure", "confidence": 0.5}'
        result = self.backend._parse_response(raw, 42)
        assert result.decision == "REJECT"

    def test_confidence_clamped(self):
        raw = '{"decision": "APPROVE", "reasoning": "ok", "confidence": 1.5}'
        result = self.backend._parse_response(raw, 42)
        assert result.confidence == 1.0

        raw2 = '{"decision": "APPROVE", "reasoning": "ok", "confidence": -0.5}'
        result2 = self.backend._parse_response(raw2, 42)
        assert result2.confidence == 0.0

    def test_needs_fix(self):
        raw = '{"decision": "NEEDS_FIX", "reasoning": "missing import", "confidence": 0.7, "suggested_fix": "add import os"}'
        result = self.backend._parse_response(raw, 42)
        assert result.decision == "NEEDS_FIX"
        assert result.suggested_fix == "add import os"


class TestReviewCaching:
    @pytest.fixture
    def mgr(self, tmp_path):
        mgr = StateManager(tmp_path / "state")
        mgr.state.active_prs["42"] = PRRecord(
            number=42, title="T", head_ref="b", head_sha="sha1", updated_at="u"
        )
        return mgr

    @pytest.mark.asyncio
    async def test_no_backend_auto_approves(self, mgr):
        reviewer = Reviewer(backend=None, state_mgr=mgr)
        result = await reviewer.review_pr(42, "sha1", "diff text")
        assert result.decision == "APPROVE"
        assert "skipped" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_cache_hit(self, mgr):
        """Second call with same SHA returns cached result."""
        call_count = 0

        class MockBackend(ReviewBackend):
            async def review(self, pr_number, diff_text, merge_context, timeout_s=120):
                nonlocal call_count
                call_count += 1
                return ReviewResult(decision="APPROVE", reasoning="ok", confidence=0.9)
            async def chat(self, message, state):
                return "hi"
            async def health_check(self):
                return True

        reviewer = Reviewer(backend=MockBackend(), state_mgr=mgr)
        r1 = await reviewer.review_pr(42, "sha1", "diff")
        r2 = await reviewer.review_pr(42, "sha1", "diff")
        assert r1.decision == r2.decision
        assert call_count == 1  # Only called once

    @pytest.mark.asyncio
    async def test_cache_invalidated_on_new_sha(self, mgr):
        call_count = 0

        class MockBackend(ReviewBackend):
            async def review(self, pr_number, diff_text, merge_context, timeout_s=120):
                nonlocal call_count
                call_count += 1
                return ReviewResult(decision="APPROVE", reasoning="ok", confidence=0.9)
            async def chat(self, message, state):
                return "hi"
            async def health_check(self):
                return True

        reviewer = Reviewer(backend=MockBackend(), state_mgr=mgr)
        await reviewer.review_pr(42, "sha1", "diff")
        await reviewer.review_pr(42, "sha2", "diff")
        assert call_count == 2  # Called for each unique SHA
