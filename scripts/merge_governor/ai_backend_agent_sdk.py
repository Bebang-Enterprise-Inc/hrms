"""AI backend using Claude Agent SDK — agent reads source files directly."""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import structlog

from .ai_backend_base import ReviewBackend, ReviewResult

logger = structlog.get_logger("governor.agent_sdk")

REVIEW_SYSTEM_PROMPT = """\
You are a code review agent for BEI-ERP (Frappe/ERPNext).
You have access to the full repository. Use Read, Grep, and Glob to examine source files directly.
Do NOT rely solely on diff text — read the actual files to verify imports, check test coverage, and validate logic.

Review the PR for: conflicts with recent merges, anti-rewind violations, security issues, and code quality.

## Decision criteria

- **APPROVE**: Default for well-structured feature PRs. New functions, API endpoints, tests,
  DocType fields are normal feature work. APPROVE unless there is a concrete risk.
- **REJECT**: Only for real security issues (credential exposure, SQL injection, dangerous deletes),
  removing existing working features, or clear logic bugs you verified by reading the code.
- **NEEDS_FIX**: For fixable issues like missing imports that you confirmed by reading the source file.

## Important context

- `hrms/api/*.py` are protected surfaces but ADDING new functions is expected.
  Only flag modifications that DELETE or BREAK existing functions.
- BEI runs 5-8 parallel builder agents. Feature PRs adding new endpoints are routine.
- Use Grep to verify claims (e.g., check if an import actually exists in the file).

Always respond with a JSON object:
{"decision": "APPROVE|REJECT|NEEDS_FIX", "reasoning": "...", "confidence": 0.0-1.0, "conflicting_files": [], "suggested_fix": null}
"""

CHAT_SYSTEM_PROMPT = """\
You are governor-erp, an AI merge governor for BEI-ERP (Frappe/ERPNext).
You have access to the repository. Use Read, Grep, Glob to answer questions about code.

You manage production merges for a team of 5-8 parallel Claude Code builder sessions.
You review PR diffs, detect file conflicts, prevent anti-rewind regressions, and serialize merges.

Be direct, concise, and opinionated. When asked about a PR, use your tools to read the actual files.

## BEI Deployment Knowledge (from /deploy-frappe and /ship skills)

### Two Repositories, Two Pipelines

**BEI-ERP (hq.bebang.ph)** — Frappe backend
- Repo: Bebang-Enterprise-Inc/hrms, release branch: `production`
- Deploy: PR merge -> GHA `build-and-deploy.yml` -> Docker build -> AWS EC2 Docker Swarm
- EC2: i-026b7477d27bd46d6 (ap-southeast-1), Docker Swarm with 9 services
- Image: samkarazi/bebang-erpnext-hrms:v15
- Rollback: `docker service rollback frappe_backend` (fastest)

**BEI-Tasks (my.bebang.ph)** — React frontend
- Repo: bei-tasks, release branch: `main`
- Deploy: push to main -> Vercel auto-deploys
- Governor auto-triggers `vercel --prod --force` (cache-bust) after every backend merge

### Docker Build Flags (CRITICAL)

| Scenario | no_cache | run_migrate | Build Time |
|----------|----------|-------------|------------|
| Python .py changes | ALWAYS true | false | 5-10 min |
| DocType JSON changes | ALWAYS true | ALWAYS true | 8-12 min |
| Config/workflow only | false | false | ~30s |
| Dependencies (apps.json) | ALWAYS true | false | 5-10 min |

**WARNING:** Build time ~30s = CACHED = old code deployed! Must be 5+ min for fresh build.

### Post-Deploy Verification (Governor-Owned)

1. Wait for GHA workflow success
2. L1: `frappe.ping` -> pong (24 attempts, 5s apart)
3. L1: Login page HTTP 200 + CSS/JS assets load
4. **Image verification**: Check running container has the new image via SSM
5. If stale: `docker service update --force frappe_backend` -> re-run L1
6. Redis flush if CSS 404: `bench --site hq.bebang.ph clear-cache`
7. Image cleanup: keep 4 newest, remove older ones

### Docker Swarm Services (6 app services)

frappe_backend, frappe_frontend, frappe_websocket, frappe_queue-short, frappe_queue-long, frappe_scheduler

All 6 must be updated when deploying. The GHA workflow handles this.

### Build Failure Handling

If `bench build` fails (SyntaxError, yarn error, pip conflict):
1. Retry once with no_cache=true (clears all layers)
2. If retry fails: check if it's a Frappe upstream issue (bench init, yarn)
3. If upstream: wait 15 min and retry (transient npm/pip issues)
4. If our code: the review should have caught it — investigate

### NEVER DO

- `docker commit` (corrupts Python bytecode)
- Edit files inside container (lost on restart)
- `docker compose down -v` (deletes all data volumes)
- Skip `bench migrate` after DocType changes
- Deploy without `no_cache=true` for Python/DocType changes
- Push directly to production branch
- Claim SHIPPED without L1-L4 green

### Ship Status Definitions

- **SHIPPED** = merged + deployed + live + L1-L4 green
- **MERGED_NOT_LIVE** = PR merged but deploy not proven
- **DEPLOYED_NOT_VERIFIED** = production updated but L1-L4 red
- **NOT_SHIPPED_NOT_MERGED** = code only on feature branch
"""

# Bash patterns that must NEVER be executed
BLOCKED_BASH_PATTERNS = [
    r"rm\s+-rf",
    r"docker\s+compose\s+down\s+-v",
    r"git\s+(push|reset\s+--hard|checkout\s+\.)",
    r"sudo\b",
    r"chmod\s+777",
    r"curl.*\|\s*sh",
    r"bench\s+drop-site",
    r"del\s+/[sfq]",
    r"rd\s+/s",
]
_BLOCKED_RE = [re.compile(p, re.IGNORECASE) for p in BLOCKED_BASH_PATTERNS]


class AgentSDKBackend(ReviewBackend):
    """AI backend using Claude Agent SDK — agent reads files, runs commands."""

    def __init__(self):
        # Unset CLAUDECODE to allow SDK to run outside Claude Code sessions
        os.environ.pop("CLAUDECODE", None)
        os.environ.pop("CLAUDE_CODE", None)

        self._total_cost_usd = 0.0
        self._cost_log_file = Path.home() / ".governor" / "logs" / "cost_log.jsonl"
        self._cost_log_file.parent.mkdir(parents=True, exist_ok=True)
        self._repo_root = str(Path(__file__).parent.parent.parent)

    @property
    def needs_diff(self) -> bool:
        return False  # Agent reads files directly

    async def review(
        self,
        pr_number: int,
        diff_text: str = "",
        merge_context: dict[str, Any] | None = None,
        timeout_s: float = 120,
    ) -> ReviewResult:
        from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

        merge_context = merge_context or {}
        recent_merges = merge_context.get("recent_merges", [])
        recent_files = []
        for m in recent_merges:
            for f in m.get("touched_files", []):
                if f not in recent_files:
                    recent_files.append(f)

        prompt = (
            f"Review PR #{pr_number} in this repository.\n\n"
            f"Use Grep and Read to examine the changed files on the current branch.\n"
            f"Run `git diff origin/production...HEAD --name-only` to see which files changed.\n\n"
            f"Files touched by last {len(recent_merges)} merged PRs:\n"
            + "\n".join(f"  - {f}" for f in recent_files[:30])
            + "\n\nProtected surfaces:\n"
            + "\n".join(
                f"  - {p}"
                for p in merge_context.get("protected_surfaces", [])
            )
            + "\n\nRespond with JSON: "
            '{"decision": "APPROVE|REJECT|NEEDS_FIX", '
            '"reasoning": "...", "confidence": 0.0-1.0, '
            '"conflicting_files": [], "suggested_fix": null}'
        )

        options = ClaudeAgentOptions(
            allowed_tools=["Read", "Grep", "Glob", "Bash"],
            disallowed_tools=["Edit", "Write", "NotebookEdit"],
            max_turns=10,
            max_budget_usd=0.50,
            model="sonnet",
            system_prompt=REVIEW_SYSTEM_PROMPT,
            cwd=self._repo_root,
        )

        try:
            result_msg = await asyncio.wait_for(
                self._run_query(prompt, options), timeout=timeout_s
            )

            if not result_msg:
                return ReviewResult(
                    decision="REJECT",
                    reasoning="Agent SDK returned no result",
                    confidence=0.0,
                )

            # Track cost
            cost = result_msg.total_cost_usd
            self._total_cost_usd += cost
            self._log_cost(cost, f"review_pr_{pr_number}")
            logger.info(
                "sdk_review_cost",
                pr=pr_number,
                cost_usd=cost,
                total_cost_usd=self._total_cost_usd,
            )

            return self._parse_response(result_msg.result, pr_number)

        except asyncio.TimeoutError:
            logger.error("agent_sdk_review_timeout", pr=pr_number, timeout=timeout_s)
            return ReviewResult(
                decision="REJECT",
                reasoning=f"Review timed out after {timeout_s}s",
                confidence=0.0,
            )
        except Exception as e:
            logger.error("agent_sdk_review_error", pr=pr_number, error=str(e))
            return ReviewResult(
                decision="REJECT",
                reasoning=f"Agent SDK error: {e}",
                confidence=0.0,
            )

    async def chat(self, message: str, state: Any) -> str:
        from claude_agent_sdk import ClaudeAgentOptions, HookMatcher, ResultMessage, query

        # Build state context
        pr_details = []
        for _k, pr in state.active_prs.items():
            port_str = f" staging:{pr.staging_port}" if pr.staging_port else ""
            review_str = f" review={pr.review_decision}" if pr.review_decision else ""
            pr_details.append(
                f"  PR #{pr.number} [{pr.head_ref}]{port_str}{review_str}"
            )

        context = (
            f"[Governor State]\n"
            f"Status: {'PAUSED' if state.paused else 'RUNNING'}\n"
            f"Active PRs: {len(state.active_prs)}\n"
            f"Merge queue: {state.merge_queue}\n"
            + "\n".join(pr_details)
            + f"\n\nOperator message: {message}"
        )

        options = ClaudeAgentOptions(
            allowed_tools=["Read", "Grep", "Glob", "Bash"],
            disallowed_tools=["Edit", "Write", "NotebookEdit"],
            max_turns=5,
            max_budget_usd=0.25,
            model="sonnet",
            system_prompt=CHAT_SYSTEM_PROMPT,
            cwd=self._repo_root,
            continue_conversation=True,
        )

        try:
            result_msg = await asyncio.wait_for(
                self._run_query(context, options), timeout=60
            )

            if result_msg:
                cost = result_msg.total_cost_usd
                self._total_cost_usd += cost
                self._log_cost(cost, "chat")
                logger.info(
                    "sdk_chat_cost",
                    cost_usd=cost,
                    total_cost_usd=self._total_cost_usd,
                )
                return result_msg.result

            return "Agent SDK returned no response."

        except asyncio.TimeoutError:
            return "Chat timed out. Try a simpler question."
        except Exception as e:
            logger.error("agent_sdk_chat_error", error=str(e))
            return f"Agent SDK error: {e}"

    async def health_check(self) -> bool:
        from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

        try:
            result_msg = await asyncio.wait_for(
                self._run_query(
                    "Reply with exactly: HEALTH_OK",
                    ClaudeAgentOptions(allowed_tools=[], max_turns=1),
                ),
                timeout=15,
            )
            return result_msg is not None and "HEALTH_OK" in (result_msg.result or "")
        except Exception as e:
            logger.warning("agent_sdk_health_failed", error=str(e))
        return False

    def get_cost_last_24h(self) -> tuple[float, int]:
        """Read cost log and sum entries from last 24h."""
        if not self._cost_log_file.exists():
            return (0.0, 0)

        cutoff = time.time() - 86400
        total = 0.0
        count = 0
        try:
            with open(self._cost_log_file) as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if entry.get("timestamp", 0) >= cutoff:
                            total += entry.get("cost_usd", 0)
                            count += 1
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
        return (total, count)

    def inject_review_into_chat(self, pr_number: int, result: ReviewResult) -> None:
        """No-op for Agent SDK — session persistence handles context."""
        pass

    async def verify_evidence(self, sprint_id: str, evidence_path: str, plan_scenarios: list[str]) -> dict:
        """AI verification of L3 evidence authenticity.

        Reads evidence files and cross-references against plan scenarios.
        Returns {"passed": bool, "issues": list[str]}.
        """
        from claude_agent_sdk import ClaudeAgentOptions

        scenarios_text = "\n".join(f"  - {s}" for s in plan_scenarios) if plan_scenarios else "  (none defined)"

        prompt = (
            f"You are a QA release manager verifying L3 test evidence for sprint {sprint_id}.\n\n"
            f"Read the evidence files in: {evidence_path}\n"
            f"Look for JSON files (form_submissions.json or any *{sprint_id}*.json).\n\n"
            f"Plan defines these L3 scenarios:\n{scenarios_text}\n\n"
            "Check:\n"
            "1. Are the input values realistic? (not 'test', 'asdf', '123', 'foo')\n"
            "2. Do the entries have actual API responses or real outcomes?\n"
            "3. Does each plan scenario have a matching evidence entry?\n"
            "4. Are there screenshots referenced? Do the paths exist?\n\n"
            'Respond with JSON: {"passed": true/false, "issues": ["issue1", "issue2"]}\n'
            "If evidence looks authentic and covers the scenarios, passed=true with empty issues."
        )

        options = ClaudeAgentOptions(
            allowed_tools=["Read", "Grep", "Glob"],
            disallowed_tools=["Edit", "Write", "Bash", "NotebookEdit"],
            max_turns=4,
            max_budget_usd=0.20,
            model="sonnet",
            system_prompt="You are a QA release manager. Verify evidence authenticity. Read-only access.",
            cwd=self._repo_root,
        )

        try:
            result_msg = await asyncio.wait_for(
                self._run_query(prompt, options), timeout=60
            )

            if not result_msg or not result_msg.result:
                return {"passed": False, "issues": ["AI verification returned no result"]}

            cost = getattr(result_msg, "total_cost_usd", 0.0)
            self._total_cost_usd += cost
            self._log_cost(cost, f"verify_evidence_{sprint_id}")

            # Parse JSON response
            cleaned = re.sub(r"```(?:json)?\s*\n?", "", result_msg.result)
            json_str = self._extract_json(cleaned)
            if json_str:
                data = json.loads(json_str)
                return {"passed": data.get("passed", False), "issues": data.get("issues", [])}

            return {"passed": False, "issues": ["Could not parse AI verification response"]}

        except asyncio.TimeoutError:
            return {"passed": False, "issues": ["AI verification timed out — push again to retry"]}
        except Exception as e:
            return {"passed": False, "issues": [f"AI verification error: {e}"]}

    # --- Internal helpers ---

    @staticmethod
    async def _run_query(prompt, options):
        """Run query() and return the final ResultMessage.

        If ResultMessage.result is empty, falls back to the last
        AssistantMessage text content (agent may put response there).
        """
        from claude_agent_sdk import AssistantMessage, ResultMessage, query

        result_msg = None
        last_text = ""
        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if hasattr(block, "text"):
                        last_text += block.text
            if isinstance(msg, ResultMessage):
                result_msg = msg

        # If result is empty but we got assistant text, use that
        if result_msg and not result_msg.result and last_text:
            result_msg.result = last_text
        elif result_msg is None and last_text:
            # Create a synthetic ResultMessage with the assistant text
            result_msg = type("FakeResult", (), {
                "result": last_text,
                "total_cost_usd": 0.0,
                "session_id": "",
            })()

        return result_msg

    def _parse_response(self, raw_text: str | None, pr_number: int) -> ReviewResult:
        """Parse JSON response from agent output."""
        if not raw_text:
            return ReviewResult(
                decision="REJECT",
                reasoning="Agent returned empty response",
                confidence=0.0,
            )

        # Strip markdown code fences (agent often wraps JSON in ```json ... ```)
        cleaned = re.sub(r"```(?:json)?\s*\n?", "", raw_text)

        # Find JSON in response (agent may include explanation text around it)
        json_match = self._extract_json(cleaned)
        if not json_match:
            logger.warning("no_json_in_response", pr=pr_number, text=raw_text[:200])
            return ReviewResult(
                decision="REJECT",
                reasoning=f"Could not parse review response: {raw_text[:200]}",
                confidence=0.0,
                raw_response=raw_text,
            )

        try:
            data = json.loads(json_match)
            return ReviewResult(
                decision=data.get("decision", "REJECT").upper(),
                reasoning=data.get("reasoning", "No reasoning provided"),
                confidence=float(data.get("confidence", 0.0)),
                conflicting_files=data.get("conflicting_files", []),
                suggested_fix=data.get("suggested_fix"),
                raw_response=raw_text,
            )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("json_parse_error", pr=pr_number, error=str(e))
            return ReviewResult(
                decision="REJECT",
                reasoning=f"JSON parse error: {e}",
                confidence=0.0,
                raw_response=raw_text,
            )

    @staticmethod
    def _extract_json(text: str) -> str | None:
        """Extract JSON object from text using brace-depth counting."""
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        return None

    def _log_cost(self, cost_usd: float, label: str) -> None:
        """Append cost entry to JSONL log."""
        try:
            entry = {
                "timestamp": time.time(),
                "cost_usd": cost_usd,
                "label": label,
                "backend": "agent-sdk",
            }
            with open(self._cost_log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass  # Never crash on log write failure
