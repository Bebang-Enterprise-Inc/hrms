"""Abstract AI backend interface for governor-erp."""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .state_manager import GovernorState


@dataclass
class ReviewResult:
    """Result of an AI code review."""
    decision: str  # APPROVE, REJECT, NEEDS_FIX
    reasoning: str
    confidence: float  # 0.0 - 1.0
    raw_response: str = ""
    conflicting_files: list[str] = field(default_factory=list)
    suggested_fix: str | None = None

    @property
    def is_approved(self) -> bool:
        return self.decision == "APPROVE"


class ReviewBackend(abc.ABC):
    """Abstract base class for AI review backends."""

    @abc.abstractmethod
    async def review(
        self,
        pr_number: int,
        diff_text: str,
        merge_context: dict[str, Any],
        timeout_s: float = 120,
    ) -> ReviewResult:
        """Review a PR diff and return a decision.

        Args:
            pr_number: The PR number being reviewed.
            diff_text: The git diff of the PR.
            merge_context: Dict with keys:
                - recent_merges: list of {number, touched_files} for last 10 merged PRs
                - protected_surfaces: list of file patterns that must not be modified
                - production_head: current production HEAD SHA
            timeout_s: Maximum time for the review in seconds.

        Returns:
            ReviewResult with decision and reasoning.
        """

    @abc.abstractmethod
    async def chat(self, message: str, state: "GovernorState") -> str:
        """Handle a natural language chat message from the operator.

        Args:
            message: The operator's message.
            state: Current governor state for context.

        Returns:
            AI response text.
        """

    @abc.abstractmethod
    async def health_check(self) -> bool:
        """Check if this backend is available and working.

        Returns:
            True if the backend can accept requests.
        """
