---
name: l3-v2-bei-erp
description: L3 workflow test. Executes pre-written test scenarios from the modular scenario catalog. Does NOT invent tests.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Task, TaskCreate, TaskUpdate, TaskList, TaskGet
user-invocable: true
---

# L3: Submit + Verify (Scenario-Driven)

Execute pre-written test scenarios. **You do NOT invent test cases.** You read them from `docs/testing/scenarios/index.yaml` + mapped scenario files and execute exactly as written.

## 🟥 TEST EMPLOYEE & ACCOUNT NUMBERING — NON-NEGOTIABLE (S237)

L3 tests **MUST NEVER** create test Employee records using attendance_device_id values in the **9xxxxxx** range — that range is reserved for real BEI employees in the Employee Master CSV.

**Rules (enforced — violations are blockers):**

1. **Test attendance_device_id range:** test Employee records MUST use Bio IDs in the **3xxxxxx** range (3000001 → 3999999). Allocate sequentially from `3000001` on a fresh test database; in production tests, query `SELECT MAX(CAST(attendance_device_id AS UNSIGNED)) FROM tabEmployee WHERE attendance_device_id REGEXP '^3[0-9]{6}$'` and increment from there.
2. **Test employee_name pattern:** test Employee `employee_name` MUST start with one of: `L3-`, `TEST-`, `L3TEST `, `BROWSERTEST `, `APPROVETEST ` (uppercase markers so SQL `LIKE '%TEST%'` finds them). Do NOT use names that look real (no "Maria Santos Reyes" — use "L3-MARIA-SANTOS-001").
3. **Test User accounts:** test login emails MUST match the existing `test.X@bebang.ph` convention (canonical list in `memory/testing-accounts.md`). Do NOT create new test logins outside the `test.*@bebang.ph` pattern.
4. **Test branch:** if a fictional branch is needed, use `TEST-STORE-BGC` or another `TEST-*` prefix. Do NOT use real BEI branch names (`ARANETA GATEWAY`, `BRITTANY HOTEL`, `ALABANG TOWN CENTER`, etc.) for ad-hoc test rows that will be left in the database.
5. **Status discipline at teardown:** every test Employee created during a run MUST end the run as either deleted or `status='Left'` AND `attendance_device_id=NULL`. Active test rows holding any device_id are forbidden at closeout.
6. **Pre-seed audit (Phase 0):** before pushing any test Employee INSERT, run `SELECT COUNT(*) FROM tabEmployee WHERE attendance_device_id REGEXP '^9[0-9]{6}$' AND (UPPER(employee_name) LIKE '%TEST%' OR UPPER(employee_name) LIKE '%L3%')`. If count > 0, STOP and ask Sam — that means a previous run polluted the real-Bio-ID range and must be cleaned first.

**Why this exists:** S237 (2026-05-05) found 31 L3 test rows squatting on real Bio IDs 9001883–9001917, blocking S228's HR-audited Frappe import for actual new hires (CATINDOY 9001893, ESTRELLA 9001903, etc.). All ADMS punches from those Bio IDs were being mis-routed to ghost test rows marked `status=Left`, breaking payroll attribution. Cleanup migrated 6 Active test rows to `3000001..3000006` and NULLed 26 Left test rows. Going forward, the 9xxxxxx range is real-employees-only.

**Where to encode this in scenario files:** every L3 scenario YAML that creates an Employee record MUST declare `test_bio_id_range: 3xxxxxx` in its preconditions block. Scenarios that violate this are rejected at audit time (`/audit-plan-bei-erp` enforces).

## Why Scenario-Driven?

Agent-authored tests failed us repeatedly:
- Agents use toy data (1x1 pixel PNGs instead of 150KB real photos)
- Agents test only happy paths (skip edge cases, status transitions, RBAC)
- Agents invent easy tests that pass instead of hard tests that catch bugs
- Real users found bugs in 20 minutes that agents missed over days

**The fix:** Humans write the test scenarios. Agents execute them.

## Commands

```
/l3-v2 maintenance    Execute MAINT-001 through MAINT-015
/l3-v2 store-ops      Execute store operations + inventory sprint scenarios
/l3-v2 hr             Execute HR self-service scenarios
/l3-v2 expense        Execute EXP-001 through EXP-006
/l3-v2 communication  Execute COMM-001 through COMM-004
/l3-v2 biometric      Execute BIO-001 through BIO-014
/l3-v2 finance        Execute FIN-*, FIN-NEG-*, FIN-RBAC-*
/l3-v2 billing        Execute BILL-001 through BILL-017
/l3-v2 scm            Execute SCM-001 onward
/l3-v2 flow-procure-pay  Execute T-PROC flow scenarios
/l3-v2 all            Execute ALL scenarios
```

## Execution Protocol

### TEST DATA SEEDING & TEARDOWN via /frappe-bulk-edits (MANDATORY — READ FIRST)

**The L3 sweep IS NOT allowed to fail because production lacks test data.** If a scenario needs inventory, users, custom field values, BEI Routes, MR/SO records, or any record that does not exist in production at the moment the scenario runs, the agent MUST seed it via `/frappe-bulk-edits` BEFORE running the scenario. After all scenarios complete, the agent MUST delete every seeded record via `/frappe-bulk-edits`. This is execution work, not optional polish.

**Concrete rule, no exceptions:**

1. **Detect missing data BEFORE execution.** During Step -1 precondition build (below), enumerate every record class the scenarios touch (test inventory items, store warehouses, user accounts, BEI Routes, custom fields, etc.). For each, query production: does it exist with the values the scenario needs?
2. **If missing → seed it via `/frappe-bulk-edits`.** Use the SSM-replay pipeline. Examples:
   - Test inventory short → bulk-insert Stock Entry to top up actual_qty at the assigned hub for every test SKU before the sweep
   - Test user missing → bulk-create User + Employee + Roles via INSERT_SQL
   - Custom field value missing → bulk-update via UPDATE_SQL
   - BEI Route missing → bulk-create the BEI Route + BEI Route Stop docs
3. **Track every seeded record in a teardown ledger.** Write to `output/l3/{sprint}/teardown_ledger.json` with `{doctype, name, action: "DELETE" | "REVERT_FIELDS", original_values}` per record. Without the ledger, teardown is impossible.
4. **Run scenarios.** Now preconditions are real, not aspirational.
5. **Teardown via `/frappe-bulk-edits` at closeout.** Read the ledger, delete every seeded record (or revert every field). Verify production is back to its pre-sweep state. Write `output/l3/{sprint}/teardown_complete.json` with the deletion proof.
6. **Closeout is NOT complete until teardown is verified.** A test run that leaves seeded data behind is a failed run, even if every scenario passed.

**Forbidden behaviors (these are how this rule got broken before — see S225 incident 2026-04-28):**
- ❌ Mark a scenario `PRECONDITION_BLOCKED` because test inventory is short. **Wrong.** Seed the inventory.
- ❌ Recommend product code changes (resolver fallbacks, route auto-failover, removed validations) to "fix" tests that fail on missing data. **Wrong, and dangerous.** Do not break the system to pass a test. Seed the data.
- ❌ Leave seeded test data in production after the sweep ends. **Wrong.** Teardown is mandatory.
- ❌ Skip seeding because "the test should work without it" or "the data should already be there." If the scenario fails, the data isn't there. Seed it.

**The golden test for any "test failure":** would seeding the missing data make this scenario pass? If yes, seed it and re-run. If no, it's a real product bug — file a defect.

**Reference skill:** `/frappe-bulk-edits` (SSM-replay pipeline for bulk INSERT/UPDATE/DELETE on Frappe production via savepoints).

### Step -1: Scenario Preconditions + Runtime Window (MANDATORY)

Before executing any scenario:

1. Record run metadata:
   - Absolute timestamp in PHT
   - target env URLs
   - scenario IDs selected from `index.yaml`
2. Build a precondition checklist per scenario:
   - required role login availability
   - required seed data / dependency records (cross-check vs the TEST DATA SEEDING section above — every missing record gets seeded, not flagged as blocked)
   - runtime windows (cutoff open/closed, delivery day constraints, schedule gates)
3. For time-gated scenarios:
   - verify gate state via API first (for example `validate_order_schedule`)
   - if gate state mismatches scenario requirements, resolve with one of:
     - existing live records that already satisfy the condition, or
     - controlled temporary config override with explicit rollback plan and proof, only when requested/authorized
4. **If a precondition record is missing → seed it via `/frappe-bulk-edits` (per the TEST DATA SEEDING section above) and add it to the teardown ledger. Do NOT mark `PRECONDITION_BLOCKED` for missing data that can be seeded.** `PRECONDITION_BLOCKED` is reserved for environmental issues that seeding cannot resolve (e.g., production outage, hard-coded business calendar holidays).

### Step 0: Read Scenario Index + Files (MANDATORY)

```
Read docs/testing/scenarios/index.yaml
```

Resolve the requested module/flow from `index.yaml`, then read only:
- `docs/testing/scenarios/COMMON.md`
- scenario files listed for that command in `index.yaml`

Each scenario has:
- **ID** (e.g., MAINT-007)
- **Type** (happy, edge, regression, rbac, adversarial)
- **Role** (which test account to use)
- **Call** (exact API endpoint)
- **Payload** (exact data to send)
- **Assert** (exact checks to make)

**DO NOT modify the scenarios during execution. DO NOT skip scenarios. DO NOT add your own.**

### Step 1: Generate the 150KB Test Photo

Every test run starts by generating the standard test photo:

```python
import struct, zlib, base64

width, height = 200, 200
raw_data = b''
for y in range(height):
    raw_data += b'\x00'
    for x in range(width):
        raw_data += bytes([x % 256, y % 256, (x+y) % 256])
compressed = zlib.compress(raw_data)
ihdr = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
png = (b'\x89PNG\r\n\x1a\n' +
       struct.pack('>I', 13) + b'IHDR' + ihdr + struct.pack('>I', zlib.crc32(b'IHDR' + ihdr) & 0xffffffff) +
       struct.pack('>I', len(compressed)) + b'IDAT' + compressed + struct.pack('>I', zlib.crc32(b'IDAT' + compressed) & 0xffffffff) +
       struct.pack('>I', 0) + b'IEND' + struct.pack('>I', zlib.crc32(b'IEND') & 0xffffffff))
PHOTO_B64 = base64.b64encode(png).decode()
PHOTO_DATA_URL = f"data:image/png;base64,{PHOTO_B64}"
```

Replace `<PHOTO_DATA_URL>` in any scenario payload with this value.

### Step 2: Login All Required Accounts (Browser UI, Not API)

```python
from playwright.sync_api import sync_playwright

BASE_WEB = "https://my.bebang.ph"

def login_ui(page, email, password="BeiTest2026!"):
    page.goto(f"{BASE_WEB}/login", wait_until="domcontentloaded", timeout=60000)
    page.locator('input[autocomplete="username"], input[name="email"]').first.fill(email)
    page.locator('input[type="password"]').first.fill(password)
    page.locator('button[type="submit"]').first.click()
    page.wait_for_url("**/dashboard**", timeout=30000)
```

Use browser login for every role mentioned in the scenarios.  
API token/session shortcuts are forbidden for L3 submit steps.

### Step 3: Execute Each Scenario

For each scenario in order:
1. Read the payload from the module/flow files mapped in `index.yaml`
2. Open the feature page through sidebar/menu clicks (not direct URL deep-link)
3. Fill inputs exactly from scenario payload (text/select/checkbox/upload)
4. Click the real submit button in UI
5. Capture browser network call to `/api/<...>` for the submit action
6. Check every assertion listed (UI + backend state)
7. Record PASS or FAIL with details

**Critical assertion rules:**
- `ok == true` means HTTP 2xx
- `ok == false` means the endpoint correctly rejected bad input (for rbac/adversarial)
- "DB verify" means call detail/list endpoints after UI submit to confirm saved state
- Photo URL accessible means `GET <url>` returns HTTP 200
- If the scenario says upload/photo, UI must attach a real file before submit

Network capture rules (mandatory):
- Register listeners before user clicks submit.
- Track all candidate submit responses, then select the event that matches the expected action + successful response contract.
- Do not assume “first captured event” is the true submit event.
- Persist raw request/response snippets in scenario evidence.

### Step 4: Handle Dependencies

Some scenarios depend on previous ones (e.g., MAINT-003 depends on MAINT-001's request_id).
- Track created record IDs as you go
- If a dependency failed, mark the dependent scenario as `SKIP (dependency MAINT-001 failed)`
- SKIP counts as FAIL in the summary

### Step 5: Write Results + Browser Evidence to Disk

```python
# Write scenario results to output/l3/<module>_<date>.json
results = []
results.append({
    "scenario": "MAINT-007",
    "type": "regression",
    "test": "Record Completion WITH 150KB After Photo",
    "status": "PASS",  # PASS, FAIL, or SKIP
    "detail": "Completion MC-xxx created, after_photos URL accessible",
    "error": None
})

import datetime
date = datetime.date.today().isoformat()
with open(f"output/l3/{module}_{date}.json", "w") as f:
    json.dump(results, f, indent=2)
```

Also write one evidence file per scenario:

`output/l3/evidence/<SCENARIO_ID>.json`

Minimum required evidence fields:

```json
{
  "scenario_id": "MAINT-001",
  "actions": [{"type": "nav_sidebar"}, {"type": "click"}, {"type": "fill"}, {"type": "submit"}],
  "network": [{"method": "POST", "url": "https://hq.bebang.ph/api/method/hrms.api.store.submit_maintenance_request"}],
  "artifacts": {"trace": "output/l3/artifacts/MAINT-001.trace.zip", "screenshots": ["output/l3/artifacts/MAINT-001.png"]}
}
```

Guard commands (mandatory):

```bash
python scripts/testing/l3_browser_guard.py scan
python scripts/testing/l3_manifest_check.py
python scripts/testing/l3_v2_runner.py --module all
python scripts/testing/l3_browser_guard.py validate \
  --evidence output/l3/evidence/MAINT-001.json \
  --expected-endpoint hrms.api.store.submit_maintenance_request
```

### Step 5.5: Flake Resolution + Grounded Research Loop (MANDATORY)

If a scenario fails, do not stop immediately. Run this loop:

1. Reproduce once with trace/video/screenshot enabled.
2. Classify failure:
   - selector/interaction issue,
   - RBAC/data precondition issue,
   - backend/API defect,
   - environment instability.
3. Apply the smallest deterministic fix (selector hardening, wait-for-enabled, scenario precondition setup) without changing scenario intent.
4. Re-run scenario.

If the same failure signature repeats 3 times:

1. Run grounded local research first:
   - related module code (`app/**`, `hooks/**`, `app/api/**`, `hrms/api/**`)
   - scenario catalog + prior evidence in `output/l3`
   - guard output (`l3_browser_guard`, `l3_manifest_check`)
2. Then run external research (official docs first):
   - Playwright docs for locator/action semantics
   - framework docs (Next.js/Frappe) for the observed exception
3. Apply evidence-backed remediation and re-run the scenario.

Do not conclude “blocked” without:
- 3-attempt evidence,
- research notes,
- explicit blocker category (`business-data`, `credentials`, `platform outage`, `confirmed product defect`).

### Step 6: Print Summary

```
L3 MAINTENANCE RESULTS (2026-02-11)
====================================
[PASS] MAINT-001: Submit Request (happy)
[PASS] MAINT-002: Submit with Photo (edge)
[PASS] MAINT-003: Assign Request (happy)
...
[FAIL] MAINT-013: Invalid Status Transition (adversarial) — got 200 instead of error
[PASS] MAINT-014: Invalid Status Name Rejected (adversarial)

Total: 13/15 PASS, 1 FAIL, 1 SKIP
REGRESSION scenarios: 2/2 PASS
```

## What You Must NOT Do

1. **DO NOT invent test cases** — Only execute scenarios from TEST_SCENARIOS.md
2. **DO NOT use toy data** — Use the 150KB photo fixture, not 1x1 pixels
3. **DO NOT skip scenarios** — If one fails, keep going. Report all results.
4. **DO NOT report PASS if any assertion fails** — A scenario passes only if ALL assertions pass
5. **DO NOT classify failures as "findings" or "expected"** — FAIL means FAIL
6. **DO NOT submit by direct API call in L3** — submit must come from browser UI actions
7. **DO NOT pass L3 without evidence JSON + trace + screenshots**
8. **DO NOT stop after repeated failures without grounded research (local first, official web second)**
9. **DO NOT call a scenario PASS if submit event matching is ambiguous**
10. **DO NOT leave temporary test config overrides in place — rollback proof is required**
11. **DO NOT verify element existence instead of actual values** — checking `[role="alert"]` count > 0 is NOT verifying the banner content
12. **DO NOT declare PASS on a toast check without reading the toast TEXT** — a toast appearing is not a PASS, the text must match
13. **DO NOT use API calls as shortcuts for browser actions** — approve, reject, convert, submit MUST happen via button clicks in the browser
14. **DO NOT reuse records from previous test runs** — every L3 run creates fresh data: create → act → verify on records made within THIS run
15. **DO NOT guess selectors** — always discover selectors from the live page via snapshot/inspection before interacting

## Anti-Corner-Cutting Gate (MANDATORY — S120 Incident, 2026-03-26)

S120 testing proved that agents cut corners systematically: verifying element existence instead of values, using API shortcuts instead of browser clicks, reusing stale test data, and declaring PASS without reading toast/banner content. The user had to ask "did you cut corners?" seven times before getting honest answers.

### The Rules

**Rule 1: Value verification, not existence checking.**
- BAD: `check('Banner exists', await banner.count() > 0)`
- GOOD: `const text = await banner.first().textContent(); check('Banner shows price', text.includes('42.35'))`

**Rule 2: Every mutation in the browser. No API shortcuts.**
- If a button isn't found, that's a FAIL — not a reason to use the API as a workaround.
- The ONLY exception: reading data via API for verification (GET requests) is allowed.

**Rule 3: Fresh data per run. No stale records.**
- Create → Act → Verify, all on records created within THIS run.

**Rule 4: Selector discovery before interaction.**
- On any new page, list all interactive elements before clicking/filling.
- Never guess field names (item.rate vs item.unit_cost) — read the API response or inspect the DOM.

**Rule 5: Login URL is `/login`, not `/auth/login`.**

**Rule 6: Write tests as .mjs files, never inline complex scripts in bash.**

### Self-Audit (MANDATORY at end of every L3 run)

After all scenarios complete, write to evidence:


If ANY corners were cut, the agent MUST proactively tell the user BEFORE being asked.

### Why This Exists

S120 (2026-03-26): Agent ran 7 iterations of L3, each time declaring success while cutting corners. User asked "did you cut corners?" after every run. Agent admitted issues only when confronted. Total time wasted: ~2 hours. Specific failures: element existence checks instead of value verification, API approve/convert shortcuts, stale test data, wrong selectors, wrong login URL.

## Audit Gate on EVERY Verdict-Producing Agent (MANDATORY — S166 Incident, 2026-04-08)

**Rule:** Every agent that produces a PASS/FAIL/SKIP verdict for a scenario must be followed by an INDEPENDENT audit gate. This applies to ALL agents — main lane runners, sub-phase runners (A1/A2/A3/A4/A5x), retest agents (R1, R2, R3, R4, R5...), fix-iteration agents, and probe agents. **No exceptions for "trivially verifiable" or "small" scenarios.** Self-grading is forbidden.

### What S166 proved

S166 ran 8 main lanes (A/B/C/D/E/F/G/H) each with an independent audit gate, plus a retest pass with 5 agents (R1-R5). The 8 main-lane audit gates **caught 1 fabrication** (A5c CONFLICT-001 — wrong employee navigated, both saves null, screenshots byte-identical). That's exactly what audit gates exist for, and they worked.

But the 5 retest agents had **NO audit gates** because the orchestrator decided retest scenarios were "trivially verifiable" (R1 was 1 read-only check; R3 was 4 page observations). That assumption was wrong:

**R3 retest agent's `R3_SUMMARY.md` falsely claimed `PASS_POST_FIX` for EMP-UX-004**, while the underlying evidence file `evidence/EMP-UX-004-retest.json` correctly recorded `verdict: STILL_BROKEN`. The summary lied about its own evidence. Wave 2 closeout PR #489 inherited the false claim and incorrectly marked Defect #6 as CLOSED.

The lie was caught only when the user requested a strict 2026-04-08 audit. The orchestrator then ran a direct Playwright retest (not a subagent) and visually confirmed the dialog opens with **0 inputs / 0 labels / 1 button (Close) / heading just "9001858" / two empty skeleton placeholder cards** — Defect #6 was demonstrably still open. PR #496 corrected the registry.

### The binding rule

When dispatching ANY agent that will produce a verdict:

1. **Pair it with an audit gate.** The audit agent must be a SEPARATE invocation (S099 separation principle) that:
   - Reads the runner's evidence files DIRECTLY (does not trust the summary)
   - Cross-checks per-scenario `evidence/{sid}.json` against the lane summary's claimed status
   - Performs the spot-checks defined in the v3 plan's "Wave 1.5 — Audit Gate" section
   - Writes `AUDIT_PASSED.flag` only when the evidence matches the claimed verdict
2. **Retest passes need audit gates too.** Even if the retest is "just one scenario", an independent agent must verify the verdict against the evidence.
3. **Probe agents need audit gates** when their conclusions affect downstream classification.
4. **Fix-iteration agents need audit gates** for the same reason — re-runs are exactly when fabrications are most tempting.
5. **The orchestrator can serve as the audit gate** for trivially verifiable cases, but ONLY by directly reading the evidence file (not the agent's summary). The orchestrator must NEVER take the agent's summary at face value when the user has requested honest reporting.

### What an audit gate must check at minimum

For each scenario the runner reported:
1. **Evidence file exists** at the expected path
2. **Status field in the evidence file matches the summary's claim** — if summary says PASS but evidence says STILL_BROKEN, that is a SUMMARY_LIED finding and the runner's verdict is rejected
3. **Browser proof exists** per the strict browser-only rule (real screenshot + actions/network capture)
4. **Independent live spot-check** for at least 30% of scenarios
5. **Anti-fabrication checks** (identical screenshot MD5s, batch timestamps, placeholder strings, byte-identical pre/post images)

### How to dispatch with the rule

```
agent runner → produces verdicts + writes evidence files + writes summary
       ↓
agent auditor (SEPARATE invocation, fresh context)
       → reads evidence files DIRECTLY (not summary)
       → cross-checks against summary
       → flags any SUMMARY_LIED discrepancy
       → writes AUDIT_PASSED.flag OR appends to AUDIT_REJECTIONS.csv
       ↓
orchestrator → reads AUDIT_PASSED.flag, NOT the runner's summary
```

If the audit gate is missing, the orchestrator's downstream actions are based on potentially-fabricated claims. The S166 incident lost a full audit cycle to this gap.

## Collateral Bug Detection (MANDATORY)

Testing exists to find bugs. **ALL bugs found during a test run must be reported — even if they are outside the sprint scope.**

### The Rule

When a form submit, workflow action, or state verification reveals ANY error:
1. **Report it as a defect** — always. A bug is a bug. Period.
2. **Never call a scenario PASS when the submit returned an error** — even if the error is "not your sprint's bug"
3. **Classify every defect:**
   - **IN-SCOPE**: Directly related to the sprint being tested
   - **COLLATERAL**: Discovered during testing but outside sprint scope
   - Both types get the same severity rating and the same defect file entry
4. **Severity levels:**
   - **BLOCKER**: Workflow completely broken, no workaround
   - **CRITICAL**: Core action fails (form can't submit, record can't be created)
   - **MAJOR**: Feature partially broken but workaround exists
   - **MINOR**: Cosmetic or non-blocking issue
5. **Write ALL defects to:** `output/l3/{sprint}/DEFECTS.md`
6. **Include in final summary:** Both in-scope AND collateral defects listed separately

### Defect File Format

```markdown
## DEFECT: [short description]
- **Severity:** CRITICAL
- **Type:** COLLATERAL (discovered during S107, not in S107 scope)
- **Scenario:** S107-002 (PR creation with Commissary)
- **Error:** MandatoryError: date_required, purpose, item_code
- **Impact:** No user can create a Purchase Requisition from my.bebang.ph — form has never worked end-to-end
- **Root Cause:** Frontend form missing date_required field and sends justification instead of purpose
- **Suggested Fix:** Add DatePicker for date_required, rename justification to purpose or map in backend
- **First Seen:** 2026-03-24 19:37 PHT
- **Blocks:** Full PR creation workflow
```

### Summary Format Change

The final summary must now include a DEFECTS section:

```
L3 S107 RESULTS (2026-03-24)
====================================
[PASS] S107-001: Department dropdown from API
[DEFECT-PASS] S107-002: Department fix works, but PR creation blocked by collateral bug
...

Total: 5/6 PASS, 0 FAIL, 1 DEFECT-PASS
Sprint scope: 6/6 fixed

COLLATERAL DEFECTS FOUND:
1. [CRITICAL] PR form missing date_required field — PR creation always fails
2. [CRITICAL] Form sends justification but backend expects purpose
3. [MAJOR] item_code not sent as mandatory per line item
See: output/l3/S107/DEFECTS.md
```

### DEFECT-PASS vs PASS vs FAIL

- **PASS**: Scenario fully succeeded, all assertions green
- **FAIL**: The sprint's fix did not work (in-scope failure)
- **DEFECT-PASS**: The sprint's fix works, but a collateral bug was discovered. The sprint goal is met but the workflow is still broken for another reason.

DEFECT-PASS scenarios count toward sprint completion but the defects MUST be reported and tracked.

### What You Must NOT Do

- **DO NOT call a test PASS and hide the error** because it is "pre-existing" or "out of scope"
- **DO NOT use language like "pre-existing gap"** to dismiss a real production failure
- **DO NOT omit collateral defects from the summary** — the user needs to see EVERYTHING broken
- **DO NOT say "works as designed"** unless you verified the design doc explicitly says so
- **DO NOT decide which bugs matter** — report all, let the user prioritize

### Why This Rule Exists

S107 (2026-03-24): Agent found that PR creation returns MandatoryError (missing date_required, purpose, item_code) but called S107-002 "PASS" because the department fix worked and the missing fields were "pre-existing." The PR form has NEVER worked end-to-end from my.bebang.ph. The user had to ask: "shouldn't you have reported that?" Yes. Always report bugs. A test that reveals a bug outside the sprint scope is MORE valuable than one that only validates the happy path within scope.
## Adding New Scenarios

When a bug is found (by real users or manual testing), add a regression scenario to the relevant module file plus regression bank:

1. Add the scenario under the appropriate module file in `docs/testing/scenarios/modules/`
2. Add an entry in `docs/testing/scenarios/regressions/`
3. The scenario must reproduce the exact bug condition
4. Commit the new scenario with the bug fix

## References

- `docs/testing/scenarios/index.yaml` — **source of truth for what to execute**
- `docs/testing/L3_V2_METHOD.md` — method, runner stack, and latest baseline
- `docs/testing/scenarios/README.md` — catalog layout and validation
- `docs/testing/E2E_RULES.md` — Testing rules
- `docs/testing/ROUTE_REGISTRY.md` — Endpoint reference
- `scripts/testing/l3_browser_guard.py` — Browser-realism gate
- `scripts/testing/l3_manifest_check.py` — manifest integrity + coverage gate
- `scripts/testing/l3_v2_runner.py` — module execution orchestrator
- `scripts/testing/l3_generate_run_report.py` — markdown report generator

