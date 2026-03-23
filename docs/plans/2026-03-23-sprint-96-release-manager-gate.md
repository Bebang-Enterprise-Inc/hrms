# S096: bei-release-manager — Two-Layer Release Gate

```yaml
canonical_sprint_id: S096
status: COMPLETED
created_date: 2026-03-23
completed_date: 2026-03-23
execution_summary: "Two-layer release gate live. Deterministic checks L3 evidence files + entry counts. AI verifies evidence authenticity. Both run in parallel, both must pass. Gate blocks merge and posts PR comment. Re-queue on new SHA via gate_blocked flag. Non-sprint PRs skip automatically."
depends_on: S095
lane: single
estimated_work_units: 15
audit_version: 2
audit_date: 2026-03-23
audit_blockers_resolved: 5
```

> **AUDIT AMENDMENT (v2, 2026-03-23):** 5 blockers resolved: evidence must be committed to git branch, dual-format support for legacy+canonical L3 files, re-queue mechanism via `gate_blocked` flag on PRRecord, AI timeout defaults to FAIL (not PASS), AI budget/turns increased. Full audit: `output/plan-audit/release-manager-gate/AUDIT_REPORT.md`

## Summary

Add a two-layer release gate to the governor's merge pipeline that blocks merge until the builder has provably completed all plan tasks AND produced valid L3 evidence. Layer 1 is deterministic (pure Python checks, $0). Layer 2 is AI verification (Agent SDK, ~$0.10). Both run in parallel. Both must pass. Builders (Max subscription, $0) do all heavy lifting — the release gate only validates.

Inspired by Stripe's Minions "blueprint" pattern: alternating creative nodes (agents write code) with deterministic gates (infrastructure validates, agents cannot skip).

## Design Rationale (For Cold-Start Agents)

### Why this exists

S092 and S093 proved that builder agents declare "COMPLETED" and "21 PASS, 0 FAIL" after only loading pages (L2) without clicking buttons, filling forms, or submitting anything (L3). Research confirms 27-78% of LLM agent "successes" are corrupt — the agent reports green while skipping procedural steps (arXiv 2603.03116).

Specific incidents:
- **S093 (2026-03-23):** Builder declared "Complete Deliverables" while L3 browser tests were still failing. Lost code changes during squash merge. Date picker test never passed. Still called it "complete."
- **S092 (2026-03-22):** Builder ran L2 page loads and reported "all pass" without any form submissions or button clicks.

The current governor reviews code quality but does NOT check whether the builder actually finished all plan tasks or produced L3 evidence. This gap lets corner-cutting agents merge incomplete work.

### Evidence transport (Audit blocker #1 fix)

Evidence files MUST be committed to the PR branch by the builder. The gate reads evidence from the checked-out branch, NOT from the governor's local filesystem. The builder workflow is:

```
1. Builder runs L3 tests → creates output/l3/{sprint}/ files
2. Builder runs: git add -f output/l3/ && git commit -m "test: add L3 evidence" && git push
3. Governor polls → detects new SHA → re-reviews → runs release gate
4. Gate checks evidence files FROM THE BRANCH (git show or local checkout)
```

The `/execute-plan-bei-erp` skill must be updated to require `git add -f output/l3/` as a mandatory pre-PR step.

### Evidence format: dual support (Audit blocker #2 fix)

Current L3 scripts write `output/l3/s093_browser_YYYYMMDD.json` (flat, date-stamped). The canonical contract expects three files in a subdirectory. The gate supports BOTH:

| Format | Pattern | When Used |
|--------|---------|-----------|
| **Canonical (new)** | `output/l3/{sprint}/form_submissions.json` | S096+ sprints |
| **Legacy (existing)** | `output/l3/{sprint}_*.json` or `output/l3/s{NNN}_*.json` | Pre-S096 sprints |

Deterministic layer checks canonical first, falls back to legacy. If either exists with valid entries, the check passes.

### Re-queue after gate block (Audit blocker #3 fix)

When the gate blocks a PR, it sets `pr.gate_blocked = True` and removes from queue. When the PR watcher detects a SHA change on a `gate_blocked` PR, it clears the flag, re-queues the PR, and the governor re-reviews + re-gates. This closes the feedback loop.

### AI timeout = FAIL (Audit blocker #4 fix)

AI verification timeout defaults to FAIL, not PASS. A fraud-detection layer that silently passes on failure defeats its purpose. The PR comment says: "AI verification timed out — push again to retry." This matches the governor's existing conservative REJECT-on-timeout pattern.

### Key trade-off: what the gate does NOT do

The release gate does NOT:
- Run tests itself (builder's job)
- Fix missing evidence (builder's job)
- Generate L3 scenarios (plan's job)
- Build code (builder's job)

It only asks: "Did the builder actually do what the plan says?" and "Is the evidence real?"

### Source references

- Governor merge flow: `scripts/merge_governor/merge_serializer.py:104` (insertion point)
- L3 evidence contract: `.claude/skills/execute-plan-bei-erp/SKILL.md` (Anti-Corrupt-Success Rule)
- Existing L3 scripts: `scripts/testing/l3_s093_browser_test.py` (legacy format example)
- Stripe Minions blueprint: https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents
- Audit report: `output/plan-audit/release-manager-gate/AUDIT_REPORT.md`

## Requirements Regression Checklist

- [ ] Deterministic layer runs pure Python — no AI, no API calls, $0 cost?
- [ ] AI layer uses Agent SDK with max_budget_usd=$0.20, max_turns=4? (Audit blocker #5)
- [ ] Both layers run in parallel (asyncio.gather)?
- [ ] Both must PASS for merge to proceed? (AI timeout = FAIL, not PASS — Audit blocker #4)
- [ ] If either fails, PR comment posted listing exact missing items?
- [ ] Builder pushes fix → SHA changes → gate_blocked cleared → PR re-queued? (Audit blocker #3)
- [ ] Gate skippable for non-sprint PRs (infra, docs, hotfixes)?
- [ ] Gate reads evidence from PR branch, not local filesystem? (Audit blocker #1)
- [ ] Gate supports both canonical and legacy L3 file formats? (Audit blocker #2)
- [ ] Deterministic checks cannot be bypassed by the AI agent?
- [ ] asyncio.gather with return_exceptions=True handles Exception objects explicitly?
- [ ] AI verifier uses fresh session (continue_conversation=False)?
- [ ] PRRecord has gate_blocked field?

## Scope

### In Scope

| Item | Classification |
|------|----------------|
| `release_gate.py` — deterministic checker (dual-format support) | [BUILD] |
| AI evidence verifier in `ai_backend_agent_sdk.py` | [EXTEND] |
| Wire gate into `merge_serializer.py` between confidence check and merge | [EXTEND] |
| PR comment feedback for missing evidence | [EXTEND] |
| Skip gate for non-sprint PRs | [BUILD] |
| Add `gate_blocked` field to PRRecord + re-queue logic in PR watcher | [BUILD] |
| Test fixtures (synthetic plan + evidence files) | [BUILD] |
| Tests for deterministic layer | [BUILD] |

### Out of Scope

- Running L3 tests (builder's job)
- Screenshot image analysis (future — current AI layer reads JSON only)
- Google Chat notifications (separate sprint)

## Phase 0: Design + PRRecord Update (2 units)

### Task 0.1: Add `gate_blocked` to PRRecord

In `state_manager.py`, add to PRRecord:
```python
gate_blocked: bool = False
```

**HARD BLOCKER:** This field must be cleared when SHA changes (in pr_watcher.py reconcile). Otherwise gate-blocked PRs stay blocked forever. (Source: Audit blocker #3)

### Task 0.2: Wire re-queue in PR watcher

In `pr_watcher.py` reconcile(), where SHA change is detected, add:
```python
if new_sha != existing.head_sha:
    existing.head_sha = new_sha
    # Re-queue gate-blocked PRs on new push
    if existing.gate_blocked:
        existing.gate_blocked = False
        existing.review_decision = None  # Force re-review
        if existing.number not in state.merge_queue:
            state.merge_queue.append(existing.number)
```

## Phase 1: Deterministic Layer (5 units)

### Task 1.1: Implement plan file discovery

```python
def find_sprint_plan(branch_name: str, plans_dir: str = "docs/plans") -> Path | None:
    match = re.search(r's0?(\d{2,3})', branch_name, re.IGNORECASE)
    if not match:
        return None
    sprint_num = match.group(1)
    # Search for matching plan file
    for f in Path(plans_dir).glob(f"*sprint*{sprint_num}*"):
        if f.suffix == ".md":
            return f
    for f in Path(plans_dir).glob(f"*s0{sprint_num}*"):
        if f.suffix == ".md":
            return f
    return None
```

### Task 1.2: Create `release_gate.py`

```python
@dataclass
class GateResult:
    passed: bool
    missing_tasks: list[str]
    missing_evidence: list[str]
    evidence_gaps: list[str]
    details: str

    @property
    def comment(self) -> str:
        """Format as actionable PR comment."""
        ...
```

**Checks (all pure Python, no AI):**

1. **L3 evidence existence (dual format):**
   - Check canonical: `output/l3/{sprint}/form_submissions.json`
   - Fallback legacy: `output/l3/{sprint}_*.json` or `output/l3/s{NNN}_*.json`
   - Evidence files must exist IN THE BRANCH (read via `git show HEAD:path` or check working tree after checkout)

2. **L3 evidence count:** Read plan's L3 Workflow Scenarios table → count rows → verify evidence has at least that many entries.

3. **No test.skip:** Scan PR diff for `test.skip`, `pytest.mark.skip`, `@unittest.skip`.

4. **Screenshot existence:** For entries with `screenshot_after`, verify path exists.

**HARD BLOCKER:** This module must NOT import `claude_agent_sdk` or any AI library. Pure Python, zero external dependencies. (Source: Stripe blueprint — deterministic gates are infrastructure, not AI.)

### Task 1.3: Wire gate into merge_serializer

Between confidence gate and `_execute_merge()`:

```python
# Release gate: deterministic + AI (parallel)
gate_passed = await self._run_release_gate(pr)
if not gate_passed:
    # Gate sets gate_blocked=True and posts comment
    if pr_num in state.merge_queue:
        state.merge_queue.remove(pr_num)
        self.state_mgr.save()
    return
```

### Task 1.4: Create test fixtures

Create synthetic test data for E2E testing:
- `scripts/merge_governor/test_fixtures/test_plan.md` — minimal plan with 2 L3 scenarios
- `scripts/merge_governor/test_fixtures/valid_evidence/form_submissions.json` — 2 valid entries
- `scripts/merge_governor/test_fixtures/fabricated_evidence/form_submissions.json` — entries with `"test"` values
- `scripts/merge_governor/test_fixtures/incomplete_evidence/form_submissions.json` — 1 entry (plan has 2)

## Phase 2: AI Verification Layer (4 units)

### Task 2.1: Implement AI evidence verifier

Add to `ai_backend_agent_sdk.py`:

```python
async def verify_evidence(self, evidence_path: str, plan_scenarios: list[str]) -> dict:
    """AI verification of L3 evidence authenticity.
    Returns: {"passed": bool, "issues": list[str]}
    """
```

Config:
- `max_budget_usd=0.20` (Audit blocker #5)
- `max_turns=4` (Audit blocker #5)
- `model="sonnet"`
- `disallowed_tools=["Edit", "Write", "Bash"]` — READ ONLY
- `continue_conversation=False` — fresh session, isolated from reviewer
- On timeout: return `{"passed": False, "issues": ["AI verification timed out"]}` (Audit blocker #4)

**HARD BLOCKER:** AI layer must NOT have write access. Read-only. (Source: S095 audit blocker #2)

### Task 2.2: Parallel execution

```python
async def _run_release_gate(self, pr) -> bool:
    det_task = asyncio.create_task(self._deterministic_check(pr))
    ai_task = asyncio.create_task(self._ai_verify_evidence(pr))

    results = await asyncio.gather(det_task, ai_task, return_exceptions=True)

    det_result = results[0] if not isinstance(results[0], Exception) else GateResult(passed=False, ...)
    ai_result = results[1] if not isinstance(results[1], Exception) else {"passed": False, "issues": [str(results[1])]}

    passed = det_result.passed and ai_result.get("passed", False)

    if not passed:
        pr.gate_blocked = True
        self.state_mgr.save()
        comment = self._format_gate_comment(det_result, ai_result)
        await self._comment_on_pr(pr.number, comment)

    return passed
```

### Task 2.3: Format combined PR comment

Combines deterministic and AI findings into one actionable comment with the `*Posted by bei-release-manager*` signature.

## Phase 3: E2E Testing and Closeout (4 units)

### Task 3.1: E2E test — gate blocks incomplete PR

1. Create branch `test/s096-gate-test-incomplete` with code but no evidence
2. Create synthetic plan file matching branch name
3. Push PR
4. Governor reviews → APPROVE → gate → BLOCKED (missing evidence)
5. Verify PR comment lists exact missing items
6. Add evidence files, commit, push
7. Verify: SHA change → gate_blocked cleared → re-queued → re-reviewed → gate PASS

### Task 3.2: E2E test — gate passes complete PR

1. Create branch `test/s096-gate-test-complete` with code AND valid evidence committed
2. Push PR
3. Governor reviews → APPROVE → gate → PASS → merge (dry-run)

### Task 3.3: E2E test — gate catches fabricated evidence

1. Create branch with evidence where all inputs = "test", "asdf"
2. Deterministic layer: PASS (entries exist, count matches)
3. AI layer: FAIL ("unrealistic input values")
4. Gate: BLOCKED

### Task 3.4: Closeout

- Update plan YAML: status → COMPLETED
- Update SPRINT_REGISTRY.md
- `git add -f docs/plans/` and push

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| sam@bebang.ph | Push sprint PR with code but no `output/l3/` evidence | Gate BLOCKED, PR comment: "form_submissions.json not found in branch" | Deterministic layer not checking |
| sam@bebang.ph | Push sprint PR with evidence but fewer entries than plan | Gate BLOCKED, PR comment: "2 entries but plan has 5 scenarios" | Count check broken |
| sam@bebang.ph | Push sprint PR with complete valid evidence | Gate PASS, governor merges | False-blocking |
| sam@bebang.ph | Push non-sprint PR (`fix/typo`) | Gate SKIPPED, merges normally | Skip logic broken |
| sam@bebang.ph | Push sprint PR with fabricated evidence (inputs="test") | AI FAIL, deterministic PASS → Gate BLOCKED | AI fraud detection broken |
| sam@bebang.ph | Push fix after gate block → new SHA | gate_blocked cleared, PR re-queued, re-gated | Re-queue mechanism broken |
| sam@bebang.ph | AI verification times out | Gate BLOCKED (conservative), comment: "AI timed out — push again" | Timeout handling wrong |

## Autonomous Execution Contract

```yaml
completion_condition:
  - release_gate.py deterministic checks pass with test fixtures
  - AI verifier catches fabricated evidence in test
  - AI timeout returns FAIL (not PASS)
  - Gate wired into merge_serializer between confidence check and merge
  - Gate skips non-sprint PRs correctly
  - gate_blocked flag clears on SHA change and re-queues PR
  - E2E: incomplete PR blocked, then evidence added → re-gated → passes
  - E2E: fabricated evidence blocked by AI layer
  - Plan YAML status updated to COMPLETED and pushed
  - SPRINT_REGISTRY.md row updated

stop_only_for:
  - Agent SDK unavailable for AI layer (degrade to deterministic-only)
  - Plan file format changed (task extraction regex breaks)

continue_without_pause_through:
  - implement
  - test
  - pr_creation
  - e2e
  - closeout

blocker_policy:
  - programmatic -> fix and continue
  - repeated failure x3 -> STOP, present options

signoff_authority: single-owner
```

## Agent Boot Sequence

1. Read this plan fully.
2. Read `scripts/merge_governor/merge_serializer.py` — understand merge flow (confidence gate at ~line 88-102, insertion point at ~line 104).
3. Read `scripts/merge_governor/pr_watcher.py` — understand SHA change detection in `reconcile()` (~line 110-121).
4. Read `scripts/merge_governor/state_manager.py` — understand PRRecord fields.
5. Read `scripts/merge_governor/ai_backend_agent_sdk.py` — understand `_run_query` pattern for AI calls.
6. Read `.claude/skills/execute-plan-bei-erp/SKILL.md` — find the L3 evidence file contract.
7. Run `ls output/l3/ 2>/dev/null` to understand existing evidence file layout.
8. Run `ls scripts/testing/l3_*.py 2>/dev/null` to understand existing test script output format.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.
