# S095: Governor AI Backend — Claude Agent SDK Upgrade

```yaml
canonical_sprint_id: S095
status: COMPLETED
created_date: 2026-03-23
completed_date: 2026-03-23
execution_summary: "S095A+B complete. Agent SDK backend live (review $0.31, chat $0.17). Builder subagent dispatch with worktree isolation. Confidence gate >= 0.80. Default switched to agent-sdk. Commits: 7a1088ba9 (S095A), next (S095B)."
depends_on: null
lane: A
estimated_work_units: 15
audit_version: 2
audit_date: 2026-03-23
audit_blockers_resolved: 7
split_into: [S095A, S095B]
```

> **AUDIT AMENDMENT (v2, 2026-03-23):** Plan split into S095A (this file, 15 units) and S095B (20 units, builder dispatch). 7 blockers resolved: permission mode fixed, confidence gate added, timeout prototype task added, self-upgrade sequencing gate added, interface mismatch resolved, worktree scaffolding moved to S095B, negative tests added. Full audit report: `output/plan-audit/governor-agent-sdk-upgrade/AUDIT_REPORT.md`

## Summary

Migrate the governor-erp AI backend from the raw `anthropic` SDK to the **Claude Agent SDK** (`claude-agent-sdk`). This upgrades the governor from a "paste diff, get JSON" reviewer to an agent that can read source code, run verification commands, and persist chat sessions across restarts.

**This is S095A (Lane A).** Builder subagent dispatch is deferred to S095B (Lane B).

## Design Rationale (For Cold-Start Agents)

### Why this exists

The governor-erp was built in S091 as a merge serializer with AI review. The AI backend (`ai_backend_sdk.py`) uses the raw `anthropic` Python package — it sends a 50K-char diff as a text prompt and parses a JSON response. This has three proven failure modes:

1. **Truncated diffs cause false rejections** — `gh pr diff` truncates at ~50K chars. The AI sees truncated test files and rejects the PR as "corrupt code" (happened 4 times in S093/S094 testing on 2026-03-23).
2. **No code verification** — the reviewer cannot check if imports exist, if tests pass, or if referenced functions are real. It can only read the diff text.
3. **No autonomous fix capability** — when the governor rejects a PR or detects merge conflicts, it posts a PR comment and waits. If no builder is running, the PR sits indefinitely (PR #310 was stuck for hours on 2026-03-23). (Addressed in S095B.)

### Why Claude Agent SDK (not keep raw `anthropic`)

| Capability | Raw `anthropic` SDK | Claude Agent SDK |
|-----------|---------------------|-----------------|
| Read actual source files | No — only sees pasted diff | Yes — built-in `Read`, `Grep`, `Glob` tools |
| Run verification commands | No | Yes — `Bash` tool (linting, tests) |
| Session persistence | Hand-rolled 40-message list | Built-in session management with compaction |
| Cost caps | Manual tracking, no enforcement | `max_budget_usd` per query |
| Tool permission hooks | None | `PreToolUse` hooks to block dangerous commands |
| Context window management | Manual truncation at 50K chars | Automatic context compaction |

### Why NOT Claude Agent SDK for everything

The merge serializer (`merge_serializer.py`), PR watcher (`pr_watcher.py`), state manager, and chat handler are pure infrastructure — they don't need AI. Only the AI backend module changes.

### Key trade-off decisions

1. **Agent SDK for review AND chat** — both benefit from tool access. The chat handler can answer "what files does PR #310 touch?" by actually reading the repo instead of guessing.
2. **Evolve `ReviewBackend` interface** — make `diff_text` optional (`diff_text: str = ""`). Agent SDK backend ignores it; old backends still use it. Add `needs_diff` property and `get_cost_last_24h()` to ABC. (Audit blocker #6 fix.)
3. **Split S095 into A + B** — Phase 1 (review migration, 15 units) is independently shippable. Phase 2 (builder dispatch, 20 units) depends on Phase 1 but is a separate sprint. (Audit blocker #1 fix.)
4. **Review agent is read-only** — `disallowed_tools=["Edit", "Write", "NotebookEdit"]`. No `acceptEdits`. Agent can `Read`, `Grep`, `Glob`, and run non-destructive `Bash`. (Audit blocker #2 fix.)
5. **Self-upgrade sequencing** — S095A PR is reviewed/merged by the OLD backend (`--backend sdk`). New backend is activated only AFTER the PR merges. (Audit blocker #5 fix.)

### Known limitations

- Claude Agent SDK bundles the Claude Code CLI as a Node.js binary (~50MB). This is fine for Sam's Windows machine but would matter for container deployments.
- The SDK requires `ANTHROPIC_API_KEY` — same as current setup via Doppler.
- `claude-agent-sdk` is at v0.1.48 (March 2026) — still pre-1.0 but stable enough for production use per Anthropic's own guidance.
- **Timeout/cancellation risk** — SDK `query()` spawns a Node.js subprocess. If `asyncio.wait_for()` cancellation doesn't kill the subprocess, orphaned processes accumulate. Task 0.4 prototypes this before Phase 1. (Audit blocker #4 fix.)

### Source references

- Current AI backend: `scripts/merge_governor/ai_backend_sdk.py` (402 lines, raw `anthropic` SDK)
- Abstract interface: `scripts/merge_governor/ai_backend_base.py` (72 lines, `ReviewBackend` ABC)
- Agent SDK skill: `.claude/skills/claude-agent-sdk/SKILL.md`
- Agent SDK hooks: `.claude/skills/claude-agent-sdk/references/hooks-permissions.md`
- Agent SDK production: `.claude/skills/claude-agent-sdk/references/production-deployment.md`
- Governor audit (this session): `output/plan-audit/governor-agent-sdk-upgrade/AUDIT_REPORT.md`

## Requirements Regression Checklist

- [ ] Does the new backend implement the `ReviewBackend` ABC interface? (ai_backend_base.py)
- [ ] Does `review()` return a `ReviewResult` with decision, reasoning, confidence, conflicting_files, suggested_fix?
- [ ] Does `chat()` return a plain string response?
- [ ] Does `health_check()` verify the SDK is available and API key works?
- [ ] Is `ANTHROPIC_API_KEY` loaded from environment (Doppler), never hardcoded?
- [ ] Is `Edit` / `Write` / `NotebookEdit` in `disallowed_tools` for review agent? (Audit blocker #2)
- [ ] Is `max_budget_usd` set per review ($0.50) and chat ($0.25) call?
- [ ] Is `max_turns` capped (review=10, chat=5)?
- [ ] Does the chat agent have `PreToolUse` hooks blocking destructive Bash commands?
- [ ] Are Windows subprocess rules followed — no visible terminal windows? (CREATE_NO_WINDOW)
- [ ] Does cost tracking work (JSONL cost log, 24h rollup, `get_cost_last_24h()` in ABC)?
- [ ] Are hardcoded paths (`C:/Users/Sam/...`, `F:/Dropbox/...`) parameterized via config.py?
- [ ] Do all existing tests pass after the migration?
- [ ] Can the governor start, detect a PR, review it, and merge it end-to-end?
- [ ] Is confidence threshold gate (>= 0.80) enforced before auto-merge? (Audit blocker #3)
- [ ] Does `asyncio.wait_for()` properly kill the SDK subprocess on timeout? (Audit blocker #4)
- [ ] Is the S095A PR reviewed by the OLD backend before switching? (Audit blocker #5)
- [ ] Is `diff_text` optional in `ReviewBackend.review()` signature? (Audit blocker #6)
- [ ] Does `_init_ai_backend()` log explicit WARNING on health check failure? (Not silent None)

## Scope

### In Scope (S095A — this sprint)

| Item | Classification |
|------|----------------|
| Create `ai_backend_agent_sdk.py` using `claude-agent-sdk` | [BUILD] |
| Add `PreToolUse` hook for Bash command safety | [BUILD] |
| Add `max_budget_usd` cost cap per review/chat | [BUILD] |
| Evolve `ReviewBackend` ABC (optional diff_text, add get_cost_last_24h, needs_diff) | [EXTEND] |
| Add confidence threshold gate (>= 0.80) in merge_serializer | [BUILD] |
| Parameterize hardcoded Windows paths (config.py) | [BUILD] |
| Fix `asyncio.create_subprocess_exec` missing `CREATE_NO_WINDOW` on Windows | [BUILD] |
| Prototype SDK timeout/cancellation behavior | [BUILD] |
| Add `"agent-sdk"` to argparse choices | [BUILD] |
| Update tests (positive + negative) | [EXTEND] |

### Deferred to S095B

| Item | Reason |
|------|--------|
| Subagent builder dispatch for conflict resolution | Logically independent, requires worktree scaffolding |
| Rejection fixer dispatch | Depends on builder infrastructure |
| PRRecord builder tracking fields | Part of builder dispatch |
| E2E test: reject + builder fix cycle | Depends on builder dispatch |

### Out of Scope

- Governor main loop, PR watcher, state manager — unchanged
- Google Chat alerts (separate sprint)
- Automated rollback on deploy failure (separate sprint)

## Phase 0: Dependencies and Setup (4 units)

### Task 0.1: Install Claude Agent SDK

```bash
pip install claude-agent-sdk
```

Verify installation:
```python
python -c "from claude_agent_sdk import query, ClaudeAgentOptions; print('OK')"
```

**HARD BLOCKER:** If `claude-agent-sdk` cannot be installed on Python 3.12 / Windows 11, STOP and present options. (Source: SDK requires Python 3.10+, Node.js 18+)

### Task 0.2: Verify API key compatibility

The Agent SDK uses the same `ANTHROPIC_API_KEY` env var. Verify:
```bash
ANTHROPIC_API_KEY=$(doppler secrets get ANTHROPIC_API_KEY --plain --project bei-erp --config dev) \
python -c "
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

async def test():
    async for msg in query(
        prompt='What is 2+2?',
        options=ClaudeAgentOptions(
            allowed_tools=[],
            max_turns=1,
        ),
    ):
        if isinstance(msg, ResultMessage):
            print(f'Result: {msg.result}')
            print(f'Cost: \${msg.total_cost_usd:.4f}')

asyncio.run(test())
"
```

### Task 0.3: Parameterize hardcoded paths

Create `scripts/merge_governor/config.py`:
```python
import os
import shutil
from pathlib import Path

DOPPLER_BIN = os.environ.get("DOPPLER_BIN") or shutil.which("doppler") or "doppler"
BEI_TASKS_DIR = os.environ.get("BEI_TASKS_DIR", "F:/Dropbox/Projects/bei-tasks")
VERCEL_SCOPE = os.environ.get("VERCEL_SCOPE", "team_xvK1nhuvsdZp3GNfd4uDJ0DW")
GOVERNOR_REPO = "Bebang-Enterprise-Inc/hrms"
```

Update `merge_serializer.py` to import from `config.py` instead of hardcoding.

### Task 0.4: Prototype SDK timeout/cancellation on Windows

**HARD BLOCKER:** Must pass before Phase 1. (Source: Audit blocker #4 — event loop deadlock risk)

Test script:
```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions

async def test_timeout():
    try:
        async for msg in asyncio.wait_for(
            _consume_query("Count to 1000 slowly"),
            timeout=5.0,  # Force timeout
        ):
            pass
    except asyncio.TimeoutError:
        print("Timeout fired")
    # Check: is the Node.js subprocess still running?
    import subprocess
    result = subprocess.run(["tasklist"], capture_output=True, text=True)
    node_procs = [l for l in result.stdout.splitlines() if "node" in l.lower()]
    print(f"Node processes after timeout: {len(node_procs)}")
    # If leaking, implement PID-tracking wrapper
```

If subprocess leaks on cancellation, implement a wrapper that:
1. Tracks the child PID from the SDK's subprocess
2. On timeout, explicitly kills the PID tree with `taskkill /F /T /PID {pid}`
3. Wraps every `query()` call in the governor

## Phase 1: Review Backend Migration (11 units)

### Task 1.1: Evolve ReviewBackend ABC

Update `ai_backend_base.py`:
```python
class ReviewBackend(abc.ABC):
    @property
    def needs_diff(self) -> bool:
        """Whether this backend needs diff_text passed to review(). Default True for backwards compat."""
        return True

    @abc.abstractmethod
    async def review(self, pr_number: int, diff_text: str = "", ...) -> ReviewResult:
        ...

    @abc.abstractmethod
    async def chat(self, message: str, state: "GovernorState") -> str:
        ...

    @abc.abstractmethod
    async def health_check(self) -> bool:
        ...

    def get_cost_last_24h(self) -> tuple[float, int]:
        """Return (cost_usd, call_count) for last 24h. Override in subclasses."""
        return (0.0, 0)

    def inject_review_into_chat(self, pr_number: int, result: "ReviewResult") -> None:
        """Optional: inject review result into chat context. Override if supported."""
        pass
```

Update `reviewer.py` to only call `get_pr_diff()` if `self.backend.needs_diff`.

### Task 1.2: Create `ai_backend_agent_sdk.py`

Implement `AgentSDKBackend(ReviewBackend)` using `claude_agent_sdk.query()`.

**Review method:**
```python
async def review(self, pr_number, diff_text="", merge_context=None, timeout_s=120):
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Grep", "Glob", "Bash"],
        disallowed_tools=["Edit", "Write", "NotebookEdit"],  # READ-ONLY review
        max_turns=10,
        max_budget_usd=0.50,
        model="sonnet",
        system_prompt=REVIEW_SYSTEM_PROMPT,
        cwd=str(Path(__file__).parent.parent.parent),  # repo root
    )
    # ... parse ResultMessage.result for JSON decision
```

**HARD BLOCKER:** `disallowed_tools` MUST include `Edit`, `Write`, `NotebookEdit`. Review agents must NEVER modify files. (Source: Audit blocker #2)

**Chat method:**
```python
async def chat(self, message, state):
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Grep", "Glob", "Bash"],
        disallowed_tools=["Edit", "Write"],
        max_turns=5,
        max_budget_usd=0.25,
        continue_conversation=True,  # session persistence
        system_prompt=CHAT_SYSTEM_PROMPT,
        hooks={"PreToolUse": [HookMatcher(matcher="Bash", hooks=[bash_safety_hook])]},
    )
```

**`needs_diff` property:** Returns `False` — Agent SDK reads files directly.

### Task 1.3: Implement PreToolUse Bash safety hook

```python
BLOCKED_BASH_PATTERNS = [
    r"rm\s+-rf",
    r"docker\s+compose\s+down\s+-v",
    r"git\s+(push|reset\s+--hard|checkout\s+\.)",
    r"sudo\b",
    r"chmod\s+777",
    r"curl.*\|\s*sh",
    r"bench\s+drop-site",
    r"del\s+/[sfq]",            # Windows destructive delete
    r"rd\s+/s",                  # Windows rmdir
]
```

Hook denies any `Bash` tool call matching these patterns. Log the blocked command for audit.

### Task 1.4: Implement cost tracking bridge

Bridge Agent SDK's `total_cost_usd` to the existing JSONL cost log. Override `get_cost_last_24h()` to read from the same file.

### Task 1.5: Add confidence threshold gate

In `merge_serializer.py` `process_queue()`, before calling `_execute_merge()`:

```python
# Audit blocker #3: confidence gate before irrevocable merge
if pr.review_decision == "APPROVE":
    confidence = getattr(pr, 'review_confidence', 1.0)
    if confidence < 0.80:
        logger.warning("low_confidence_review", pr=pr_num, confidence=confidence)
        await self._comment_on_pr(pr_num,
            f"**Governor: Low confidence review ({confidence:.2f})**\n\n"
            "Auto-merge paused. Manual review recommended.\n\n*Posted by governor-erp*"
        )
        state.merge_queue.remove(pr_num)
        self.state_mgr.save()
        return
```

Add `review_confidence: float = 1.0` to `PRRecord`. Set it when review completes.

### Task 1.6: Wire new backend into governor

In `governor_erp.py` `_init_ai_backend()`:
```python
elif self.ai_backend_type == "agent-sdk":
    from .ai_backend_agent_sdk import AgentSDKBackend
    backend = AgentSDKBackend()
    if await backend.health_check():
        logger.info("ai_backend_ready", type="agent-sdk")
        return backend
    else:
        logger.warning("agent_sdk_backend_unavailable",
                       hint="Falling back — check ANTHROPIC_API_KEY and claude-agent-sdk install")
        return None
```

Add `"agent-sdk"` to argparse choices. Do NOT change default yet (self-upgrade sequencing gate — audit blocker #5).

### Task 1.7: Fix Windows CREATE_NO_WINDOW

Add to `merge_serializer.py` and `governor_erp.py`:
```python
import sys
_WIN_FLAGS = 0x08000000 if sys.platform == "win32" else 0
```

Apply `creationflags=_WIN_FLAGS` to all `asyncio.create_subprocess_exec()` calls.

### Task 1.8: Update tests (positive + negative)

**Positive tests:**
- `AgentSDKBackend` implements `ReviewBackend` ABC
- `ReviewResult` parsing from Agent SDK output
- Cost logging with `ResultMessage.total_cost_usd`
- `needs_diff` returns `False`

**Negative tests (audit blocker — Deployment QA W2):**
- Agent SDK query() timeout → governor continues, no orphaned subprocess
- Budget exceeded → review returns error, not crash
- SDK unavailable → health_check returns False, governor falls back
- Malformed agent response → parse failure returns REJECT with reasoning
- PreToolUse hook blocks `rm -rf` → verify deny

## Phase 2: E2E Verification and Closeout (4 units)

### Task 2.1: Live E2E test — review + merge

1. Create a real feature branch with a small change
2. Push PR to `Bebang-Enterprise-Inc/hrms`
3. Start governor with `bei-governor --backend agent-sdk`
4. Verify: detect → review (agent reads files, not just diff) → approve → merge → deploy → L1 → Vercel

### Task 2.2: Cost audit

Compare costs:
- Old backend: ~$0.05-0.10 per review
- New backend: expected ~$0.10-0.30 per review
- Verify `max_budget_usd` cap enforced in cost log

### Task 2.3: Commit, PR, and merge using OLD backend

**HARD BLOCKER:** The S095A PR MUST be reviewed and merged by the OLD `sdk` backend. Do NOT switch the default to `agent-sdk` in this commit. (Source: Audit blocker #5 — self-upgrade circularity)

```bash
git add scripts/merge_governor/
git commit -m "feat(s095a): migrate governor review backend to Claude Agent SDK"
# PR is reviewed by old backend → governor merges → deploy
```

After merge succeeds, create a SECOND commit that changes the argparse default:
```bash
# Now safe to switch default
# Edit governor_erp.py: default="sdk" → default="agent-sdk"
git commit -m "feat(s095a): activate agent-sdk as default governor backend"
# This PR is the first one reviewed by the NEW backend
```

### Task 2.4: Closeout

- Update this plan YAML: status → COMPLETED, add completed_date and execution_summary
- Update `docs/plans/SPRINT_REGISTRY.md` row for S095A
- `git add -f docs/plans/` and push

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| sam@bebang.ph | Push PR with clean feature code to `feat/test-s095` | Governor reviews using Agent SDK (uses `Read`+`Grep` on actual files) → APPROVE (>= 0.80 confidence) → merge → deploy → L1 → Vercel cache-bust | Agent SDK review not working |
| sam@bebang.ph | Push PR with `rm -rf /` in a shell script | Governor review REJECT + PreToolUse hook blocks if agent tries to execute it. PR comment posted with reasoning. | Bash safety hook not working |
| sam@bebang.ph | Ask governor chat "what files does PR X touch?" | Governor agent uses `Grep`/`Glob` on repo, lists actual files with line counts | Chat tool access not working |
| sam@bebang.ph | Run 5 reviews in one session | Each review under $0.50, total under $2.50 in cost log | Cost caps not enforced |
| sam@bebang.ph | Push PR that gets APPROVE with confidence 0.65 | Governor pauses queue, posts "Low confidence review" comment, does NOT merge | Confidence gate not working |
| sam@bebang.ph | Kill governor mid-review (Ctrl+C) | No orphaned Node.js processes remain after 10s | Timeout/cleanup not working |

## Autonomous Execution Contract

```yaml
completion_condition:
  - AgentSDKBackend passes all ReviewBackend interface tests
  - Governor start -> detect PR -> agent-sdk review -> merge pipeline works E2E
  - PreToolUse hook blocks all dangerous Bash patterns
  - max_budget_usd enforced per review ($0.50) and chat ($0.25)
  - Confidence threshold (>= 0.80) enforced before auto-merge
  - SDK timeout/cancellation verified (no orphaned processes)
  - Hardcoded paths parameterized via config.py
  - CREATE_NO_WINDOW applied to all subprocess calls
  - S095A PR merged by OLD backend, then default switched
  - Plan YAML status updated to COMPLETED and pushed to production
  - SPRINT_REGISTRY.md row updated to COMPLETED and pushed to production

stop_only_for:
  - claude-agent-sdk package cannot be installed (compatibility issue)
  - ANTHROPIC_API_KEY not working with Agent SDK (auth model difference)
  - Agent SDK subprocess spawning conflicts with Windows event loop (Task 0.4 fails)
  - Cost per review exceeds $1.00 (unexpected pricing change)

continue_without_pause_through:
  - install
  - implement
  - test
  - pr_creation
  - e2e
  - closeout

blocker_policy:
  - programmatic -> fix and continue
  - SDK compatibility issue -> research, try workaround, continue
  - repeated failure x3 -> STOP, summarize, present options
  - cost model surprise -> STOP, present options

signoff_authority: single-owner
```

## Agent Boot Sequence

1. Read this plan fully.
2. Read `docs/plans/SPRINT_REGISTRY.md` for cross-sprint context.
3. Read `.claude/skills/claude-agent-sdk/SKILL.md` for SDK API reference.
4. Read `.claude/skills/claude-agent-sdk/references/hooks-permissions.md` for PreToolUse hook patterns.
5. Read `scripts/merge_governor/ai_backend_base.py` for the interface contract.
6. Read `scripts/merge_governor/ai_backend_sdk.py` for the current implementation being replaced.
7. Confirm `pip install claude-agent-sdk` succeeds before starting Phase 1.
8. Run Task 0.4 (timeout prototype) and confirm it passes before starting Phase 1.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.
