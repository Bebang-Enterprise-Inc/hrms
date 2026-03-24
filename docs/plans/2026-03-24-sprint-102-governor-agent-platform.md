# S102: Governor Agent Platform — API, Inter-Agent Communication, Self-Diagnosis

```yaml
canonical_sprint_id: S102
status: COMPLETED
created_date: 2026-03-24
depends_on: S101
branch: s102-governor-agent-platform
lane: single
estimated_work_units: 55
```

## Summary

Transform the governor from an isolated process into a platform that other agents can interact with. Adds a REST API for status/control, a shared event bus for real-time notifications, inter-agent messaging, and self-diagnosis that auto-investigates when the governor gets stuck.

## Design Rationale (For Cold-Start Agents)

### Why this exists

Today's governor operates in total isolation. Builder agents:
- Can't check if the governor is running (waited 7 hours for a dead process)
- Can't see what step the pipeline is on (guessed "maybe it's building?")
- Can't wake it up (had to ask the human to Ctrl+C and restart)
- Can't ask it questions (chat AI was blind to its own pipeline)

The governor's chat AI was equally blind:
- Told the user "maybe you need to trigger the merge manually" while actively merging
- Couldn't check CI, GHA, production health, or container status
- Had 5 turns and $0.25 budget — not enough to investigate anything

### Architecture: Event Bus + REST API + Self-Diagnosis

```
┌─────────────────────────────────────────────────────┐
│                 GOVERNOR PROCESS                      │
│                                                       │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ PR       │  │ Merge        │  │ Chat AI       │  │
│  │ Watcher  │──│ Serializer   │──│ (full tools)  │  │
│  └────┬─────┘  └──────┬───────┘  └───────────────┘  │
│       │               │                              │
│       ▼               ▼                              │
│  ┌─────────────────────────────────┐                 │
│  │         EVENT BUS               │                 │
│  │  (in-process async pub/sub)     │                 │
│  └──────────────┬──────────────────┘                 │
│                 │                                     │
│       ┌─────────┼─────────┐                          │
│       ▼         ▼         ▼                          │
│  ┌────────┐ ┌────────┐ ┌──────────┐                 │
│  │ REST   │ │ Live   │ │ Self-    │                 │
│  │ API    │ │ Log    │ │ Diagnosis│                 │
│  │ :8000  │ │ Files  │ │ Monitor  │                 │
│  └────────┘ └────────┘ └──────────┘                 │
└─────────────────────────────────────────────────────┘
       ▲                    ▲
       │                    │
  Builder agents        Builder agents
  (curl /status)        (tail -f log)
```

### What belongs where

| Feature | Sprint | Why |
|---------|--------|-----|
| Deterministic pre-checks, streaming review, confidence | S101 | Review quality |
| REST API, event bus, inter-agent, self-diagnosis | S102 | Agent platform |

### Source references

- Health server: `scripts/merge_governor/health_server.py` (30 lines, only `/healthz`)
- Pipeline state: `merge_serializer.get_pipeline_summary()` (added in this session)
- Chat AI: `ai_backend_agent_sdk.py` CHAT_SYSTEM_PROMPT (full Bash access added)
- Lessons from tonight: `~/.governor/memory/lesson-2026-03-24-governor-architecture-failures.md`

## Requirements Regression Checklist

- [ ] Can a builder agent check governor liveness? (`curl localhost:8000/healthz`)
- [ ] Can a builder agent see PR review status? (`curl localhost:8000/pr/321`)
- [ ] Can a builder agent see what pipeline step is running? (`curl localhost:8000/status`)
- [ ] Can a builder agent force-wake the governor? (`curl -X POST localhost:8000/wake`)
- [ ] Can a builder agent force a review? (`curl -X POST localhost:8000/pr/321/review`)
- [ ] Can a builder agent tail live events? (`tail -f ~/.governor/live/pr_321.jsonl`)
- [ ] Does the governor push events to subscribed agents? (event bus)
- [ ] Does the governor auto-investigate when stuck for >5 minutes?
- [ ] Does self-diagnosis check: CI status, GHA runs, production ping, container image?
- [ ] Does the governor notify the operator (terminal + PR comment) when self-diagnosis finds an issue?
- [ ] Is the wake event shared across PR watcher, merge serializer, and health server?

## Scope

### In Scope

| Item | Classification |
|------|----------------|
| REST API on health server (status, PR, queue, lessons, wake, review, merge) | [EXTEND] |
| Force-wake event (shared asyncio.Event across all loops) | [BUILD] |
| Live event log files (`~/.governor/live/pr_{num}.jsonl`) | [BUILD] |
| Event bus (in-process async pub/sub) | [BUILD] |
| Self-diagnosis monitor (auto-investigate when stuck) | [BUILD] |
| Builder notification via PR comments on state changes | [EXTEND] |

### Out of Scope

- MCP server (future — too complex for this sprint)
- External webhook delivery (future — requires auth)
- Web dashboard UI (future — REST API is sufficient for agents)
- Changing the merge pipeline flow (already fixed in previous session)

## Phase 1: REST API + Force Wake (15 units)

### Task 1.1: Extend health server to full REST API

Rewrite `health_server.py` to handle multiple routes:

```python
ROUTES = {
    ("GET", "/healthz"): handle_healthz,
    ("GET", "/status"): handle_status,       # full governor state + pipeline
    ("GET", "/pr"): handle_pr_list,          # all active PRs
    ("GET", "/pr/{num}"): handle_pr_detail,  # specific PR with review, queue pos, pipeline step
    ("GET", "/pr/{num}/log"): handle_pr_log, # live event log for this PR
    ("GET", "/queue"): handle_queue,         # merge queue with positions
    ("GET", "/lessons"): handle_lessons,     # all governor lessons
    ("POST", "/wake"): handle_wake,          # force-wake all loops
    ("POST", "/pr/{num}/review"): handle_force_review,  # force immediate review
    ("POST", "/pr/{num}/merge"): handle_force_merge,    # force queue + process
}
```

Each handler returns JSON. Parse path params from URL.

**HARD BLOCKER — Circular Import Resolution:** Health server needs GovernorERP capabilities but importing GovernorERP would create a circular dependency (`governor_erp → health_server → governor_erp`). The solution: do NOT import GovernorERP. Instead, pass individual references during initialization:
```python
class HealthServer:
    def __init__(self, state_mgr, merge_serializer, wake_event, pr_review_callback):
        self.state_mgr = state_mgr
        self.merge_serializer = merge_serializer  # for get_pipeline_summary()
        self.wake_event = wake_event               # for POST /wake
        self._review_callback = pr_review_callback  # for POST /pr/{num}/review
```
No GovernorERP import needed. The governor passes its components individually. (Source: system architecture audit — C-2)

### Task 1.2: Force-wake event

```python
# governor_erp.py
self._wake_event = asyncio.Event()

# Pass to all components
self.health_server = HealthServer(state_mgr, merge_serializer, self._wake_event, review_callback)
self.pr_watcher = PRWatcher(self.state_mgr, wake_event=self._wake_event)
self.merge_serializer = MergeSerializer(..., wake_event=self._wake_event)
```

**HARD BLOCKER:** `_self_heal_state()` creates a temporary `PRWatcher(self.state_mgr, poll_interval=30)` for startup polling. When PRWatcher gains a `wake_event` parameter, this call will break unless `wake_event` defaults to `None`. Ensure PRWatcher constructor has `wake_event: asyncio.Event | None = None` with fallback to `asyncio.sleep()` when no event is provided. (Source: code verification audit)

Replace all `asyncio.sleep(N)` in poll loops with:
```python
try:
    await asyncio.wait_for(self._wake_event.wait(), timeout=interval)
    self._wake_event.clear()
except asyncio.TimeoutError:
    pass
```

**HARD BLOCKER — Double-Processing Guard:** Force-wake can cause `process_queue` to re-enter while already running (merge serializer wakes while mid-merge). Add a guard at the top of `process_queue`:
```python
if self._is_processing:
    return  # Already running, ignore this cycle
self._is_processing = True
try:
    ... # existing process_queue body
finally:
    self._is_processing = False
```
Initialize `self._is_processing = False` in `__init__`. This MUST be done before testing force-wake. (Source: deployment/QA audit — C-01)

**HARD BLOCKER — asyncio.Event Race:** A single shared Event has a race: if two loops call `wait()` simultaneously and one calls `clear()`, the other misses the wake signal. Fix: use a per-loop pattern where wake sets the event and each loop clears its own copy, OR use `asyncio.Condition` instead of `Event`. Simplest: let each loop call `clear()` independently — the Event remains set until ALL waiters have processed it. (Source: system architecture audit — C-3)

Builder workflow becomes:
```bash
git push origin HEAD
curl -X POST localhost:8000/pr/321/review  # instant, no 30s wait
```

### Task 1.2b: Add asyncio.Lock to StateManager

**HARD BLOCKER:** S102 introduces new concurrent `save()` callers: REST API handlers, self-diagnosis, and the existing merge serializer. Without a lock, two callers can read-modify-write the state simultaneously, producing torn writes (especially on Windows with Dropbox file locking).

Add to `StateManager.__init__`:
```python
self._lock = asyncio.Lock()
```

Wrap `save()`:
```python
async def save(self):
    async with self._lock:
        self._save_sync()  # existing os.replace() logic
```

All callers that modify state and then save must use the lock. (Source: system architecture audit — C-1)

### Task 1.3: Force-review and force-merge endpoints

`POST /pr/{num}/review`:
1. Find PR in state (or add it if missing)
2. Set review_decision = None (invalidate)
3. Set wake event
4. Return `{"status": "review_queued", "pr": num}`

`POST /pr/{num}/merge`:
1. Find PR in state
2. Add to merge_queue if not already there
3. Set wake event
4. Return `{"status": "merge_queued", "pr": num, "position": N}`

## Phase 2: Live Event Log + Event Bus (15 units)

### Task 2.1: Event bus (in-process pub/sub)

```python
class EventBus:
    """In-process async pub/sub for governor events."""

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = {}
        self._log_dir = Path.home() / ".governor" / "live"
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def emit(self, event_type: str, data: dict) -> None:
        """Emit event to all subscribers + write to log file.

        HARD BLOCKER: File I/O must be non-blocking. Use loop.run_in_executor
        for the file write, or buffer events and flush periodically.
        Synchronous open()+write() inside an async coroutine blocks the
        entire event loop during Dropbox-synced writes.
        (Source: system architecture audit — C-4)
        """
        data["ts"] = datetime.now().isoformat()
        data["event"] = event_type

        # Print to terminal (fast, non-blocking)
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {event_type}: {json.dumps({k:v for k,v in data.items() if k not in ('ts','event')}, default=str)[:120]}", flush=True)

        # Write to per-PR log file (NON-BLOCKING via thread pool)
        pr_num = data.get("pr")
        if pr_num:
            log_file = self._log_dir / f"pr_{pr_num}.jsonl"
            line = json.dumps(data) + "\n"
            # Fire-and-forget in thread pool — don't await
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.run_in_executor(None, self._write_log, str(log_file), line)
            except RuntimeError:
                self._write_log(str(log_file), line)  # Fallback if no loop

        # Notify subscribers
        for cb in self._subscribers.get(event_type, []):
            try:
                cb(data)
            except Exception:
                pass

    @staticmethod
    def _write_log(path: str, line: str) -> None:
        with open(path, "a") as f:
            f.write(line)

    def subscribe(self, event_type: str, callback: Callable) -> None:
        self._subscribers.setdefault(event_type, []).append(callback)
```

Event types:
- `pr.detected` — new PR found
- `pr.review_started` — review beginning
- `pr.review_complete` — review done with decision
- `pr.ci_waiting` — waiting for CI
- `pr.ci_passed` / `pr.ci_failed`
- `pr.merge_started` / `pr.merged`
- `pr.deploy_started` / `pr.deploy_complete` / `pr.deploy_failed`
- `pr.l1_passed` / `pr.l1_failed`
- `governor.stuck` — self-diagnosis triggered
- `governor.wake` — force-woken by API

### Task 2.2: Wire event bus into merge serializer

Replace all `print()` + `logger.info()` calls with `event_bus.emit()`:
```python
# Before:
print(f"[{ts}] Step 2/7: Merging PR #{pr_num}...", flush=True)

# After:
self.event_bus.emit("pr.merge_started", {"pr": pr_num, "step": "2/7"})
```

The event bus handles both terminal output AND log file writing. Single source of truth.

### Task 2.3: Wire event bus into PR watcher

Emit events for new PRs, closed PRs, SHA changes.

### Task 2.4: Live log API endpoint

`GET /pr/{num}/log` reads the last 100 lines from `~/.governor/live/pr_{num}.jsonl` and returns as JSON array.

Cleanup: on startup, delete log files older than 24 hours.

## Phase 3: Self-Diagnosis Monitor (15 units)

### Task 3.1: Stuck detection

A background task that checks every 60 seconds:

```python
async def _self_diagnosis_loop(self, stop_event):
    while not stop_event.is_set():
        await asyncio.sleep(60)
        if self.merge_serializer.pipeline_status != "idle":
            elapsed = time.time() - self.merge_serializer.pipeline_started_at
            if elapsed > 300:  # 5 minutes on same step
                await self._investigate_stuck()
```

### Task 3.2: Auto-investigation

**HARD BLOCKER:** All subprocess calls in self-diagnosis MUST use `asyncio.create_subprocess_exec` (not `subprocess.run`). Blocking subprocess calls freeze the entire event loop — the health server stops responding, the merge serializer stalls, and the PR watcher stops polling. Follow the pattern from `pr_watcher.py` which uses `loop.run_in_executor` for `subprocess.run`, or better yet use `asyncio.create_subprocess_exec` with `stdout=PIPE` as `merge_serializer.py` already does. (Source: deployment/QA audit — C-02)

When stuck is detected, the governor:

1. **Check what step it's on** — read pipeline_status
2. **If CI wait** — run `gh pr view {num} --json statusCheckRollup` and report
3. **If deploy wait** — run `gh run list --workflow=build-and-deploy.yml` and report
4. **If L1 wait** — run `curl hq.bebang.ph/api/method/ping` and report
5. **If merge failed** — read error from last merge attempt
6. **Print diagnosis to terminal:**
```
[HH:MM:SS] SELF-DIAGNOSIS: Pipeline stuck on "Step 4/7: waiting for GHA build" for 8 minutes
[HH:MM:SS]   Checked GHA: run #23449356870 status=in_progress (still building)
[HH:MM:SS]   Action: continuing to wait (build in progress, not stuck)
```
or:
```
[HH:MM:SS] SELF-DIAGNOSIS: Pipeline stuck on "Step 4/7: waiting for GHA build" for 20 minutes
[HH:MM:SS]   Checked GHA: run #23449356870 status=completed conclusion=failure
[HH:MM:SS]   Action: deploy FAILED but governor didn't detect it. Triggering failure handler.
```

### Task 3.3: Auto-recovery actions

Based on diagnosis:

| Diagnosis | Auto-Recovery |
|-----------|---------------|
| GHA still building | Do nothing, log "build in progress" |
| GHA failed but not detected | Call `_handle_deploy_failure()` |
| CI passed but merge not attempted | Force wake merge serializer |
| Production ping fails | Log critical alert, attempt rollback |
| Container image stale | Call `_force_service_update()` |
| No active PR but queue not empty | Clean stale queue entries |

### Task 3.4: Notify builder agents via PR comment

When self-diagnosis takes action, post a PR comment:
```
**Governor Self-Diagnosis Report**

Pipeline was stuck on "waiting for GHA build" for 20 minutes.
- GHA run #23449356870: FAILED (bench build SyntaxError)
- Auto-recovery: dispatching builder to fix CI failure

Builder: check your code for syntax errors. The governor will re-review after your fix.

*Posted by governor-erp (self-diagnosis)*
```

## Phase 4: Integration and Testing (10 units)

### Task 4.1: Wire event bus into governor startup

Initialize event bus in `GovernorERP.initialize()`, pass to all components.

### Task 4.2: Test REST API endpoints

```bash
# Start governor, then in another terminal:
curl localhost:8000/healthz          # should return {"status": "ok", ...}
curl localhost:8000/status           # should return full state + pipeline
curl -X POST localhost:8000/wake     # should wake governor immediately
```

### Task 4.3: Test force-wake

1. Governor idle, sleeping
2. `curl -X POST localhost:8000/wake`
3. Governor immediately runs poll cycle (visible in terminal)

### Task 4.4: Test self-diagnosis

1. Manually set `pipeline_started_at` to 10 minutes ago
2. Self-diagnosis should trigger within 60 seconds
3. Verify it checks GHA, production, and prints diagnosis

### Task 4.5: Test inter-agent flow

1. Start governor
2. In a separate terminal, simulate builder:
   ```bash
   # Check governor is alive
   curl -s localhost:8000/healthz | python -c "import sys,json; d=json.load(sys.stdin); print('Governor:', d['status'])"

   # Push code and force review
   curl -X POST localhost:8000/pr/323/review

   # Watch live log
   tail -f ~/.governor/live/pr_323.jsonl

   # Check when merged
   curl localhost:8000/pr/323 | python -c "import sys,json; print(json.load(sys.stdin)['state'])"
   ```

### Task 4.6: Closeout

- Update plan YAML: status → COMPLETED
- Update SPRINT_REGISTRY.md
- `git add -f docs/plans/` and push

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| sam@bebang.ph | `curl localhost:8000/status` | Returns JSON with pipeline state, active PRs, queue | API not working |
| sam@bebang.ph | `curl localhost:8000/pr/323` | Returns PR review, confidence, queue position | PR endpoint broken |
| sam@bebang.ph | `curl -X POST localhost:8000/wake` | Governor wakes, runs poll (visible in terminal within 2s) | Wake event not wired |
| sam@bebang.ph | `curl -X POST localhost:8000/pr/323/review` | Governor starts reviewing immediately | Force-review broken |
| sam@bebang.ph | `tail -f ~/.governor/live/pr_323.jsonl` | Shows events as they happen | Event log not writing |
| sam@bebang.ph | Governor stuck for 5+ minutes | Self-diagnosis prints what's wrong + takes action | Self-diagnosis not running |
| sam@bebang.ph | GHA build fails silently | Self-diagnosis detects and posts PR comment | Auto-recovery not working |

## Autonomous Execution Contract

```yaml
completion_condition:
  - REST API responds to all 10 endpoints (healthz, status, pr, pr/{num}, pr/{num}/log, queue, lessons, wake, pr/{num}/review, pr/{num}/merge)
  - Force-wake wakes all loops within 2 seconds
  - Event bus emits events for all pipeline steps
  - Live log files written for every PR
  - Self-diagnosis triggers after 5 min stuck
  - Self-diagnosis auto-recovers from GHA failure, stale container, undetected CI pass
  - Builder can do full cycle: healthz → force-review → tail log → check status → see merged
  - Plan YAML status updated to COMPLETED and pushed

stop_only_for:
  - asyncio.Event sharing doesn't work across components (unlikely)
  - Health server can't accept GovernorERP reference (circular import)

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

0. **`git checkout -b s102-governor-agent-platform production`** — MANDATORY before any code. Committing to production is FORBIDDEN.
1. Read this plan fully.
2. Read `scripts/merge_governor/health_server.py` — current health server (89 lines, needs rewrite).
3. Read `scripts/merge_governor/governor_erp.py` — understand component initialization and the run() TaskGroup.
4. Read `scripts/merge_governor/merge_serializer.py` — understand pipeline_status tracking and the run() loop.
5. Read `scripts/merge_governor/pr_watcher.py` — understand poll loop and callbacks.
6. Read `scripts/merge_governor/chat_handler.py` — understand how chat passes pipeline_summary.
7. Read `~/.governor/memory/lesson-2026-03-24-governor-architecture-failures.md` — the 14 failures from tonight.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.
