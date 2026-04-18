---
sprint: S206
title: Reliever Labor Cost-Sharing Engine (Paired JE, No VAT/EWT)
branch: s206-reliever-allocation-engine
base: production
status: DEPLOYED_PENDING_L3_AND_FINANCE_SIGNOFF
plan_version: v2
completed_date: 2026-04-18
backend_pr: https://github.com/Bebang-Enterprise-Inc/hrms/pull/615
l3_result: pending (fresh session post-deploy per S092 corrupt-success rule)
execution_summary: |
  Phases 0-5 shipped via PR #615. Phase 6 unit tests written; L3 scenarios
  run in fresh session after deploy + TP Policy signoff + account seeding.
plan_v1_reason_superseded: |
  v1 used multi-company single JE (invalid in ERPNext) + Sales Invoice pattern would
  trigger VAT/EWT per service-transaction treatment. Audit surfaced 10 architectural
  blockers. Sam 2026-04-18 confirmed cost-sharing (no VAT/EWT) is the correct pattern
  and paired JEs with Frappe native `inter_company_journal_entry_reference` is the
  correct mechanism.
planned_date: 2026-04-17
revised_date: 2026-04-18
planned_by: Claude (BEI-ERP)
owner: Sam Karazi (CEO)
depends_on: [S201]
followed_by: []
estimated_units: 54
primary_repo: hrms
touches_frontend: false
l3_required: true
hard_deadline: 2026-05-15
completion_condition: |
  - docs/compliance/s206-transfer-pricing-policy.md exists and committed (MANDATORY)
  - hrms/utils/device_store_bridge.py normalizes DEVICE_TO_STORE names to branch_company_map keys
  - hrms/utils/punch_allocation.py uses correct Frappe fields (time, device_id — NOT event_time/device_sn)
  - hrms/utils/labor_allocation.py produces PAIRED JEs via Frappe native inter_company_journal_entry_reference
  - hrms/hr/doctype/bei_labor_allocation_log DocType for idempotency (unique on year+month+employee)
  - hrms/api/labor_allocation.py preview + post with S206_APPLY=1 gate + Sentry context
  - All JEs satisfy DM-1: party_type=Company on intercompany rows; party_type=Employee on Salaries rows
  - All JEs satisfy DM-6: user_remark cites cost-sharing policy; reference fields; cost_center
  - Intercompany account seeder is on_demand (NOT in patches.txt) — avoids dry-run-marked-DONE trap
  - Production Apply Runbook documents `docker exec -e S206_APPLY=1` explicitly
  - L3: April 2026 dry-run reviewed; apply posts paired JEs cleanly for 3+ store Companies
  - Plan YAML status -> COMPLETED and SPRINT_REGISTRY.md updated
stop_only_for:
  - Missing intercompany accounts on >10 Companies requires Sam/Finance COA decision
  - Finance declines Transfer Pricing Policy signoff (Phase 0 HARD BLOCKER)
  - Punch data gap > 10% of any employee's payroll period (insufficient basis)
  - Destructive apply requires Sam approval (always dry-run first)
  - Merge conflict on production during rebase
---

# Sprint S206 v2 — Reliever Labor Cost-Sharing Engine

## Audit response summary (v1 -> v2)

v1 plan failed audit with 10 architectural CRITICAL blockers. v2 addresses all:

| v1 blocker | v1 (wrong) | v2 (correct) |
|---|---|---|
| B1 multi-company single JE invalid | Home+covered rows in one JE | **Paired JEs** via `inter_company_journal_entry_reference` (Frappe native) |
| B2 wrong party_type | Employee on all rows | Company on Due From/To; Employee on Salaries only |
| B3 no idempotency | None | New `BEI Labor Allocation Log` DocType, unique on (year, month, employee) |
| B4 missing TPD | None | `docs/compliance/s206-transfer-pricing-policy.md` drafted; Finance signoff gate |
| B5 docker env not propagated | Assumed local shell | Production Apply Runbook with `docker exec -e S206_APPLY=1` |
| B6 patches.txt dry-run trap | In patches.txt | **on_demand script**, always-apply semantics |
| B7 device->branch mismatch | Assumed direct | New `hrms/utils/device_store_bridge.py` normalizes names |
| B8 wrong Checkin fields | event_time, device_sn | **time, device_id** (actual Frappe fields) |
| B9 wrong default-account API | `frappe.defaults.get_default` | Query `tabCompany.default_payroll_payable_account` / COA template |
| B10 no BEI JE precedent | Invented new pattern | Mirror S175 intercompany accounts; paired-JE linking is Frappe native |

**Tax savings via cost-sharing (not Sales Invoice):** ~PHP 1.35M/year in avoided VAT + EWT.

## Background

S201 Option X kept `Employee.company` on the legal employer. Per-store internal billing must flow via monthly inter-Company **cost-sharing reclassification** (NOT service transaction — see TP policy).

Without S206, per-store P&L is fiction. Relievers who cover multiple stores need fair attribution. Data starts 2026-04-01. Deadline **2026-05-15** (first half-month cutoff where April becomes material).

## Locked Decisions

| ID | Decision | Source |
|---|---|---|
| LD-1 | Employee.company NOT touched by S206 | S201 Option X |
| LD-2 | Internal cost allocation (NOT service). Zero VAT, zero EWT. | Sam 2026-04-18 |
| LD-3 | Paired JEs via Frappe native inter_company_journal_entry_reference | Sam 2026-04-18 |
| LD-4 | TP Policy drafted by Claude, Finance (Denise) signs off | Sam 2026-04-18 |
| LD-5 | Non-store billers (roving/AS/RM/HO/Commissary producers) excluded | S201 LD-2/LD-3 |
| LD-6 | Data starts 2026-04-01; no retro before | S201 LD-6 |
| LD-7 | Deadline 2026-05-15 | S201 B15 |
| LD-8 | Allocation unit = shift-share (IN/OUT pair counts) | Plan default |
| LD-9 | Apply gated by docker exec -e S206_APPLY=1 documented in runbook | Audit B5 |
| LD-10 | Intercompany balance settlement = quarterly non-cash JE (no EWT trigger) | TP policy S5.2 |

## Requirements Regression Checklist

Before COMPLETED, executing agent MUST answer YES:

- [ ] `docs/compliance/s206-transfer-pricing-policy.md` exists, committed?
- [ ] TP Policy signed off by Finance (signature section filled) before first apply?
- [ ] Every JE pair uses `voucher_type='Inter Company Journal Entry'` + `inter_company_journal_entry_reference`?
- [ ] `party_type='Company'` + `party=<counterparty>` on Due From/To rows (DM-1)?
- [ ] `party_type='Employee'` + `party=slip.employee` on Salaries rows (DM-1)?
- [ ] Each JE's `user_remark` cites S206 cost-sharing + slip + period + share (DM-6)?
- [ ] Each row has `cost_center` set to Company default (DM-6)?
- [ ] Each JE has `reference_type='Salary Slip'` + `reference_name` (DM-6)?
- [ ] Every `@frappe.whitelist()` calls `set_backend_observability_context()` (DM-7)?
- [ ] `BEI Labor Allocation Log` per (year, month, employee) — re-run = 0 new JEs?
- [ ] `is_non_store_billing` employees skipped?
- [ ] Commissary producers (dept=Commissary + branch=SHAW COMMISSARY - PRODUCTION) skipped?
- [ ] Zero-punches / all-home-store / zero-gross employees skipped (logged, not errored)?
- [ ] Per-slip savepoint — one bad slip doesn't kill the batch (DM-2)?
- [ ] Query uses `tabEmployee Checkin.time` + `device_id` (NOT event_time/device_sn)?
- [ ] `device_store_bridge` resolves every DEVICE_TO_STORE value to a valid Company?
- [ ] Production Apply Runbook present with `docker exec -e S206_APPLY=1` syntax?
- [ ] Intercompany account seeder is `on_demand`, NOT in patches.txt?
- [ ] Plan YAML status=COMPLETED and SPRINT_REGISTRY.md row updated?

## Design Rationale (Cold-Start)

### Why cost-sharing JE, not Sales Invoice?

- **SI** triggers Section 108 NIRC Output VAT (12%) + Input VAT + EWT 2% (RR 2-98). For ~PHP 810K/month reliever load = ~PHP 1.35M/year avoidable tax.
- **Cost-sharing JE** per BIR RR 2-2013 Section 4(B): cost recharge at-cost = NOT a service. Zero-margin recharge between commonly-controlled entities is explicitly permitted. No VAT. No EWT.
- Per-store P&L reflects consumed labor. Books stay clean.

Source: `docs/compliance/s206-transfer-pricing-policy.md` Sections 2 + 6.

### Why paired JEs via Frappe native intercompany linking?

- ERPNext Journal Entry has single `company` field — one JE books to one Company's books.
- Frappe has built-in support: `voucher_type='Inter Company Journal Entry'` + `inter_company_journal_entry_reference` cross-links two JEs.
- Both JEs auto-validate matching Due From/Due To accounts. No invented pattern.

### Why BEI Labor Allocation Log DocType for idempotency?

- v1 had no duplicate-JE guard. Second call = double-booked costs.
- Options considered:
  - Salary Slip custom field — ties idempotency to Slip, messy on Slip amendment.
  - SQL unique constraint on JE user_remark — fragile string match.
  - **BEI Labor Allocation Log** ✓ — clean, queryable, standard Frappe.
- Unique constraint on (year, month, employee).

### Why on_demand script (not patches.txt)?

- `patches.txt` runs patches ONCE per environment. A dry-run patch on first `bench migrate` gets marked DONE in `__PatchLog`, NEVER re-runs. Apply is unreachable.
- On-demand scripts live in `hrms/on_demand/` and run only when explicitly invoked: `bench execute hrms.on_demand.<module>.execute`.
- Always-apply semantics (no dry-run gate needed — invoker decides).

### Why `docker exec -e` runbook?

- S201 had same gap. `S206_APPLY=1 bench ...` run from host shell doesn't propagate env into the container process.
- Explicit `docker exec -e S206_APPLY=1 $CONTAINER bench ...` is mandatory on production.

### Known limitations (cold-start must know)

- **Punch gaps:** <90% complete punches → allocation SKIPPED + logged. Finance handles manually.
- **Amended Slips:** post-allocation amendments leave JEs as-is. Manual reversal (v2 enhancement deferred to S207).
- **Part-time employees:** shift-share counts IN/OUT pairs equally regardless of shift length. Acceptable for BEI (~80% full-time).

## Phase 0 — Preflight + TP Policy (8u)

- [ ] P0-T1 **CONFIRM TP Policy** at `docs/compliance/s206-transfer-pricing-policy.md`. Drafted in same commit as v2 plan revision. Finance signs off (Sam + Denise signatures) BEFORE first `post_monthly_allocation` apply. HARD BLOCKER.
  - MUST_MODIFY: `docs/compliance/s206-transfer-pricing-policy.md`
  - MUST_CONTAIN: `Zero-margin`, `RR 2-2013`, `cost-sharing arrangement`, `No VAT`, `No EWT`

- [ ] P0-T2 **Company COA audit** — query live Frappe for each store Company + BEI parent + BKI. For each: verify `Salaries Expense` account + `Due From Group Entities - <abbr>` + `Due To Group Entities - <abbr>` + default `cost_center`. Output to `output/s206/diagnostics/company_coa_audit_<timestamp>.json`.
  - MUST_MODIFY: `output/s206/diagnostics/company_coa_audit_*.json`
  - MUST_CONTAIN: entries for all 49 store Companies + parent + BKI

- [ ] P0-T3 **Gap report** — missing accounts flagged to `output/s206/diagnostics/MISSING_ACCOUNTS.md`. If >10 Companies have gaps → HARD BLOCKER.

## Phase 1 — device_store_bridge + punch_allocation (12u)

- [ ] P1-T1 **device_store_bridge.py** — new file:
  - `DEVICE_STORE_BRIDGE: dict[str, str]` — normalizes DEVICE_TO_STORE values to branch_company_map keys.
  - e.g. `'BGC CAPITAL HOUSE' -> 'CAPITAL HOUSE'`, `'GREENHILLS' -> 'ORTIGAS GREENHILLS'`.
  - `resolve_device_company(device_sn) -> str` wraps DEVICE_TO_STORE + bridge + `resolve_branch_to_company`. Raises `UnknownDeviceCompany` on miss.
  - MUST_MODIFY: `hrms/utils/device_store_bridge.py`
  - MUST_CONTAIN: `DEVICE_STORE_BRIDGE`, `resolve_device_company`, `UnknownDeviceCompany`

- [ ] P1-T2 **punch_allocation.py** — new file:
  - `compute_shift_share(employee, start_date, end_date) -> dict[str, float]` returns normalized `{company: share}`.
  - `_pair_punches(checkins)` pairs IN with next OUT per device.
  - **SQL uses correct fields:** `tabEmployee Checkin.time`, `device_id`, `log_type`, `employee`.
  - Edge cases: zero punches -> `{}`; all-at-one -> `{company: 1.0}`; orphan IN -> 0.5 shift; unknown device -> skip + log.
  - MUST_MODIFY: `hrms/utils/punch_allocation.py`
  - MUST_CONTAIN: `compute_shift_share`, `tabEmployee Checkin`, `time`, `device_id`, `log_type`, `resolve_device_company`

- [ ] P1-T3 **Tests** `hrms/tests/test_s206_punch_allocation.py` — 6+ tests covering bridge, shift-share math, edge cases.
  - MUST_MODIFY: `hrms/tests/test_s206_punch_allocation.py`

## Phase 2 — labor_allocation.py paired-JE generator (14u)

- [ ] P2-T1 **labor_allocation.py** — new file:
  - `allocate_slip(slip_name, dry_run=True) -> dict`
  - `_skip_reason(slip_doc) -> str | None` (non_store_billing / commissary_producer / no_punches / all_home / zero_gross / already_allocated)
  - `_build_paired_jes(slip, shares, home, covered, amount) -> tuple[dict, dict]` — constructs two JE dicts.
  - `_insert_and_link(home_dict, covered_dict) -> tuple[str, str]` — inserts both, sets `inter_company_journal_entry_reference` cross-link, submits both.

- [ ] P2-T2 **Paired JE rules (STRICT DM-1/DM-6):**
  - **Home JE:** `voucher_type='Inter Company Journal Entry'`, `company=<home>`. Rows:
    - CR `Salaries Expense - <home>`, `party_type='Employee'`, `party=slip.employee`, `cost_center=<home default>`, `reference_type='Salary Slip'`, `reference_name=slip.name`
    - DR `Due From Group Entities - <home>`, `party_type='Company'`, `party=<covered>`, `cost_center=<home default>`, reference fields
  - **Covered JE (mirrored):** `company=<covered>`. Rows:
    - DR `Salaries Expense - <covered>`, `party_type='Employee'`, `party=slip.employee`, `cost_center=<covered default>`, reference fields
    - CR `Due To Group Entities - <covered>`, `party_type='Company'`, `party=<home>`, `cost_center=<covered default>`, reference fields
  - `user_remark = f"S206 cost-sharing recharge: {slip.employee} to {covered}, period {slip.start_date}..{slip.end_date}, share={share:.2%}"`

- [ ] P2-T3 **Insertion + pairing:** Insert both drafts. Update `inter_company_journal_entry_reference` cross-links. Submit both. Wrap in per-slip savepoint; rollback + `frappe.log_error` on any failure.

- [ ] P2-T4 **Tests** `hrms/tests/test_s206_labor_allocation.py` — 7+ tests.
  - MUST_MODIFY: `hrms/utils/labor_allocation.py`, `hrms/tests/test_s206_labor_allocation.py`
  - MUST_CONTAIN: `Inter Company Journal Entry`, `inter_company_journal_entry_reference`, `party_type='Company'`, `party_type='Employee'`, `S206 cost-sharing`

## Phase 3 — BEI Labor Allocation Log DocType + API (10u)

- [ ] P3-T1 **New DocType** `hrms/hr/doctype/bei_labor_allocation_log/`:
  - Fields: `year` (Int), `month` (Int), `employee` (Link -> Employee), `period_start` (Date), `period_end` (Date), `home_company` (Link -> Company), `covered_companies` (Small Text), `home_je` (Link -> Journal Entry), `covered_jes_json` (Small Text), `total_allocated` (Currency), `shift_shares_json` (Small Text), `allocated_on` (Datetime), `allocated_by` (Link -> User)
  - Unique index on (year, month, employee) via `bei_labor_allocation_log.json` unique field
  - Permissions: Accounts Manager + CFO + System Manager read+write
  - MUST_MODIFY: `hrms/hr/doctype/bei_labor_allocation_log/bei_labor_allocation_log.json`, `.py`, `__init__.py`

- [ ] P3-T2 **API** `hrms/api/labor_allocation.py`:
  - `preview_monthly_allocation(year, month) -> dict` — whitelisted, dry-run, no DB writes. Starts with `set_backend_observability_context(module='finance', action='preview_monthly_allocation', mutation_type='read')`.
  - `post_monthly_allocation(year, month) -> dict` — whitelisted, gated on `os.environ.get('S206_APPLY')=='1'` OR kwarg `confirm=True`. For each in-scope slip:
    - Check Log for (year, month, employee) — if exists, skip.
    - Else allocate + insert Log row.
    - Per-slip savepoint.
  - Returns `{'applied', 'skipped_idempotent', 'skipped_other', 'errors'}`.
  - Sentry context `module='finance', action='post_monthly_allocation', mutation_type='create'`.

- [ ] P3-T3 **Permissions:** `post` requires Accounts Manager|CFO|System Manager; `preview` additionally allows Accounts User.
  - MUST_MODIFY: `hrms/api/labor_allocation.py`
  - MUST_CONTAIN: `@frappe.whitelist()`, `set_backend_observability_context`, `S206_APPLY`, `BEI Labor Allocation Log`, `savepoint`

## Phase 4 — On-demand account seeder (5u)

- [ ] P4-T1 **on_demand script** `hrms/on_demand/__init__.py` + `hrms/on_demand/s206_seed_intercompany_accounts.py`:
  - Always-apply (no dry-run gate).
  - For each Company where `entity_category='Store'` OR `name IN ['BEBANG ENTERPRISE INC.', 'BEBANG KITCHEN INC.']`:
    - INSERT IGNORE `2104200 - DUE TO GROUP ENTITIES - <abbr>` under Current Liabilities, `account_type='Payable'`
    - INSERT IGNORE `1104200 - DUE FROM GROUP ENTITIES - <abbr>` under Current Assets, `account_type='Receivable'`
  - Savepoint + rollback on partial failure + `frappe.log_error` (DM-7).
  - Emit `output/s206/diagnostics/intercompany_seed_report_<timestamp>.json`.
  - MUST_MODIFY: `hrms/on_demand/s206_seed_intercompany_accounts.py`
  - MUST_CONTAIN: `frappe.db.savepoint`, `frappe.log_error`, `DUE TO GROUP ENTITIES`, `DUE FROM GROUP ENTITIES`, `account_type`

- [ ] P4-T2 **NOT in patches.txt.** Documented in module docstring: "run via `bench execute hrms.on_demand.s206_seed_intercompany_accounts.execute` manually, once per environment."

## Phase 5 — Monthly scheduler (4u)

- [ ] P5-T1 **Scheduler hook** in `hrms/hooks.py`:
```python
scheduler_events = {
    "cron": {
        # S206 — first of each month at 06:00 PHT (22:00 UTC prior day)
        # preview-only; emails Sam + Denise the prior-month report.
        "0 22 1 * *": [
            "hrms.api.labor_allocation.preview_monthly_allocation_scheduled",
        ],
    },
}
```
- [ ] P5-T2 **Wrapper** `preview_monthly_allocation_scheduled()`:
  - Compute prior-month year/month (handle Jan edge case).
  - Call `preview_monthly_allocation(year, month)`.
  - Email report to Sam + Denise via `frappe.sendmail`.
  - MUST_MODIFY: `hrms/hooks.py`, `hrms/api/labor_allocation.py`
  - MUST_CONTAIN: `preview_monthly_allocation_scheduled`, `frappe.sendmail`, `scheduler_events`, `cron`

## Phase 6 — Tests + Runbook + Closeout (11u)

- [ ] P6-T1 Run unit tests locally via Frappe stub (S201 pattern).
- [ ] P6-T2 **Production Apply Runbook** section exists (below).
- [ ] P6-T3 Update plan YAML: `status: COMPLETED`, `completed_date`, `backend_pr`, `l3_result`.
- [ ] P6-T4 Update `docs/plans/SPRINT_REGISTRY.md` S206 row with status + PR.
- [ ] P6-T5 `git add -f docs/plans/*.md docs/compliance/*.md output/s206/`.
- [ ] P6-T6 Create PR to production.

## Production Apply Runbook

### One-time setup (first environment deploy)

```bash
CONTAINER=$(sudo docker ps --format '{{.Names}}' | grep frappe_backend | head -1)

# 1. Seed intercompany accounts (49 stores + BEI + BKI)
sudo docker exec $CONTAINER \
  bench --site hq.bebang.ph execute \
  hrms.on_demand.s206_seed_intercompany_accounts.execute

# 2. Verify
sudo docker exec $CONTAINER bench --site hq.bebang.ph mariadb \
  -e "SELECT company, COUNT(*) FROM tabAccount WHERE name LIKE '%GROUP ENTITIES%' GROUP BY company;"
```

### Preview monthly allocation (safe, no writes)

```bash
sudo docker exec $CONTAINER \
  bench --site hq.bebang.ph execute \
  hrms.api.labor_allocation.preview_monthly_allocation \
  --kwargs '{"year": 2026, "month": 4}'
```

### Apply monthly allocation (writes paired JEs)

```bash
# REQUIRES: TP Policy signed + preview reviewed
sudo docker exec -e S206_APPLY=1 $CONTAINER \
  bench --site hq.bebang.ph execute \
  hrms.api.labor_allocation.post_monthly_allocation \
  --kwargs '{"year": 2026, "month": 4}'
```

**The `-e S206_APPLY=1` is MANDATORY.** Without it the apply path silently falls back to dry-run.

### Re-run idempotency test

```bash
# Running apply twice should produce zero new JEs:
sudo docker exec -e S206_APPLY=1 $CONTAINER \
  bench --site hq.bebang.ph execute \
  hrms.api.labor_allocation.post_monthly_allocation \
  --kwargs '{"year": 2026, "month": 4}'
# Expected: applied=[], all skipped_idempotent
```

## L3 Workflow Scenarios (FRESH session per S092)

| # | Scenario | Expected | Failure Means |
|---|---|---|---|
| L3-1 | `preview_monthly_allocation(2026, 4)` | dry_run=True, no JEs, no Log rows | preview leaking writes |
| L3-2 | Edlice (REGIONAL AREA MANAGER) in skipped_other reason=`non_store_billing` | — | classifier broken |
| L3-3 | Cashier all-April at home store in skipped_other reason=`all_home` | — | shortcut broken |
| L3-4 | Reliever 2+ stores applied | Two JEs with `voucher_type='Inter Company Journal Entry'`, cross-referenced, `party_type='Company'` on Due, `Employee` on Salaries, user_remark cites cost-sharing | paired JE broken |
| L3-5 | Apply April twice | Second call: `skipped_idempotent` for every slip; zero new JEs; zero new Log | idempotency broken |
| L3-6 | Corrupt one slip cost_center, apply | Only that slip fails + log_error; other slips post cleanly | DM-2 violation |

**Evidence:** `output/l3/s206/{form_submissions,api_mutations,state_verification}.json`.

## Ownership Matrix

| File | Owner | Protected |
|---|---|---|
| `hrms/utils/punch_allocation.py` | S206 new | — |
| `hrms/utils/labor_allocation.py` | S206 new | — |
| `hrms/utils/device_store_bridge.py` | S206 new | — |
| `hrms/api/labor_allocation.py` | S206 new | — |
| `hrms/hr/doctype/bei_labor_allocation_log/` | S206 new | — |
| `hrms/on_demand/s206_seed_intercompany_accounts.py` | S206 new | — |
| `hrms/tests/test_s206_*.py` | S206 new | — |
| `docs/compliance/s206-transfer-pricing-policy.md` | S206 new | — |
| `hrms/utils/company_lookup.py` | S201 | **PROTECTED — consume only** |
| `hrms/utils/non_store_billing.py` | S201 | **PROTECTED — consume only** |
| `hrms/utils/device_mapping.py` | S019 era | **PROTECTED — via bridge only** |
| `hrms/utils/roving_employees.py` | HR audit | **PROTECTED — via is_roving only** |
| `hrms/hooks.py` | shared | **append scheduler_events only** |
| `hrms/patches.txt` | shared | **DO NOT MODIFY — seeder is on_demand** |
| Existing JV/GL/Salary Slip | Finance | **PROTECTED** |

## Rollback Contract

1. Query `BEI Labor Allocation Log` for affected period, list JE names.
2. Cancel JEs in pairs (Frappe validates paired cancellation): `frappe.get_doc('Journal Entry', je_name).cancel()`.
3. Delete Log rows: `DELETE FROM \`tabBEI Labor Allocation Log\` WHERE year=X AND month=Y`.
4. Code rollback: `git revert` PR + redeploy.
5. Seeded accounts: safe to leave (unused harmless).

## Files Modified/Created

| Action | File |
|---|---|
| CREATE | `docs/compliance/s206-transfer-pricing-policy.md` |
| CREATE | `hrms/utils/device_store_bridge.py` |
| CREATE | `hrms/utils/punch_allocation.py` |
| CREATE | `hrms/utils/labor_allocation.py` |
| CREATE | `hrms/api/labor_allocation.py` |
| CREATE | `hrms/hr/doctype/bei_labor_allocation_log/bei_labor_allocation_log.json` |
| CREATE | `hrms/hr/doctype/bei_labor_allocation_log/bei_labor_allocation_log.py` |
| CREATE | `hrms/hr/doctype/bei_labor_allocation_log/__init__.py` |
| CREATE | `hrms/on_demand/__init__.py` |
| CREATE | `hrms/on_demand/s206_seed_intercompany_accounts.py` |
| CREATE | `hrms/tests/test_s206_device_store_bridge.py` |
| CREATE | `hrms/tests/test_s206_punch_allocation.py` |
| CREATE | `hrms/tests/test_s206_labor_allocation.py` |
| MODIFY | `hrms/hooks.py` (append scheduler_events cron entry only) |

**NOT modified:** `hrms/patches.txt`.

## Zero-Skip Enforcement

**Phase gate before advancing:**

```bash
git diff --name-only origin/production...HEAD   # confirm MUST_MODIFY files present
grep -l "<pattern>" <file>                       # confirm MUST_CONTAIN patterns
```

Any assertion fail → fix before advancing. No silent skipping. No "deferred to next sprint". No DM shortcuts.

## Autonomous Execution Contract

- completion_condition: per plan YAML
- stop_only_for:
  - Missing intercompany accounts on >10 Companies (P0 HARD BLOCKER)
  - Finance declines TP Policy signoff (P0 HARD BLOCKER)
  - Punch data gap > 10% (allocation skipped, not errored)
  - Destructive apply requires Sam approval
  - Merge conflict on production
- continue_without_pause_through: audit -> execute -> PR -> L3 handoff
- signoff_authority: single-owner (Sam)
- canonical_closeout_artifacts:
  - `docs/compliance/s206-transfer-pricing-policy.md`
  - `output/s206/diagnostics/company_coa_audit_*.json`
  - `output/s206/diagnostics/intercompany_seed_report_*.json`
  - `output/l3/s206/{form_submissions,api_mutations,state_verification}.json`
  - `docs/plans/2026-04-17-sprint-206-reliever-allocation-engine.md` (COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (S206 row updated)

## Dependencies

- **S201 Option X** (PR #606) MERGED — libraries stable.
- **S175** MERGED — COA structure.
- **S188** MERGED — 49 per-store Companies.
- **S196** MERGED — ALL CAPS naming.

## Out of Scope (deferred)

- Quarterly intercompany clearing JE automation (S207)
- Hour-share allocation (v2 refinement)
- Retroactive re-allocation on Slip amendment (S207)
- Finance UI for review+approve (S208 — CLI + scheduled email for S206)

## Agent Boot Sequence

1. Read this v2 plan fully.
2. Verify on branch `s206-reliever-allocation-engine` from origin/production.
3. Read v2 audit response table (top) — understand why each v1 blocker is addressed differently.
4. Read `hrms/utils/company_lookup.py`, `hrms/utils/non_store_billing.py`, `hrms/utils/device_mapping.py`.
5. Read `hrms/utils/sales_location_mapping.py` for cache pattern reference.
6. Read Frappe upstream `frappe/accounts/doctype/journal_entry/journal_entry.py` for `inter_company_journal_entry_reference` semantics.
7. Begin Phase 0.
