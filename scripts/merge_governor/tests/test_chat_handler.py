"""Tests for two-tier chat handler."""
from __future__ import annotations

import pytest

from scripts.merge_governor.chat_handler import ChatHandler
from scripts.merge_governor.state_manager import GovernorState, PRRecord


@pytest.fixture
def state():
    s = GovernorState()
    s.started_at = 1711100000.0
    s.production_head = "abc123def456"
    s.active_prs["42"] = PRRecord(
        number=42, title="Add feature X", head_ref="feature/x",
        head_sha="deadbeef", updated_at="2026-03-22", staging_port=8001,
        review_decision="APPROVE",
    )
    s.merge_queue = [42]
    s.port_registry = {"8001": 42, "8002": None, "8003": None}
    return s


@pytest.fixture
def handler():
    return ChatHandler(ai_backend=None)


class TestKeywordParsing:
    def test_status(self, handler, state):
        resp = handler.parse_keyword("status", state)
        assert resp is not None
        assert "RUNNING" in resp.text
        assert resp.source == "keyword"

    def test_status_shorthand(self, handler, state):
        resp = handler.parse_keyword("s", state)
        assert resp is not None
        assert "Governor Status" in resp.text

    def test_queue(self, handler, state):
        resp = handler.parse_keyword("queue", state)
        assert resp is not None
        assert "PR #42" in resp.text

    def test_queue_shorthand(self, handler, state):
        resp = handler.parse_keyword("q", state)
        assert resp is not None

    def test_help(self, handler, state):
        resp = handler.parse_keyword("help", state)
        assert resp is not None
        assert "Commands" in resp.text

    def test_help_question_mark(self, handler, state):
        resp = handler.parse_keyword("?", state)
        assert resp is not None

    def test_pause(self, handler, state):
        resp = handler.parse_keyword("pause", state)
        assert resp is not None
        assert state.paused is True
        assert "PAUSED" in resp.text

    def test_resume(self, handler, state):
        state.paused = True
        resp = handler.parse_keyword("resume", state)
        assert resp is not None
        assert state.paused is False

    def test_merge_adds_to_queue(self, handler, state):
        state.merge_queue = []
        resp = handler.parse_keyword("merge 99", state)
        assert resp is not None
        assert 99 in state.merge_queue

    def test_merge_duplicate(self, handler, state):
        resp = handler.parse_keyword("merge 42", state)
        assert "already" in resp.text

    def test_skip_removes_from_queue(self, handler, state):
        resp = handler.parse_keyword("skip 42", state)
        assert 42 not in state.merge_queue

    def test_skip_nonexistent(self, handler, state):
        resp = handler.parse_keyword("skip 999", state)
        assert "not in" in resp.text

    def test_history_empty(self, handler, state):
        resp = handler.parse_keyword("history", state)
        assert "No merge history" in resp.text

    def test_ports(self, handler, state):
        resp = handler.parse_keyword("ports", state)
        assert ":8001" in resp.text
        assert "PR #42" in resp.text

    def test_nonkeyword_returns_none(self, handler, state):
        resp = handler.parse_keyword("what's happening with PR 42?", state)
        assert resp is None

    def test_case_insensitive(self, handler, state):
        resp = handler.parse_keyword("STATUS", state)
        assert resp is not None

        resp = handler.parse_keyword("Queue", state)
        assert resp is not None


class TestChatHandle:
    @pytest.mark.asyncio
    async def test_keyword_handled(self, handler, state):
        resp = await handler.handle("status", state)
        assert resp.source == "keyword"

    @pytest.mark.asyncio
    async def test_no_backend_fallback(self, handler, state):
        resp = await handler.handle("what's happening?", state)
        assert "No AI backend" in resp.text
