"""Review orchestrator — selects backend and manages review caching."""
from __future__ import annotations

import asyncio
from typing import Any

import structlog

from .ai_backend_base import ReviewBackend, ReviewResult
from .state_manager import StateManager

logger = structlog.get_logger("governor.reviewer")


class Reviewer:
    """Orchestrates AI reviews with caching and backend selection."""

    def __init__(self, backend: ReviewBackend | None, state_mgr: StateManager):
        self.backend = backend
        self.state_mgr = state_mgr
        # Cache: {pr_number: {sha: ReviewResult}}
        self._cache: dict[int, dict[str, ReviewResult]] = {}

    async def review_pr(
        self,
        pr_number: int,
        head_sha: str,
        diff_text: str,
        timeout_s: float = 120,
    ) -> ReviewResult:
        """Review a PR. Returns cached result if HEAD hasn't changed."""
        if not self.backend:
            logger.info("review_skipped", pr=pr_number, reason="no_backend")
            return ReviewResult(
                decision="APPROVE",
                reasoning="Review skipped (no AI backend configured)",
                confidence=0.0,
            )

        # Check cache
        if pr_number in self._cache and head_sha in self._cache[pr_number]:
            cached = self._cache[pr_number][head_sha]
            logger.info("review_cached", pr=pr_number, sha=head_sha[:8], decision=cached.decision)
            return cached

        # Build merge context
        state = self.state_mgr.state
        merge_context: dict[str, Any] = {
            "recent_merges": state.merge_history,
            "protected_surfaces": [
                "hrms/api/*.py",
                ".github/workflows/build-and-deploy.yml",
            ],
            "production_head": state.production_head,
        }

        # Run review
        logger.info("reviewing_pr", pr=pr_number, sha=head_sha[:8])
        result = await self.backend.review(
            pr_number=pr_number,
            diff_text=diff_text,
            merge_context=merge_context,
            timeout_s=timeout_s,
        )

        # Cache result
        self._cache.setdefault(pr_number, {})[head_sha] = result

        # Update state
        pr_key = str(pr_number)
        if pr_key in state.active_prs:
            state.active_prs[pr_key].review_decision = result.decision
            state.active_prs[pr_key].review_confidence = result.confidence
            state.active_prs[pr_key].review_sha = head_sha
            self.state_mgr.save()

        logger.info(
            "review_complete",
            pr=pr_number,
            decision=result.decision,
            confidence=result.confidence,
            reasoning=result.reasoning[:100],
        )

        # Inject review into chat history so the agent remembers it
        if hasattr(self.backend, "inject_review_into_chat"):
            self.backend.inject_review_into_chat(pr_number, result)

        return result

    def invalidate_cache(self, pr_number: int) -> None:
        """Invalidate cached reviews for a PR (e.g., after force push)."""
        if pr_number in self._cache:
            del self._cache[pr_number]
            logger.info("cache_invalidated", pr=pr_number)


async def get_pr_diff(pr_number: int, repo: str = "Bebang-Enterprise-Inc/hrms") -> str:
    """Get the diff for a PR using gh CLI (thread-safe for Windows)."""
    import shutil
    import subprocess

    loop = asyncio.get_event_loop()
    gh = shutil.which("gh") or "gh"

    def _fetch():
        return subprocess.run(
            [gh, "pr", "diff", str(pr_number), "--repo", repo],
            capture_output=True, text=True, timeout=60,
            stdin=subprocess.DEVNULL,
            encoding="utf-8", errors="replace",
        )

    result = await loop.run_in_executor(None, _fetch)
    if result.returncode != 0:
        logger.error("gh_pr_diff_failed", pr=pr_number, stderr=result.stderr[:200])
        return ""
    return result.stdout
