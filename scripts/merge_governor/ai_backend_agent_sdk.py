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

## Response format

Always respond with this JSON object at the end of your review:
{"decision": "APPROVE|REJECT|NEEDS_FIX", "reasoning": "...", "confidence": 0.0-1.0, "files_read": ["file1.py", "file2.py"], "checks_performed": ["imports", "logic", "anti-patterns"], "conflicting_files": [], "suggested_fix": null}
"""

REVIEW_PROMPT_TEMPLATE = """\
You are reviewing PR #{pr_number}. Follow these steps IN ORDER and report what you find at each step.

STEP 1: Read the pre-check results below. If any are BLOCKING, your decision is REJECT — explain why.
{pre_check_results}

STEP 2: Run `git diff origin/production...HEAD --name-only` to see changed files.

STEP 3: For each changed Python file, use Read to examine the FULL file (not just the diff).
Focus on: imports that may be missing, function signatures, error handling.

STEP 4: For each changed DocType JSON, verify:
- New fields have correct fieldtype
- No Link fields with defaults referencing production-only data
- Required fields have proper validation

STEP 5: Use Grep to check if any new function names conflict with existing functions.

STEP 6: Check for these specific anti-patterns from governor lessons:
{lessons_checklist}

STEP 7: Generate your verdict. Base confidence on HOW MUCH you actually verified:
- 0.90+ = Read all changed files, all checks passed, no warnings
- 0.70-0.89 = Read most files, minor warnings only
- 0.50-0.69 = Could not read some files, or unresolved warnings
- Below 0.50 = Significant issues found or could not verify

Files touched by last {merge_count} merged PRs:
{recent_files}

Protected surfaces:
{protected_surfaces}

Respond with JSON:
{{"decision": "APPROVE|REJECT|NEEDS_FIX", "reasoning": "...", "confidence": 0.0-1.0, "files_read": [...], "checks_performed": [...], "conflicting_files": [], "suggested_fix": null}}
"""

CHAT_SYSTEM_PROMPT = """\
You are governor-erp, an AI merge governor for BEI-ERP (Frappe/ERPNext).
You have FULL access to the repository, Bash commands, and external systems.
You are NOT a chatbot — you are an OPERATOR. When asked a question, CHECK the actual state before answering.

## Your tools — USE THEM
- **Read/Grep/Glob** — read source files, search code
- **Bash** — run ANY command: gh, curl, aws ssm, docker, python, vercel

## When asked about status, ALWAYS check live state:
```bash
# PR status
gh pr view <NUM> --repo Bebang-Enterprise-Inc/hrms --json state,mergedAt,statusCheckRollup

# CI status
gh pr view <NUM> --repo Bebang-Enterprise-Inc/hrms --json statusCheckRollup --jq '.statusCheckRollup[] | [.name, .status, .conclusion] | @tsv'

# Deploy status (GHA workflow)
gh run list --repo Bebang-Enterprise-Inc/hrms --workflow=build-and-deploy.yml --limit 1 --json status,conclusion

# Production health
curl -s https://hq.bebang.ph/api/method/ping

# Container image on EC2
aws ssm send-command --instance-ids i-026b7477d27bd46d6 --document-name AWS-RunShellScript --parameters '{"commands":["docker service ls --format {{.Name}}:{{.Image}}"]}' --output json

# Vercel deploy status (my.bebang.ph)
curl -s -o /dev/null -w '%{http_code}' https://my.bebang.ph
```

## NEVER guess. ALWAYS check.
If someone asks "is the deploy working?" — run the command and report the actual result.
If someone asks "why is it stuck?" — check CI, GHA runs, production ping, and report findings.
If someone asks "what step are you on?" — read the pipeline state from context below.

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


def _print_tool_call(ts: str, step_num: int, tool_name: str, tool_input: dict) -> None:
    """Print a tool call to terminal in a human-readable format."""
    if tool_name == "Read":
        path = tool_input.get("file_path", "?")
        print(f"[{ts}]     Step {step_num}: Read {path}", flush=True)
    elif tool_name == "Grep":
        pattern = tool_input.get("pattern", "?")
        path = tool_input.get("path", ".")
        print(f"[{ts}]     Step {step_num}: Grep '{pattern}' in {path}", flush=True)
    elif tool_name == "Glob":
        pattern = tool_input.get("pattern", "?")
        print(f"[{ts}]     Step {step_num}: Glob {pattern}", flush=True)
    elif tool_name == "Bash":
        cmd = tool_input.get("command", "?")
        print(f"[{ts}]     Step {step_num}: Bash: {cmd[:120]}", flush=True)
    else:
        print(f"[{ts}]     Step {step_num}: {tool_name}({str(tool_input)[:100]})", flush=True)


def _print_tool_result(ts: str, msg) -> None:
    """Print abbreviated tool result to terminal."""
    content = ""
    if hasattr(msg, "content"):
        if isinstance(msg.content, str):
            content = msg.content
        elif isinstance(msg.content, list):
            for block in msg.content:
                if hasattr(block, "text"):
                    content += block.text
    if content:
        lines = content.strip().splitlines()
        preview = lines[0][:120] if lines else ""
        line_count = len(lines)
        if line_count > 1:
            print(f"[{ts}]       -> {preview} ... ({line_count} lines)", flush=True)
        elif preview:
            print(f"[{ts}]       -> {preview}", flush=True)


def calculate_confidence(
    ai_confidence: float,
    files_read: list[str],
    total_files: int,
    pre_check_passed: bool,
    lesson_matches: int,
    checks_performed: list[str],
) -> float:
    """Calculate confidence from verification depth, not AI self-assessment."""
    confidence = 0.50  # Base

    # Read coverage: +0.10 for reading all changed files
    if total_files > 0:
        coverage = len(files_read) / total_files
        confidence += 0.10 * min(coverage, 1.0)
    else:
        confidence += 0.10  # No files = nothing to read

    # Pre-checks passed: +0.10
    if pre_check_passed:
        confidence += 0.10

    # No lesson matches: +0.10
    if lesson_matches == 0:
        confidence += 0.10

    # Checks performed: +0.10 if AI reported doing 3+ checks
    if len(checks_performed) >= 3:
        confidence += 0.10

    # AI's own confidence adds up to +0.10
    confidence += 0.10 * min(ai_confidence, 1.0)

    return min(round(confidence, 2), 1.0)


def print_review_summary(
    pr_number: int,
    result: "ReviewResult",
    total_files: int,
    pre_check_count: int,
    pre_check_passed: int,
    lesson_count: int,
    lesson_matched: int,
    elapsed_s: float,
    cost_usd: float,
) -> None:
    """Print a structured review summary to terminal."""
    ts = time.strftime("%H:%M:%S")
    files_pct = int(len(result.files_read) / total_files * 100) if total_files > 0 else 100
    print(f"[{ts}] Review complete for PR #{pr_number}:", flush=True)
    print(f"[{ts}]   Decision: {result.decision} (confidence: {result.confidence:.2f})", flush=True)
    print(f"[{ts}]   Files read: {len(result.files_read)}/{total_files} ({files_pct}%)", flush=True)
    print(f"[{ts}]   Pre-checks: {pre_check_passed}/{pre_check_count} passed", flush=True)
    print(f"[{ts}]   Lessons checked: {lesson_count}, matched: {lesson_matched}", flush=True)
    print(f"[{ts}]   Time: {int(elapsed_s)}s | Cost: ${cost_usd:.4f}", flush=True)
    # Truncate reasoning for terminal
    reasoning_preview = result.reasoning[:200].replace("\n", " ")
    print(f"[{ts}]   Reasoning: {reasoning_preview}", flush=True)


class AgentSDKBackend(ReviewBackend):
    """AI backend using Claude Agent SDK — agent reads files, runs commands."""

    _lessons_context: str = ""  # Injected on startup from governor memory

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
        timeout_s: float = 180,
    ) -> ReviewResult:
        from claude_agent_sdk import ClaudeAgentOptions

        from .pre_check import get_changed_files, run_all as run_pre_checks

        review_start = time.time()
        ts = time.strftime("%H:%M:%S")
        merge_context = merge_context or {}

        # --- Step 1: Get changed files ---
        changed_files = get_changed_files(self._repo_root)
        total_files = len(changed_files)
        print(f"[{ts}] Reviewing PR #{pr_number} ({total_files} files changed)...", flush=True)

        # --- Step 2: Run deterministic pre-checks ---
        print(f"[{time.strftime('%H:%M:%S')}]   Running deterministic pre-checks...", flush=True)
        pre_result = run_pre_checks(changed_files, self._repo_root)

        pre_check_count = len(pre_result.checks)
        pre_check_passed = sum(1 for c in pre_result.checks if c.passed)
        lesson_matched = len(pre_result.warnings)

        # If BLOCKING issues found, REJECT immediately (no AI call = save money)
        if not pre_result.passed:
            elapsed = time.time() - review_start
            result = ReviewResult(
                decision="REJECT",
                reasoning=f"Deterministic pre-checks failed: {'; '.join(pre_result.blocking_issues[:3])}",
                confidence=0.95,  # High confidence — deterministic check
                checks_performed=["py_compile", "link_defaults", "decorator_placement", "lesson_match"],
            )
            print_review_summary(
                pr_number, result, total_files,
                pre_check_count, pre_check_passed,
                pre_check_count, lesson_matched,
                elapsed, 0.0,
            )
            return result

        # --- Step 3: Build structured AI review prompt ---
        recent_merges = merge_context.get("recent_merges", [])
        recent_files_list = []
        for m in recent_merges:
            for f in m.get("touched_files", []):
                if f not in recent_files_list:
                    recent_files_list.append(f)

        # Build lessons checklist for the prompt
        lessons_checklist = self._lessons_context if self._lessons_context else "(No lessons loaded)"

        prompt = REVIEW_PROMPT_TEMPLATE.format(
            pr_number=pr_number,
            pre_check_results=pre_result.summary_for_prompt(),
            lessons_checklist=lessons_checklist,
            merge_count=len(recent_merges),
            recent_files="\n".join(f"  - {f}" for f in recent_files_list[:30]) or "  (none)",
            protected_surfaces="\n".join(
                f"  - {p}" for p in merge_context.get("protected_surfaces", [])
            ) or "  (none)",
        )

        options = ClaudeAgentOptions(
            allowed_tools=["Read", "Grep", "Glob", "Bash"],
            disallowed_tools=["Edit", "Write", "NotebookEdit"],
            max_turns=15,
            max_budget_usd=1.00,
            model="sonnet",
            system_prompt=REVIEW_SYSTEM_PROMPT + self._lessons_context,
            cwd=self._repo_root,
        )

        # --- Step 4: Run AI review ---
        # Try Agent SDK first (has tools), fall back to raw Anthropic API
        raw_text = None
        cost = 0.0

        print(f"[{time.strftime('%H:%M:%S')}]   Starting AI review (Agent SDK)...", flush=True)
        try:
            result_msg = await asyncio.wait_for(
                self._run_query_streaming(prompt, options), timeout=timeout_s
            )
            if result_msg:
                raw_text = result_msg.result
                cost = getattr(result_msg, "total_cost_usd", 0.0)
        except Exception as sdk_err:
            sdk_err_str = str(sdk_err)
            if "Control request timeout" in sdk_err_str or "initialize" in sdk_err_str:
                print(f"[{time.strftime('%H:%M:%S')}]   Agent SDK unavailable (nested session), falling back to Anthropic API...", flush=True)
                raw_text, cost = await self._review_via_anthropic_api(prompt, pr_number, diff_text, timeout_s)
            else:
                logger.error("agent_sdk_review_error", pr=pr_number, error=sdk_err_str)
                return ReviewResult(
                    decision="REJECT",
                    reasoning=f"Agent SDK error: {sdk_err}",
                    confidence=0.0,
                )

        if not raw_text:
            return ReviewResult(
                decision="REJECT",
                reasoning="AI review returned no result",
                confidence=0.0,
            )

        # Track cost
        self._total_cost_usd += cost
        self._log_cost(cost, f"review_pr_{pr_number}")

        # Parse AI response
        ai_result = self._parse_response(raw_text, pr_number)

        # --- Step 5: Calculate confidence from verification depth ---
        from .lessons import get_memory_stats

        lesson_stats = get_memory_stats()
        calculated_confidence = calculate_confidence(
            ai_confidence=ai_result.confidence,
            files_read=ai_result.files_read,
            total_files=total_files,
            pre_check_passed=pre_result.passed,
            lesson_matches=lesson_matched,
            checks_performed=ai_result.checks_performed,
        )
        ai_result.confidence = calculated_confidence

        # --- Step 6: Print review summary ---
        elapsed = time.time() - review_start
        print_review_summary(
            pr_number, ai_result, total_files,
            pre_check_count, pre_check_passed,
            lesson_stats.get("lesson_count", 0), lesson_matched,
            elapsed, cost,
        )

        return ai_result

    async def chat(self, message: str, state: Any, pipeline_summary: str = "") -> str:
        from claude_agent_sdk import ClaudeAgentOptions, HookMatcher, ResultMessage, query

        # Build rich state context with live pipeline info
        pr_details = []
        for _k, pr in state.active_prs.items():
            port_str = f" staging:{pr.staging_port}" if pr.staging_port else ""
            review_str = f" review={pr.review_decision}" if pr.review_decision else ""
            confidence_str = f" confidence={pr.review_confidence:.2f}" if hasattr(pr, 'review_confidence') and pr.review_confidence else ""
            gate_str = " GATE_BLOCKED" if getattr(pr, 'gate_blocked', False) else ""
            builder_str = f" builder_dispatches={pr.builder_dispatch_count}" if getattr(pr, 'builder_dispatch_count', 0) else ""
            pr_details.append(
                f"  PR #{pr.number} [{pr.head_ref}]{port_str}{review_str}{confidence_str}{gate_str}{builder_str}"
            )

        context = (
            f"[Governor Live State]\n"
            f"Status: {'PAUSED' if state.paused else 'RUNNING'}\n"
            f"Active PRs: {len(state.active_prs)}\n"
            f"Merge queue: {state.merge_queue}\n"
            f"Production HEAD: {state.production_head[:8] if state.production_head else 'unknown'}\n"
            + "\n".join(pr_details)
            + f"\n\n[Live Pipeline]\n{pipeline_summary or 'No pipeline state available'}\n"
            + f"\n[Operator Message]\n{message}"
        )

        options = ClaudeAgentOptions(
            allowed_tools=["Read", "Grep", "Glob", "Bash"],
            disallowed_tools=["Edit", "Write", "NotebookEdit"],
            max_turns=10,
            max_budget_usd=0.50,
            model="sonnet",
            system_prompt=CHAT_SYSTEM_PROMPT + self._lessons_context,
            cwd=self._repo_root,
            continue_conversation=True,
        )

        try:
            result_msg = await asyncio.wait_for(
                self._run_query(context, options), timeout=120
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
        """Skip the expensive health check — just verify the SDK imports.

        The old health check spawned a full Claude Code subprocess (30s timeout)
        which hangs in non-interactive terminals. If the SDK doesn't work,
        the first real review will fail with a clear error.
        """
        try:
            from claude_agent_sdk import ClaudeAgentOptions, query
            print(f"[{time.strftime('%H:%M:%S')}] Agent SDK: import OK, ready", flush=True)
            return True
        except ImportError as e:
            print(f"[{time.strftime('%H:%M:%S')}] Agent SDK: import FAILED ({e})", flush=True)
            return False

    async def _review_via_anthropic_api(
        self, prompt: str, pr_number: int, diff_text: str, timeout_s: float
    ) -> tuple[str, float]:
        """Fallback: review using raw Anthropic API when Agent SDK can't initialize.

        No tools available — sends the diff + pre-check results as context.
        Returns (raw_text, cost_usd).
        """
        import anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return "", 0.0

        client = anthropic.AsyncAnthropic(api_key=api_key)

        # Include diff text since we can't use tools to read files
        if diff_text:
            full_prompt = prompt + f"\n\nDiff text (since tools are unavailable):\n```\n{diff_text[:50000]}\n```"
        else:
            # Fetch diff ourselves
            from .reviewer import get_pr_diff
            fetched_diff = await get_pr_diff(pr_number)
            full_prompt = prompt + f"\n\nDiff text:\n```\n{fetched_diff[:50000]}\n```"

        try:
            response = await asyncio.wait_for(
                client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1024,
                    system=REVIEW_SYSTEM_PROMPT + self._lessons_context,
                    messages=[{"role": "user", "content": full_prompt}],
                ),
                timeout=timeout_s,
            )

            raw_text = response.content[0].text if response.content else ""
            input_tokens = getattr(response.usage, "input_tokens", 0)
            output_tokens = getattr(response.usage, "output_tokens", 0)
            cost = (input_tokens * 3 / 1_000_000) + (output_tokens * 15 / 1_000_000)

            print(f"[{time.strftime('%H:%M:%S')}]   Anthropic API review: {input_tokens} in / {output_tokens} out (${cost:.4f})", flush=True)
            return raw_text, cost

        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}]   Anthropic API error: {e}", flush=True)
            return "", 0.0

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

    def inject_lessons(self, lessons_text: str) -> None:
        """Inject lessons + playbooks into the system prompts."""
        self._lessons_context = lessons_text
        logger.info("lessons_injected", length=len(lessons_text))

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
        """Run query() silently and return the final ResultMessage.

        Used for chat and health checks where terminal streaming is not needed.
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
            result_msg = type("FakeResult", (), {
                "result": last_text,
                "total_cost_usd": 0.0,
                "session_id": "",
            })()

        return result_msg

    @staticmethod
    async def _run_query_streaming(prompt, options):
        """Run query() with streaming output to terminal.

        Prints AI reasoning, tool calls, and tool results in real time
        so the operator can watch the AI think — same as watching Claude Code work.
        """
        from claude_agent_sdk import AssistantMessage, ResultMessage, query

        result_msg = None
        last_text = ""
        step_num = 0

        async for msg in query(prompt=prompt, options=options):
            ts = time.strftime("%H:%M:%S")

            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if hasattr(block, "text") and block.text.strip():
                        for line in block.text.strip().splitlines():
                            truncated = line[:150]
                            print(f"[{ts}]     AI: {truncated}", flush=True)
                        last_text += block.text
                    elif hasattr(block, "name"):
                        step_num += 1
                        tool_name = block.name
                        tool_input = getattr(block, "input", {})
                        _print_tool_call(ts, step_num, tool_name, tool_input)

            elif isinstance(msg, ResultMessage):
                result_msg = msg

            else:
                # Handle tool results and other message types
                _print_tool_result(ts, msg)

        # If result is empty but we got assistant text, use that
        if result_msg and not result_msg.result and last_text:
            result_msg.result = last_text
        elif result_msg is None and last_text:
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
            files_read = data.get("files_read", [])
            checks_performed = data.get("checks_performed", [])
            return ReviewResult(
                decision=data.get("decision", "REJECT").upper(),
                reasoning=data.get("reasoning", "No reasoning provided"),
                confidence=float(data.get("confidence", 0.0)),
                conflicting_files=data.get("conflicting_files", []),
                suggested_fix=data.get("suggested_fix"),
                raw_response=raw_text,
                files_read=files_read if isinstance(files_read, list) else [],
                checks_performed=checks_performed if isinstance(checks_performed, list) else [],
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
