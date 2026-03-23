"""Two-tier chat handler: keyword parser + LLM forwarding."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from .state_manager import GovernorState

logger = structlog.get_logger("governor.chat")


@dataclass
class ChatResponse:
    text: str
    source: str  # "keyword" or "llm"


# Keyword commands — instant, no AI needed
KEYWORD_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^(status|s)$", re.IGNORECASE), "cmd_status"),
    (re.compile(r"^(queue|q)$", re.IGNORECASE), "cmd_queue"),
    (re.compile(r"^(help|h|\?)$", re.IGNORECASE), "cmd_help"),
    (re.compile(r"^(cost|costs|spending)$", re.IGNORECASE), "cmd_cost"),
    (re.compile(r"^pause$", re.IGNORECASE), "cmd_pause"),
    (re.compile(r"^resume$", re.IGNORECASE), "cmd_resume"),
    (re.compile(r"^merge\s+(\d+)$", re.IGNORECASE), "cmd_merge"),
    (re.compile(r"^skip\s+(\d+)$", re.IGNORECASE), "cmd_skip"),
    (re.compile(r"^history$", re.IGNORECASE), "cmd_history"),
    (re.compile(r"^ports$", re.IGNORECASE), "cmd_ports"),
]


class ChatHandler:
    """Two-tier chat: keyword commands (instant) + LLM forwarding (complex queries)."""

    def __init__(self, ai_backend=None):
        self.ai_backend = ai_backend

    def parse_keyword(self, message: str, state: GovernorState) -> ChatResponse | None:
        """Try to handle message as a keyword command. Returns None if not a keyword."""
        message = message.strip()
        for pattern, cmd_name in KEYWORD_PATTERNS:
            match = pattern.match(message)
            if match:
                handler = getattr(self, cmd_name)
                return handler(match, state)
        return None

    async def handle(self, message: str, state: GovernorState) -> ChatResponse:
        """Handle a chat message. Try keyword first, fall back to LLM."""
        # Try keyword parser first (instant, always works)
        result = self.parse_keyword(message, state)
        if result:
            logger.info("chat_keyword", command=result.text[:50])
            return result

        # Forward to LLM if available
        if self.ai_backend:
            try:
                # Auto-fetch PR details if user mentions a PR number
                enriched = await self._enrich_with_pr_details(message)
                llm_response = await self.ai_backend.chat(enriched, state)
                logger.info("chat_llm", message=message[:50])
                return ChatResponse(text=llm_response, source="llm")
            except Exception as e:
                logger.error("chat_llm_error", error=str(e))
                return ChatResponse(
                    text=f"AI backend unavailable: {e}\nUse 'help' for available commands.",
                    source="keyword",
                )

        return ChatResponse(
            text="No AI backend configured. Use 'help' for available commands.",
            source="keyword",
        )

    # --- Keyword command handlers ---

    def cmd_status(self, match: re.Match, state: GovernorState) -> ChatResponse:
        active = len(state.active_prs)
        queued = len(state.merge_queue)
        paused = "PAUSED" if state.paused else "RUNNING"
        uptime = time.time() - state.started_at if state.started_at else 0
        uptime_str = _format_duration(uptime)

        lines = [
            f"Governor Status: {paused}",
            f"Uptime: {uptime_str}",
            f"Active PRs: {active}",
            f"Merge queue: {queued}",
            f"Production HEAD: {state.production_head[:8] if state.production_head else 'unknown'}",
        ]
        if state.active_prs:
            lines.append("\nActive PRs:")
            for pr_key, pr in state.active_prs.items():
                port_str = f":{pr.staging_port}" if pr.staging_port else ""
                review_str = pr.review_decision or "pending"
                lines.append(f"  PR #{pr.number} [{pr.head_ref}] {port_str} review={review_str}")

        return ChatResponse(text="\n".join(lines), source="keyword")

    def cmd_queue(self, match: re.Match, state: GovernorState) -> ChatResponse:
        if not state.merge_queue:
            return ChatResponse(text="Merge queue is empty.", source="keyword")
        lines = ["Merge Queue:"]
        for i, pr_num in enumerate(state.merge_queue, 1):
            pr = state.active_prs.get(str(pr_num))
            title = pr.title if pr else "unknown"
            lines.append(f"  {i}. PR #{pr_num} — {title}")
        return ChatResponse(text="\n".join(lines), source="keyword")

    def cmd_cost(self, match: re.Match, state: GovernorState) -> ChatResponse:
        if self.ai_backend and hasattr(self.ai_backend, "total_cost_usd"):
            session_cost = self.ai_backend.total_cost_usd
            cost_24h, calls_24h = (0.0, 0)
            if hasattr(self.ai_backend, "get_cost_last_24h"):
                cost_24h, calls_24h = self.ai_backend.get_cost_last_24h()
            lines = [
                "AI Cost Tracker:",
                f"  Last 24h:      ${cost_24h:.4f} ({calls_24h} API calls)",
                f"  This session:  ${session_cost:.4f}",
                f"  Chat messages: {len(getattr(self.ai_backend, '_chat_history', []))}",
            ]
            return ChatResponse(text="\n".join(lines), source="keyword")
        return ChatResponse(text="No AI backend active -- no costs.", source="keyword")

    def cmd_help(self, match: re.Match, state: GovernorState) -> ChatResponse:
        return ChatResponse(
            text=(
                "Governor Commands:\n"
                "  status / s     - Show governor status\n"
                "  queue / q      - Show merge queue\n"
                "  cost           - Show AI spending this session\n"
                "  merge <PR#>    - Force-queue a PR for merge\n"
                "  skip <PR#>     - Remove a PR from queue\n"
                "  pause          - Pause governor (stops merges)\n"
                "  resume         - Resume governor\n"
                "  history        - Show last 10 merged PRs\n"
                "  ports          - Show port assignments\n"
                "  help / h / ?   - Show this help\n"
                "\nAnything else is forwarded to AI for natural language processing."
            ),
            source="keyword",
        )

    def cmd_pause(self, match: re.Match, state: GovernorState) -> ChatResponse:
        state.paused = True
        return ChatResponse(text="Governor PAUSED. Merge queue halted. Use 'resume' to continue.", source="keyword")

    def cmd_resume(self, match: re.Match, state: GovernorState) -> ChatResponse:
        state.paused = False
        return ChatResponse(text="Governor RESUMED. Merge queue active.", source="keyword")

    def cmd_merge(self, match: re.Match, state: GovernorState) -> ChatResponse:
        pr_num = int(match.group(1))
        if pr_num not in state.merge_queue:
            state.merge_queue.append(pr_num)
            return ChatResponse(text=f"PR #{pr_num} added to merge queue.", source="keyword")
        return ChatResponse(text=f"PR #{pr_num} is already in the merge queue.", source="keyword")

    def cmd_skip(self, match: re.Match, state: GovernorState) -> ChatResponse:
        pr_num = int(match.group(1))
        if pr_num in state.merge_queue:
            state.merge_queue.remove(pr_num)
            return ChatResponse(text=f"PR #{pr_num} removed from merge queue.", source="keyword")
        return ChatResponse(text=f"PR #{pr_num} is not in the merge queue.", source="keyword")

    def cmd_history(self, match: re.Match, state: GovernorState) -> ChatResponse:
        if not state.merge_history:
            return ChatResponse(text="No merge history yet.", source="keyword")
        lines = ["Last merged PRs:"]
        for entry in reversed(state.merge_history):
            pr_num = entry.get("number", "?")
            files = entry.get("touched_files", [])
            lines.append(f"  PR #{pr_num} — {len(files)} files touched")
        return ChatResponse(text="\n".join(lines), source="keyword")

    def cmd_ports(self, match: re.Match, state: GovernorState) -> ChatResponse:
        assigned = {
            k: v for k, v in state.port_registry.items() if v is not None
        }
        if not assigned:
            return ChatResponse(text="No ports assigned. All staging slots free.", source="keyword")
        lines = ["Port Assignments:"]
        for port, pr_num in sorted(assigned.items()):
            lines.append(f"  :{port} -> PR #{pr_num}")
        return ChatResponse(text="\n".join(lines), source="keyword")


    async def _enrich_with_pr_details(self, message: str) -> str:
        """If the message mentions PR numbers, fetch details + diff from GitHub."""
        # Find ALL 3-4 digit numbers in the message
        pr_matches = re.findall(r"\b(\d{3,4})\b", message)
        if not pr_matches:
            return message

        # Deduplicate, limit to 4 PRs max
        pr_nums = list(dict.fromkeys(pr_matches))[:4]

        import asyncio
        import shutil
        import subprocess

        loop = asyncio.get_event_loop()
        gh = shutil.which("gh") or "gh"
        repo = "Bebang-Enterprise-Inc/hrms"
        enriched = message

        for pr_num in pr_nums:
            try:
                # Fetch metadata
                def _fetch_meta(n=pr_num):
                    return subprocess.run(
                        [gh, "pr", "view", n, "--repo", repo,
                         "--json", "number,title,body,state,headRefName,changedFiles,additions,deletions,files"],
                        capture_output=True, text=True, timeout=30,
                        stdin=subprocess.DEVNULL,
                    )

                # Fetch diff (the actual code changes)
                def _fetch_diff(n=pr_num):
                    return subprocess.run(
                        [gh, "pr", "diff", n, "--repo", repo],
                        capture_output=True, text=True, timeout=30,
                        stdin=subprocess.DEVNULL,
                    )

                meta_result, diff_result = await asyncio.gather(
                    loop.run_in_executor(None, _fetch_meta),
                    loop.run_in_executor(None, _fetch_diff),
                )

                context = f"\n\n[Auto-fetched PR #{pr_num}]\n"

                if meta_result.returncode == 0:
                    import json
                    pr_data = json.loads(meta_result.stdout)
                    files = [f.get("path", "") for f in pr_data.get("files", [])]
                    context += (
                        f"Title: {pr_data.get('title', '')}\n"
                        f"State: {pr_data.get('state', '')}\n"
                        f"Branch: {pr_data.get('headRefName', '')}\n"
                        f"Changes: +{pr_data.get('additions', 0)} -{pr_data.get('deletions', 0)} across {pr_data.get('changedFiles', 0)} files\n"
                        f"Files: {', '.join(files[:15])}\n"
                    )
                    body = pr_data.get("body", "")
                    if body:
                        context += f"Description: {body[:300]}\n"

                if diff_result.returncode == 0 and diff_result.stdout:
                    # Include the diff (truncated to avoid token explosion)
                    diff_text = diff_result.stdout[:3000]
                    context += f"\nDiff:\n```\n{diff_text}\n```\n"

                enriched += context

            except Exception:
                continue

        return enriched


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}h {minutes}m"
