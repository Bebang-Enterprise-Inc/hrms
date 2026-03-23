"""Conflict detection — compares PR touched files against recent merges."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import structlog

from .state_manager import StateManager

logger = structlog.get_logger("governor.conflict")


@dataclass
class ConflictReport:
    pr_number: int
    has_conflicts: bool
    conflicting_files: list[str] = field(default_factory=list)
    pr_files: list[str] = field(default_factory=list)
    recent_merge_files: dict[int, list[str]] = field(default_factory=dict)


class ConflictDetector:
    """Detects file conflicts between a PR and recently merged PRs."""

    def __init__(self, state_mgr: StateManager):
        self.state_mgr = state_mgr

    async def get_pr_files(
        self,
        pr_number: int,
        head_ref: str,
        repo: str = "Bebang-Enterprise-Inc/hrms",
    ) -> list[str]:
        """Get files touched by a PR using git diff --name-only.

        Rebuilds from git at queue-entry time — no persistent cache.
        """
        proc = await asyncio.create_subprocess_exec(
            "gh", "pr", "diff", str(pr_number),
            "--repo", repo, "--name-only",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error("conflict_diff_failed", pr=pr_number, stderr=stderr.decode())
            return []

        files = [f.strip() for f in stdout.decode().splitlines() if f.strip()]
        return files

    async def check_conflicts(
        self,
        pr_number: int,
        head_ref: str,
    ) -> ConflictReport:
        """Check a PR for file conflicts against recent merges.

        Conflict data is rebuilt from git each time — not cached.
        """
        pr_files = await self.get_pr_files(pr_number, head_ref)

        state = self.state_mgr.state
        recent_files: dict[int, list[str]] = {}
        for entry in state.merge_history:
            merge_num = entry.get("number", 0)
            merge_touched = entry.get("touched_files", [])
            recent_files[merge_num] = merge_touched

        # Find overlapping files
        all_recent = set()
        for files in recent_files.values():
            all_recent.update(files)

        conflicts = [f for f in pr_files if f in all_recent]

        report = ConflictReport(
            pr_number=pr_number,
            has_conflicts=bool(conflicts),
            conflicting_files=conflicts,
            pr_files=pr_files,
            recent_merge_files=recent_files,
        )

        if conflicts:
            logger.warning(
                "conflicts_detected",
                pr=pr_number,
                count=len(conflicts),
                files=conflicts[:10],
            )
        else:
            logger.info("no_conflicts", pr=pr_number, files_checked=len(pr_files))

        return report
