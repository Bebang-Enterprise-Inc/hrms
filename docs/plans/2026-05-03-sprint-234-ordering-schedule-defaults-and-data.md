---
sprint_id: S234
sprint_title: Ordering Schedule Defaults Defense + Smoke Test Repoint + Data Foundation
plan_branch: s234-ordering-schedule-defaults-and-data
status: COMPLETED
version: 2
created_date: 2026-05-03
audited_date: 2026-05-03
build_completed_date: 2026-05-03
completed_date: 2026-05-03
backend_pr: 716
merge_sha: 29a1b5857
l3_result: N/A (read-only API change; no L3 scenarios)
execution_summary: |
  All phases PASS. PR #716 merged (29a1b5857) and deployed.

  Phase 0: canonical preflight 0 violations; state_before — Estancia=null
  (defaults branch confirmed failing), ARANETA=ISO via fallback_last_week.
  SHAs captured: hrms 71e77d706 / bei-tasks d3c663a58.

  Lane A (327e9b11f): synthesized add_days(today, 2/3) in defaults dict.
  cold_interval/dry_interval deliberately omitted (REC-ENGINE-DRIFT defense
  from v2 audit).

  Lane B: local-only edit to .claude/skills/merge-bei-erp/SKILL.md (gitignored).
  Mirrors synced to .agent/.agents. Live smoke proof captured.

  Lane C (cfe967ae5): seeder (savepoint+dry-run-default), cron skeleton
  (DISABLED_BY_DEFAULT), CSV template, runbook, doctype_schema.json.

  Phase D post-deploy validation:
  - 3-cycle ARANETA smoke: 3/3 PASS (cold=2026-05-04, dry=2026-05-04, schedule_source=fallback_last_week)
  - Estancia post-deploy: PASS (cold=2026-05-05, dry=2026-05-06, schedule_source=default)
  - 49-store state_after: 47 default + 2 fallback_last_week + 0 null
  - Canonical postcheck: 0 violations across 49 stores (preflight parity)

  Outcome: 47 default-stores no longer return null for next_cold_delivery /
  next_dry_delivery. Smoke probe now actually canaries the schedule pipeline
  (was always-failing on Estancia which has no entries). Recommendation
  engine math UNCHANGED for all 49 stores (cold_interval/dry_interval guards
  in place).
canonical_scope: in
canonical_model_reference: docs/STORE_COMPANY_CANONICAL.md
canonical_preflight: required
evidence_committed:
  - output/s234/SUMMARY.md
  - output/s234/verification/state_before.json
  - output/s234/verification/state_after.json
  - output/s234/verification/api_probe_after_fix.json
  - output/s234/verification/smoke_repoint_proof.txt
  - output/s234/verification/canonical_postcheck.log
  - output/l3/s234/api_probe_estancia_after.json
  - output/l3/s234/api_probe_araneta_after.json
  - output/l3/s234/smoke_3_cycle_log.txt
  - output/l3/s234/state_verification.json
evidence_transient:
  - tmp/s234/probe_*.json
  - tmp/s234/seed_dry_run_*.log
  - tmp/s234/cron_dry_run_*.log
  - tmp/s234/remote_truth_baseline_*.sha
  - tmp/s234/store.py.before
sprint_registry_row: |
  | `S234` | Sprint 234 | `s234-ordering-schedule-defaults-and-data` (hrms) | TBD | PLANNED_AUDITED_v2 2026-05-03 — Ordering Schedule Defaults Defense + Smoke Test Repoint + Data Foundation | `docs/plans/2026-05-03-sprint-234-ordering-schedule-defaults-and-data.md` |
---

## v2 Amendment Summary (2026-05-03)

Applied after `/audit-plan-bei-erp` ran 4 parallel domain auditors + code-verifier + adversarial fact-checker. Audit evidence: `output/plan-audit/sprint-234-ordering-schedule-defaults-and-data/AUDIT_REPORT.md`.

**3 CRITICAL fixes:**
1. **REC-ENGINE-DRIFT** — dropped `cold_interval=7`/`dry_interval=7` from Lane A defaults dict. The "shape consistency" rationale was verifiably wrong (the unreachable `_delivery_interval(set())` branch made the new keys unnecessary). Adding them would have inflated `coverage_window_days` from 2/3 → 7/7 for 47 default-stores, scaling `suggested_qty` by 2.3-3.5×. v2 keeps only the synthesized date fields + the existing `days_to_*` keys.
2. **Evidence path schism** — added `output/l3/s234/*` paths to YAML `evidence_committed`. Closeout `canonical_closeout_artifacts` now enumerates all 9 committed files (was 5).
3. **Orphaned state files** — added Phase D-T2.5 (write `state_after.json` post-deploy probe) and D-T2.6 (write `state_verification.json` read-only attestation). Both files now have a writer.

**8 WARNING fixes:**
- W1: Test Data Seeding Contract now has structured precondition table.
- W2: `verify_phase_a.py` extended to grep for Sentry preservation.
- W3: L3 Scenarios retitled "API Smoke (L1) + L3 Banner Spot-Check"; scenario 4 (frontend banner DOM check) DROPPED — out of scope for read-only API change; banner rendering is bei-tasks frontend concern, not S234.
- W4: Lane A+B+C explicitly ship in ONE PR (defer PR creation until Phase C committed) — avoids merged-branch hook blocking subsequent pushes.
- W5: Phase 0-T6 added to capture origin/production + origin/main SHAs into `tmp/s234/remote_truth_baseline_*.sha`.
- W6: `verify_phase_c.py` extended to check `next_monday = add_days` MUST_CONTAIN + `--dry-run default=True` argparse default.
- W7: Lane C seeder must use `frappe.db.savepoint("s234_week_<name>")` per DM-2.
- W8: A-T2 explicitly says skip if `/local-frappe` not configured; A-T5 post-deploy probe catches the same regression.

**STALE findings dropped:**
- Concurrent S231/S232/S233 hot-file claim (those PRs already merged; no in-flight collision)
- Lane C logical independence (auditor preference, not a code gap)

# S234 — Ordering Schedule Defaults Defense + Smoke Test Repoint + Data Foundation

## Why this exists (Design Rationale for Cold-Start Agents)

**The defect:** for 20+ consecutive `/merge-bei-erp` cycles since mid-April, the smoke test at `https://my.bebang.ph/api/ordering?action=validate_order_schedule&store=Estancia` has returned `next_cold_delivery=null` and `next_dry_delivery=null`. Smoke FAIL was reported every cycle but proceeded because no merged PR plausibly caused it (PRs were docs, scripts, billing endpoints — none touched the ordering code path).

**Investigation finding (2026-05-03 trace by another agent):**
- The frontend route `bei-tasks/app/api/ordering/route.ts` proxies to Frappe `hrms.api.store.validate_order_schedule`.
- That endpoint reads from `_get_next_deliveries(store_warehouse)` in `hrms/api/store.py:1282-1407`.
- `_get_next_deliveries` returns a **defaults dict** (lines 1297-1303) whenever no schedule is found:
  ```python
  defaults = {
      "next_cold_delivery": None,
      "next_dry_delivery": None,
      "days_to_cold": 2,
      "days_to_dry": 3,
      "schedule_source": "default",
  }
  ```
- That defaults dict is **internally inconsistent**: it claims `days_to_cold=2` but `next_cold_delivery=null`. A consumer can't render "the next cold delivery is in 2 days but I don't know the date."
- The smoke test consumer treats `null` as failure → smoke FAIL every cycle.

**Why only Estancia gets defaults:** out of 49 stores, only **ARANETA GATEWAY** and **AYALA UP TOWN CENTER** have rows in `tabBEI Delivery Schedule Entry`. The latest published `BEI Delivery Schedule Week` is `BEI-SCHED-2026-00003` (week_start `2026-04-06`) — 4 weeks stale. Estancia is one of the 47 stores that hit the defaults branch.

**What this is NOT:**
- NOT a regression introduced by recent merges (the defaults branch has always returned null dates)
- NOT a blocker for ordering itself — the v15 (2026-05-01) and v16 (2026-05-03) full 49-store happy-chain sweeps PASSED 49/49 effective. Orders create, get approved, dispatched, received, and invoiced regardless of `validate_order_schedule` returning null dates.
- NOT a recommendation engine bug — `_compose_signal_modifiers` and `_build_recommendation_contract` use `cold_interval`/`dry_interval` (which the defaults DO return), not the absolute dates. The dates are for UI banner display only.

**What this fix does:**
- **Phase A (code fix, 5 units)**: synthesize `next_cold_delivery = str(add_days(today, 2))` / `next_dry_delivery = str(add_days(today, 3))` in the defaults dict so the response is internally consistent and the UI banner can render a "best-guess" date. The `schedule_source: "default"` tag stays — consumers that want to distinguish synthetic vs real schedules still can.
- **Phase B (smoke repoint, 3 units)**: switch the smoke test from `Estancia` (a store with no schedule rows; always hits defaults; wrong canary) to `ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC` (one of the 2 stores with real schedule rows). Now the smoke test actually canaries the schedule pipeline — if it fails, something genuinely broke.
- **Phase C (data foundation, 30 units)**: author the seeder + cron skeleton so future logistics handoffs can populate real cadence data without engineering follow-up. The cron is built but DISABLED until logistics provides cadence data; only the dry-run mode is enabled at closeout.
- **Phase D (closeout, 10 units)**: PRs, registry update, evidence, sweep delta confirmation.

**Reasons for splitting it this way:**
- Lane A is the smallest possible patch that fixes the smoke alarm while preserving forward semantics.
- Lane B is one-line and decouples the test from a known-empty data path.
- Lane C is genuinely operational — logistics owns the cadence — but engineering can build the import surface so when logistics is ready, populating the data takes minutes not days. Without Lane C, the synthesized defaults from Lane A become drift over time (real Tue/Fri cadence vs synthesized "in 2 days regardless").

**Reference incidents:**
- 2026-04-30 → 2026-05-01: S225 v15 sweep proved that ordering happy chain works even when `validate_order_schedule` returns null. Lane A is therefore safe to ship without Lane C.
- 2026-05-03: v16 sweep + billing audit (PR #714, #715) confirmed Lane A scope (defaults dict only) doesn't intersect with any GL or canonical-master-data path.

## Canonical Model Preflight (Mandatory)

Executing agent MUST run before the first code change:

```bash
cd <worktree> && python scripts/verify_canonical_structure.py
```

If the verifier prints `[VIOLATION]`, STOP and ask the user. Do NOT add records, flip fields, or create customers/warehouses to paper over a violation.

**Canonical law applies to this plan because:**
- Touches `hrms/api/store.py` (in the canonical-gate file list per `.claude/CLAUDE.md`)

**Canonical law does NOT change behavior in this plan because:**
- No INSERT/UPDATE/DELETE on `tabCompany`, `tabWarehouse`, `tabCustomer`, `tabSupplier`
- No SI/PO/MR/SE/JE/PE/GL Entry creation
- No Chart of Accounts changes
- No `resolve_store_buyer_entity` / `resolve_warehouse_company` / `_STORE_TO_CHILD` mutations
- The `_get_next_deliveries` change only modifies the **defaults dict in a function body** — pure read path; no master data touched
- The Lane C seeder writes ONLY to `BEI Delivery Schedule Week` + `BEI Delivery Schedule Entry` — operational schedule child tables, NOT canonical Company/Warehouse/Customer master data

**Scope claim:**
- 0 Companies created/updated/disabled
- 0 Warehouses created/updated/disabled
- 0 Customers created/updated/disabled
- 0 Suppliers created/updated/disabled
- N rows in `BEI Delivery Schedule Week` created (N = number of weeks logistics provides; 0 in dry-run mode for this sprint)
- N×49 rows in `BEI Delivery Schedule Entry` created (deferred until logistics provides cadence; only seeder script ships)

## Canonical Model Binding

This feature reads canonical fields:
- Reads `Warehouse.name` to map smoke-test store name → `store_warehouse` (canonical per-store warehouse name)
- Reads `BEI Delivery Schedule Week` + `BEI Delivery Schedule Entry` (operational schedule, not canonical)

This feature does NOT:
- Bypass `resolve_store_buyer_entity` for any computation
- Add new fallback logic to canonical resolvers
- Use parent Company name string-parsing
- Hardcode parent Company names

## Requirements Regression Checklist

Executing agent MUST verify these before each PR:

- [ ] Lane A defaults dict synthesizes BOTH `next_cold_delivery` AND `next_dry_delivery` (not just one)
- [ ] Lane A defaults dict uses `add_days(today, days_to_cold)` and `add_days(today, days_to_dry)` (not hardcoded date strings)
- [ ] Lane A `schedule_source` tag remains `"default"` (consumers must be able to distinguish synthesized from published)
- [ ] Lane A does NOT change behavior when a published schedule exists (the `entries` branch is untouched)
- [ ] Lane A returns the same dict shape (no new keys, no removed keys) so downstream callers don't break
- [ ] Lane B updates `merge-bei-erp/SKILL.md` to use a store name that exists in `tabBEI Delivery Schedule Entry`
- [ ] Lane B does NOT delete the store-name parameter; just changes the value
- [ ] Lane C seeder is idempotent (running twice with the same CSV produces the same end state)
- [ ] Lane C cron is committed but registered DISABLED until logistics signs off on cadence
- [ ] No Company/Warehouse/Customer/Supplier mutations introduced anywhere
- [ ] No new `frappe.db.set_value` or `frappe.db.sql` UPDATE/INSERT/DELETE on `tabCompany`/`tabWarehouse`/`tabCustomer`
- [ ] Sentry observability: `validate_order_schedule` already calls `set_backend_observability_context` (verify, don't add)
- [ ] Cold-start test passed: an agent reading only this plan can complete every phase

## API Smoke Probes (L1) + L3 Banner Spot-Check (v2 audit fix W3)

This sprint touches a read-only API and a smoke test, NOT operator-facing surfaces with form submissions. The probes below are mechanically L1 (API smoke + JSON shape checks). Banner DOM verification (originally listed as scenario 4) is OUT OF SCOPE — that's a bei-tasks frontend concern; the synthesized date is already proven via JSON probe, and a Playwright banner check would require infrastructure not justified by the read-only API change.

### L1 API Smoke Probes (mandatory)

| User | Action | Expected outcome | Failure means |
|---|---|---|---|
| Anonymous (auth via session cookie) | `GET /api/ordering?action=validate_order_schedule&store=Estancia` | Response has `data.next_cold_delivery` and `data.next_dry_delivery` as ISO date strings (not null), with `data.schedule_source = "default"` | Lane A code fix not deployed or regression |
| Anonymous (auth via session cookie) | `GET /api/ordering?action=validate_order_schedule&store=ARANETA%20GATEWAY%20-%20TUNGSTEN%20CAPITAL%20HOLDINGS%20OPC` | Response has `data.next_cold_delivery` and `data.next_dry_delivery` as ISO date strings, `data.schedule_source = "current"` or `"fallback_last_week"` | Schedule pipeline genuinely broken (this is what the smoke test should catch) |
| Sam (running `/merge-bei-erp` after the deploy) | Trigger Step 3.5 smoke probe | Smoke prints `PASS: cold=YYYY-MM-DD dry=YYYY-MM-DD` for 3 consecutive cycles | Lane B repoint not deployed OR Lane A regression |

**Evidence files (committed):**
- `output/l3/s234/api_probe_estancia_after.json`: raw response from validate_order_schedule for Estancia post-deploy
- `output/l3/s234/api_probe_araneta_after.json`: raw response for ARANETA GATEWAY post-deploy
- `output/l3/s234/smoke_3_cycle_log.txt`: 3 consecutive `/merge-bei-erp` cycles all PASS
- `output/l3/s234/state_verification.json`: minimal verification structure (no form submissions to log)

No `form_submissions.json` / `api_mutations.json` required — this sprint creates zero docs.

## Test Data Seeding Contract

**N/A — Read-only sprint.** No production data seeded; no records mutated; no teardown required.

### L3 scenario precondition table (v2 audit fix W1)

Every L3 scenario depends on existing production state. The plan does NOT create or mutate any of these — it only reads them.

| Scenario | Required existing state | Owner | How to verify pre-execution |
|---|---|---|---|
| Estancia probe (Lane A canary) | `Warehouse` "ORTIGAS ESTANCIA - BB ESTANCIA FOOD CORP." exists; ZERO entries in `BEI Delivery Schedule Entry` for that store (forces defaults branch) | Ops master data | `frappe.db.exists("Warehouse", "ORTIGAS ESTANCIA - BB ESTANCIA FOOD CORP.")` + `frappe.db.count("BEI Delivery Schedule Entry", {"store": "..."}) == 0` |
| ARANETA GATEWAY probe (Lane B canary) | `Warehouse` "ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC" exists; has rows in `BEI Delivery Schedule Entry` under latest published `BEI Delivery Schedule Week` | Logistics (already populated) | Phase 0 state_before.json probe captures + verifies non-null `next_cold_delivery` |
| 3-cycle smoke (Lane B post-deploy) | Frappe `validate_order_schedule` whitelisted endpoint reachable + auth via `FRAPPE_ADMIN_PASSWORD` Doppler secret | Doppler (`bei-erp` / `dev` config) | `doppler secrets get FRAPPE_ADMIN_PASSWORD --plain` returns non-empty |
| Lane C seeder dry-run | `BEI Delivery Schedule Week` + `BEI Delivery Schedule Entry` DocTypes exist; `data/operational/delivery_cadence_template.csv` template (newly committed in Phase C-T4) | This plan | C-T1 schema probe writes `output/s234/verification/doctype_schema.json` |

### Seeder execution policy

For Phase C (data foundation), the seeder script DOES seed real production schedule data — but only when run with a real CSV input from logistics. In THIS sprint we ship:
- Seeder script (idempotent, dry-run capable, savepoint-protected per DM-2)
- Empty input template (`data/operational/delivery_cadence_template.csv`)
- Cron skeleton (DISABLED until logistics signoff)

We do NOT execute the seeder against production. That is a follow-up operational task for when logistics provides the cadence CSV. If the executing agent ends up needing test data (unlikely — Lane C tests are dry-run only), use `/frappe-bulk-edits` per `.claude/skills/frappe-bulk-edits/` and tear down via the same skill.

## Failure Response

If a test fails during execution, classify and respond:

- **Mode A (app bug)**: file `[BUG] s234 — <symptom>` to GitHub, do NOT modify the smoke test or the test library. Re-run after the bug fix lands.
- **Mode B (test bug)**: fix the test directly. If the fix generalizes, promote it to the test library.
- **Mode C (brittleness/flakiness)**: fix the LIBRARY, not the spec. No `waitForTimeout`, no `retry(3)` masking. Library code lives in `bei-tasks/tests/e2e/` (pages/, fixtures/, builders/, assertions/).

If ≥3 library fixes happen during this sprint, emit `output/l3/s234/LIBRARY_IMPROVEMENTS.md` as a closeout artifact.

## Phases

### Phase 0 — Boot & Worktree Spawn (5 units)

**0-T1** Read this plan fully (every section, including Design Rationale).

**0-T2** Spawn worktree (NEVER work in main checkout per `.claude/rules/worktree-isolation.md`):
```bash
BR=s234-ordering-schedule-defaults-and-data
WT=F:/Dropbox/Projects/BEI-ERP-${BR##*/}
cd F:/Dropbox/Projects/BEI-ERP && git fetch origin --prune
git worktree add "$WT" -B "$BR" origin/production
cd "$WT"
```

**0-T3** Run canonical preflight:
```bash
python scripts/verify_canonical_structure.py 2>&1 | tee tmp/s234/canonical_preflight.log
```
If `[VIOLATION]` appears → STOP and ask Sam.

**0-T4** Capture pre-fix state (for delta proof at closeout):
```bash
mkdir -p output/s234/verification tmp/s234
# probe Estancia (the failing canary) and ARANETA GATEWAY (the new canary)
cat > tmp/s234/probe_before.py <<'PY'
import os, sys, json, requests
PWD = os.environ["FRAPPE_ADMIN_PASSWORD"]
s = requests.Session()
s.post("https://hq.bebang.ph/api/method/login", data={"usr":"sam@bebang.ph","pwd":PWD})
out = {}
for name in ["Estancia", "ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC"]:
    r = s.get("https://my.bebang.ph/api/ordering",
              params={"action":"validate_order_schedule","store":name})
    out[name] = {"status": r.status_code, "data": r.json().get("data", {})}
print(json.dumps(out, indent=2))
PY
FRAPPE_ADMIN_PASSWORD=$(C:/Users/Sam/bin/doppler.exe secrets get FRAPPE_ADMIN_PASSWORD --plain --project bei-erp --config dev) python tmp/s234/probe_before.py > output/s234/verification/state_before.json
```

**0-T5** Verify the fix files exist where the plan says:
```bash
test -f hrms/api/store.py && echo "✓ store.py present"
test -f .claude/skills/merge-bei-erp/SKILL.md && echo "✓ merge-bei-erp SKILL present"
grep -n "_get_next_deliveries" hrms/api/store.py | head -5
grep -n "validate_order_schedule&store=Estancia" .claude/skills/merge-bei-erp/SKILL.md | head -5
```

**0-T6** (v2 audit fix W5) Capture remote-truth-baseline SHAs per the Anti-Rewind contract:

```bash
git rev-parse origin/production > tmp/s234/remote_truth_baseline_hrms.sha
git -C F:/Dropbox/Projects/bei-tasks rev-parse origin/main > tmp/s234/remote_truth_baseline_bei_tasks.sha
echo "hrms baseline: $(cat tmp/s234/remote_truth_baseline_hrms.sha)"
echo "bei-tasks baseline: $(cat tmp/s234/remote_truth_baseline_bei_tasks.sha)"
```

Sprint must NOT be merged if either baseline has moved AND those moves include changes to `hrms/api/store.py:1280-1410` (Lane A surface) or `.claude/skills/merge-bei-erp/SKILL.md` lines 95-125 (Lane B surface). Re-run preflight after rebase if either upstream changed.

**Phase 0 verification script** (machine-checkable per S154 rule):
```bash
cat > tmp/s234/verify_phase_0.py <<'PY'
import os, sys, json
errs = []
required = [
    "hrms/api/store.py",
    ".claude/skills/merge-bei-erp/SKILL.md",
    "tmp/s234/canonical_preflight.log",
    "output/s234/verification/state_before.json",
]
for f in required:
    if not os.path.exists(f): errs.append(f"MISSING: {f}")
state = json.load(open("output/s234/verification/state_before.json"))
estancia = state.get("Estancia", {}).get("data", {})
if estancia.get("next_cold_delivery") is not None:
    errs.append("UNEXPECTED: Estancia already has non-null cold delivery before fix — preconditions wrong")
print("PASS" if not errs else "\n".join(errs))
sys.exit(0 if not errs else 1)
PY
python tmp/s234/verify_phase_0.py
```

### Phase A — Code Fix: Synthesize defaults dict (5 units)

**A-T1** Modify `hrms/api/store.py` lines 1295-1303. Replace the static defaults dict with one that synthesizes the dates from the day offsets.

```python
# MUST_MODIFY: hrms/api/store.py
# MUST_CONTAIN (after change): 'next_cold_delivery": str(add_days(today, 2))'
# MUST_CONTAIN (after change): 'next_dry_delivery": str(add_days(today, 3))'
# MUST_CONTAIN (after change, unchanged): 'schedule_source": "default"'
# MUST_NOT_CONTAIN (v2 audit fix REC-ENGINE-DRIFT): 'cold_interval' OR 'dry_interval' anywhere in this defaults dict
```

Exact diff:
```python
# BEFORE (lines 1295-1303):
today = getdate(nowdate())

defaults = {
    "next_cold_delivery": None,
    "next_dry_delivery": None,
    "days_to_cold": 2,  # Frozen default
    "days_to_dry": 3,  # Dry default
    "schedule_source": "default",
}

# AFTER (v2 — interval keys deliberately omitted):
today = getdate(nowdate())

# S234: synthesize default delivery dates from day offsets so the response
# is internally consistent (was: dates None but days_to_cold/dry positive).
# UI banners can now render a "best-guess" date when no schedule is published.
# schedule_source="default" tag preserved so consumers can distinguish
# synthetic vs published schedules.
defaults = {
    "next_cold_delivery": str(add_days(today, 2)),
    "next_dry_delivery": str(add_days(today, 3)),
    "days_to_cold": 2,  # Frozen default
    "days_to_dry": 3,  # Dry default
    "schedule_source": "default",
}
```

**v2 audit fix:** `cold_interval` and `dry_interval` are deliberately NOT added to the defaults dict. The plan v1 added them for "shape consistency" with the entries-branch return at line 1399-1407, but the adversarial fact-checker confirmed that's a behavior-changing regression: the consumer at `hrms/api/store.py:2710-2715` resolves `coverage_window_days = store_deliveries.get("cold_interval") or store_deliveries.get("days_to_cold") or 2`. Today's defaults have no `cold_interval` key → falls through to `days_to_cold or 2` (= 2 cold, 3 dry). Adding `cold_interval=7`/`dry_interval=7` would jump `coverage_window_days` to 7, scaling `suggested_qty` by 2.3-3.5× for 47 default-stores. The shape-consistency rationale was a dead-code premise: the entries branch's `_delivery_interval(set())` is unreachable in production (line 1342 returns defaults early when entries are empty). Keep the defaults dict shape as-is — the consumer's `or` chain handles missing keys correctly.

**A-T2** Verify the fix locally with `bench`:
```bash
cd hrms-bench  # local Frappe — see /local-frappe skill
bench --site test_site console <<'PY'
from hrms.api.store import _get_next_deliveries
result = _get_next_deliveries("Estancia")
import json
print(json.dumps(result, indent=2, default=str))
assert result["next_cold_delivery"] is not None, "FAIL: cold still null"
assert result["next_dry_delivery"] is not None, "FAIL: dry still null"
assert result["schedule_source"] == "default", "FAIL: source should be 'default' for unknown store"
PY
```

If `/local-frappe` isn't available, skip the local test — the Phase 0 dry-run + production probe in Phase A-T3 catches regressions.

**A-T3** (v2 audit fix W4) Commit Lane A on the branch — DO NOT open the PR yet. PR creation is deferred to Phase C-T7 so all three lanes ship in ONE PR. This avoids the merged-branch hook blocking Lane B/C pushes if Sam merges Lane A immediately.

```bash
git add hrms/api/store.py
git commit -m "fix(S234-A): synthesize default delivery dates in _get_next_deliveries"
# NO push, NO gh pr create yet — wait for Lane B + Lane C
```

**A-T4** (v2: deferred to Phase C-T7) PR creation is consolidated in Phase C-T7 once all three lanes are committed. Builder waits on PR comments after that single PR opens — no agent self-merge.

**A-T5** Post-deploy probe (runs after Sam merges + Vercel/deploy completes; this happens AFTER Phase D-T1):
```bash
FRAPPE_ADMIN_PASSWORD=... python tmp/s234/probe_after.py > output/s234/verification/api_probe_after_fix.json
# Assertions: Estancia next_cold_delivery is now ISO date string; ARANETA still has its real schedule date
```

**Note (v2 audit fix W8):** A-T2 below required local Frappe bench. If `/local-frappe` is not configured in the executing agent's environment, **SKIP A-T2** — the post-deploy probe at A-T5 catches the same regression class (Estancia returning null after deploy = code fix not effective). Agent must NOT block on local bench unavailability.

**Phase A verification script:**
```bash
cat > tmp/s234/verify_phase_a.py <<'PY'
import json, sys, subprocess, re
errs = []
diff = subprocess.run(["git","diff","origin/production","--name-only"], capture_output=True, text=True).stdout
if "hrms/api/store.py" not in diff:
    errs.append("MUST_MODIFY violated: hrms/api/store.py not in diff")
content = open("hrms/api/store.py").read()
if "str(add_days(today, 2))" not in content or "str(add_days(today, 3))" not in content:
    errs.append("MUST_CONTAIN violated: synthesized add_days calls missing")
if 'schedule_source": "default"' not in content and "schedule_source\": \"default\"" not in content:
    errs.append("MUST_CONTAIN violated: schedule_source default tag missing")

# v2 audit fix REC-ENGINE-DRIFT: confirm cold_interval/dry_interval NOT added to defaults dict.
# Look in the function body of _get_next_deliveries (lines 1280-1410 approx).
defaults_block = re.search(r"def _get_next_deliveries.*?(?=\ndef |\nclass |\Z)", content, re.DOTALL)
if defaults_block:
    body = defaults_block.group(0)
    # The defaults dict is the FIRST dict literal in the function body
    first_dict = re.search(r"defaults\s*=\s*\{[^}]+\}", body, re.DOTALL)
    if first_dict and ("cold_interval" in first_dict.group(0) or "dry_interval" in first_dict.group(0)):
        errs.append("MUST_NOT_CONTAIN violated: cold_interval/dry_interval added to defaults dict — would cause REC-ENGINE-DRIFT regression")

# v2 audit fix W2: verify Sentry observability preservation on validate_order_schedule.
# Sentry context is wired around line 3000-3006. Confirm the call is still present
# (a future agent could remove it when editing nearby code).
sentry_block = re.search(r"def validate_order_schedule.*?(?=\ndef |\nclass |\Z)", content, re.DOTALL)
if sentry_block and "set_backend_observability_context(" not in sentry_block.group(0):
    errs.append("REGRESSION: Sentry context call missing from validate_order_schedule (was at store.py:3000-3006)")

state = json.load(open("output/s234/verification/api_probe_after_fix.json"))
estancia = state.get("Estancia", {}).get("data", {})
if estancia.get("next_cold_delivery") is None or estancia.get("next_dry_delivery") is None:
    errs.append(f"DEPLOY violated: Estancia still has null after fix: {estancia}")
print("PASS" if not errs else "\n".join(errs))
sys.exit(0 if not errs else 1)
PY
python tmp/s234/verify_phase_a.py
```

### Phase B — Smoke Test Repoint (3 units)

**B-T1** Edit `.claude/skills/merge-bei-erp/SKILL.md` at line 106.

```bash
# MUST_MODIFY: .claude/skills/merge-bei-erp/SKILL.md
# MUST_CONTAIN (after change): "store=ARANETA%20GATEWAY%20-%20TUNGSTEN%20CAPITAL%20HOLDINGS%20OPC"
# MUST_NOT_CONTAIN (after change): "store=Estancia"  (in the validate_order_schedule probe — other Estancia mentions in different probes can stay)
```

Exact diff:
```diff
-curl -sS "https://my.bebang.ph/api/ordering?action=validate_order_schedule&store=Estancia" \
+# S234: probe a store with REAL schedule data (one of ARANETA GATEWAY / AYALA UP TOWN CENTER).
+# Estancia (the previous canary) has no published schedule entries → always returns
+# synthesized defaults; it doesn't actually canary the schedule pipeline. ARANETA
+# GATEWAY has real entries → smoke FAIL on this URL means the publish pipeline broke.
+curl -sS "https://my.bebang.ph/api/ordering?action=validate_order_schedule&store=ARANETA%20GATEWAY%20-%20TUNGSTEN%20CAPITAL%20HOLDINGS%20OPC" \
```

Update the FAIL message comment too:
```diff
 if cold and dry:
     print(f'PASS: cold={cold} dry={dry}')
 else:
-    print(f'FAIL: cold={cold} dry={dry} — delivery schedule regression!')
+    print(f'FAIL: cold={cold} dry={dry} — delivery schedule pipeline regression for ARANETA GATEWAY!')
```

**B-T2** Test the repoint locally:
```bash
SID=$(python -c "
import requests, os
r = requests.post('https://hq.bebang.ph/api/method/login',
    data={'usr':'sam@bebang.ph','pwd': os.environ['FRAPPE_ADMIN_PASSWORD']})
print(r.cookies.get('sid',''))
")
curl -sS "https://my.bebang.ph/api/ordering?action=validate_order_schedule&store=ARANETA%20GATEWAY%20-%20TUNGSTEN%20CAPITAL%20HOLDINGS%20OPC" \
  -H "Cookie: sid=$SID" | tee output/s234/verification/smoke_repoint_proof.txt | python -c "
import sys, json
d = json.load(sys.stdin)
data = d.get('data', {})
cold = data.get('next_cold_delivery')
dry = data.get('next_dry_delivery')
assert cold and dry, f'FAIL: cold={cold} dry={dry}'
print(f'PASS: cold={cold} dry={dry}')"
```

**B-T3** Commit on the same branch (Lane A + Lane B in one PR is acceptable since both are tiny + same domain). Or push as separate commit on the same branch:
```bash
git add .claude/skills/merge-bei-erp/SKILL.md
git commit -m "fix(S234-B): repoint smoke probe from Estancia (no schedule) to ARANETA GATEWAY"
git push origin s234-ordering-schedule-defaults-and-data
```

**Phase B verification script:**
```bash
cat > tmp/s234/verify_phase_b.py <<'PY'
import sys, subprocess, os
errs = []
diff = subprocess.run(["git","diff","origin/production","--name-only"], capture_output=True, text=True).stdout
if ".claude/skills/merge-bei-erp/SKILL.md" not in diff:
    errs.append("MUST_MODIFY violated: SKILL.md not in diff")
content = open(".claude/skills/merge-bei-erp/SKILL.md").read()
if "ARANETA%20GATEWAY%20-%20TUNGSTEN%20CAPITAL%20HOLDINGS%20OPC" not in content:
    errs.append("MUST_CONTAIN violated: ARANETA URL missing")
# Find the validate_order_schedule probe block and ensure no Estancia in IT specifically
import re
m = re.search(r'curl -sS "[^"]*validate_order_schedule[^"]*"', content)
if m and "Estancia" in m.group(0):
    errs.append("MUST_NOT_CONTAIN violated: validate_order_schedule probe still uses Estancia")
proof = open("output/s234/verification/smoke_repoint_proof.txt").read()
import json
d = json.loads(proof)
data = d.get("data", {})
if not data.get("next_cold_delivery") or not data.get("next_dry_delivery"):
    errs.append("PROOF violated: ARANETA probe didn't return ISO dates")
print("PASS" if not errs else "\n".join(errs))
sys.exit(0 if not errs else 1)
PY
python tmp/s234/verify_phase_b.py
```

### Phase C — Data Foundation: Seeder + Cron Skeleton (30 units)

**C-T1** Inspect `BEI Delivery Schedule Week` and `BEI Delivery Schedule Entry` DocType schemas:
```bash
cat > tmp/s234/probe_doctypes.py <<'PY'
import os, sys
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe, json
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")
out = {}
for dt in ["BEI Delivery Schedule Week", "BEI Delivery Schedule Entry"]:
    if not frappe.db.exists("DocType", dt):
        out[dt] = "MISSING"; continue
    meta = frappe.get_meta(dt)
    out[dt] = [{"fieldname":f.fieldname,"fieldtype":f.fieldtype,"options":f.options,"reqd":f.reqd}
               for f in meta.fields]
print(json.dumps(out, indent=2, default=str))
PY
# Run via SSM (script-from-stdin pattern in scripts/s225/README.md)
```
Save output to `output/s234/verification/doctype_schema.json`.

**C-T2** Author `scripts/s234_seed_delivery_schedule.py` — idempotent CSV→Frappe bulk seeder, savepoint-protected per DM-2 (v2 audit fix W7).

```python
# MUST_MODIFY: scripts/s234_seed_delivery_schedule.py (NEW)
# MUST_CONTAIN: "argparse" (CLI args)
# MUST_CONTAIN: "--dry-run"
# MUST_CONTAIN: "--week-start"
# MUST_CONTAIN: "frappe.db.get_value(\"BEI Delivery Schedule Week\""  (idempotency check)
# MUST_CONTAIN: "frappe.db.savepoint"  (v2 audit fix W7 — DM-2 atomic multi-doc write)
# MUST_CONTAIN: "default=True"  (v2 audit fix W6 — --dry-run safe-by-default)
```

**DM-2 savepoint requirement:** the seeder writes to `BEI Delivery Schedule Week` (parent) AND `BEI Delivery Schedule Entry` (children) per CSV import. Per `.claude/rules/frappe-development.md` DM-2, multi-doc updates must wrap in `frappe.db.savepoint("s234_week_<name>")` with `frappe.db.rollback_to_savepoint()` on any exception. If the children fail mid-import, the parent Week record must roll back too — never leave a published Week with partial entries.

```python
# Example structure (seeder body):
for week_name, csv_rows in groups.items():
    sp = f"s234_week_{week_name}"
    try:
        frappe.db.savepoint(sp)
        week_doc = _upsert_week(week_name, dry_run=args.dry_run)
        _replace_entries(week_doc.name, csv_rows, dry_run=args.dry_run)
        if not args.dry_run:
            frappe.db.release_savepoint(sp)
    except Exception as e:
        if not args.dry_run:
            frappe.db.rollback_to_savepoint(sp)
        log_error(f"Week {week_name} import failed: {e}; rolled back")
        raise
```

Required CLI:
```
python scripts/s234_seed_delivery_schedule.py \
  --csv data/operational/delivery_cadence_2026-05-04.csv \
  --week-start 2026-05-04 \
  --dry-run         # default=True: print intended changes, write nothing
  # to actually write, pass --no-dry-run (or --dry-run=false depending on argparse setup)
```

CSV format (10 columns; one row per store-delivery-day combo):
```csv
store,delivery_type,day_of_week,active
ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC,COLD,Mon,1
ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC,COLD,Thu,1
ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC,DRY,Tue,1
...
```

Idempotency rule: if a week with `week_start = X` already exists, the seeder UPDATES its entries to match the CSV (deletes orphans, inserts new, leaves identical rows). Re-running produces no diff.

Logging rule: every action emits to `tmp/s234/seed_dry_run_<timestamp>.log` with `INTENT` (dry-run) or `EXECUTED` (real run).

**C-T3** Author `scripts/s234_publish_next_week_cron.py` — weekly cron that copies last-known cadence forward.

```python
# MUST_MODIFY: scripts/s234_publish_next_week_cron.py (NEW)
# MUST_CONTAIN: "DISABLED_BY_DEFAULT = True"
# MUST_CONTAIN: "next_monday = add_days"
```

Behavior:
- Find latest `BEI Delivery Schedule Week` → `latest_week_start`
- If `latest_week_start >= next_monday(today)`: nothing to do, exit 0
- Else: clone all `BEI Delivery Schedule Entry` rows from `latest_week_start` into a new Week with `week_start = next_monday(today)`
- Default mode: print intended action + exit (DISABLED). Active mode: pass `--enable` flag. Cron registration (Frappe scheduler hooks) is NOT added to `hooks.py` in this sprint — only when logistics signs off on cadence and Sam approves the cron live-launch in a follow-up sprint.

**C-T4** Author empty CSV template at `data/operational/delivery_cadence_template.csv`:
```csv
store,delivery_type,day_of_week,active
# Fill one row per (store, delivery_type, day_of_week) combination.
# delivery_type: COLD or DRY
# day_of_week: Mon, Tue, Wed, Thu, Fri, Sat, Sun
# active: 1 to enable, 0 to disable
# Example:
# ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC,COLD,Mon,1
```

**C-T5** Test the seeder in dry-run mode against the template (should be a no-op):
```bash
python scripts/s234_seed_delivery_schedule.py \
  --csv data/operational/delivery_cadence_template.csv \
  --week-start 2026-05-04 \
  --dry-run
# Expected output: "No changes — template has 0 data rows."
```

Test against a 1-row trial CSV:
```bash
cat > tmp/s234/trial_cadence.csv <<'CSV'
store,delivery_type,day_of_week,active
ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC,COLD,Mon,1
CSV
python scripts/s234_seed_delivery_schedule.py \
  --csv tmp/s234/trial_cadence.csv \
  --week-start 2026-05-04 \
  --dry-run 2>&1 | tee tmp/s234/seed_dry_run_trial.log
# Expected: prints intended INSERT for 1 entry, exits 0, writes nothing
```

**C-T6** Document the operational handoff. Write `docs/operations/delivery-schedule-runbook.md`:
- Who owns the cadence data (logistics)
- What CSV columns mean
- Dry-run-first protocol
- Cron activation procedure (when ready)
- Rollback procedure (`disabled=1` on Week record; entries inherit)

**C-T7** (v2 audit fix W4 — consolidated commit + single PR for all 3 lanes) Commit Lane C, then push the branch + open ONE PR covering Lanes A+B+C. This is the FIRST push of the branch.

```bash
git add scripts/s234_seed_delivery_schedule.py scripts/s234_publish_next_week_cron.py
git add data/operational/delivery_cadence_template.csv  # may need git add -f if data/ is gitignored
git add docs/operations/delivery-schedule-runbook.md
git add -f output/s234/verification/doctype_schema.json  # output/ is gitignored
git commit -m "feat(S234-C): delivery schedule seeder + cron skeleton + runbook (DISABLED until logistics signs off)"

# First push of the branch (Lane A + B + C all committed locally)
git push -u origin s234-ordering-schedule-defaults-and-data

# Open the consolidated PR
GH_TOKEN="" gh pr create --base production --head s234-ordering-schedule-defaults-and-data \
  --title "fix(S234): synthesize ordering-schedule defaults + repoint smoke + data foundation" \
  --body-file output/s234/PR_BODY.md
```

PR body includes per-lane summary, behavioral impact (47 default-stores get synthesized dates; 2 schedule-published stores unchanged; cron DISABLED until logistics signoff), risk assessment, audit reference, and per-task checklist (✅/❌ per task in this plan).

**Phase C verification script (v2 audit fix W6 — extended checks):**
```bash
cat > tmp/s234/verify_phase_c.py <<'PY'
import os, sys
errs = []
required = [
    "scripts/s234_seed_delivery_schedule.py",
    "scripts/s234_publish_next_week_cron.py",
    "data/operational/delivery_cadence_template.csv",
    "docs/operations/delivery-schedule-runbook.md",
    "output/s234/verification/doctype_schema.json",
]
for f in required:
    if not os.path.exists(f): errs.append(f"MISSING: {f}")
seeder = open("scripts/s234_seed_delivery_schedule.py").read()
for must_have in ["argparse", "--dry-run", "--week-start", "BEI Delivery Schedule Week"]:
    if must_have not in seeder: errs.append(f"seeder MUST_CONTAIN: {must_have}")
# v2 audit fix W6: argparse default=True for --dry-run
if "default=True" not in seeder and "default=\"true\"" not in seeder.lower():
    errs.append("seeder argparse: --dry-run must default to True (safe-by-default)")
# v2 audit fix W7: DM-2 savepoint protection on multi-doc write
if "frappe.db.savepoint" not in seeder:
    errs.append("seeder DM-2 violation: must wrap Week+Entries write in frappe.db.savepoint() with rollback on error")

cron = open("scripts/s234_publish_next_week_cron.py").read()
# v2 audit fix W6: both declared MUST_CONTAINs
for must_have in ["DISABLED_BY_DEFAULT = True", "next_monday = add_days"]:
    if must_have not in cron: errs.append(f"cron MUST_CONTAIN: {must_have}")
hooks = open("hrms/hooks.py").read() if os.path.exists("hrms/hooks.py") else ""
if "s234_publish_next_week_cron" in hooks:
    errs.append("REGRESSION: cron registered in hooks.py — must NOT be active until logistics signoff")
print("PASS" if not errs else "\n".join(errs))
sys.exit(0 if not errs else 1)
PY
python tmp/s234/verify_phase_c.py
```

### Phase D — Closeout (10 units)

**D-T1** Wait for PR merge + deploy. Run smoke 3 consecutive cycles:
```bash
for i in 1 2 3; do
  echo "=== cycle $i ==="
  curl -sS "https://my.bebang.ph/api/ordering?action=validate_order_schedule&store=ARANETA%20GATEWAY%20-%20TUNGSTEN%20CAPITAL%20HOLDINGS%20OPC" \
    -H "Cookie: sid=$SID" | python -c "
import sys, json
d = json.load(sys.stdin); data = d.get('data', {})
c, dr = data.get('next_cold_delivery'), data.get('next_dry_delivery')
print(f'cycle {sys.argv[1]}: cold={c} dry={dr}')
assert c and dr, 'FAIL'
" $i
  sleep 10
done | tee output/l3/s234/smoke_3_cycle_log.txt
```

**D-T2** Probe Estancia post-deploy:
```bash
curl -sS "https://my.bebang.ph/api/ordering?action=validate_order_schedule&store=Estancia" \
  -H "Cookie: sid=$SID" | tee output/l3/s234/api_probe_estancia_after.json | jq .data
# Expected: next_cold_delivery and next_dry_delivery are non-null ISO date strings;
# schedule_source = "default"
```

**D-T2.5** (v2 audit fix CRIT-3) Write `state_after.json` — full 49-store post-deploy probe snapshot.

```bash
cat > tmp/s234/probe_all_49_after.py <<'PY'
import os, json, requests
PWD = os.environ["FRAPPE_ADMIN_PASSWORD"]
s = requests.Session()
s.post("https://hq.bebang.ph/api/method/login", data={"usr":"sam@bebang.ph","pwd":PWD})
import sys
fixture_path = "F:/Dropbox/Projects/bei-tasks-s234-ordering-schedule-defaults-and-data/tests/e2e/fixtures/s204_all_stores.json"
fixture = json.load(open(fixture_path))
out = []
for entry in fixture:
    store = entry["store"]
    r = s.get("https://my.bebang.ph/api/ordering",
              params={"action":"validate_order_schedule","store":store})
    out.append({
        "store": store,
        "status": r.status_code,
        "next_cold_delivery": r.json().get("data", {}).get("next_cold_delivery"),
        "next_dry_delivery": r.json().get("data", {}).get("next_dry_delivery"),
        "schedule_source": r.json().get("data", {}).get("schedule_source"),
    })
print(json.dumps({"probed_at": "<UTC>", "stores": out}, indent=2))
PY
FRAPPE_ADMIN_PASSWORD=$(C:/Users/Sam/bin/doppler.exe secrets get FRAPPE_ADMIN_PASSWORD --plain --project bei-erp --config dev) \
  python tmp/s234/probe_all_49_after.py > output/s234/verification/state_after.json
# Expected: 47 of 49 with schedule_source="default" and ISO date strings;
# 2 (ARANETA, AYALA UP TOWN CENTER) with schedule_source="current" or "fallback_last_week"
```

**D-T2.6** (v2 audit fix CRIT-3) Write `state_verification.json` — read-only attestation.

```bash
cat > output/l3/s234/state_verification.json <<JSON
{
  "sprint": "S234",
  "sweep_type": "read-only",
  "mutations": [],
  "attested_by": "agent",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "lanes": {
    "A": "code-only (hrms/api/store.py defaults dict)",
    "B": "doc-only (.claude/skills/merge-bei-erp/SKILL.md smoke probe)",
    "C": "scripts-only (no production seeder execution; cron DISABLED)"
  },
  "production_writes": "none",
  "canonical_postcheck": "see canonical_postcheck.log",
  "rollback_plan": "git revert + redeploy; no data restore needed"
}
JSON
```

**D-T3** Run canonical postcheck:
```bash
python scripts/verify_canonical_structure.py 2>&1 | tee output/s234/verification/canonical_postcheck.log
# Expected: identical to preflight (or +0 new violations)
```

**D-T4** Update plan YAML status:
```yaml
status: COMPLETED
completed_date: 2026-05-XX
execution_summary: |
  Lane A: defaults dict synthesizes next_cold_delivery + next_dry_delivery from
  day offsets. Smoke probe Estancia now returns ISO date strings (was null for
  20+ cycles). schedule_source="default" tag preserved.

  Lane B: smoke test repointed from Estancia (no schedule data) to ARANETA
  GATEWAY (real schedule). Smoke now actually canaries the schedule pipeline.

  Lane C: scripts/s234_seed_delivery_schedule.py + scripts/s234_publish_next_week_cron.py
  + delivery_cadence_template.csv + delivery-schedule-runbook.md committed.
  Cron DISABLED pending logistics cadence signoff.

  Canonical: 0 violations introduced. Sweep delta: v17 49-store sweep optional
  (defaults change is read-path; v15/v16 already proved happy chain works
  regardless of schedule data).
```

**D-T5** Update `SPRINT_REGISTRY.md` row to COMPLETED:
```bash
git add docs/plans/SPRINT_REGISTRY.md docs/plans/2026-05-03-sprint-234-ordering-schedule-defaults-and-data.md
git commit -m "chore(S234): registry + plan COMPLETED"
git push  # may be blocked by merged-branch hook → create new branch chore/s234-closeout
```

**D-T6** Write `output/s234/SUMMARY.md`:
- One paragraph: what shipped, what's deferred (Lane C cron activation), what's next (logistics cadence handoff).
- Include Lane A before/after probe samples.
- Include 3-cycle smoke PASS log.
- List PR numbers.

**D-T7** Worktree closeout:
```bash
cd "$WT" && git status --short  # must be clean
cd F:/Dropbox/Projects/BEI-ERP
git worktree remove F:/Dropbox/Projects/BEI-ERP-s234-ordering-schedule-defaults-and-data
```

**Phase D verification script (v2: extended for state files):**
```bash
cat > tmp/s234/verify_phase_d.py <<'PY'
import os, sys, json, re
errs = []
# Smoke 3 PASS
log = open("output/l3/s234/smoke_3_cycle_log.txt").read()
if log.count("FAIL") > 0: errs.append("smoke 3-cycle has FAIL")
if log.count("cold=") < 3: errs.append("smoke didn't run 3 cycles")
# Estancia post-deploy
estancia = json.load(open("output/l3/s234/api_probe_estancia_after.json"))
data = estancia.get("data", {})
if not data.get("next_cold_delivery") or not data.get("next_dry_delivery"):
    errs.append("Estancia still has null after deploy")
# v2 audit fix CRIT-3: state files written
if not os.path.exists("output/s234/verification/state_after.json"):
    errs.append("state_after.json missing (D-T2.5 not run)")
if not os.path.exists("output/l3/s234/state_verification.json"):
    errs.append("state_verification.json missing (D-T2.6 not run)")
# Plan YAML COMPLETED
plan = open("docs/plans/2026-05-03-sprint-234-ordering-schedule-defaults-and-data.md").read()
if "status: COMPLETED" not in plan: errs.append("plan YAML not flipped to COMPLETED")
# Registry COMPLETED
reg = open("docs/plans/SPRINT_REGISTRY.md").read()
if not re.search(r"`S234`.*COMPLETED", reg, re.DOTALL): errs.append("registry not updated to COMPLETED")
# Summary written
if not os.path.exists("output/s234/SUMMARY.md"): errs.append("output/s234/SUMMARY.md missing")
print("PASS" if not errs else "\n".join(errs))
sys.exit(0 if not errs else 1)
PY
python tmp/s234/verify_phase_d.py
```

## Autonomous Execution Contract

- completion_condition:
  - Lane A code merged + deployed; Estancia probe returns ISO dates; ARANETA probe returns ISO dates with `schedule_source` ∈ {"current", "fallback_last_week"}
  - Lane B smoke repointed; 3 consecutive `/merge-bei-erp` cycles PASS
  - Lane C seeder + cron + template + runbook committed; cron registered DISABLED
  - Canonical postcheck: 0 new violations
  - Plan YAML `status: COMPLETED`; sprint registry row updated
  - PRs created (one or two — agent's choice based on diff coupling); user merges
  - Worktree removed
- stop_only_for:
  - Canonical preflight prints `[VIOLATION]`
  - Estancia probe returns the SAME null after deploy (deploy didn't pick up the change)
  - ARANETA probe regresses (schedule pipeline genuinely broken — file [BUG], halt)
  - Logistics provides cadence CSV before sprint ends — pause Lane C cron-DISABLED policy and ask Sam if cron should ship enabled
  - Any DocType `BEI Delivery Schedule Week` or `BEI Delivery Schedule Entry` field added/renamed/removed by another in-flight sprint that conflicts with seeder schema assumptions
- continue_without_pause_through:
  - audit → execute (Phase A → B → C) → PR creation → smoke validation → closeout
- blocker_policy:
  - programmatic → fix and continue
  - PR review feedback → apply suggested fix on same branch, push, wait for re-review
  - repeated technical failure ×3 → grounded research, then continue
  - canonical drift → pause and present to Sam
- signoff_authority: `single-owner` (Sam)
- canonical_closeout_artifacts:
  - `output/s234/SUMMARY.md`
  - `output/s234/verification/state_before.json`
  - `output/s234/verification/api_probe_after_fix.json`
  - `output/s234/verification/smoke_repoint_proof.txt`
  - `output/s234/verification/canonical_postcheck.log`
  - `output/l3/s234/smoke_3_cycle_log.txt`
  - `output/l3/s234/api_probe_estancia_after.json`
  - `docs/plans/2026-05-03-sprint-234-ordering-schedule-defaults-and-data.md` (status COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (S234 row → COMPLETED)

## Zero-Skip Enforcement

Every task MUST be implemented. No exceptions.

If a task cannot be completed (e.g., DocType missing, deploy fails 3×, canonical preflight blocks), the agent STOPS and asks Sam. Forbidden agent behaviors:
- Skipping a task silently
- Marking partial work as "done" (e.g., commit Lane A but skip Lane B "for next sprint")
- Replacing a task with a simpler version without user approval
- Saying "deferred to next sprint" without Sam's explicit OK
- Combining tasks and dropping features in the merge
- Implementing happy path only, skipping verification scripts
- Marking COMPLETED while verification scripts say FAIL

**PR description gate:** every PR description must include a task-by-task checklist (✅ / ❌ / explanation). Unchecked items need an explanation. Sam rejects PRs with unexplained gaps.

**Phase verification scripts:** every phase has a verification script (defined inline above) that the agent MUST run before marking the phase complete. The script reads from filesystem (git diff, grep, file existence) — not from agent self-report. If the script returns non-zero, the agent MUST fix the underlying issue before proceeding to the next phase.

## Status Reconciliation Contract

When status changes (any phase complete, blocker resolved, plan COMPLETED), update in the SAME work unit:
1. `output/s234/SUMMARY.md`
2. `docs/plans/2026-05-03-sprint-234-ordering-schedule-defaults-and-data.md` YAML frontmatter
3. `docs/plans/SPRINT_REGISTRY.md` S234 row
4. PR description (re-edit if status changed mid-flight)

## Signoff Model

- mode: `single-owner`
- approver_of_record: Sam (CEO)
- signoff_artifact: `output/s234/SUMMARY.md`
- note: This is a 3-lane plan. Lane A and Lane B can ship in one PR (small, same domain). Lane C may ship in the same PR or a separate one — agent's choice based on diff size. User merges all PRs. No department signoff required.

## Execution Workflow

- Test Python changes locally (Lane A): `/local-frappe`
- Deploy changes: `/deploy-frappe` (user-mediated; agent does not self-deploy)
- Full workflow reference: `/agent-kickoff`
- E2E spot-check (optional): `/e2e-test`

## Library Audit (Test Library Discipline)

This sprint touches `_get_next_deliveries` (read-only API helper) and a smoke probe script. **No Page Objects, fixtures, builders, or assertions are added or modified.** The smoke test in `merge-bei-erp/SKILL.md` is a curl command, not a Playwright spec — outside the test library scope.

If the executing agent finds a Playwright spec covering `validate_order_schedule` (none exists today, per grep), it must use the existing `tests/e2e/support/frappeReadback.ts` helpers (which already handle ECONNRESET retries per S232 PR #460).

## Library Contributions

None. This sprint adds only:
- 1 backend Python diff (`hrms/api/store.py`)
- 1 markdown smoke probe edit (`merge-bei-erp/SKILL.md`)
- 2 new operational scripts (`scripts/s234_*.py`)
- 1 CSV template (`data/operational/delivery_cadence_template.csv`)
- 1 runbook (`docs/operations/delivery-schedule-runbook.md`)

No `tests/e2e/` changes.

## Phase Budget Contract (v2)

- Phase 0: 6 units (was 5; +1 for 0-T6 SHA capture)
- Phase A: 5 units (Lane A diff is the same; deferred-PR change is 0-cost)
- Phase B: 3 units
- Phase C: 32 units (was 30; +2 for DM-2 savepoint logic)
- Phase D: 12 units (was 10; +2 for D-T2.5/D-T2.6 state file writers)
- **Total: 58 units** (was 53; under 80-unit S089 ceiling)
- Phase C breakdown to stay under 12-unit micro-threshold:
  - C-T1 schema probe: 3
  - C-T2 seeder: 12 (intentionally allowed; one cohesive script)
  - C-T3 cron: 8
  - C-T4 template + C-T5 trial test + C-T6 runbook + C-T7 commit: 7
- Phase C hard limit: 15 units per sub-task (none exceed)

## Anti-Rewind / Concurrent-Run Protection Contract

- ownership_matrix:
  - exclusive: `hrms/api/store.py:1295-1303` (defaults dict only)
  - exclusive: `.claude/skills/merge-bei-erp/SKILL.md` (smoke probe block)
  - exclusive: `scripts/s234_*.py` (new files)
  - exclusive: `data/operational/delivery_cadence_template.csv` (new file)
  - exclusive: `docs/operations/delivery-schedule-runbook.md` (new file)
- protected_surfaces:
  - `hrms/api/store.py` outside lines 1295-1303 — DO NOT MODIFY (esp. the `entries` branch line 1342+)
  - `validate_order_schedule` whitelist endpoint signature — UNCHANGED
  - `BEI Delivery Schedule Week`/`Entry` DocType definitions — UNCHANGED (read-only consumer in this plan)
  - `cold_interval`/`dry_interval` semantics in `_compose_signal_modifiers` — UNCHANGED (recommendation engine relies on these)
  - All canonical Company/Warehouse/Customer master data — UNCHANGED
- remote_truth_baseline:
  - hrms `origin/production` head SHA at sprint start: TBD (record in Phase 0)
  - bei-tasks `origin/main` head SHA: TBD (record in Phase 0; this sprint touches NO bei-tasks files but baseline kept for parity)
  - Live evidence: `output/s234/verification/state_before.json` (Estancia + ARANETA pre-fix probes)
- pretouch_backup:
  - hrms/api/store.py: `cp hrms/api/store.py tmp/s234/store.py.before` before Phase A edit
- supersession_map:
  - Replaces nothing in production. The defaults dict has been null-default since the function was written. This is the FIRST fix.
- touch_preservation:
  - All 5 file mutations declared above. Cleanup allowed at closeout only after merge.

## Ground-Truth Lock

- evidence_sources:
  - `hrms/api/store.py:1282-1407` — function definition (`_get_next_deliveries`)
  - `hrms/api/store.py:1297-1303` — defaults dict (target of Lane A fix)
  - `.claude/skills/merge-bei-erp/SKILL.md:106` — smoke probe URL (target of Lane B fix)
  - `output/s234/verification/state_before.json` — Phase 0 Estancia + ARANETA probe (proves Estancia=null, ARANETA=ISO dates)
  - `output/s234/verification/api_probe_after_fix.json` — Phase A Estancia + ARANETA probe (proves Estancia=ISO dates after fix)
  - Earlier-agent investigation: `tmp/ordering-schedule-trace/FINDINGS.md` (forensic trace of root cause)
- count_method:
  - "47 of 49 stores hit defaults" — derived from: 49 fixture stores in `tests/e2e/fixtures/s204_all_stores.json` MINUS 2 stores (ARANETA GATEWAY, AYALA UP TOWN CENTER) confirmed via `frappe.db.sql("SELECT DISTINCT store FROM tabBEI Delivery Schedule Entry")`
  - "Latest published week 2026-04-06" — `frappe.db.get_value("BEI Delivery Schedule Week", {}, "name", order_by="week_start desc")` → BEI-SCHED-2026-00003
- authoritative_sections:
  - Phase 0–D task tables are execution truth
  - Design Rationale section is the cold-start primer
  - L3 Workflow Scenarios are the success conditions
  - Audit history (if any) is traceability only
- normalization_required:
  - Any change to phase ordering, MUST_MODIFY targets, or evidence file paths → update authoritative sections in the SAME edit

## Surface Ownership Matrix (per S087)

| Surface | Owner | Allowed mutations |
|---|---|---|
| `hrms/api/store.py:1295-1303` | S234 | Lane A only |
| `hrms/api/store.py` outside 1295-1303 | NOT S234 | DO NOT MODIFY |
| `.claude/skills/merge-bei-erp/SKILL.md:106-117` | S234 | Lane B only |
| `.claude/skills/merge-bei-erp/SKILL.md` outside 106-117 | NOT S234 | DO NOT MODIFY |
| `scripts/s234_*.py` | S234 | NEW files only |
| `data/operational/delivery_cadence_template.csv` | S234 | NEW file only |
| `docs/operations/delivery-schedule-runbook.md` | S234 | NEW file only |
| `tabBEI Delivery Schedule Week` | S234 (read in this sprint; write only via seeder dry-run) | NO production writes in Phase 0–D |
| `tabBEI Delivery Schedule Entry` | S234 (read only) | NO production writes |
| Canonical Company/Warehouse/Customer | NOT S234 | NO mutations |

## Sprint Registry Row (Evidence of Lock)

```
| `S234` | Sprint 234 | `s234-ordering-schedule-defaults-and-data` (hrms backend `_get_next_deliveries` + `.claude/skills/merge-bei-erp/SKILL.md` smoke fix + new `scripts/s234_*.py` for data foundation) | TBD | PLANNED 2026-05-03 — Ordering Schedule Defaults Defense + Smoke Test Repoint + Data Foundation. | `docs/plans/2026-05-03-sprint-234-ordering-schedule-defaults-and-data.md` |
```

This row was added to `docs/plans/SPRINT_REGISTRY.md` BEFORE this plan body was written. Cross-checked via `git branch -a | grep -i s234` — no remote branches collide. Cross-checked via `ls docs/plans/ | grep sprint-234` — no plan files collide.

## Execution Authority

This sprint is intended for autonomous end-to-end execution by a single agent in a single session.

Do not stop for progress-only updates.

Only pause for items listed in the `Autonomous Execution Contract` `stop_only_for` section.

Lane A + Lane B may ship in one PR. Lane C may ship in the same PR or a separate one (agent's discretion based on diff coupling).
