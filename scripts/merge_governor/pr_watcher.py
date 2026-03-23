"""PR watcher — polls GitHub for open PRs against production."""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import structlog

from .state_manager import PRRecord, StateManager

logger = structlog.get_logger("governor.pr_watcher")


def _activity(msg: str) -> None:
    """Print activity line directly to terminal (Windows-safe)."""
    import re
    ts = time.strftime("%H:%M:%S")
    # Replace non-ASCII with single dash, collapse multiple dashes
    safe = msg.encode("ascii", errors="replace").decode()
    safe = re.sub(r"\?{2,}", "-", safe)
    print(f"[{ts}] {safe}", flush=True)

REPOS = [
    "Bebang-Enterprise-Inc/hrms",
]


class PRWatcher:
    """Polls `gh pr list` for open PRs every poll_interval seconds."""

    def __init__(self, state_mgr: StateManager, poll_interval: int = 30):
        self.state_mgr = state_mgr
        self.poll_interval = poll_interval
        self._on_new_pr_callbacks: list = []
        self._on_closed_pr_callbacks: list = []
        self._on_pr_updated_callbacks: list = []

    def on_new_pr(self, callback):
        self._on_new_pr_callbacks.append(callback)

    def on_closed_pr(self, callback):
        self._on_closed_pr_callbacks.append(callback)

    def on_pr_updated(self, callback):
        self._on_pr_updated_callbacks.append(callback)

    async def poll_once(self) -> list[dict[str, Any]]:
        """Poll GitHub for open PRs. Uses subprocess in thread for Windows reliability."""
        loop = asyncio.get_event_loop()
        all_prs = []
        for repo in REPOS:
            try:
                result = await loop.run_in_executor(None, self._gh_pr_list, repo)
                all_prs.extend(result)
            except Exception as e:
                _activity(f"ERROR polling {repo}: {e}")
        return all_prs

    @staticmethod
    def _gh_pr_list(repo: str) -> list[dict[str, Any]]:
        """Run gh pr list synchronously (called from thread executor)."""
        import shutil
        import subprocess

        gh_path = shutil.which("gh") or "gh"
        result = subprocess.run(
            [gh_path, "pr", "list",
             "--repo", repo,
             "--state", "open",
             "--json", "number,title,headRefName,headRefOid,updatedAt,labels"],
            capture_output=True, text=True, timeout=60,
            stdin=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            err = result.stderr.strip() or f"exit code {result.returncode}"
            _activity(f"ERROR: gh pr list failed: {err}")
            return []

        prs = json.loads(result.stdout)
        for pr in prs:
            pr["_repo"] = repo
        return prs

    async def reconcile(self, open_prs: list[dict[str, Any]]) -> None:
        """Reconcile polled PRs against state. Fire callbacks for new/closed."""
        state = self.state_mgr.state
        open_numbers = set()

        for pr_data in open_prs:
            pr_num = pr_data["number"]
            open_numbers.add(pr_num)
            key = str(pr_num)

            if key not in state.active_prs:
                # New PR detected
                record = PRRecord(
                    number=pr_num,
                    title=pr_data.get("title", ""),
                    head_ref=pr_data.get("headRefName", ""),
                    head_sha=pr_data.get("headRefOid", ""),
                    updated_at=pr_data.get("updatedAt", ""),
                    labels=[l.get("name", "") for l in pr_data.get("labels", [])],
                )
                state.active_prs[key] = record
                _activity(f"New PR #{pr_num} detected: {record.title} [{record.head_ref}]")
                for cb in self._on_new_pr_callbacks:
                    try:
                        await cb(record)
                    except Exception as e:
                        _activity(f"ERROR handling PR #{pr_num}: {e}")
            else:
                # Update SHA if changed (force push)
                existing = state.active_prs[key]
                new_sha = pr_data.get("headRefOid", "")
                if new_sha and new_sha != existing.head_sha:
                    logger.info("pr_updated", pr=pr_num, old_sha=existing.head_sha[:8], new_sha=new_sha[:8])
                    existing.head_sha = new_sha
                    existing.updated_at = pr_data.get("updatedAt", "")
                    # Invalidate review if SHA changed
                    if existing.review_sha and existing.review_sha != new_sha:
                        existing.review_decision = None
                        existing.review_sha = None
                        logger.info("review_invalidated", pr=pr_num, reason="sha_changed")
                    # Reset builder dispatch count on new SHA (fresh attempt)
                    existing.builder_dispatch_count = 0
                    existing.builder_dispatched = False

                    # Re-queue gate-blocked PRs on new push (builder fixed the issue)
                    if getattr(existing, "gate_blocked", False):
                        existing.gate_blocked = False
                        if pr_num not in state.merge_queue:
                            state.merge_queue.append(pr_num)
                        _activity(f"PR #{pr_num} re-queued (gate block cleared by new push)")

                    # Fire update callbacks (triggers auto-re-review)
                    for cb in self._on_pr_updated_callbacks:
                        try:
                            await cb(existing)
                        except Exception as e:
                            _activity(f"ERROR handling PR #{pr_num} update: {e}")

        # Detect closed PRs
        for key in list(state.active_prs.keys()):
            pr_num = int(key)
            if pr_num not in open_numbers:
                closed_pr = state.active_prs.pop(key)
                _activity(f"PR #{pr_num} closed: {closed_pr.title}")
                # Remove from merge queue
                if pr_num in state.merge_queue:
                    state.merge_queue.remove(pr_num)
                for cb in self._on_closed_pr_callbacks:
                    await cb(closed_pr)

        import time
        state.last_poll_at = time.time()
        self.state_mgr.save()

    async def run(self, stop_event: asyncio.Event) -> None:
        """Run the PR watcher loop until stop_event is set."""
        _activity(f"PR watcher started (polling every {self.poll_interval}s)")
        while not stop_event.is_set():
            try:
                open_prs = await self.poll_once()
                await self.reconcile(open_prs)
            except Exception as e:
                _activity(f"ERROR in PR watcher: {e}")
                import traceback
                traceback.print_exc()

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self.poll_interval)
            except asyncio.TimeoutError:
                pass  # Normal: timeout means poll again
