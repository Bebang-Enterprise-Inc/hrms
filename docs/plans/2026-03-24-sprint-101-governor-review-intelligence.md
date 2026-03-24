# S101: Governor AI Review Intelligence

```yaml
canonical_sprint_id: S101
status: COMPLETED
execution_started: 2026-03-24
created_date: 2026-03-24
depends_on: S098
branch: s101-governor-review-intelligence
lane: single
estimated_work_units: 45
```

## Summary

Replace the governor's rubber-stamp AI reviews with real code analysis that uses tools, shows chain-of-thought in the terminal, checks against known failure patterns (lessons), and runs deterministic validations (py_compile, Link field audits). The operator must be able to watch the AI think in real time — exactly like watching Claude Code work.

## Design Rationale (For Cold-Start Agents)

### Why this exists

Today's governor AI review is a single API call: prompt in, JSON out, 6 seconds, 0.95 confidence on everything. It:

- Did NOT catch `@frappe.whitelist()` on a constant (S097 — 3 build failures)
- Did NOT catch a DocType Link field with a default referencing data absent from CI (S100 — CI failure)
- Did NOT catch hardcoded approver emails (S099 audit finding)
- Gives 0.95 confidence on 2000-line PRs it "reviewed" in 6 seconds
- Shows zero reasoning in the terminal — operator has no idea what it checked

The confidence number is meaningless, the review is shallow, and the operator can't validate it.

### Why tool-driven review (not better prompts)

| Approach | Pros | Cons | Fit |
|----------|------|------|-----|
| Better system prompt | Zero cost, easy | Still single-pass, no verification | Not enough |
| Multi-turn with tools | Reads files, runs checks, iterates | Costs more (~$0.30/review vs $0.05) | **Best fit** |
| Deterministic-only | Zero cost, catches known patterns | Can't reason about logic or context | Complement, not replacement |
| Fine-tuned model | Learns BEI patterns | Requires training data, can't update quickly | Overkill |

The right answer is **two layers**: deterministic checks (free, instant) PLUS multi-turn AI review (with tools, chain-of-thought, $0.30).

### What the operator sees today vs. what they should see

**Today:**
```
[00:48:08] Reviewing PR #321...
[00:48:14] PR #321 -> APPROVE (confidence: 0.95)
    Reason: This is a well-structured feature PR...
```

**After S101:**
```
[00:48:08] Reviewing PR #321 (25 files changed)...
[00:48:09]   Step 1/6: Running deterministic checks...
[00:48:09]     py_compile: 12 .py files OK
[00:48:09]     Link defaults: FAIL — bei_settings.json line 301 has default "Bebang Kitchen Inc." on Link field
[00:48:09]     Decorator check: OK — no decorators on non-functions
[00:48:09]     Lesson check: 0/10 lessons triggered
[00:48:10]   Step 2/6: AI reading changed files...
[00:48:12]     Read hrms/api/procurement.py (450 lines)
[00:48:13]     Read hrms/api/warehouse.py (380 lines)
[00:48:14]     Read hrms/hr/doctype/bei_settings/bei_settings.json (320 lines)
[00:48:15]   Step 3/6: Checking imports and dependencies...
[00:48:16]     Grep: get_procurement_settings imported in 4 files — all valid
[00:48:17]   Step 4/6: Checking for anti-patterns...
[00:48:18]     Grep: hardcoded emails — found 2 in delivery_billing_policy.py (known, in BEI Settings migration)
[00:48:19]   Step 5/6: Cross-referencing with recent merges...
[00:48:20]     No conflicting file modifications with last 5 merged PRs
[00:48:21]   Step 6/6: Generating verdict...
[00:48:22] PR #321 -> NEEDS_FIX (confidence: 0.72)
    Issue: Link field default will break CI (lesson: 2026-03-24-ci-link-validation)
    Fix: Remove "default" from commissary_company field in bei_settings.json
```

### Source references

- Current review backend: `scripts/merge_governor/ai_backend_agent_sdk.py` (lines 156-238)
- Governor lessons: `~/.governor/memory/lesson-*.md` (10 lessons, 4 playbooks)
- Agent SDK docs: `claude_agent_sdk` — `ClaudeAgentOptions`, `query()` async generator
- S097 incident: `@frappe.whitelist()` on constant caused 3 build failures
- S100 incident: Link default broke CI install
- S099 audit: hardcoded approver emails discovered

## Requirements Regression Checklist

- [ ] Does every review show step-by-step progress in the terminal?
- [ ] Does the AI use Read/Grep/Glob tools during review (not just parse a diff)?
- [ ] Does the deterministic layer run py_compile on every changed .py file?
- [ ] Does the deterministic layer check Link field defaults in DocType JSONs?
- [ ] Does the deterministic layer check for decorators on non-functions?
- [ ] Does the deterministic layer match changed code against all governor lessons?
- [ ] Does the AI layer read the actual source files, not just diff text?
- [ ] Does the AI explain WHAT it checked and WHY it approved/rejected?
- [ ] Is confidence based on verification depth (files read, checks passed), not vibes?
- [ ] Can the operator see the AI's chain-of-thought in real time?
- [ ] Does the review stream tool calls to terminal as they happen?
- [ ] Are deterministic check results included in the AI's context?
- [ ] Is cost per review tracked and displayed?
- [ ] Does the review complete within 2 minutes for typical PRs?

## Scope

### In Scope

| Item | Classification |
|------|----------------|
| Deterministic pre-check layer (py_compile, Link audit, decorator check, lesson match) | [BUILD] |
| Terminal streaming of AI tool calls and reasoning | [BUILD] |
| Structured multi-step review prompt with tool use | [EXTEND] |
| Confidence scoring based on verification depth | [BUILD] |
| Lesson-driven pattern checking during review | [EXTEND] |
| Review progress display in terminal | [BUILD] |

### Out of Scope

- Changing the merge pipeline flow (already working)
- Release gate improvements (separate sprint)
- Builder dispatch changes
- Frontend/Vercel deploy changes

## Phase 1: Deterministic Pre-Check Layer (12 units)

Pure Python checks that run BEFORE the AI review. Zero cost, instant, catches 80% of known issues.

### Task 1.1: Create `pre_check.py` module

```python
@dataclass
class PreCheckResult:
    passed: bool
    checks: list[CheckItem]  # name, passed, detail
    blocking_issues: list[str]  # issues that should trigger REJECT
    warnings: list[str]  # issues the AI should investigate further

@dataclass
class CheckItem:
    name: str
    passed: bool
    detail: str
```

### Task 1.2: py_compile check

For every `.py` file in the PR diff:
```python
import py_compile
py_compile.compile(filepath, doraise=True)
```
**HARD BLOCKER:** Must run on actual files, not diff text. Use `git diff --name-only` to get the file list.

### Task 1.3: Link field default audit

For every `.json` file in `hrms/hr/doctype/bei_*/`:
- Parse the JSON
- Find fields where `fieldtype == "Link"` and `default` is set
- Flag as BLOCKING — Link defaults reference records that may not exist in CI

**Source:** Lesson `2026-03-24-ci-link-validation-error-on-default`

### Task 1.4: Decorator placement check

For every changed `.py` file:
- Parse with `ast.parse()`
- Check that decorators (`@frappe.whitelist()`, `@frappe.validate_and_sanitize_search_inputs`) are only on `FunctionDef` or `AsyncFunctionDef` nodes
- Flag decorators on `Assign`, `AnnAssign`, or module-level statements as BLOCKING

**Source:** Lesson `2026-03-23-decorator-frappe-whitelist-applied-to`

### Task 1.5: Lesson pattern matcher

Load all lessons from `~/.governor/memory/lesson-*.md`:
- Extract `trigger` field from YAML frontmatter
- For each changed file, check if any lesson trigger pattern matches
- Return matching lessons as warnings for the AI to investigate

### Task 1.6: Terminal output for pre-checks

Print each check result as it runs:
```
[HH:MM:SS]   Pre-checks: py_compile (12 files)... OK
[HH:MM:SS]   Pre-checks: Link defaults... FAIL (1 issue)
[HH:MM:SS]     bei_settings.json:301 — Link field "commissary_company" has default "Bebang Kitchen Inc."
[HH:MM:SS]   Pre-checks: Decorators... OK
[HH:MM:SS]   Pre-checks: Lesson match... 0 triggered
```

## Phase 2A: Streaming AI Review (12 units)

### Task 2.1: Stream tool calls to terminal

The Agent SDK's `query()` returns an async generator of messages. Currently `_run_query()` silently consumes all messages and returns the final result. Change it to **print tool calls and reasoning to terminal in real time**.

```python
async for msg in query(prompt=prompt, options=options):
    if isinstance(msg, AssistantMessage):
        for block in msg.content:
            if hasattr(block, "text") and block.text.strip():
                # Print AI reasoning to terminal
                for line in block.text.strip().splitlines():
                    print(f"[{ts}]     AI: {line[:120]}", flush=True)
            elif hasattr(block, "name"):
                # Tool call — print what the AI is doing
                tool_name = block.name
                tool_input = getattr(block, "input", {})
                _print_tool_call(ts, tool_name, tool_input)
    if isinstance(msg, ToolResultMessage):
        # Print abbreviated tool result
        _print_tool_result(ts, msg)
```

**HARD BLOCKER:** The streaming output must show the SAME information visible when watching Claude Code work — which tool is being called, on which file, and what the AI concluded. (Source: user requirement "I want to see its chain of thought")

**HARD BLOCKER:** Add `ToolResultMessage` to the import from `claude_agent_sdk` in the streaming `_run_query`. The current import only has `AssistantMessage` and `ResultMessage`. Without `ToolResultMessage`, the `isinstance` check for tool results will fail silently. (Source: code verification audit)

### Task 2.2: Structured multi-step review prompt

Replace the single-shot review prompt with a structured multi-step prompt that forces the AI to use tools:

```
You are reviewing PR #{pr_number}. Follow these steps IN ORDER:

STEP 1: Read the pre-check results below. If any are BLOCKING, your decision is REJECT.
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
{lessons_as_checklist}

STEP 7: Generate your verdict. Base confidence on HOW MUCH you actually verified:
- 0.90+ = Read all changed files, all checks passed, no warnings
- 0.70-0.89 = Read most files, minor warnings only
- 0.50-0.69 = Could not read some files, or unresolved warnings
- Below 0.50 = Significant issues found or could not verify

Respond with JSON: {"decision": "...", "reasoning": "...", "confidence": ..., "files_read": [...], "checks_performed": [...], "conflicting_files": [], "suggested_fix": null}
```

## Phase 2B: Confidence Scoring + Review Summary (8 units)

### Task 2.3: Confidence scoring based on verification depth

**HARD BLOCKER:** Before implementing confidence calculation, add `files_read: list[str] = field(default_factory=list)` and `checks_performed: list[str] = field(default_factory=list)` to the `ReviewResult` dataclass in `ai_backend_base.py`. The AI response JSON must include these fields, and `_parse_response` must extract them. Without this, confidence calculation has no data. (Source: code verification audit)

Confidence must be calculated, not vibed:

```python
confidence = 0.5  # Base
confidence += 0.1 * min(files_read / total_files, 1.0)  # Read coverage
confidence += 0.1 if pre_checks_all_passed else 0.0      # Pre-checks
confidence += 0.1 if no_lesson_matches else 0.0           # No known anti-patterns
confidence += 0.1 if no_import_issues else 0.0            # Import verification
confidence += 0.1 if no_protected_surface_conflicts else 0.0  # No conflicts
confidence = min(confidence, 1.0)
```

The AI reports `files_read` and `checks_performed` in the JSON response. The governor calculates confidence from those, not from the AI's self-assessment.

### Task 2.4: Review summary with evidence

After the review completes, print a summary showing what was actually verified:

```
[HH:MM:SS] Review complete for PR #321:
[HH:MM:SS]   Decision: APPROVE (confidence: 0.87)
[HH:MM:SS]   Files read: 8/12 (67%)
[HH:MM:SS]   Pre-checks: 4/4 passed
[HH:MM:SS]   Lessons checked: 10, matched: 0
[HH:MM:SS]   Time: 45s | Cost: $0.28
[HH:MM:SS]   Reasoning: New SCM features add procurement notifications...
```

### Task 2.5: Increase review timeout and budget

- Timeout: 120s → 180s (the AI needs time for multi-step review)
- Budget: $0.50 → $1.00 (more tool calls = higher cost)
- Max turns: 10 → 15

> **Phase 3 (Status API + Inter-Agent Communication) moved to S102.**
> S101 focuses on review intelligence. S102 adds the API, force-wake, event bus, and self-diagnosis.

## Phase 3: Integration and Testing (13 units)

### Task 4.1: Wire pre-checks into review flow

In `AgentSDKBackend.review()`:
1. Run `pre_check.run_all(changed_files)` first
2. Print results to terminal
3. If any BLOCKING issues, return REJECT immediately (no AI call needed — saves money)
4. Pass pre-check results + warnings into the AI prompt

### Task 4.2: Wire streaming into `_run_query`

Replace the silent `_run_query` with a streaming version that prints to terminal. Keep the non-streaming version as `_run_query_silent` for health checks and chat.

### Task 4.3: Test with a known-bad PR

Create a test branch with intentional issues:
1. A `.py` file with a syntax error
2. A DocType JSON with a Link default
3. A decorator on a constant
4. A file that matches a governor lesson

Push as PR. Verify the governor:
- Pre-checks catch issues 1-3
- AI review reads the files and confirms
- Terminal shows full chain-of-thought
- Confidence is appropriately low

### Task 4.4: Test with a known-good PR

Push a clean feature PR. Verify:
- Pre-checks all pass
- AI reads files and approves
- Confidence is high (0.85+)
- Terminal shows what was verified

### Task 4.5: Closeout

- Update plan YAML: status → COMPLETED
- Update SPRINT_REGISTRY.md
- `git add -f docs/plans/` and push

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| sam@bebang.ph | Push PR with `.py` syntax error | Pre-check REJECTS with py_compile failure, no AI call made | Pre-check not wired |
| sam@bebang.ph | Push PR with Link field default | Pre-check flags BLOCKING, AI confirms with REJECT | Link audit not working |
| sam@bebang.ph | Push PR with `@whitelist` on constant | Pre-check flags BLOCKING via decorator check | Decorator check not working |
| sam@bebang.ph | Push clean feature PR | AI uses Read/Grep on files, APPROVE with 0.85+ confidence | AI not using tools |
| sam@bebang.ph | Watch terminal during review | Step-by-step output showing tool calls and reasoning | Streaming not wired |
| sam@bebang.ph | Check confidence after review | Confidence based on files_read/checks_passed, not AI vibes | Confidence not calculated |
| sam@bebang.ph | Ask governor chat "is hq healthy?" | Chat AI runs curl, reports actual HTTP status | Chat AI not using Bash |

## Autonomous Execution Contract

```yaml
completion_condition:
  - pre_check.py module implements py_compile, Link audit, decorator check, lesson match
  - AI review streams tool calls to terminal in real time
  - Confidence calculated from verification depth, not AI self-report
  - Pre-checks run before AI review, BLOCKING issues skip AI (save cost)
  - All test scenarios pass (syntax error, Link default, decorator, clean PR)
  - ReviewResult dataclass has files_read and checks_performed fields
  - Plan YAML status updated to COMPLETED and pushed (git add -f docs/plans/)
  - SPRINT_REGISTRY.md row updated to COMPLETED and pushed (git add -f docs/plans/)

stop_only_for:
  - Agent SDK streaming API doesn't support message-level iteration (unlikely — already works)
  - Pre-check breaks existing review flow for non-Python PRs

continue_without_pause_through:
  - implement
  - test
  - pr_creation
  - closeout

blocker_policy:
  - programmatic -> fix and continue
  - repeated failure x3 -> STOP, present options

signoff_authority: single-owner
```

## Agent Boot Sequence

0. **`git checkout -b s101-governor-review-intelligence production`** — MANDATORY before any code. Committing to production is FORBIDDEN.
1. Read this plan fully.
2. Read `scripts/merge_governor/ai_backend_agent_sdk.py` — understand current review flow, `_run_query`, system prompts.
3. Read `scripts/merge_governor/ai_backend_base.py` — understand `ReviewResult` dataclass.
4. Read `scripts/merge_governor/lessons.py` — understand how lessons are loaded.
5. Read 2-3 lesson files from `~/.governor/memory/lesson-*.md` — understand lesson format.
6. Read `scripts/merge_governor/governor_erp.py` — understand how reviews are triggered and results displayed.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.
