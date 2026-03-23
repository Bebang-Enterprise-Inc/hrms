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

    @property
    def needs_diff(self) -> bool:
        """Whether this backend needs diff_text passed to review().

        Backends that read source files directly (e.g., Agent SDK) return False.
        Legacy backends that parse diffs return True (default).
        """
        return True

    @abc.abstractmethod
    async def review(
        self,
        pr_number: int,
        diff_text: str = "",
        merge_context: dict[str, Any] | None = None,
        timeout_s: float = 120,
    ) -> ReviewResult:
        """Review a PR and return a decision.

        Args:
            pr_number: The PR number being reviewed.
            diff_text: The git diff (optional — backends with needs_diff=False ignore this).
            merge_context: Dict with recent_merges, protected_surfaces, production_head.
            timeout_s: Maximum time for the review in seconds.

        Returns:
            ReviewResult with decision and reasoning.
        """

    @abc.abstractmethod
    async def chat(self, message: str, state: "GovernorState") -> str:
        """Handle a natural language chat message from the operator."""

    @abc.abstractmethod
    async def health_check(self) -> bool:
        """Check if this backend is available and working."""

    def get_cost_last_24h(self) -> tuple[float, int]:
        """Return (cost_usd, call_count) for last 24 hours. Override in subclasses."""
        return (0.0, 0)

    def inject_review_into_chat(self, pr_number: int, result: "ReviewResult") -> None:
        """Inject review result into chat context. Override if supported."""
