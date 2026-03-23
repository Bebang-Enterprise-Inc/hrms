# S098: Governor Self-Evolution — Reflexion + Procedural Memory

```yaml
canonical_sprint_id: S098
status: GO
created_date: 2026-03-23
completed_date: null
execution_summary: null
depends_on: S096
lane: single
estimated_work_units: 15
```

## Summary

Add a two-tier self-evolution system to the governor:

1. **Reflexion memory (lessons):** When the governor encounters failures, it writes a structured lesson ("don't do X, do Y instead"). Injected into prompts on startup. The governor never makes the same mistake twice.

2. **Procedural memory (playbooks):** When the governor successfully handles a complex situation (build recovery, conflict resolution, deploy verification), it distills the steps into a reusable playbook. Next time the same situation arises, it follows the proven procedure instead of improvising.

Both use the same pattern: plain markdown files in `~/.governor/memory/`, loaded into prompts on startup. This is the "write-manage-read" memory loop from agent memory research (arXiv 2603.07670), combining Reflexion (learn from failures) with procedural memory (learn from successes).

## Design Rationale (For Cold-Start Agents)

### Why this exists

Today's governor has static knowledge — it knows what we hardcoded into the system prompts. When it encounters a new failure pattern (like `@frappe.whitelist()` on a constant, or Docker Swarm not pulling new images), someone has to manually update the prompt. This doesn't scale.

Specific incidents that should have been auto-learned:
- **S097:** `@frappe.whitelist()` applied to a tuple constant caused SyntaxError in Docker build. Three identical build failures before a human investigated.
- **S097:** Docker deploy succeeded but container still ran old code. Governor's L1 passed (ping works) but didn't verify code freshness.
- **S093/S094:** Truncated `gh pr diff` caused false REJECT decisions. Governor kept rejecting the same PR for "truncated code."
- **S092/S093/S097:** Builders declared COMPLETED without L3 evidence. Same corner-cutting pattern three sprints in a row.

### Why Reflexion pattern (not fine-tuning or RAG)

| Approach | Pros | Cons | Fit |
|----------|------|------|-----|
| **Reflexion (text lessons in prompt)** | Zero infra, instant, auditable, editable | Context window cost (~50 tokens/lesson) | Best for <100 lessons |
| **Fine-tuning** | Permanent learning | Expensive, slow, opaque, can't un-learn | Overkill for <100 incidents |
| **RAG with vector DB** | Scales to thousands | Requires embedding pipeline, retrieval errors | Over-engineered for this |
| **Procedural memory** | Structured, replayable | Complex to implement | Future upgrade path |

At BEI's scale (~5-10 incidents/week, <100 total lessons), Reflexion is the right pattern. Each lesson is ~50 tokens in the prompt. 100 lessons = 5K tokens — well within budget.

### The three-part loop

```
1. WRITE: Governor hits failure → writes structured lesson to ~/.governor/lessons/
2. MANAGE: Dedup, categorize, cap at 100 lessons, prune stale ones
3. READ: On startup + every review, inject lessons into system prompt
```

### Key trade-off: prompt injection cost vs learning value

Each lesson costs ~50 tokens per review call. At $3/1M input tokens (Sonnet), 100 lessons = 5K tokens = $0.015 per review. This is negligible compared to the $0.30/review base cost. The learning value (avoiding repeated failures) far exceeds the cost.

### Two memory types, one system

| Type | Trigger | Content | Example |
|------|---------|---------|---------|
| **Lesson** (Reflexion) | Failure occurs | "Don't do X, do Y instead" | "Don't approve decorators on constants" |
| **Playbook** (Procedural) | Success after difficulty | "When situation S, follow steps 1-2-3" | "When build fails 2x: check logs → find error → fix → retry" |

Both stored as markdown in `~/.governor/memory/`, both injected into prompts. Lessons prevent repeating failures. Playbooks replicate successful patterns.

### What belongs where

| Knowledge Type | Where It Lives | Why |
|---------------|---------------|-----|
| Incident patterns ("when X, do Y") | Governor memory (lessons + playbooks) | Auto-learned, governor-specific |
| Deployment procedures | Skills (`/deploy-frappe`) | Shared across all agents |
| Business rules | Plans + CLAUDE.md | Human-authored policy |
| Architecture decisions | CLAUDE.md | Project-wide, not governor-specific |

### Source references

- Reflexion paper: arXiv 2303.11366 (Shinn et al., NeurIPS 2023)
- Agent memory survey: arXiv 2603.07670 (March 2026)
- OpenAI Self-Evolving Agents Cookbook: https://cookbook.openai.com/examples/partners/self_evolving_agents/autonomous_agent_retraining
- Addy Osmani on self-improving agents: https://addyosmani.com/blog/self-improving-agents/
- Current governor: `scripts/merge_governor/governor_erp.py`, `ai_backend_agent_sdk.py`

## Requirements Regression Checklist

- [ ] Memory files (lessons + playbooks) are plain markdown in `~/.governor/memory/` (no database)?
- [ ] Lessons have: category, trigger, wrong_action, correct_action, source_incident?
- [ ] Playbooks have: category, trigger, steps (ordered), source_incident?
- [ ] Playbooks are written after SUCCESSFUL recovery, not during failure?
- [ ] Lessons are injected into REVIEW_SYSTEM_PROMPT and CHAT_SYSTEM_PROMPT on startup?
- [ ] Lesson writer is called from every failure handler (review error, build fail, deploy fail, gate block)?
- [ ] Dedup prevents the same lesson from being written twice?
- [ ] Max 100 lessons enforced (oldest pruned)?
- [ ] Lessons are human-readable and editable (not binary, not encrypted)?
- [ ] Governor logs when it applies a lesson ("lesson_applied: {title}")?
- [ ] Self-diagnosis: if same error occurs despite existing lesson, lesson is escalated?
- [ ] Total lesson context stays under 10K tokens?

## Scope

### In Scope

| Item | Classification |
|------|----------------|
| `lessons.py` — write/read/manage lesson files | [BUILD] |
| Wire lesson writer into all failure handlers | [EXTEND] |
| Inject lessons into AI prompts on startup | [EXTEND] |
| Dedup + cap + prune logic | [BUILD] |
| Self-diagnosis (same error twice = escalate) | [BUILD] |
| Seed with today's 5 known incidents | [BUILD] |

### Out of Scope

- Fine-tuning or model retraining
- Vector database or embedding pipeline
- Modifying deployment skills (lessons complement, not replace skills)
- Modifying CLAUDE.md or memory system (lessons are governor-specific)

## Phase 1: Lesson Storage + Writer (5 units)

### Task 1.1: Create `lessons.py` module

```python
@dataclass
class Lesson:
    id: str                # e.g., "2026-03-23-whitelist-on-constant"
    category: str          # review | build | deploy | gate | merge
    trigger: str           # "Decorator @frappe.whitelist() applied to non-function"
    wrong_action: str      # "Governor approved the PR without flagging the decorator"
    correct_action: str    # "Flag any decorator on a constant/variable as REJECT"
    source_incident: str   # "S097 PR #317 — caused 3 build failures"
    created_at: str        # ISO timestamp
    applied_count: int     # How many times this lesson was matched
    last_applied: str      # Last time this lesson prevented an error
```

Storage: one `.md` file per lesson in `~/.governor/lessons/`:
```markdown
---
id: 2026-03-23-whitelist-on-constant
category: review
trigger: "@frappe.whitelist() decorator on a non-function (constant, variable, tuple)"
wrong_action: "Approved PR without flagging misplaced decorator"
correct_action: "REJECT — decorators on constants cause SyntaxError in bench build"
source_incident: "S097 PR #317 — 3 consecutive build failures"
created_at: 2026-03-23T18:45:00+08:00
applied_count: 0
---
```

**HARD BLOCKER:** Lesson files must be plain markdown with YAML frontmatter. No binary formats, no databases. Lessons must be human-readable and editable. (Source: auditability requirement)

### Task 1.2: Implement lesson writer

```python
async def record_lesson(category, trigger, wrong_action, correct_action, source_incident):
    """Write a lesson after a failure. Dedup by trigger similarity."""
```

Dedup: before writing, check if any existing lesson has >80% trigger text overlap (simple word intersection). If so, increment `applied_count` instead of creating a duplicate.

### Task 1.3: Wire into failure handlers

Add `record_lesson()` calls to:

| Handler | Location | Category |
|---------|----------|----------|
| Review REJECT | `governor_erp.py:_auto_review_pr()` | `review` |
| Build failure (GHA) | `merge_serializer.py:_wait_for_deploy()` | `build` |
| Deploy stale image | `merge_serializer.py:_verify_deployed_image()` | `deploy` |
| Release gate block | `merge_serializer.py:_run_release_gate()` | `gate` |
| Merge conflict | `merge_serializer.py:_execute_merge()` | `merge` |
| Builder dispatch failure | `builder_dispatch.py:_run_builder_in_worktree()` | `builder` |

Each call extracts the incident details from the error context and formats a structured lesson.

### Task 1.4: Seed with today's known incidents

Pre-create 5 lessons from today's failures:

1. `@frappe.whitelist()` on constant → SyntaxError
2. Docker deploy success but stale container → verify image SHA
3. Truncated `gh pr diff` → false REJECT → use Agent SDK file reading
4. Builder declares COMPLETED without L3 → release gate blocks
5. Governor not running → stale state blocks PRs → self-heal on startup

## Phase 1b: Procedural Memory (3 units)

### Task 1.5: Define playbook structure

Playbooks are step-by-step procedures extracted from successful complex operations:

```markdown
---
id: 2026-03-23-build-failure-recovery
type: playbook
category: build
trigger: "Docker build fails with bench build or SyntaxError"
steps:
  - "Check GHA logs: gh run view --log-failed | grep 'SyntaxError\\|Error'"
  - "If SyntaxError: identify the file and line from the error"
  - "If bench build: check if it's a yarn/npm transient issue (retry once)"
  - "If our code: run py_compile on the file locally to verify"
  - "Fix the code, push, and trigger rebuild with no_cache=true"
  - "If 3rd failure: STOP and escalate to human"
source_incident: "S097 — 3 consecutive build failures from @whitelist on constant"
created_at: 2026-03-23T19:00:00+08:00
success_count: 0
---
```

### Task 1.6: Implement playbook writer

```python
async def record_playbook(category, trigger, steps, source_incident):
    """Write a playbook after successfully handling a complex situation."""
```

Playbooks are written AFTER a successful recovery, not during the failure. The governor records what steps it took to fix the issue.

### Task 1.7: Seed with today's known playbooks

Pre-create 3 playbooks from today's successful patterns:

1. **Build failure recovery:** Check logs → identify error → fix → retry with no_cache
2. **Stale container recovery:** Verify image SHA → force service update → wait 30s → re-run L1
3. **Gate-blocked PR recovery:** Post comment → builder fixes → SHA changes → re-queue → re-gate

## Phase 2: Memory Reader + Prompt Injection (4 units)

### Task 2.1: Implement unified memory loader

```python
def load_memory(max_items=100, max_tokens=10000) -> str:
    """Read all lessons + playbooks, format as prompt context block."""
```

Returns a text block like:
```
## Governor Memory (auto-evolved from past incidents)

### Lessons (avoid these mistakes)
- REVIEW: @frappe.whitelist() on a non-function → REJECT. Causes SyntaxError. (S097)
- DEPLOY: Verify container image SHA after deploy. Swarm may not pull new image. (S097)
- REVIEW: Don't reject for truncated test files in diffs. Use Read/Grep instead. (S093)

### Playbooks (follow these procedures)
- BUILD FAILURE: Check logs → identify error → fix → retry with no_cache=true. If 3rd failure, escalate. (S097)
- STALE CONTAINER: Verify image SHA → force service update → wait 30s → re-run L1. (S097)
- GATE BLOCKED: Post comment → builder fixes → SHA change → re-queue → re-gate. (S096)
```

### Task 2.2: Inject into prompts on startup

In `governor_erp.py:initialize()`, after `_init_ai_backend()`:

```python
# Load lessons and inject into AI prompts
from .lessons import load_lessons
lessons_context = load_lessons()
if lessons_context and self.ai_backend:
    self.ai_backend.inject_lessons(lessons_context)
```

Add `inject_lessons(text)` to `AgentSDKBackend` — appends to both REVIEW_SYSTEM_PROMPT and CHAT_SYSTEM_PROMPT.

### Task 2.3: Self-diagnosis — escalate repeated failures

```python
def check_repeat_failure(trigger: str) -> bool:
    """Check if a lesson exists for this trigger pattern.
    If yes, the lesson didn't prevent the error — escalate."""
```

When the same error happens despite an existing lesson:
1. Increment the lesson's `applied_count` but mark it as `ineffective`
2. Log a WARNING: "Lesson '{id}' exists but error recurred — lesson may need strengthening"
3. Rewrite the lesson with more detail from the new incident

### Task 2.4: Lesson management — cap and prune

- Max 100 lessons. When exceeded, prune by:
  1. Remove lessons with `applied_count == 0` and `age > 30 days` (never triggered = probably not useful)
  2. Remove oldest lessons first (FIFO after age filter)
- Never prune lessons with `applied_count > 5` (frequently useful)

## Phase 3: E2E Test and Closeout (3 units)

### Task 3.1: Test lesson write + read cycle

1. Trigger a review failure (intentional REJECT)
2. Verify lesson file created in `~/.governor/lessons/`
3. Restart governor
4. Verify lesson appears in the AI prompt
5. Trigger the same pattern → verify lesson is applied (logged as `lesson_applied`)

### Task 3.2: Test dedup and self-diagnosis

1. Write same lesson twice → verify dedup (only one file, `applied_count` incremented)
2. Trigger failure that matches existing lesson → verify escalation warning

### Task 3.3: Closeout

- Update plan YAML: status → COMPLETED
- Update SPRINT_REGISTRY.md
- `git add -f docs/plans/` and push

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| sam@bebang.ph | Governor reviews PR with `@whitelist()` on constant | Governor REJECT + lesson "whitelist-on-constant" exists in prompt | Lesson injection not working |
| sam@bebang.ph | Governor encounters stale Docker image after deploy | Force-update runs + lesson recorded about image verification | Lesson writer not wired to deploy handler |
| sam@bebang.ph | Same build error happens twice | Governor logs "lesson exists but error recurred" escalation | Self-diagnosis not working |
| sam@bebang.ph | 101st lesson written | Oldest zero-applied lesson pruned, count stays at 100 | Pruning not working |
| sam@bebang.ph | Governor restarts | "Loaded N lessons" message in startup, lessons in AI prompts | Lesson loader broken |

## Autonomous Execution Contract

```yaml
completion_condition:
  - lessons.py module implements write/read/manage/dedup/prune
  - All 6 failure handlers call record_lesson()
  - Lessons injected into AI prompts on startup
  - 5 seed lessons created from today's incidents
  - Self-diagnosis escalates repeated failures
  - E2E: lesson written → restart → lesson in prompt → lesson applied
  - Plan YAML status updated to COMPLETED and pushed
  - SPRINT_REGISTRY.md row updated

stop_only_for:
  - Lesson files conflict with governor state management
  - Prompt token budget exceeded (>10K tokens from lessons)

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

1. Read this plan fully.
2. Read `scripts/merge_governor/governor_erp.py` — understand initialization flow and failure handlers.
3. Read `scripts/merge_governor/ai_backend_agent_sdk.py` — understand prompt structure (REVIEW_SYSTEM_PROMPT, CHAT_SYSTEM_PROMPT).
4. Read `scripts/merge_governor/merge_serializer.py` — find all failure handlers (_wait_for_deploy, _verify_deployed_image, _run_release_gate, _handle_deploy_failure).
5. Read `scripts/merge_governor/builder_dispatch.py` — find failure handlers.
6. Check `~/.governor/lessons/` exists or needs creation.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.
