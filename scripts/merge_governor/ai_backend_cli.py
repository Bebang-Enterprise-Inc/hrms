"""Backend A: claude --print (Max subscription, $0 extra cost).

Uses asyncio.create_subprocess_exec() — NEVER subprocess.run().
Fail-closed: parse failures → REJECT.
Auto-fallback to Backend B after 3 consecutive parse failures.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import TYPE_CHECKING, Any

import structlog

from .ai_backend_base import ReviewBackend, ReviewResult

if TYPE_CHECKING:
    from .state_manager import GovernorState

logger = structlog.get_logger("governor.ai.cli")

REVIEW_PROMPT_TEMPLATE = """\
You are a code review agent for BEI-ERP (Frappe/ERPNext).

## Task
Review this PR diff and decide: APPROVE, REJECT, or NEEDS_FIX.

## PR #{pr_number}

## Recent merge context
These files were touched by the last {merge_count} merged PRs:
{recent_files}

## Protected surfaces (do NOT modify these)
{protected_surfaces}

## PR Diff
```
{diff_text}
```

## Rules
1. REJECT if the diff modifies files that were touched by a recent merge AND the changes conflict semantically
2. REJECT if the diff modifies protected surfaces
3. REJECT if the diff reverts or overwrites recently-shipped behavior (anti-rewind)
4. APPROVE if the changes are safe and don't conflict
5. NEEDS_FIX if there's a minor issue that can be auto-fixed (missing import, typo)

## Response Format (STRICT JSON)
Respond with ONLY this JSON, no other text:
{{"decision": "APPROVE|REJECT|NEEDS_FIX", "reasoning": "...", "confidence": 0.0-1.0, "conflicting_files": [], "suggested_fix": null}}
"""


class CLIBackend(ReviewBackend):
    """AI backend using `claude --print` subprocess."""

    def __init__(self):
        self._consecutive_failures = 0
        self._available = True

    async def review(
        self,
        pr_number: int,
        diff_text: str,
        merge_context: dict[str, Any],
        timeout_s: float = 120,
    ) -> ReviewResult:
        if not self._available:
            return ReviewResult(
                decision="REJECT",
                reasoning="CLI backend unavailable (nested session or repeated failures)",
                confidence=0.0,
                raw_response="",
            )

        # Build prompt
        recent_merges = merge_context.get("recent_merges", [])
        recent_files = []
        for m in recent_merges:
            for f in m.get("touched_files", []):
                if f not in recent_files:
                    recent_files.append(f)

        prompt = REVIEW_PROMPT_TEMPLATE.format(
            pr_number=pr_number,
            merge_count=len(recent_merges),
            recent_files="\n".join(f"  - {f}" for f in recent_files) or "  (none)",
            protected_surfaces="\n".join(
                f"  - {p}" for p in merge_context.get("protected_surfaces", [])
            ) or "  (none)",
            diff_text=diff_text[:50000],  # Truncate huge diffs
        )

        try:
            raw = await self._call_claude(prompt, timeout_s)
            result = self._parse_response(raw, pr_number)
            self._consecutive_failures = 0
            return result
        except Exception as e:
            self._consecutive_failures += 1
            logger.error(
                "cli_review_failed",
                pr=pr_number,
                error=str(e),
                consecutive_failures=self._consecutive_failures,
            )
            if self._consecutive_failures >= 3:
                self._available = False
                logger.warning("cli_backend_disabled", reason="3 consecutive failures")
            return ReviewResult(
                decision="REJECT",
                reasoning=f"CLI backend parse failure: {e}",
                confidence=0.0,
                raw_response=str(e),
            )

    async def chat(self, message: str, state: "GovernorState") -> str:
        if not self._available:
            raise RuntimeError("CLI backend unavailable")

        prompt = (
            f"You are governor-erp, an AI merge governor for BEI-ERP.\n"
            f"The operator asked: {message}\n\n"
            f"Current state: {len(state.active_prs)} active PRs, "
            f"{len(state.merge_queue)} in queue, "
            f"{'PAUSED' if state.paused else 'RUNNING'}.\n\n"
            f"Answer concisely."
        )
        return await self._call_claude(prompt, timeout_s=30)

    async def health_check(self) -> bool:
        """Test if claude --print works (not in a nested session)."""
        try:
            result = await self._call_claude("Reply with exactly: OK", timeout_s=15)
            ok = "OK" in result.upper()
            if not ok:
                logger.warning("cli_health_unexpected", response=result[:100])
            return ok
        except Exception as e:
            logger.warning("cli_health_failed", error=str(e))
            return False

    async def _call_claude(self, prompt: str, timeout_s: float = 120) -> str:
        """Call claude --print via async subprocess."""
        proc = await asyncio.create_subprocess_exec(
            "claude", "--print", prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_s
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise TimeoutError(f"claude --print timed out after {timeout_s}s")

        if proc.returncode != 0:
            err_msg = stderr.decode().strip()
            raise RuntimeError(f"claude --print failed (rc={proc.returncode}): {err_msg}")

        return stdout.decode().strip()

    def _parse_response(self, raw: str, pr_number: int) -> ReviewResult:
        """Parse claude --print output into ReviewResult.

        Strict validator: detect non-JSON content, ANSI codes, preamble.
        Fail-closed: if parse fails, return REJECT.
        """
        # Strip ANSI escape codes
        clean = re.sub(r"\x1b\[[0-9;]*m", "", raw)

        # Try to extract JSON from response (may have preamble text)
        json_match = re.search(r"\{[^{}]*\}", clean, re.DOTALL)
        if not json_match:
            raise ValueError(f"No JSON found in response for PR #{pr_number}")

        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in response for PR #{pr_number}: {e}")

        decision = data.get("decision", "REJECT").upper()
        if decision not in ("APPROVE", "REJECT", "NEEDS_FIX"):
            decision = "REJECT"

        confidence = float(data.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))

        return ReviewResult(
            decision=decision,
            reasoning=data.get("reasoning", "No reasoning provided"),
            confidence=confidence,
            raw_response=raw,
            conflicting_files=data.get("conflicting_files", []),
            suggested_fix=data.get("suggested_fix"),
        )
