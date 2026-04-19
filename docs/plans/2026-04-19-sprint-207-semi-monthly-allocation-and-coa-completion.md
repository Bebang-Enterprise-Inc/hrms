---
sprint: S207
title: S206 Long-Term Completion — Bimonthly Cadence + Salary Structure Alignment + 4-Children COA Finish
branch: s207-semi-monthly-allocation-and-coa-completion
base: production
status: GO
plan_version: v5
canonical_model_reference: docs/STORE_COMPANY_CANONICAL.md
canonical_preflight: required
plan_v4_reason_superseded: |
  v4 predates the 2026-04-19/20 canonical cleanup (PR #638 + PR #639 + the
  three workflow-skill canonical gates). v5 brings the plan into compliance
  with `docs/STORE_COMPANY_CANONICAL.md` — the SSOT for every BEI store's
  Company + Warehouse + billing Customer + Internal Customer. S207 was
  already canonical-compatible in its ACTIONS (targets the correct per-store
  Company docnames, uses the canonical Internal Customer/Supplier pattern,
  doesn't touch Warehouse or billing Customer master), but missed the
  gate-required plan sections. v5 adds them:
    - `canonical_model_reference` + `canonical_preflight` in YAML frontmatter
    - `## Canonical Model Preflight (Mandatory)` section before Phase 0
    - `## Canonical Model Binding` section before Phase 0 (names what S207
      reads/writes and asserts it does not drift the canonical model)
    - 5 new Requirements Regression Checklist items (v5 checks)
    - Canonical verifier rerun wired into Phase 8 closeout (P8-T6)
    - Source reference to `docs/STORE_COMPANY_CANONICAL.md` in Design
      Rationale and Phase 6 rationale
    - Zero-Skip Enforcement amended — canonical gate additions are
      non-negotiable like every other task
  No technical behavior change. The code S207 ships is identical to v4.
plan_v3_reason_superseded: |
  v3 cold-start audit 2026-04-19 found 3 BLOCKERs breaking "autonomous end-to-end" execution:
  (1) `freezegun` referenced 6x as mandatory test harness but not in `hrms/pyproject.toml` +
      no install step — agent hits ModuleNotFoundError at Phase 7 with no recovery path;
  (2) SSM/AWS/Doppler auth absent despite `boto3.client("ssm", ...)` calls in Phases 4/6 —
      agent hits NoCredentialsError with plan saying "refresh Doppler" but no concrete command;
  (3) `/frappe-bulk-edits` boilerplate referenced 8x but not inlined — agents that don't
      pre-create `/home/frappe/logs/` etc. crash on first Frappe logger init.
  Plus 2 high-impact GAPs: G1 (CEO approval proof format unverifiable — chat isn't
  cold-start-accessible) and G5 (L3-9 expected string doesn't match actual `s206_verify_all.py`
  output). v4 fixes all 5: P0-T4 installs freezegun; Agent Boot step 3 documents credential
  chain; Appendix A inlines full SSM boilerplate; P0-T0 (new) creates committed
  `docs/compliance/s207-ceo-approval-2026-04-19.md` as cold-start artifact; Appendix D
  corrects L3-9 expected outcome to match actual JSON output.
plan_v2_reason_superseded: |
  v2 failed audit 2026-04-19 (2nd pass) with 6 CRITICAL findings: (1) day-guard
  `tomorrow_pht = (datetime.now(utc) + timedelta(days=1)).astimezone(PHT)` is
  off-by-one — cron at UTC 22:00 is already PHT 06:00 next day, `+ 1 day`
  double-increments → cron never fires (3 independent confirmations);
  (2) `_ensure_root_group()` omitted `account_currency` — Frappe's
  `validate_currency()` fires regardless of `ignore_root_company_validation`;
  (3) Old S206 monthly cron `"0 22 1 * *"` still live during Phases 1-4 while
  Phase 1 removes the target functions — any UTC day-1 boundary in execution =
  Sentry error storm; (4) Patch backfill SQL undefined for year-12 rollover
  and NULL-safety; (5) TP Policy § 4.2 said gross_pay "includes statutory
  contributions" but Frappe `salary_slip.py:841-842` computes gross_pay as
  earnings only (ER contributions separate); (6) Idempotency keyed on
  (period_start, period_end, employee) lets ad-hoc full-month re-runs
  double-post half-period Slips. v3 fixes all 6.
plan_v1_reason_superseded: |
  v1 failed audit 2026-04-19 with ~15 CRITICAL blockers: (1) `Semi-Monthly` is not
  a stock Frappe `payroll_frequency` option (stock: Monthly|Fortnightly|Bimonthly|
  Weekly|Daily; "Bimonthly" in Frappe = twice-a-month = our semi-monthly);
  (2) cron `"0 22 1,16 * *"` UTC fires at 06:00 PHT on 2nd/17th, not 1st/16th;
  (3) Phase 5 "temp-unset parent_company + re-seed" breaks the S206 `_find_parent_group`
  fallback — the fallback engages only when parent_company IS set;
  (4) posting_date used slip.end_date but CFO PNL-001 requires payout-date;
  (5) _existing_log would double-post across monthly→bimonthly migration boundary;
  (6) Phase 3 (cron) shipped before Phase 4 (Structures) creating concurrent-run
  race with old monthly cron;
  (7) no coordinated rollback for Phase 4+5 cross-phase failure;
  (8) scripts/s206_verify_coverage.py referenced but doesn't exist (actual:
  s206_verify_all.py);
  (9) 4 Company PKs listed without `- BEBANG ENTERPRISE INC.` suffix;
  (10) autonomous CEO-signature insertion on TP Policy.
  v2 incorporates Sam's 2026-04-19 decisions on all 7 audit questions.
planned_date: 2026-04-19
revised_date: 2026-04-19
planned_by: Claude (BEI-ERP)
owner: Sam Karazi (CEO)
depends_on: [S206]
followed_by: []
estimated_units: 74
primary_repo: hrms
touches_frontend: false
l3_required: true
hard_deadline: 2026-05-16
registry_row: |
  | `S207` | Sprint 207 | `s207-semi-monthly-allocation-and-coa-completion` (hrms) | TBD | PLANNED 2026-04-19 | `docs/plans/2026-04-19-sprint-207-semi-monthly-allocation-and-coa-completion.md` |
ceo_approvals:
  - 2026-04-19 chat: "Use Bimonthly; use /frappe-bulk-edits for the 4-children COA and do it yourself; posting_date hits April P&L for March 16-31 work; my CEO approval suffices — no Denise signature needed; long-term sustainable solution; I might want to run April calculation for Q2 2026 reporting; you decide phase ordering and low-traffic-window enforcement."
completion_condition: |
  All TRUE at closeout, verified by scripts/s207_verify_all.py:
  - hrms/api/labor_allocation.py: preview_allocation + post_allocation accept (start_date, end_date) only (no year/month shim — clean break per CEO sustainability directive)
  - hrms/api/labor_allocation.py: `preview_scheduled()` uses daily cron + Python day-guard — fires only when tomorrow-in-PHT.day is 1 or 16
  - hrms/hooks.py: scheduler_events.cron contains ONE S207 entry `"0 22 * * *"` pointing to `preview_scheduled`. Old `"0 22 1 * *"` S206 entry removed.
  - hrms/utils/labor_allocation.py: `posting_date_for_slip()` helper computes payout date per CFO PNL-001 (10th of next month for 16-end-of-prev-month slips; 25th of same month for 1-15 slips). Applied to both home + covered JE in `_build_paired_jes`.
  - BEI Labor Allocation Log DocType: unique on (period_start, period_end, employee). `year`/`month` fields DROPPED (not stored — violates DM-5). Patch drops old `idx_year_month_employee`, creates `idx_period_employee`.
  - Frappe Salary Structures: all 4 active structures updated from `payroll_frequency=Monthly` to `payroll_frequency=Bimonthly` (Frappe's term for twice-a-month = our semi-monthly, per HRMS Select enum).
  - COA coverage = 51/51: the 4 BEI-Enterprise-direct-children (ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC., SM MANILA - BEBANG ENTERPRISE INC., SM MEGAMALL - BEBANG ENTERPRISE INC., SM SOUTHMALL - BEBANG ENTERPRISE INC.) each have Asset root group + Liability root group + Due From + Due To + internal Customer + internal Supplier. Fix via bulk-edits SSM that creates root groups THEN runs the S206 seeder.
  - TP Policy v1.2: cadence clarification applied; CEO approval-proof = reference to 2026-04-19 chat message. No autonomous signature insertion.
  - docs/runbooks/s206_production_apply.md: bimonthly flow documented; examples use (period_start, period_end) only.
  - docs/plans/2026-04-17-sprint-206-reliever-allocation-engine.md: execution_summary amended to note S207 completed.
  - docs/plans/SPRINT_REGISTRY.md S207 row → COMPLETED with PR link.
  - output/l3/s207/VERIFICATION_SUMMARY.md shows 9/9 PASS.
  - **Canonical gate (v5):** `output/l3/s207/canonical_postcheck.txt` matches the `output/s207/preflight/canonical_precheck.txt` baseline exactly (zero new violations) — OR the only remaining violation is the pre-existing `BILLING_CUST_TIN_EMPTY` for `ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC`.
  - Evidence committed to branch via `git add -f output/l3/s207/` + `git add -f output/s207/`.
  - PR created base=production head=s207-semi-monthly-allocation-and-coa-completion; agent STOPS after PR creation.
stop_only_for:
  - SSM auth / Doppler credential failure
  - Frappe `payroll_frequency` Select does NOT accept 'Bimonthly' on live site (unexpected — stock enum)
  - Draft Salary Slips exist when Phase 4 runs (coordinate with payroll team)
  - Seeder fails for ≥1 of the 4 children after bulk-edits adds root groups (diagnose, don't force)
  - Merge conflict on production during final rebase
  - Canonical preflight (P0-T6) reports any violation beyond the pre-existing `BILLING_CUST_TIN_EMPTY` for `ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC` — master-data drift must be resolved before S207 proceeds
  - Canonical postcheck (P8-T5) shows new violations introduced by S207 — roll back offending commit, do not create PR
  - S206 seeder returns `created` (not `existed`/`updated`) for any of the 4 BEBANG ENTERPRISE Internal Customers — indicates canonical drift between PR #638 and S207 execution
---

# Sprint S207 v2 — S206 Long-Term Completion

## Design Rationale (For Cold-Start Agents)

### Why this exists (problem)

S206 shipped a monthly labor cost-sharing engine. Three post-deploy deficiencies:
1. **Wrong cadence.** Engine is monthly. BEI's actual pay cycle is twice-a-month (10th + 25th payouts).
2. **Frappe Structures mis-configured.** All 4 active Salary Structures are `payroll_frequency=Monthly`. Must be twice-a-month.
3. **4 uncovered Companies.** S206 closed 47/51. The 4 missing are all direct children of `BEBANG ENTERPRISE INC.` with empty own-COA.

### Why this architecture (long-term sustainable, per CEO directive 2026-04-19)

- **`Bimonthly` not `Semi-Monthly`.** Frappe's `payroll_frequency` Select field has no `Semi-Monthly` option. Stock values: `Monthly | Fortnightly | Bimonthly | Weekly | Daily`. In Frappe HRMS, `Bimonthly` means "twice a month" (24 payouts/year) — same semantics as English "semi-monthly". No custom Select extension, no fighting Frappe defaults. Uses `payroll_entry.py` and `salary_slip.py`'s built-in half-period logic.

- **Daily cron + Python day-guard** (not `"0 22 1,16 * *"`). UTC 22:00 on day N = PHT 06:00 on day N+1. A cron at `"0 22 1,16 * *"` would fire on PHT 2nd/17th. Alternatives: calendar gymnastics (`"0 22 15,28-31 * *"` with last-day guard) are brittle across Feb/28-29-day months. Daily cron `"0 22 * * *"` + Python wrapper that checks `tomorrow_in_PHT.day in (1, 16)` is robust, self-documenting, and testable. Trade-off: cron fires ~28 extra times/month as no-op; Frappe scheduler overhead is negligible. Long-term win: no timezone bugs, no month-end edge cases, easy to add other firing days without touching Frappe hooks.

- **Period-agnostic API (no year/month shim).** Sam's requirement: "I might want to run April calculation for Q2 2026 reporting". The API must accept ANY date range — half-month for regular cadence, full month for ad-hoc reporting. `preview_allocation(start_date, end_date)` handles all cases. The `(year, month)` signature is DROPPED entirely — no backward-compat shim. S206 has never posted real JEs yet (April payroll hasn't run), so there are zero real callers to break. Clean break = simpler, safer, more maintainable.

- **Posting date = payout date (CFO PNL-001).** Butch Formoso 2026-02-17: "Payroll is billed to the P&L of the month PROCESSED (payout date), NOT the month work was performed". Algorithm:
  - Half-period ending on 15th → payout on 25th of SAME month → posting_date = 25th
  - Half-period ending on last-day-of-month → payout on 10th of NEXT month → posting_date = 10th of next month
  - Function: `posting_date_for_slip(slip.end_date) → date`. Pure + deterministic.
  - LD-7 from v1 ("ZERO changes to JE construction") is **explicitly relaxed**: `_build_paired_jes` now takes `posting_date=` computed upstream rather than `slip.end_date`.

- **4-children COA fix via bulk-edits (CEO directive 2026-04-19).** Use `/frappe-bulk-edits` SSM pattern (`base64 → docker cp → bench python`) to:
  1. Create Asset root group (`1100000 - ASSETS - <abbr>`, root_type=Asset, is_group=1, parent_account=None) in each child's OWN COA
  2. Create Liability root group (`2100000 - LIABILITIES - <abbr>`, root_type=Liability, is_group=1, parent_account=None) in each child's OWN COA
  3. Run the S206 seeder on the 4 children — now the own-COA fallback in `_find_parent_group` finds the new roots and succeeds
  4. Wrapped in per-Company savepoint; idempotent (existing roots are left in place)

  This approach is sustainable: the root groups become a PERMANENT part of each child's COA, so any future account creation on those children will work without escape hatches. Clean architectural fix vs. temp-unset workaround.

- **Long-term enforcement for low-traffic window: NONE.** Rather than hard-coding `02:00-04:00 PHT` blockers, make Phase 5 operations inherently safe: per-company savepoint, idempotent (no-op on re-run), fast (<2 seconds per Company), no parent_company mutation. Safe to run any time. If Sam needs an emergency re-run during business hours, it just works. Long-term sustainable = operations that are correct by construction, not by schedule.

- **Phase ordering: Structures before Cron.** Phase 4 (Structures → Bimonthly) must run BEFORE Phase 5 (cron change). Rationale: Frappe payroll generates Salary Slips based on Structure frequency. If the new cron fires on a Bimonthly-correct day but Structures are still Monthly, Salary Slips won't exist for the half-period and preview would return empty. Correct sequence: (a) Structures → Bimonthly, (b) DocType schema migration, (c) API refactor, (d) engine uses new posting_date algo, (e) cron change, (f) 4-children COA, (g) tests + docs + closeout.

### Known limitations and mitigations

1. **First Bimonthly payroll run must be monitored.** Frappe's `payroll_entry.py` computes half-period dates automatically for `Bimonthly`, but this is BEI's first real test. Mitigation: Phase 4 includes a `bench execute` that generates a dry-run Salary Slip for one test employee and verifies `start_date, end_date` are half-month boundaries.

2. **Existing Salary Slip drafts (from Monthly era).** If any Draft slips exist with `payroll_frequency=Monthly` when Structures change, Frappe may refuse validation. Mitigation: Phase 4 preflight aborts if any Drafts detected.

3. **Salary Slip cross-month periods.** A half-period from 2026-03-16 to 2026-03-31 lives in March, but posts to April P&L. This is correct per CFO PNL-001 but may surprise reviewers. Mitigation: TP Policy v1.2 explicitly documents cross-month treatment; runbook shows examples.

4. **Q2 2026 reporting use case.** Sam may run `post_allocation(2026-04-01, 2026-04-30)` as a FULL April slice for Q2 reporting. The engine needs to handle full-month periods correctly. Mitigation: API accepts any date range; idempotency key is (period_start, period_end, employee), so full-month and half-month periods for the same employee don't collide (different period_end values).

### Source references

- **Canonical store/company model (SSOT):** `docs/STORE_COMPANY_CANONICAL.md` — the per-store Company + Warehouse + billing Customer + Internal Customer contract that S207 binds to. Enforced by `scripts/verify_canonical_structure.py` in Phase 0 P0-T6 and Phase 8 P8-T5.
- **Canonical migration evidence:** `data/_CONSOLIDATED/STORE_CANONICAL_STATE_2026-04-19.csv/.json` — frozen snapshot of all 49 stores post PR #638 + PR #639. S207 depends on this baseline.
- S206 plan: `docs/plans/2026-04-17-sprint-206-reliever-allocation-engine.md`
- S206 final status: `output/s206/audit/FINAL_STATUS_2026-04-18.md`
- CFO PNL-001: `data/_cleanroom/agent_runs/2026-03-02_w1_a4_hr_admin_audit/02_HR/packet/sources/phase3_p2_decisions.md`
- S207 v1 audit: `output/plan-audit/s207-semi-monthly-allocation-and-coa-completion/CONSOLIDATED_REPORT.md`
- Frappe `payroll_frequency` enum: stock Frappe HRMS Salary Structure DocType — confirmed values `Monthly|Fortnightly|Bimonthly|Weekly|Daily`
- S181 `ignore_root_company_validation`: `hrms/overrides/company.py:644` (single line; v1 plan's `:638-644` was wrong)
- S206 seeder `_find_parent_group` fallback logic: `hrms/on_demand/s206_seed_intercompany_accounts.py:90-168`
- S206 seeder `_ensure_internal_customer` idempotency: `hrms/on_demand/s206_seed_intercompany_accounts.py:227-273` — looks up by `represents_company` first; finds the 4 Internal Customers from PR #638 and returns `existed`/`updated` without duplicating.
- `/frappe-bulk-edits` skill pattern: `.claude/skills/frappe-bulk-edits/SKILL.md`
- CEO approval (2026-04-19 chat): 7 decisions covering all audit questions — quoted in `ceo_approvals` field above

## Agent Boot Sequence

1. **CANONICAL FIRST.** Read `docs/STORE_COMPANY_CANONICAL.md` fully before anything else. Then run `python scripts/verify_canonical_structure.py` and confirm output is `[RESULT] ALL CANONICAL` (or at most the single known `BILLING_CUST_TIN_EMPTY` for `ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC`). If any other violation is reported, STOP — master-data drift must be resolved before S207 begins. See the **Canonical Model Preflight** section of this plan.
2. Read this plan fully including Design Rationale + Requirements Regression Checklist + Canonical Model Binding.
3. **Create sprint branch:** `git fetch origin production && git checkout -b s207-semi-monthly-allocation-and-coa-completion origin/production`. NEVER commit to production.
4. **Verify SSM / Doppler / AWS credentials** BEFORE running any script that calls `boto3.client("ssm", ...)`:
   ```bash
   # Verify boto3 SSM client can authenticate:
   python -c "import boto3; print(boto3.client('ssm', region_name='ap-southeast-1').list_commands(MaxResults=1).get('Commands', [])[:1])"
   # If NoCredentialsError: AWS uses default credential chain (env vars, ~/.aws/credentials, IAM role).
   # BEI standard: Sam's local machine has AWS CLI configured. Confirm with:
   aws sts get-caller-identity --region ap-southeast-1
   # If still fails: Doppler fallback —
   doppler secrets --project bei-erp --config dev | grep -iE "AWS_ACCESS|AWS_SECRET"
   # If Doppler has keys, run future scripts via:
   doppler run --project bei-erp --config dev -- python scripts/s207_<script>.py
   ```
5. Read `docs/plans/2026-04-17-sprint-206-reliever-allocation-engine.md` for S206 execution history.
6. Read `output/s206/audit/FINAL_STATUS_2026-04-18.md` for current production baseline.
7. Read `output/plan-audit/s207-semi-monthly-allocation-and-coa-completion/CONSOLIDATED_REPORT.md` (v1) and `.../v2/CONSOLIDATED_REPORT.md` (v2) and `.../v3/cold_start_check.md` (v3) to understand what prior versions got wrong.
8. Read `.claude/skills/frappe-bulk-edits/SKILL.md` for the SSM pattern — or use the inlined **SSM Boilerplate Appendix** at the bottom of this plan (same content).
9. Read `hrms/api/labor_allocation.py`, `hrms/utils/labor_allocation.py`, `hrms/on_demand/s206_seed_intercompany_accounts.py`, `hrms/hooks.py` to confirm state matches baseline.
10. Verify no open PRs touching labor_allocation files: `GH_TOKEN="" gh pr list --repo Bebang-Enterprise-Inc/hrms --state open --search "labor_allocation"`.
11. Start Phase 0.

## Execution Authority

Autonomous end-to-end. Stop ONLY for items in `stop_only_for` (YAML frontmatter).

## Requirements Regression Checklist

Before writing ANY code, verify you will satisfy every item. "No" on any item = STOP.

- [ ] Does the plan use `payroll_frequency='Bimonthly'` (Frappe's term for twice-a-month)? (LD-1; CEO 2026-04-19)
- [ ] Does the cron use daily firing `"0 22 * * *"` with Python wrapper that checks `tomorrow_in_PHT.day in (1, 16)`? (LD-2)
- [ ] Is the S206 monthly cron `"0 22 1 * *"` REMOVED from hooks.py? (LD-3)
- [ ] Does the API accept `(start_date, end_date)` ONLY, with NO `(year, month)` shim? (LD-4; clean break)
- [ ] Does `_build_paired_jes` use `posting_date_for_slip()` helper (= 10th of next month or 25th of same month)? (LD-5; CFO PNL-001)
- [ ] Does `BEI Labor Allocation Log` DocType DROP `year` + `month` fields and keep only `(period_start, period_end, employee)` unique? (LD-6; DM-5)
- [ ] Does the DB unique index patch drop the old `idx_year_month_employee` AND create `idx_period_employee` in the same patch? (LD-7)
- [ ] Does the Phase 4 preflight abort if any Draft Salary Slips exist with Monthly frequency? (LD-8)
- [ ] Does the Phase 5 bulk-edits script CREATE Asset + Liability root groups in each child's own COA BEFORE running the seeder? (LD-9; CEO-directed approach)
- [ ] Is every Company name in Phase 5 fully qualified with ` - BEBANG ENTERPRISE INC.` suffix? (v1 audit fix)
- [ ] Does Phase ordering run Structures (P4) BEFORE cron change (P5)? (v1 audit: phase-order fix)
- [ ] Does TP Policy v1.2 cite the 2026-04-19 CEO chat message as approval-proof, NOT insert a signature? (CEO directive)
- [ ] Does every modified `@frappe.whitelist()` endpoint call `set_backend_observability_context()`? (DM-7)
- [ ] Does the plan preserve S206's paired-JE structure (DR/CR, party_type=Customer/Supplier, `inter_company_journal_entry_reference`)?
- [ ] Does the plan keep `ignore_root_company_validation` flag in the seeder (needed for the child Companies after Phase 5 root-group creation)?
- [ ] Does `_existing_log` query the new `(period_start, period_end, employee)` key ONLY (no backward-compat to old key, since DocType migration drops year/month)?
- [ ] Does the plan use `git add -f output/l3/s207/` and `git add -f output/s207/` to commit evidence files?
- [ ] Does Completion Condition include plan YAML → COMPLETED + SPRINT_REGISTRY update + PR creation + agent STOPS?

### v3 specific checks (added post-v2 audit)

- [ ] Day-guard uses `datetime.now(utc).astimezone(PHT).date()` DIRECTLY — NO `+ timedelta(days=1)` anywhere? (LD-17)
- [ ] `datetime`, `timedelta`, `timezone`, `PHT` are MODULE-LEVEL imports in `hrms/api/labor_allocation.py` (not function-local) for mockability? (LD-16)
- [ ] `_ensure_root_group()` includes `account_currency` from `Company.default_currency` fallback `PHP`? (LD-15)
- [ ] Old S206 cron `"0 22 1 * *"` REMOVED in Phase 0 P0-T5 (before API refactor), NOT in Phase 5? (v2 audit Deployment C-NEW-1)
- [ ] Phase 2 patch backfill SQL uses `STR_TO_DATE(CONCAT(year, '-', LPAD(month, 2, '0'), '-01'), '%Y-%m-%d')` and `LAST_DAY(...)` with explicit NULL-check before column drop?
- [ ] BEI Labor Allocation Log unique key is `(slip_name, employee)` not `(period_start, period_end, employee)`? (LD-14)
- [ ] TP Policy v1.2 § 4.2 clarifies gross_pay = earnings only (NOT ER contributions)?
- [ ] L3-3/L3-4/L3-5 use `freezegun.freeze_time` syntax, not manual `unittest.mock` on function-local imports?

### v4 specific checks (added post-v3 cold-start audit)

- [ ] P0-T0 creates `docs/compliance/s207-ceo-approval-2026-04-19.md` with Q1-Q7 sections?
- [ ] P0-T4 adds `freezegun>=1.4.0` to `hrms/pyproject.toml` dev dependencies?
- [ ] Agent Boot Sequence step 3 includes AWS credential verification commands?
- [ ] Appendix A inlined with full SSM boilerplate (INSTANCE_ID, REGION, log dir list, frappe.init)?
- [ ] Appendix B defines schemas for all 3 evidence files (form_submissions, api_mutations, state_verification)?
- [ ] Appendix C (CEO approval) referenced from TP Policy P7-T4 signature row (committed artifact, not chat)?
- [ ] L3-9 corrected to parse JSON output block, not grep for literal "COMPLETE: 51/51" string?

### v5 canonical-model checks (MANDATORY — the three workflow skills enforce these)

- [ ] **YAML frontmatter declares canonical compliance:** `canonical_model_reference: docs/STORE_COMPANY_CANONICAL.md` + `canonical_preflight: required`?
- [ ] **Canonical Model Preflight section exists** (before Phase 0) and requires running `scripts/verify_canonical_structure.py` before the first code change?
- [ ] **Canonical Model Binding section exists** (before Phase 0) enumerating every canonical record S207 reads, every canonical write, and the surfaces S207 does NOT touch (Warehouse, billing Customer, resolver)?
- [ ] **Phase 8 closeout includes a task (P8-T6) that reruns `scripts/verify_canonical_structure.py`** and asserts zero new violations compared to the preflight baseline?
- [ ] **PR #638 precondition verified:** before S207 starts, 49/49 stores resolve cleanly and the 4 BEBANG ENTERPRISE Internal Customers (`ROBINSONS ANTIPOLO (Internal)`, `SM MANILA (Internal)`, `SM MEGAMALL (Internal)`, `SM SOUTHMALL (Internal)`) exist with `represents_company` pointing to the canonical per-store Company names?
- [ ] **S207 scope claim is honest:** Phase 4 (Salary Structures), Phase 6 (Accounts), Phase 2 (Labor Allocation Log schema), Phase 5 (cron) are all non-canonical-master-data changes? Zero edits to `tabWarehouse`, `tabCustomer (is_internal_customer=0)`, `tabCompany` master fields, or `resolve_store_buyer_entity`?

## Locked Decisions (v5 — inherits v2-v4; v5 adds canonical-model gate)

| ID | Decision | Source |
|---|---|---|
| LD-1 | `payroll_frequency='Bimonthly'` (Frappe twice-a-month) — NOT `Semi-Monthly` (not a Frappe option) | CEO 2026-04-19 Q1 |
| LD-2 | Daily cron `"0 22 * * *"` + Python wrapper checking `tomorrow_in_PHT.day in (1, 16)` — robust across all month lengths and DST | Architecture audit fix + CEO long-term directive Q6 |
| LD-3 | Old S206 cron `"0 22 1 * *"` REMOVED entirely | v1 plan LD; explicit for cold-start clarity |
| LD-4 | API signature: `(start_date, end_date)` ONLY — no `(year, month)` shim (clean break) | CEO "long-term sustainable" Q5 |
| LD-5 | `posting_date = posting_date_for_slip(slip.end_date)` where: day ≤15 → date(year, month, 25); day > 15 → first-of-next-month → offset to 10th of next month | CFO PNL-001 + CEO Q3 |
| LD-6 | DocType drops `year` + `month` stored fields (DM-5 violation); keeps `(slip_name, employee, period_start, period_end, home_company, covered_companies, home_jes_json, covered_jes_json, total_allocated, shift_shares_json, allocated_on, allocated_by)`. `period_start`/`period_end` are informational (not unique) — `slip_name` is the new uniqueness axis per LD-14. | v1 audit DM-5 + v2 audit PH Finance W-7 |
| LD-7 | DB unique migration: `idx_year_month_employee` DROPPED; `idx_slip_employee (slip_name, employee)` CREATED — slip-based idempotency per LD-14. | v1 audit + v2 audit PH Finance W-7 |
| LD-8 | Phase 4 aborts if any Draft Salary Slips exist (any status=0 with Monthly frequency) | v1 audit + race-condition mitigation |
| LD-9 | Phase 5 uses `/frappe-bulk-edits` SSM pattern: CREATE Asset + Liability root groups in each child's own COA, THEN run seeder | CEO Q2 directive |
| LD-10 | Phase 4 ships before Phase 5 (Structures → cron change order) to avoid monthly-cron concurrent race | v1 audit + Architecture audit fix |
| LD-11 | Low-traffic-window restriction REMOVED. Phase 5 operation is idempotent + savepoint-safe by design | CEO Q7 "long-term sustainable" — operations safe by construction |
| LD-12 | TP Policy v1.2: cadence clarification + reference to CEO 2026-04-19 chat message as approval-proof. No autonomous signature insertion | CEO Q4 directive |
| LD-13 | Engine supports ad-hoc full-month periods (e.g., `preview_allocation(2026-04-01, 2026-04-30)`) for Q2 2026 reporting — not just regular half-period cadence | CEO Q5 "I might want to run April calculation for Q2 2026" |
| LD-14 | Idempotency keyed on `slip_name` (one Log row per Salary Slip), NOT on `(period_start, period_end, employee)`. Reason: ad-hoc full-month runs (e.g., April 1-30) iterate over the same Slips that half-month runs already processed (April 1-15, April 16-30 produce 2 Slips per employee). If keyed on period, the full-month run would NOT find the half-period Log rows → double-post. Slip-based key: each Salary Slip can only be allocated ONCE regardless of what date range the operator passes. Full-month run finds existing per-Slip Log rows → all skipped_idempotent. Clean. | v2 audit PH Finance W-7 |
| LD-15 | `account_currency` is MANDATORY on root group creation in Phase 6 (Frappe `validate_currency()` fires regardless of `ignore_root_company_validation`). Pull from `Company.default_currency` with `PHP` fallback. | v2 audit Frappe Backend CRITICAL-2 |
| LD-16 | `datetime` imports in `hrms/api/labor_allocation.py` are MODULE-level, not function-local. Reason: `unittest.mock.patch` / `freezegun.freeze_time` test harnesses cannot patch function-local imports. Tests in P8-T1 require mockable datetime. | v2 audit Deployment Q2 |
| LD-17 | `preview_scheduled` day-guard uses `datetime.now(utc).astimezone(PHT).date()` DIRECTLY — NO `+ timedelta(days=1)` arithmetic. At UTC 22:00 fire time, PHT is already the target date (UTC+8 puts PHT at 06:00 of next calendar day). Adding another day = off-by-one, cron never fires. | v2 audit: 3 independent audits confirmed with Python math |
| LD-18 | **Canonical model is SSOT.** S207 reads from `docs/STORE_COMPANY_CANONICAL.md` baseline (49 per-store Companies + Warehouses + billing Customers + Internal Customers, post PR #638/#639). Phase 0 P0-T6 captures the canonical baseline; Phase 8 P8-T5 reruns the verifier and asserts zero new violations. If S207 execution introduces ANY new canonical violation, STOP and roll back before PR. | 2026-04-20 canonical gate added to workflow skills |

## Phase Budget Contract

- Phase 0 (CEO approval artifact + preflight + library audit + freezegun install + disable old cron + canonical precheck): 12 units (+2 for P0-T0 approval artifact, +2 for P0-T4 freezegun, +2 for P0-T5 cron disable, +1 for P0-T6 canonical precheck)
- Phase 1 (Period-aware API + posting_date helper): 10 units
- Phase 2 (DocType schema migration with year/month drop + slip_name unique): 8 units
- Phase 3 (posting_date_for_slip integration in _build_paired_jes): 5 units
- Phase 4 (Salary Structure bulk-edit to Bimonthly): 7 units
- Phase 5 (Daily cron + Python day-guard wrapper — note: only NEW cron install; old cron removed in P0): 5 units
- Phase 6 (4-children COA via bulk-edits: create roots WITH account_currency + run seeder): 10 units
- Phase 7 (Tests with freezegun + TP Policy v1.2 + runbook + memory): 10 units
- Phase 8 (L3 verification + canonical postcheck + PR + closeout): 11 units (+1 for P8-T5 canonical gate)
- **Total: 74 units** (within 80-unit ceiling)
- Hard per-phase limit: 15. None exceed.

## Anti-Rewind / Concurrent-Run Protection Contract

- **ownership_matrix:** S207 owns `hrms/api/labor_allocation.py`, `hrms/utils/labor_allocation.py` (posting_date helper only; _build_paired_jes signature extended but internal JE structure FROZEN), `hrms/hr/doctype/bei_labor_allocation_log/*`, `hrms/hooks.py` scheduler_events.cron only, `hrms/patches/v16_0/s207_*.py` (new), `hrms/tests/test_s206_*.py`, `hrms/tests/test_s207_*.py`, `docs/compliance/s206-transfer-pricing-policy.md`, `docs/runbooks/s206_production_apply.md`, `scripts/s207_*.py` (new), `memory/s206-rollout.md` + `memory/MEMORY.md` (amend only).
- **protected_surfaces:** Frappe stock Salary Structure / Salary Slip / Payroll Entry DocTypes (VALUE changes only via UPDATE, no schema mods). S206 seeder's `_find_parent_group`, `_ensure_account`, `_ensure_internal_customer`, `_ensure_internal_supplier` — FROZEN (consumed as-is after roots created).
- **remote_truth_baseline:** `output/l3/s207/REMOTE_TRUTH_BASELINE.json` captures origin/production SHA at Phase 0 start + S206 final state (47/51 coverage, cron `"0 22 1 * *"`, Log unique on year+month+employee, 4 Structures Monthly, 4 children missing Asset/Liability root groups).
- **freshness_reintegration_gate:** Before final PR, rebase onto `origin/production`. If any sprint touched `labor_allocation.py` / `hooks.py` / seeder after Phase 0 baseline, reintegrate + re-run Phase 8 verification.
- **pretouch_backup:** Phase 4 (Structures) and Phase 6 (4-children) MUST write pre-touch backups to `output/s207/backups/` before mutation.

## Canonical Model Preflight (Mandatory)

**Every agent executing S207 MUST do the following BEFORE the first code change:**

1. **Read `docs/STORE_COMPANY_CANONICAL.md` in full.** It defines the single canonical model (per-store Company + Warehouse + billing Customer + Internal Customer) on top of which the entire BEI ERP — procurement, payroll, supply chain, store ops, billing, inventory, analytics — is built. S207 is a payroll sprint that depends directly on the canonical per-store Company model for per-store P&L rollup and the S206 Internal Customer pattern.

2. **Run the canonical verifier:**
   ```bash
   python scripts/verify_canonical_structure.py
   ```
   Expected output: `[RESULT] ALL CANONICAL — no action required` (or at most the single known `BILLING_CUST_TIN_EMPTY` for `ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC` which is a pre-existing BIR-TIN data gap, not a structural violation). If any other `[VIOLATION]` is reported, **STOP** — master data is off; do not paper over it by adding records, flipping fields, or mutating the resolver. Fix the violation through the canonical scripts in `scripts/canonical/` with Sam's approval before proceeding with S207.

3. **Canonical law summary (full text in `docs/STORE_COMPANY_CANONICAL.md`):**
   - Every store has EXACTLY 1 per-store Company + 1 Warehouse + 1 billing Customer + 1 Internal Customer.
   - All four share the same name string (e.g. `SM TANZA - BEBANG MEGA INC.`).
   - Per-store Company's `parent_company` links to the legal-entity parent.
   - `Warehouse.company` = the per-store Company (never the parent).
   - Billing Customer: `customer_name` = per-store Company name, `is_internal_customer=0`, `tax_id` = BIR TIN.
   - Internal Customer: `represents_company` = per-store Company, `is_internal_customer=1`, no TIN — **used by S206/S207 labor journals ONLY, never for regular SIs.**

4. **Prohibited actions during S207 execution** (any of these = STOP + ask Sam):
   - Creating a second Warehouse, billing Customer, or Company for a store that already has a canonical record
   - Mutating `represents_company` on an Internal Customer (breaks the labor-journal match)
   - Using the parent Customer (e.g. `BEBANG ENTERPRISE INC.`) for a per-store SI or paired journal entry
   - Reusing an Internal Customer for a regular SI (no TIN → BIR non-compliant)
   - Adding new fallback logic to `resolve_store_buyer_entity` — the resolver is step-1-only, fallbacks hide drift
   - Running ad-hoc SQL like `UPDATE tabCompany/tabWarehouse/tabCustomer` on production
   - Calling `frappe.delete_doc` on Company / Warehouse / Customer records with transactional history (use `disabled=1`)
   - Parsing `warehouse_name` strings to infer store identity — use `Warehouse.company` → per-store Company

5. **PR #638 precondition check.** Confirm that before S207 starts, `scripts/canonical_resolver_live_check.py` shows 49/49 stores resolving cleanly and the 4 Internal Customers (`ROBINSONS ANTIPOLO (Internal)`, `SM MANILA (Internal)`, `SM MEGAMALL (Internal)`, `SM SOUTHMALL (Internal)`) exist. S207 Phase 6 relies on the S206 seeder's `_ensure_internal_customer` finding these and returning `existed`/`updated` — **not** creating duplicates.

## Canonical Model Binding

This section names exactly what S207 reads and writes in the canonical model, and asserts the things it does NOT touch.

### S207 READS from the canonical model

| Canonical record | How S207 consumes it |
|---|---|
| Per-store `Company` (e.g. `SM MEGAMALL - BEBANG ENTERPRISE INC.`) | Target for Phase 6 COA completion (Asset + Liability root groups, Due From / Due To, internal Customer / Supplier). Target for Phase 4 Salary Structure updates (4 Structures → Bimonthly). Source for per-store P&L rollup on posted labor JEs. |
| `Company.parent_company` | Used by S206 seeder's `_find_parent_group` fallback when inherited COA doesn't cover the child — now succeeds because Phase 6 creates the missing Asset/Liability root groups. |
| `Company.default_currency` (→ `PHP` fallback) | Populated on every new Account row in Phase 6 (LD-15, v2 audit CRITICAL-2). |
| Internal `Customer` (`is_internal_customer=1`, `represents_company=<per-store Company>`) | Looked up by the S206 seeder's `_ensure_internal_customer`. S207 does NOT create these — PR #638 already seeded the 4 BEBANG ENTERPRISE children. S207 only confirms they exist and that `companies` allowlist is complete. |
| Internal `Supplier` (mirror of Internal Customer) | Same pattern — created by S206 seeder if missing, skipped if present. |

### S207 WRITES to the canonical model (tightly scoped)

| Write | Scope | Canonical-safe? |
|---|---|---|
| `tabAccount` — Asset + Liability root groups on the 4 BEI ENTERPRISE children | Phase 6 `_ensure_root_group()` via `/frappe-bulk-edits` SSM pattern with `ignore_root_company_validation=True`. Per-Company savepoint. Idempotent (skip if exists). | Yes. Accounts are NOT canonical master records; they are the per-store Company's P&L/BS scaffolding. Adding root groups completes the Company's COA without touching Company, Warehouse, or Customer records. |
| `tabAccount` — Due From / Due To group accounts under the new roots | Phase 6 via S206 seeder's `_ensure_account` (consumed FROZEN, not modified). | Yes. Same reasoning. |
| `tabSalary Structure.payroll_frequency` — 4 active Structures | Phase 4 bulk UPDATE from `Monthly` to `Bimonthly`. Preflight aborts if any Draft Salary Slips exist. | Yes. Salary Structure is NOT canonical master data; it's a payroll-config DocType. The canonical Warehouse / billing Customer / per-store Company records are untouched. |
| `tabBEI Labor Allocation Log` — schema change | Phase 2 drops `year` + `month` stored fields (DM-5 violation), creates unique index on `slip_name, employee` (LD-14). | Yes. BEI Labor Allocation Log is a child-of-payroll DocType, not a canonical master record. |
| `hrms/hooks.py` — scheduler cron | Phase 5 removes `"0 22 1 * *"` S206 entry; installs `"0 22 * * *"` daily guard. | Yes. Cron config, not master data. |

### S207 does NOT touch

| Canonical surface | Why it's safe |
|---|---|
| `tabWarehouse` | Not referenced anywhere in Phases 0-8. No Warehouse renames, no `Warehouse.company` flips, no area-supervisor changes. |
| Billing `Customer` (`is_internal_customer=0`) | Not referenced. All 49 billing Customers created in PR #638 are untouched. |
| `tabCompany` master fields (`name`, `parent_company`, `entity_category`, `tax_id`, S181 fields) | Read-only usage. S207 never runs UPDATE on tabCompany or renames a Company. |
| `resolve_store_buyer_entity` resolver | Unmodified. No new fallback branches. Step-1-only stays step-1-only. |
| Per-store billing Customer → Sales Invoice paths | Unchanged. Store sales continue to bill to per-store billing Customer with parent TIN (the canonical model). |

### Assertion for audit

If any change S207 produces ends up touching a row in the "does NOT touch" list above, it is out of scope for this sprint. Stop, rebase, ask Sam.

## Phase 0 — Preflight (12 units)

### P0-T1. Baseline capture

**MUST_MODIFY:** `scripts/s207_preflight_baseline.py` (create); writes `output/s207/preflight/baseline.json`

**MUST_CONTAIN (baseline.json fields):** `production_head_sha`, `cron_entries`, `salary_structures_frequency`, `labor_allocation_log_columns` (list of field names), `labor_allocation_log_unique_keys`, `coverage_before_count`, `uncovered_companies_fully_qualified` (list of 4 names each ending `- BEBANG ENTERPRISE INC.`).

**Verification:**
```bash
test -f output/s207/preflight/baseline.json
python -c "import json; d=json.load(open('output/s207/preflight/baseline.json'));
assert d['coverage_before_count']==47;
assert len(d['uncovered_companies_fully_qualified'])==4;
assert all(n.endswith('- BEBANG ENTERPRISE INC.') for n in d['uncovered_companies_fully_qualified'])"
```

### P0-T2. Verify Frappe Bimonthly enum value

**MUST_CONTAIN:** SSM query returns non-empty result for `SELECT DISTINCT payroll_frequency FROM tabSalary Structure` — confirms `Bimonthly` is a valid enum value. If returns only `Monthly`, that's fine (we'll UPDATE). If `Bimonthly` is rejected at validation, STOP (LD-1 wrong).

**MUST_MODIFY:** `output/s207/preflight/frappe_bimonthly_check.json`

### P0-T3. Active run coordination claim

**MUST_MODIFY:** `output/state/s207_active_run_claim.json` — PID, start time, owned file globs, `released_at: null`. MUST have Python context-manager wrapper that releases the claim on normal exit AND crash (via `atexit` + signal handler).

### P0-T4. Install `freezegun` test dependency

**RATIONALE (v3 audit B1):** L3-3/L3-4/L3-5 require `freezegun.freeze_time()` to mock `datetime.now()` for day-guard testing. `freezegun` is NOT in `hrms/pyproject.toml`. Without installation, agent hits `ModuleNotFoundError` at Phase 7.

**MUST_MODIFY:** `hrms/pyproject.toml`

**MUST_CONTAIN:**
- Add `freezegun>=1.4.0` to `[project.optional-dependencies].dev` (or create the `dev` group if absent)
- After merge + deploy, Sam runs on prod container: `docker exec $BACKEND pip install freezegun` (or via `bench pip install freezegun`) — documented in PR body
- For LOCAL test runs (CI/dev), the pyproject.toml change is sufficient

**Verification:**
```bash
rg "freezegun" hrms/pyproject.toml | wc -l  # 1
```

### P0-T5. DISABLE old monthly cron IMMEDIATELY (prevents crash during Phases 1-4)

**RATIONALE (v2 audit C-NEW-1):** Phase 1 removes `preview_monthly_allocation_scheduled`, `preview_monthly_allocation`, `post_monthly_allocation` function definitions. During Phases 1-4 execution, the OLD cron entry `"0 22 1 * *"` still points at the removed function. If execution straddles any UTC day-1 (happens every month), the cron fires calling a nonexistent function → Sentry error storm + monthly-email broken. Fix: disable old cron BEFORE refactoring the API.

**MUST_MODIFY:** `hrms/hooks.py`

**MUST_CONTAIN:**
- DELETE the S206 cron entry `"0 22 1 * *": ["hrms.api.labor_allocation.preview_monthly_allocation_scheduled"]`
- No replacement yet — Phase 5 adds the new daily cron. During Phases 1-4, cron is simply OFF for S206. Zero fire = zero crash.

**Verification:**
```bash
! rg 'preview_monthly_allocation_scheduled' hrms/hooks.py  # 0 matches
! rg '"0 22 1 \* \* \*"' hrms/hooks.py  # 0 matches (only old S206 cron had this schedule)
```

### P0-T6. Canonical Model Preflight baseline capture (v5 gate)

**RATIONALE:** The v5 canonical gate requires proof that S207 didn't introduce master-data drift. Capture the baseline now; Phase 8 P8-T5 will diff against it.

**MUST_MODIFY:** `output/s207/preflight/canonical_precheck.txt` (capture stdout)

**MUST_CONTAIN:**
```bash
python scripts/verify_canonical_structure.py > output/s207/preflight/canonical_precheck.txt 2>&1
```

**Verification (HARD BLOCKER if not satisfied):**
- File contains either `[RESULT] ALL CANONICAL — no action required` OR exactly `[BILLING_CUST_TIN_EMPTY] 1 stores: ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC` and nothing else flagged.
- If any other `[VIOLATION]` appears: **STOP.** Do not start Phase 1. Master-data drift must be resolved before labor-allocation refactor; otherwise S207 will build on top of broken foundations. Report to Sam with the verifier output.

### Phase 0 Gate

Run `scripts/s207_verify_phase.py 0` — must exit 0. Failure blocks Phase 1. Phase 0 gate ALSO verifies that `output/s207/preflight/canonical_precheck.txt` exists and contains no unexpected violations (P0-T6).

## Phase 1 — Period-Aware API (10 units)

### P1-T1. Drop `(year, month)` API signatures; period-only

**MUST_MODIFY:** `hrms/api/labor_allocation.py`

**MUST_CONTAIN:**
- `def preview_allocation(period_start, period_end):` — positional args, both required, both `date` or ISO str
- `def post_allocation(period_start, period_end, confirm=False):` — same
- `set_backend_observability_context(module="finance", action="preview_allocation", extras={"period_start": str(period_start), "period_end": str(period_end)})` on every whitelisted endpoint
- NO `year=`, NO `month=`, NO shim

**Verification:**
```bash
rg 'def preview_allocation\(period_start, period_end' hrms/api/labor_allocation.py | wc -l  # 1
rg 'def post_allocation\(period_start, period_end' hrms/api/labor_allocation.py | wc -l  # 1
! rg 'def preview_monthly_allocation' hrms/api/labor_allocation.py  # should return nothing (shim removed)
! rg 'def post_monthly_allocation' hrms/api/labor_allocation.py  # nothing
```

### P1-T2. Update `_existing_log` for new unique key

**MUST_MODIFY:** `hrms/api/labor_allocation.py`

**MUST_CONTAIN:**
```python
def _existing_log(slip_name):
    """LD-14: idempotency keyed on slip_name, not period. One Log row per Salary
    Slip — prevents double-posting when Sam runs ad-hoc full-month queries
    after per-half-month runs (e.g., full April 1-30 after running April 1-15 +
    April 16-30 half-periods)."""
    return frappe.db.get_value(LOG_DOCTYPE, {"slip_name": slip_name}, "name")
```

**Verification:** `rg '_existing_log\(slip_name\)' hrms/api/labor_allocation.py | wc -l` ≥ 1.

### P1-T3. Update `_record_log` to drop year/month, use period fields

**MUST_MODIFY:** `hrms/api/labor_allocation.py`

**MUST_CONTAIN:** `_record_log` inserts `{slip_name, employee, period_start, period_end, home_company, covered_companies, home_jes_json, covered_jes_json, total_allocated, shift_shares_json}`. `slip_name` is the new uniqueness axis (LD-14); `period_start`/`period_end` are informational only.

### P1-T4. Helper: `posting_date_for_slip`

**MUST_MODIFY:** `hrms/utils/labor_allocation.py`

**MUST_CONTAIN:**
```python
from datetime import date, timedelta

def posting_date_for_slip(slip_end_date):
    """CFO PNL-001: payroll hits P&L of payout month.
    - Slip ending on/before 15th → payout 25th of same month
    - Slip ending after 15th (end-of-month) → payout 10th of next month
    """
    d = slip_end_date
    if d.day <= 15:
        return date(d.year, d.month, 25)
    # Second-half slip — next month's 10th
    if d.month == 12:
        return date(d.year + 1, 1, 10)
    return date(d.year, d.month + 1, 10)
```

**Verification:**
```bash
rg 'def posting_date_for_slip' hrms/utils/labor_allocation.py | wc -l  # 1
```

## Phase 2 — DocType Schema Migration (8 units)

### P2-T1. Update `BEI Labor Allocation Log` DocType JSON

**MUST_MODIFY:** `hrms/hr/doctype/bei_labor_allocation_log/bei_labor_allocation_log.json`

**MUST_CONTAIN:**
- `slip_name` (Link Salary Slip, reqd=1, in_list_view=1) — **NEW primary uniqueness axis per LD-14**
- `period_start` (Date, reqd=1, in_list_view=1) — informational
- `period_end` (Date, reqd=1, in_list_view=1) — informational
- `employee` (Link Employee, reqd=1, in_list_view=1)
- `year` field REMOVED from `field_order` AND from `fields[]` array
- `month` field REMOVED

**Verification:**
```bash
python -c "import json; d=json.load(open('hrms/hr/doctype/bei_labor_allocation_log/bei_labor_allocation_log.json'));
names={f['fieldname'] for f in d['fields']};
assert 'slip_name' in names and 'period_start' in names and 'period_end' in names;
assert 'year' not in names and 'month' not in names, 'year/month must be dropped (DM-5)'"
```

### P2-T2. Update DocType controller

**MUST_MODIFY:** `hrms/hr/doctype/bei_labor_allocation_log/bei_labor_allocation_log.py`

**MUST_CONTAIN:** `validate()` enforces unique `(slip_name, employee)` with actionable error message referencing LD-14 ("One Log row per Salary Slip — idempotency prevents full-month reruns from double-posting half-period slips").

### P2-T3. Patch: drop year/month columns, drop old index, add new index

**MUST_MODIFY:** `hrms/patches/v16_0/s207_labor_allocation_log_bimonthly.py` (create) + `hrms/patches.txt` (register)

**MUST_CONTAIN:** Exact SQL ordering (v2 audit C-NEW-2 — backfill math + NULL-safety):

```python
# Step 1: Backfill period fields BEFORE column drop. Use MariaDB LAST_DAY() for
# end-of-month regardless of 28/29/30/31. YYYY-MM-01 string handles year/month
# rollover naturally (no 12→1 edge case; MySQL STR_TO_DATE does the math).
frappe.db.sql("""
    UPDATE `tabBEI Labor Allocation Log`
    SET period_start = STR_TO_DATE(CONCAT(year, '-', LPAD(month, 2, '0'), '-01'), '%Y-%m-%d'),
        period_end   = LAST_DAY(STR_TO_DATE(CONCAT(year, '-', LPAD(month, 2, '0'), '-01'), '%Y-%m-%d'))
    WHERE period_start IS NULL
       OR period_end IS NULL
""")  # nosemgrep: frappe-sql-format-injection -- no user input, literal table+cols

# Step 2: Verify backfill completeness BEFORE column drop
orphans = frappe.db.sql("""
    SELECT COUNT(*) AS c FROM `tabBEI Labor Allocation Log`
    WHERE period_start IS NULL OR period_end IS NULL
""", as_dict=True)
if orphans and orphans[0]["c"] > 0:
    frappe.throw(f"S207 backfill incomplete: {orphans[0]['c']} rows have NULL period fields. Abort migration.")

# Step 3: Drop old unique index (if exists — idempotent)
try:
    frappe.db.sql("ALTER TABLE `tabBEI Labor Allocation Log` DROP INDEX `idx_year_month_employee`")
except Exception:
    pass  # index may already be gone on re-run

# Step 4: Drop year + month columns
for col in ("year", "month"):
    exists = frappe.db.sql("""
        SELECT COUNT(*) AS c FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'tabBEI Labor Allocation Log' AND column_name = %s
    """, (col,), as_dict=True)
    if exists and exists[0]["c"] > 0:
        frappe.db.sql(f"ALTER TABLE `tabBEI Labor Allocation Log` DROP COLUMN `{col}`")  # nosemgrep: frappe-sql-format-injection -- col is literal from tuple

# Step 5: Create new unique index (with IF NOT EXISTS guard)
exists = frappe.db.sql("""
    SHOW INDEX FROM `tabBEI Labor Allocation Log` WHERE Key_name = 'idx_slip_employee'
""", as_dict=True)
if not exists:
    frappe.db.sql("""
        CREATE UNIQUE INDEX `idx_slip_employee`
        ON `tabBEI Labor Allocation Log` (`slip_name`, `employee`)
    """)

frappe.db.commit()  # nosemgrep: frappe-manual-commit -- intentional: schema migration needs persist between steps
```

- The new unique index is `(slip_name, employee)` — see **Fix 6** below for the rationale (idempotency key changes from period-based to slip-based to avoid full-month/half-month double-post risk).
- Wrapped in savepoint at the outer execute level; `frappe.log_error` on failure.

**Verification:**
```bash
rg 'DROP INDEX.*idx_year_month_employee' hrms/patches/v16_0/s207_labor_allocation_log_bimonthly.py
rg 'DROP COLUMN year' hrms/patches/v16_0/s207_labor_allocation_log_bimonthly.py
rg 'CREATE UNIQUE INDEX.*idx_period_employee' hrms/patches/v16_0/s207_labor_allocation_log_bimonthly.py
rg 's207_labor_allocation_log_bimonthly' hrms/patches.txt
```

## Phase 3 — Posting Date Integration (5 units)

### P3-T1. Update `_build_paired_jes` to use `posting_date_for_slip`

**MUST_MODIFY:** `hrms/utils/labor_allocation.py`

**MUST_CONTAIN:**
- `_build_paired_jes(*, slip, share, home, covered, amount)` — internal body changes:
- `posting_date = posting_date_for_slip(slip.end_date)` — new line near top
- Replace `"posting_date": slip.end_date` with `"posting_date": posting_date` in BOTH home_je and covered_je dicts
- user_remark updated: `"...period {slip.start_date}..{slip.end_date}, posting_date={posting_date}, slip={slip.name}"`

**Verification:**
```bash
rg 'posting_date_for_slip\(slip\.end_date\)' hrms/utils/labor_allocation.py | wc -l  # 1
rg '"posting_date": posting_date' hrms/utils/labor_allocation.py | wc -l  # 2 (home + covered)
! rg '"posting_date": slip\.end_date' hrms/utils/labor_allocation.py  # must be gone
```

### P3-T2. Unit test for posting_date_for_slip

**MUST_MODIFY:** `hrms/tests/test_s207_posting_date.py` (create)

**MUST_CONTAIN:**
```python
from datetime import date
from hrms.utils.labor_allocation import posting_date_for_slip
# First half (1-15) → 25th same month
assert posting_date_for_slip(date(2026,4,15)) == date(2026,4,25)
# Second half (16-end) → 10th next month
assert posting_date_for_slip(date(2026,4,30)) == date(2026,5,10)
assert posting_date_for_slip(date(2026,3,31)) == date(2026,4,10)
# Year rollover
assert posting_date_for_slip(date(2026,12,31)) == date(2027,1,10)
```

## Phase 4 — Salary Structure Bulk-Edit to Bimonthly (7 units)

### P4-T1. Preflight: no Draft slips with Monthly frequency

**MUST_MODIFY:** `scripts/s207_preflight_phase4.py` (create)

**MUST_CONTAIN:** SSM query `SELECT name, employee FROM tabSalary Slip WHERE docstatus=0 AND payroll_frequency='Monthly'`. If non-empty, STOP with clear error listing the blocking slips. Save result to `output/s207/preflight/phase4_draft_check.json`.

### P4-T2. Pre-touch backup of Salary Structures

**MUST_MODIFY:** `scripts/s207_backup_salary_structures.py` (create)

**MUST_CONTAIN:** SSM query saves before-state to `output/s207/backups/salary_structures_before.json` (name + payroll_frequency for all `is_active='Yes'`). Writes a restore script `scripts/s207_restore_salary_structures.py` that inverts the change.

### P4-T3. Bulk UPDATE Structures to Bimonthly

**MUST_MODIFY:** `scripts/s207_switch_salary_structures_bimonthly.py` (create) — uses `/frappe-bulk-edits` SSM pattern

**MUST_CONTAIN:**
- SSM Python script with frappe init boilerplate (per `/frappe-bulk-edits` SKILL.md §"Frappe Init Boilerplate")
- `frappe.db.sql("UPDATE \`tabSalary Structure\` SET payroll_frequency='Bimonthly' WHERE is_active='Yes' AND payroll_frequency='Monthly'")`
- Post-update verify: `SELECT DISTINCT payroll_frequency FROM tabSalary Structure WHERE is_active='Yes'` returns `[('Bimonthly',)]` only
- `frappe.db.commit()  # nosemgrep: frappe-manual-commit` with comment explaining intentional manual commit
- Write evidence to `output/s207/evidence/salary_structure_update_report.json`

**Verification:** Evidence JSON shows `after_state == {'Bimonthly': 4}`.

### P4-T4. Smoke: generate 1 test Salary Slip draft to verify period math

**MUST_MODIFY:** `scripts/s207_smoke_bimonthly_slip.py` (create)

**MUST_CONTAIN:** Via bench, create 1 Salary Slip Draft for one test Employee using `Bimonthly` Structure. Verify Frappe auto-computes `start_date` and `end_date` as half-month boundaries. Delete the draft after check.

## Phase 5 — Daily Cron + Python Day-Guard Wrapper (5 units)

### P5-T1. Update `preview_scheduled` wrapper

**MUST_MODIFY:** `hrms/api/labor_allocation.py`

**MUST_CONTAIN:**
```python
# Module-level imports (NOT function-local — so unittest.mock + freezegun work)
from datetime import datetime, timedelta, timezone
PHT = timezone(timedelta(hours=8))

def preview_scheduled():
    """Fires daily at 22:00 UTC (= 06:00 PHT on that SAME PHT day since UTC+8).
    Runs only if `pht_now.day in (1, 16)`. LD-2 rationale: cron fires at UTC 22:00;
    `datetime.now(utc).astimezone(PHT)` directly gives PHT wall-clock at fire time,
    which is already "next day" on the PHT calendar because UTC 22:00 → PHT 06:00
    of the following date. NO +1 day arithmetic needed.
    """
    pht_now = datetime.now(timezone.utc).astimezone(PHT)
    pht_date = pht_now.date()
    if pht_date.day not in (1, 16):
        return  # no-op on non-firing days
    set_backend_observability_context(
        module="finance",
        action="preview_scheduled",
        mutation_type="read",
        extras={"firing_pht_date": str(pht_date)},
    )
    # Derive period from today's PHT date
    if pht_date.day == 1:
        # Period: 16 → end of PREVIOUS month
        prev_month_last = pht_date - timedelta(days=1)
        period_start = prev_month_last.replace(day=16)
        period_end = prev_month_last
    else:  # day == 16
        period_start = pht_date.replace(day=1)
        period_end = pht_date.replace(day=15)
    # Preview + email
    report = preview_allocation(period_start, period_end)
    _email_preview(report, period_start, period_end)
```

**Verification:**
```bash
rg "def preview_scheduled" hrms/api/labor_allocation.py | wc -l  # 1
rg "pht_date.day not in \(1, 16\)" hrms/api/labor_allocation.py | wc -l  # 1
rg "^PHT = timezone\(timedelta\(hours=8\)\)" hrms/api/labor_allocation.py | wc -l  # 1 (module-level)
! rg "tomorrow_pht" hrms/api/labor_allocation.py  # old variable name removed
! rg "timedelta\(days=1\).*astimezone" hrms/api/labor_allocation.py  # old off-by-one pattern gone
```

**HARD BLOCKER:** Do NOT use `datetime.now(utc) + timedelta(days=1)`. At cron fire time (UTC 22:00), `datetime.now(utc).astimezone(PHT)` IS ALREADY the target PHT date (UTC+8 puts us at 06:00 the next calendar day). Adding 1 more day = day+2 = cron never fires. (v2 audit: 3 independent confirmations with Python math.)

### P5-T2. Install new daily cron in hooks.py

**MUST_MODIFY:** `hrms/hooks.py`

**MUST_CONTAIN:**
- ADD: `"0 22 * * *": ["hrms.api.labor_allocation.preview_scheduled"]` to scheduler_events.cron
- (Old `"0 22 1 * *"` S206 entry was already removed in Phase 0 P0-T5 — verify with grep that it's still absent.)

**Verification:**
```bash
rg '"0 22 \* \* \*".*preview_scheduled' hrms/hooks.py | wc -l  # 1
! rg 'preview_monthly_allocation_scheduled' hrms/hooks.py  # still gone from P0-T5
```

**HARD BLOCKER:** If the old cron re-appeared (e.g., merge conflict resolution restored it), STOP — will cause crash on UTC day-1 because Phase 1 removed the target function.

## Phase 6 — 4-Children COA Completion (10 units)

Uses `/frappe-bulk-edits` SSM pattern per CEO directive.

**Canonical binding (v5):** This phase creates Asset + Liability root-group **Accounts** on the 4 BEBANG ENTERPRISE per-store Companies — NOT new Company, Warehouse, or Customer master records. The 4 per-store Companies and their canonical Internal Customers (`ROBINSONS ANTIPOLO (Internal)`, `SM MANILA (Internal)`, `SM MEGAMALL (Internal)`, `SM SOUTHMALL (Internal)`) already exist post PR #638. The S206 seeder's `_ensure_internal_customer` is idempotent (looks up by `represents_company`) — it will find the 4 Internal Customers from PR #638 and return `existed` or `updated`, never creating duplicates. If the seeder logs any `created` for the 4 BEBANG ENTERPRISE Internal Customers, that indicates the canonical state drifted between PR #638 and S207 execution — STOP and investigate.

### P6-T1. Pre-touch backup: current state of 4 children's accounts

**MUST_MODIFY:** `scripts/s207_backup_4_children_coa.py` (create)

**MUST_CONTAIN:** SSM query: `SELECT name, account_name, root_type, parent_account, is_group FROM tabAccount WHERE company IN ('ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.', 'SM MANILA - BEBANG ENTERPRISE INC.', 'SM MEGAMALL - BEBANG ENTERPRISE INC.', 'SM SOUTHMALL - BEBANG ENTERPRISE INC.')`. Save to `output/s207/backups/4_children_coa_before.json`.

### P6-T2. Bulk-edits script: create root groups in each child's own COA

**MUST_MODIFY:** `scripts/s207_create_4_children_root_groups.py` (create)

**MUST_CONTAIN:**
- `/frappe-bulk-edits` SSM pattern boilerplate (log dir creation, frappe.init, frappe.connect, frappe.set_user("Administrator"))
- For each of 4 companies (fully qualified names — `LD-9` requirement):
  ```python
  FOUR_CHILDREN = [
      "ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.",
      "SM MANILA - BEBANG ENTERPRISE INC.",
      "SM MEGAMALL - BEBANG ENTERPRISE INC.",
      "SM SOUTHMALL - BEBANG ENTERPRISE INC.",
  ]
  for company in FOUR_CHILDREN:
      abbr = frappe.db.get_value("Company", company, "abbr")
      sp = f"s207_rootgroups_{abbr}"
      frappe.db.savepoint(sp)
      try:
          frappe.local.flags.ignore_root_company_validation = True
          _ensure_root_group(company, abbr, "ASSETS", "Asset", "1100000")
          _ensure_root_group(company, abbr, "LIABILITIES", "Liability", "2100000")
          frappe.db.release_savepoint(sp)
      except Exception as exc:
          frappe.db.rollback(save_point=sp)
          ...  # log_error, continue
      finally:
          frappe.local.flags.ignore_root_company_validation = False
  frappe.db.commit()  # nosemgrep: frappe-manual-commit
  ```
- `_ensure_root_group(company, abbr, label, root_type, account_number)` creates an `is_group=1`, `root_type=<type>`, `parent_account=None` Account with name `"<account_number> - <label> - <abbr>"` if it doesn't exist. REQUIRED fields the Frappe Account validator demands (v2 audit CRITICAL-2):
  ```python
  doc = frappe.get_doc({
      "doctype": "Account",
      "account_name": f"{account_number} - {label}",
      "account_number": account_number,
      "parent_account": None,
      "is_group": 1,
      "root_type": root_type,  # "Asset" or "Liability"
      "report_type": "Balance Sheet",
      "company": company,
      "account_currency": frappe.db.get_value("Company", company, "default_currency") or "PHP",  # MANDATORY — validate_currency() fires regardless of ignore_root_company_validation
  })
  doc.insert(ignore_permissions=True)
  ```
- Writes evidence to `output/s207/evidence/4_children_root_groups.json`

**Verification:** After run, for each of 4 companies: SQL returns ≥1 is_group=1 Asset and ≥1 is_group=1 Liability account. Evidence JSON confirms.

### P6-T3. Run S206 seeder on the 4 children (now has own-COA roots)

**MUST_MODIFY:** `scripts/s207_seed_4_children.py` (create)

**MUST_CONTAIN:**
- Call `hrms.on_demand.s206_seed_intercompany_accounts.execute()` — the seeder's `_find_parent_group` now finds own-COA roots for the 4 children
- Verify result: `errors_count == 0` AND `missing_parents_count == 0` for the 4 children
- Save evidence to `output/s207/evidence/4_children_seed_result.json`

**Verification:** Evidence JSON shows 0 errors for the 4 children.

### P6-T4. Post-fix coverage verification

**MUST_CONTAIN:** Use existing `scripts/s206_verify_all.py` (ACTUAL file name — `s206_verify_coverage.py` does NOT exist per v1 audit) to run full coverage check. Expected: 51/51 complete. Evidence in `output/s207/evidence/coverage_after.json`.

**HARD BLOCKER:** If coverage < 51/51 after P6, STOP — the bulk-edits + seeder approach didn't work. Diagnose before proceeding to Phase 7.

## Phase 7 — Tests + TP Policy v1.2 + Runbook + Memory (10 units)

### P7-T1. Update unit tests for period-aware signatures

**MUST_MODIFY:** `hrms/tests/test_s206_labor_allocation.py`

**MUST_CONTAIN:** Replace all `(year=2026, month=4)` patterns with `(period_start=date(2026,4,1), period_end=date(2026,4,15))`. Add assertion that `posting_date` matches `posting_date_for_slip(slip.end_date)` not `slip.end_date`.

### P7-T2. New test file for bimonthly cadence + scheduled wrapper day-guard

**MUST_MODIFY:** `hrms/tests/test_s207_bimonthly_cadence.py` (create)

**MUST_CONTAIN:** Tests for `preview_scheduled` with mocked UTC date such that `tomorrow_in_PHT.day` is 1 or 16 or 7. Tests for period derivation correctness.

### P7-T3. Integration test update

**MUST_MODIFY:** `hrms/tests/test_s206_integration.py`

**MUST_CONTAIN:** Use half-month period (e.g., 2026-04-01 to 2026-04-15) and verify `posting_date == date(2026, 4, 25)` in posted JEs.

### P7-T4. TP Policy v1.2

**MUST_MODIFY:** `docs/compliance/s206-transfer-pricing-policy.md`

**MUST_CONTAIN:**
- `**Document version:** v1.2 — 2026-04-19 (bimonthly cadence + CFO PNL-001 payout-month posting + gross_pay scope clarification)`
- Section 4.2 CORRECTED (v2 audit PH Finance C-1): gross_pay base is `Salary Slip.gross_pay` = SUM of EARNINGS components only (basic pay, OT, allowances, holiday premium, tardiness deductions). It does NOT include employer-side SSS/PhilHealth/HDMF contributions; those accrue separately on each Company's books. The zero-margin characterization under BIR RR 2-2013 § 4(B) holds because earnings ARE the operator-facing labor cost of the employee's time at the covered store.
- Section 5.1 updated: paired JE `posting_date` = PAYOUT date per CFO PNL-001 (10th next month for 16-end, 25th same month for 1-15). Give an explicit cross-month example: "March 16-31 work → April 10 payout → `posting_date=2026-04-10` → P&L hits APRIL."
- Section 5.2 updated: balances accrue bimonthly (twice a month), cleared quarterly (unchanged).
- Section 6 (Form 1709 RPT disclosure) updated: with 24 postings/year per reliever pair (vs 12 monthly), annual disclosure may list aggregate per counterparty rather than each posting, per RR 19-2020 materiality thresholds.
- Section 10 Signatures: CEO row reads `| CEO | Sam Karazi | Approved — see `docs/compliance/s207-ceo-approval-2026-04-19.md` (Q1-Q7). No rescind of 2026-04-18 v1.1 signature. | 2026-04-19 |` (references the COMMITTED artifact from P0-T0, not a non-cold-start-accessible chat session)
- Finance row unchanged (pending)
- **HARD BLOCKER:** Do NOT write `/s/ Sam Karazi` anywhere without explicit text from Sam's message. (CEO directive Q4 — approval-proof = quoting the chat, not imitating signature.)

**Verification:**
```bash
rg "v1.2" docs/compliance/s206-transfer-pricing-policy.md
rg "earnings components" docs/compliance/s206-transfer-pricing-policy.md  # gross_pay clarification
rg "March 16-31.*April 10" docs/compliance/s206-transfer-pricing-policy.md  # cross-month example
! rg "/s/ Sam Karazi" docs/compliance/s206-transfer-pricing-policy.md  # no autonomous signature
```

### P7-T5. Apply runbook update

**MUST_MODIFY:** `docs/runbooks/s206_production_apply.md`

**MUST_CONTAIN:** Bimonthly flow replacing monthly. Examples use `preview_allocation(date(2026,4,1), date(2026,4,15))`. Troubleshooting section updated.

### P7-T6. Memory amend

**MUST_MODIFY:** `C:\Users\Sam\.claude\projects\F--Dropbox-Projects-BEI-ERP\memory\s206-rollout.md` (FULL path per v1 audit)

**MUST_CONTAIN:** Amendment block documenting: (1) bimonthly cadence live, (2) 51/51 coverage, (3) posting_date = payout date, (4) cron = daily + day-guard (not fixed-day), (5) Frappe's `Bimonthly` = our semi-monthly.

## Phase 8 — L3 Verification + Canonical Postcheck + PR + Closeout (11 units)

### P8-T1. Build `scripts/s207_verify_all.py`

**MUST_MODIFY:** `scripts/s207_verify_all.py` (create)

**Writes to:** `output/l3/s207/VERIFICATION_SUMMARY.md` with 9 checks, each PASS/FAIL + evidence file path + inline schema:

```
{
  "schema_version": "s207.v1",
  "run_timestamp_utc": "...",
  "run_timestamp_pht": "...",
  "checks": [
    {"id": "1_coa_coverage", "passed": bool, "expected_count": 51, "actual_count": int, "missing_companies": []},
    {"id": "2_reseed_clean", "passed": bool, "errors_count": int, "missing_parents_count": int},
    {"id": "3_structures_bimonthly", "passed": bool, "distinct_frequencies": [str]},
    {"id": "4_integration_smoke_first_half", "passed": bool, "paired_je_names": {"home": str, "covered": str}, "posting_date_actual": str, "posting_date_expected": str},
    {"id": "5_integration_smoke_second_half", "passed": bool, ...},
    {"id": "6_idempotency_first_half", "passed": bool, "first_applied": int, "second_skipped": int},
    {"id": "7_day_guard_day1", "passed": bool, "mocked_utc_date": str, "firing_pht_day": int, "derived_period": {"start": str, "end": str}},
    {"id": "8_day_guard_day16", "passed": bool, ...},
    {"id": "9_day_guard_noop", "passed": bool, "mocked_utc_date": str, "should_fire": false, "did_fire": false}
  ],
  "all_passed": bool
}
```

### P8-T2. Commit evidence to branch

**MUST_CONTAIN:**
- `git add -f output/l3/s207/` (all JSON + MD)
- `git add -f output/s207/` (preflight, backups, evidence, phase_completion)
- `git add -f output/state/s207_active_run_claim.json`
- Commit before PR (release manager gate requires evidence in branch)

### P8-T3. Amend S206 plan + update registry

**MUST_MODIFY:** `docs/plans/2026-04-17-sprint-206-reliever-allocation-engine.md` (amend execution_summary), `docs/plans/SPRINT_REGISTRY.md` (S207 row COMPLETED + PR)

### P8-T4. Flip S207 plan YAML → COMPLETED

**MUST_MODIFY:** This plan file

**MUST_CONTAIN:**
- `status: COMPLETED`
- `completed_date: 2026-04-19`
- `backend_pr: <actual PR URL>`
- `l3_result: 9/9 PASS — output/l3/s207/VERIFICATION_SUMMARY.md`
- `execution_summary: |` with concrete accomplishments

### P8-T5. Canonical verifier re-run (v5 gate)

**RATIONALE:** S207 reads from the canonical model (per-store Companies, Internal Customers) and writes to non-canonical scaffolding (Accounts, Salary Structure, Log schema, cron). The v5 canonical gate requires proof that S207 didn't accidentally drift any canonical record.

**MUST_MODIFY:** `output/l3/s207/canonical_postcheck.txt` (capture stdout)

**MUST_CONTAIN:**
```bash
python scripts/verify_canonical_structure.py > output/l3/s207/canonical_postcheck.txt 2>&1
```

**Verification (HARD BLOCKER):**
- Same number of violations as the Phase 0 preflight baseline. Zero new violations introduced by S207.
- Expected state: `[RESULT] ALL CANONICAL` or at most `[BILLING_CUST_TIN_EMPTY] 1 stores: ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC` (pre-existing BIR data gap, not a structural violation).
- If ANY new violation class appears (`WH_*`, `BILLING_CUST_MISSING`, `INTERNAL_CUST_*`, `CANONICAL_*`) — STOP, do not create PR, investigate which S207 change introduced the drift, roll back the offending commit.

```bash
# Compare with preflight baseline
diff output/s207/preflight/canonical_precheck.txt output/l3/s207/canonical_postcheck.txt
# Expected: identical (zero new violations) OR empty diff if verifier output stable
```

### P8-T6. Create PR + STOP

**MUST_CONTAIN:**
- `GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms --base production --head s207-semi-monthly-allocation-and-coa-completion ...`
- Body includes: summary, 8 phase accomplishments, link to VERIFICATION_SUMMARY.md, how to run verify post-deploy
- Body includes the v5 canonical-gate evidence: preflight baseline + postcheck diff (zero new violations)
- PR checklist table: each phase task with status + evidence

**HARD BLOCKER:** Agent STOPS after PR creation. User (Sam) merges + deploys.

## L3 Workflow Scenarios

| # | User | Action | Expected Outcome | Failure Means |
|---|---|---|---|---|
| L3-1 | Agent | Call `preview_allocation(date(2026,4,1), date(2026,4,15))` | `dry_run=True`, `period={"start":"2026-04-01","end":"2026-04-15"}`, counts, NO DB writes | API not period-aware |
| L3-2 | Agent | Call `preview_allocation(date(2026,3,16), date(2026,3,31))` | same structure, different period | cross-month case broken |
| L3-3 | Agent | Use `freezegun.freeze_time("2026-04-30T22:30:00+00:00")`, call `preview_scheduled()` | Fires (pht_date=2026-05-01, day=1 because UTC 22:00 = PHT 06:00 next day); period=2026-04-16..2026-04-30; email sent | day-guard day=1 broken |
| L3-4 | Agent | Use `freezegun.freeze_time("2026-04-15T22:30:00+00:00")`, call `preview_scheduled()` | Fires (pht_date=2026-04-16, day=16); period=2026-04-01..2026-04-15; email sent | day-guard day=16 broken |
| L3-5 | Agent | Use `freezegun.freeze_time("2026-04-07T22:30:00+00:00")`, call `preview_scheduled()` | No-op (pht_date=2026-04-08, day=8 not in {1,16}); no email | day-guard broken |
| L3-6 | Agent | Call `post_allocation(date(2026,4,1), date(2026,4,15), confirm=True)` twice | First: applied>0; Second: applied=0, skipped_idempotent=first_applied | Idempotency key broken |
| L3-7 | Agent | Inspect a posted JE from L3-6 | `posting_date == 2026-04-25` (CFO PNL-001) NOT 2026-04-15 | posting_date_for_slip not wired |
| L3-8 | Agent | SSM query `SELECT DISTINCT payroll_frequency FROM tabSalary Structure WHERE is_active='Yes'` | Returns `[('Bimonthly',)]` only | Phase 4 didn't apply |
| L3-9 | Agent | Run `scripts/s206_verify_all.py` and parse the JSON output block between `===RESULT_JSON_BEGIN===` and `===RESULT_JSON_END===` | `result["steps"]["1_coa_audit"]["complete_count"] == 51` AND `result["steps"]["1_coa_audit"]["incomplete_count"] == 0` (see Appendix D) | Phase 6 didn't finish 4-children |

**Evidence files required (ALL before COMPLETED):**
- `output/l3/s207/form_submissions.json` — L3-1..L3-9 result payloads
- `output/l3/s207/api_mutations.json` — JE names + Log row names from L3-6
- `output/l3/s207/state_verification.json` — pre/post SQL snapshots for P4 + P6
- `output/l3/s207/VERIFICATION_SUMMARY.md` — 9/9 PASS

## Zero-Skip Enforcement

**Every task MUST be implemented. No exceptions.**

Forbidden agent behaviors:
1. Skipping a task silently
2. Marking partial as "done"
3. Replacing a task with simpler version without explicit Sam approval
4. Saying "deferred to next sprint"
5. Combining tasks and dropping features
6. Implementing happy path only, skipping edge cases

### Phase Completion Checklist (machine-verifiable)

After each Phase, agent writes `output/s207/phase_completion/phase{N}_status.json`:

```json
{
  "phase": 4,
  "tasks": [
    {"id": "P4-T1", "status": "PASS|FAIL", "MUST_MODIFY": ["scripts/s207_preflight_phase4.py"], "must_modify_verified": true, "evidence": "output/s207/preflight/phase4_draft_check.json", "skipped": false, "if_skipped_why": null},
    {"id": "P4-T2", "status": "PASS|FAIL", ...},
    ...
  ],
  "all_passed": true
}
```

### Verification Script (MANDATORY — run after each Phase)

`scripts/s207_verify_phase.py <N>`:
- Reads this plan's Phase N MUST_MODIFY and MUST_CONTAIN assertions
- Runs `git diff --name-only origin/production...HEAD` — fails if any MUST_MODIFY file isn't in diff
- Runs `grep -F "<MUST_CONTAIN>" <file>` for every assertion — fails if not found
- Returns 0 if all assertions satisfied; non-zero otherwise

**If FAIL:** agent MUST fix before proceeding. No "I'll come back to it."

Per-phase assertion extraction: the script parses this markdown file's `**MUST_MODIFY:**` and `**MUST_CONTAIN:**` blocks under each `### P<N>-T<M>` heading.

## Autonomous Execution Contract

- **completion_condition:** see YAML frontmatter
- **stop_only_for:** see YAML frontmatter
- **continue_without_pause_through:** preflight → API refactor → DocType migration → posting_date integration → Structure change → cron change → 4-children COA → tests/docs → L3 verify → PR creation → closeout
- **blocker_policy:**
  - programmatic → fix and continue
  - environment/SSM auth → refresh Doppler, retry, continue
  - repeated Frappe validator failure (>3x) → read Frappe source, then continue
  - business-data policy change → pause
  - Draft Salary Slips in P4 preflight → STOP, notify payroll team
- **signoff_authority:** `single-owner` — Sam Karazi (CEO); approval proof = 2026-04-19 chat session (quoted in this plan's `ceo_approvals` metadata)
- **canonical_closeout_artifacts:**
  - `output/l3/s207/VERIFICATION_SUMMARY.md` (9/9 PASS)
  - `output/l3/s207/{form_submissions,api_mutations,state_verification}.json`
  - `output/s207/evidence/*.json`, `output/s207/backups/*.json`, `output/s207/phase_completion/*.json`
  - This plan file (status COMPLETED)
  - `docs/plans/2026-04-17-sprint-206-reliever-allocation-engine.md` (amended)
  - `docs/plans/SPRINT_REGISTRY.md` (S207 row COMPLETED + PR)
  - `docs/compliance/s206-transfer-pricing-policy.md` (v1.2)
  - `docs/runbooks/s206_production_apply.md` (bimonthly flow)
  - PR on `Bebang-Enterprise-Inc/hrms` base=production head=s207-...

## Status Reconciliation Contract

Every phase completion or blocker resolution triggers update in same work unit:
1. `output/s207/phase_completion/phase{N}_status.json`
2. `output/l3/s207/VERIFICATION_SUMMARY.md` (running totals)
3. `docs/plans/SPRINT_REGISTRY.md` S207 row (if state changed)
4. This plan's YAML status (if state changed)
5. PR description (if open) — task-by-task checklist

## Signoff Model

- **mode:** `single-owner`
- **approver_of_record:** Sam Karazi (CEO)
- **signoff_artifact:** PR approval + merge by Sam on `Bebang-Enterprise-Inc/hrms` S207 PR
- **approval_proof_for_v1.2_tp_policy:** 2026-04-19 Claude Code chat session (Q1-Q7 answers quoted in `ceo_approvals` metadata)
- **note:** Finance (Denise) countersign from TP Policy v1.1 gating is **waived by CEO 2026-04-19**. No new human gate added by S207.

## Failure Response

- **Mode A (production bug uncovered):** file Issue, STOP, present to Sam. Example: Bimonthly Select option rejected at Salary Structure save despite being in stock enum.
- **Mode B (test bug):** fix test; if helpful for others, promote to shared fixture.
- **Mode C (flakiness):** fix library code (labor_allocation.py, seeder), not spec. No `time.sleep(N)` masking.
- **≥3 library fixes during execution:** emit `output/l3/s207/LIBRARY_IMPROVEMENTS.md`.

## Ground-Truth Lock

- **evidence_sources:**
  - `data/_cleanroom/agent_runs/2026-03-02_w1_a4_hr_admin_audit/02_HR/packet/sources/phase3_p2_decisions.md` → CFO PNL-001
  - `output/s206/audit/FINAL_STATUS_2026-04-18.md` → S206 baseline
  - `output/plan-audit/s207-semi-monthly-allocation-and-coa-completion/CONSOLIDATED_REPORT.md` → v1 audit findings
  - `.claude/skills/frappe-bulk-edits/SKILL.md` → bulk-edits SSM pattern
  - Frappe stock `Salary Structure` DocType → `Bimonthly` enum value
  - `hrms/on_demand/s206_seed_intercompany_accounts.py` → seeder (FROZEN internal structure)

- **count_method:**
  - **metric:** Company coverage (complete / total in-scope)
  - **basis:** Company is "complete" iff it has `1104200 - DUE FROM GROUP ENTITIES - <abbr>` Account + `2104200 - DUE TO GROUP ENTITIES - <abbr>` Account + internal Customer (is_internal_customer=1, represents_company=<self>) + internal Supplier (is_internal_supplier=1, represents_company=<self>)
  - **method:** `scripts/s206_verify_all.py` (existing, verified file name)

- **authoritative_sections:** Phases 0-8 tasks + L3 Scenarios + Requirements Regression Checklist control execution. Design Rationale is context. `ceo_approvals` YAML field is approval proof.

- **unresolved_value_policy:** Any unresolved value `[UNVERIFIED]` at plan-write; filled during execution.

## Files to Create or Modify

| Action | File |
|---|---|
| MODIFY | `hrms/api/labor_allocation.py` (period-aware API, preview_scheduled day-guard, posting_date integration) |
| MODIFY | `hrms/utils/labor_allocation.py` (add `posting_date_for_slip` helper, use it in `_build_paired_jes`) |
| MODIFY | `hrms/hr/doctype/bei_labor_allocation_log/bei_labor_allocation_log.json` (drop year/month, add period_start/end) |
| MODIFY | `hrms/hr/doctype/bei_labor_allocation_log/bei_labor_allocation_log.py` (validate on new unique key) |
| CREATE | `hrms/patches/v16_0/s207_labor_allocation_log_bimonthly.py` (drop columns + old index + create new index with backfill) |
| MODIFY | `hrms/patches.txt` (register S207 patch) |
| MODIFY | `hrms/hooks.py` (daily cron, remove old monthly cron) |
| MODIFY | `hrms/tests/test_s206_labor_allocation.py` (period-aware assertions + posting_date check) |
| CREATE | `hrms/tests/test_s207_bimonthly_cadence.py` (day-guard + period derivation tests) |
| CREATE | `hrms/tests/test_s207_posting_date.py` (posting_date_for_slip unit tests) |
| MODIFY | `hrms/tests/test_s206_integration.py` (period-aware + posting_date check) |
| MODIFY | `docs/compliance/s206-transfer-pricing-policy.md` (v1.2 with CEO approval reference) |
| MODIFY | `docs/runbooks/s206_production_apply.md` (bimonthly flow) |
| MODIFY | `docs/plans/2026-04-17-sprint-206-reliever-allocation-engine.md` (amend execution_summary) |
| MODIFY | `docs/plans/SPRINT_REGISTRY.md` (S207 row COMPLETED + PR) |
| MODIFY | This plan file (status COMPLETED) |
| MODIFY | `C:\Users\Sam\.claude\projects\F--Dropbox-Projects-BEI-ERP\memory\s206-rollout.md` (amendment block) |
| MODIFY | `C:\Users\Sam\.claude\projects\F--Dropbox-Projects-BEI-ERP\memory\MEMORY.md` (index line update) |
| CREATE | `docs/compliance/s207-ceo-approval-2026-04-19.md` (P0-T0 — CEO approval artifact) |
| MODIFY | `hrms/pyproject.toml` (P0-T4 — add `freezegun>=1.4.0` to dev dependencies) |
| CREATE | `scripts/s207_preflight_baseline.py` |
| CREATE | `scripts/s207_preflight_phase4.py` (draft slip check) |
| CREATE | `scripts/s207_backup_salary_structures.py` |
| CREATE | `scripts/s207_switch_salary_structures_bimonthly.py` |
| CREATE | `scripts/s207_restore_salary_structures.py` |
| CREATE | `scripts/s207_smoke_bimonthly_slip.py` |
| CREATE | `scripts/s207_backup_4_children_coa.py` |
| CREATE | `scripts/s207_create_4_children_root_groups.py` |
| CREATE | `scripts/s207_seed_4_children.py` |
| CREATE | `scripts/s207_verify_all.py` |
| CREATE | `scripts/s207_verify_phase.py` |
| CREATE (artifacts) | `output/s207/{preflight,backups,evidence,phase_completion}/*.json`, `output/l3/s207/*.{json,md}` |
| CREATE (canonical v5) | `output/s207/preflight/canonical_precheck.txt` (P0-T6 output) + `output/l3/s207/canonical_postcheck.txt` (P8-T5 output). Diff must be empty-or-pre-existing-only. |

## Reusable Patterns/Functions Cited

- **`/frappe-bulk-edits` SSM pattern** — `.claude/skills/frappe-bulk-edits/SKILL.md`. Phase 4, 5 (partial), 6 use this pattern: base64 → docker cp → bench python. Includes mandatory log-dir creation boilerplate.
- **S181 `ignore_root_company_validation`** — `hrms/overrides/company.py:644` (verified single line). Used in Phase 6 when creating root groups in child Companies.
- **S206 seeder `_find_parent_group`** — `hrms/on_demand/s206_seed_intercompany_accounts.py`. FROZEN; Phase 6 runs it AS-IS after creating root groups.
- **S206 paired-JE generator `_build_paired_jes`** — internal JE dict structure FROZEN; only `posting_date` computation changes in Phase 3.
- **DM-1/DM-2/DM-6/DM-7 compliance** — preserved across all phases.
- **Sentry `set_backend_observability_context`** — `hrms.utils.sentry`. Applied at every whitelisted endpoint S207 touches.

## Review Gates

Before COMPLETED:
- [ ] `rg "page\.request|fetch\(" output/l3/s207/` returns 0
- [ ] All 9 L3 scenarios PASS in `output/l3/s207/VERIFICATION_SUMMARY.md`
- [ ] `scripts/s207_verify_phase.py 8` returns exit 0
- [ ] `git diff --name-only origin/production...HEAD` shows exactly the "Files to Create or Modify" list (no unexpected files)
- [ ] All `output/s207/phase_completion/phase{0..8}_status.json` show `all_passed=true`
- [ ] TP Policy v1.2 committed with CEO approval-reference line (NOT autonomous signature)
- [ ] Structure SQL: `SELECT DISTINCT payroll_frequency FROM tabSalary Structure WHERE is_active='Yes'` returns `['Bimonthly']` only
- [ ] COA: 51/51 Companies complete
- [ ] Cron: `grep '"0 22 \* \* \*".*preview_scheduled' hrms/hooks.py` returns 1 match; OLD monthly cron removed
- [ ] **Canonical gate (v5):** `output/s207/preflight/canonical_precheck.txt` + `output/l3/s207/canonical_postcheck.txt` both exist; `diff` shows zero new violations; existing `BILLING_CUST_TIN_EMPTY` on `ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC` is unchanged (not our responsibility to fix).
- [ ] **Canonical binding sanity:** `git diff origin/production...HEAD -- hrms/api/supply_chain_contracts.py hrms/utils/supply_chain_contracts.py scripts/canonical/` returns empty (S207 did not modify the resolver or the canonical scripts).
- [ ] **No canonical master mutations:** `git diff origin/production...HEAD | grep -E "frappe.rename_doc.*(Company|Warehouse|Customer)|frappe.delete_doc.*(Company|Warehouse|Customer)|UPDATE.*tabCompany|UPDATE.*tabWarehouse"` returns empty.
- [ ] S206 seeder call in Phase 6 returned `existed`/`updated` (not `created`) for the 4 BEBANG ENTERPRISE Internal Customers — confirms PR #638 state held through execution.
- [ ] SPRINT_REGISTRY S207 row COMPLETED with PR link
- [ ] S206 plan execution_summary amended
- [ ] PR created; agent STOPs; Sam merges + deploys

---

## Appendix A — SSM Boilerplate (inlined from `/frappe-bulk-edits` skill)

All Phase 4, 5 (partial), 6 scripts that execute on production Frappe MUST use this template.

### Constants

```python
INSTANCE_ID = "i-026b7477d27bd46d6"   # BEI production Frappe EC2
REGION = "ap-southeast-1"              # Singapore
```

### 4-step SSM command chain (base64 → docker cp → exec)

```python
import base64, time, boto3

PYTHON_SCRIPT = r'''
# Your Frappe code goes here (see "Frappe Init Boilerplate" below)
'''

def run_via_ssm(script: str) -> tuple[int, str, str]:
    encoded = base64.b64encode(script.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{encoded}' | base64 -d > /tmp/s207_task.py",
        "docker cp /tmp/s207_task.py $BACKEND:/tmp/s207_task.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s207_task.py",
    ]
    ssm = boto3.client("ssm", region_name=REGION)
    resp = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": ["900"]},
    )
    cid = resp["Command"]["CommandId"]
    for _ in range(300):  # 300 × 3s = 15 min max
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut", "Cancelled"):
            return (
                0 if inv["Status"] == "Success" else 1,
                inv["StandardOutputContent"],
                inv["StandardErrorContent"],
            )
    return 2, "", "timeout"
```

### Frappe Init Boilerplate (REQUIRED at top of every Python script run inside container)

```python
import os, sys
# Step 0: Create ALL log directories before importing frappe
# Frappe's logger crashes if these don't exist in the container
for d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/private/files",
]:
    os.makedirs(d, exist_ok=True)

import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# --- Your code here ---

frappe.db.commit()  # nosemgrep: frappe-manual-commit -- intentional for batch ops
frappe.destroy()
```

### Failure modes + recovery

- **`NoCredentialsError` (boto3):** AWS creds missing. Agent Boot Sequence step 3 covers this (AWS CLI / Doppler fallback).
- **`FileNotFoundError: /home/frappe/...log`:** The script skipped the log-dir boilerplate. Add it.
- **Command TimedOut after 15 min:** Increase `executionTimeout` and the poll loop count; rerun.
- **`frappe.db.commit()` + nosemgrep:** Mandatory for batch ops. Each new commit call needs `# nosemgrep: frappe-manual-commit` and a comment explaining intent (semgrep linter in CI will block otherwise).

---

## Appendix B — Evidence File Schemas

Required L3 evidence files. Each MUST match the schema below (consumed by release-manager gate + cross-sprint audit tools).

### `output/l3/s207/form_submissions.json`

```json
{
  "schema_version": "s207.evidence.v1",
  "run_timestamp_utc": "2026-04-19T14:30:00Z",
  "scenarios": [
    {
      "id": "L3-1",
      "description": "preview_allocation(2026-04-01, 2026-04-15)",
      "inputs": {"period_start": "2026-04-01", "period_end": "2026-04-15"},
      "outputs": {"dry_run": true, "total_slips": 12, "planned_count": 3, "skipped_count": 9},
      "passed": true
    }
    // ... L3-2 through L3-9
  ]
}
```

### `output/l3/s207/api_mutations.json`

```json
{
  "schema_version": "s207.evidence.v1",
  "run_timestamp_utc": "2026-04-19T14:30:00Z",
  "je_pairs": [
    {
      "scenario_id": "L3-6",
      "slip_name": "HR-SAL-2026-00123",
      "home_je": "ACC-JV-2026-00456",
      "covered_je": "ACC-JV-2026-00457",
      "posting_date": "2026-04-25",
      "amount": 5000.00,
      "party_type_home_due_from": "Customer",
      "party_type_covered_due_to": "Supplier"
    }
  ],
  "log_rows": [
    {
      "slip_name": "HR-SAL-2026-00123",
      "period_start": "2026-04-01",
      "period_end": "2026-04-15",
      "allocated_on": "2026-04-19T14:31:00"
    }
  ]
}
```

### `output/l3/s207/state_verification.json`

```json
{
  "schema_version": "s207.evidence.v1",
  "run_timestamp_utc": "2026-04-19T14:30:00Z",
  "phase4_salary_structure_before": {"Monthly": 4, "Semi-Monthly": 0, "Bimonthly": 0},
  "phase4_salary_structure_after": {"Monthly": 0, "Bimonthly": 4},
  "phase6_coa_before": {"complete": 47, "incomplete": 4, "uncovered_companies": ["ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.", "..."]},
  "phase6_coa_after": {"complete": 51, "incomplete": 0, "uncovered_companies": []},
  "phase2_log_schema_before": {"columns": ["year", "month", "employee", ...], "unique_index": "idx_year_month_employee"},
  "phase2_log_schema_after": {"columns": ["slip_name", "employee", "period_start", "period_end", ...], "unique_index": "idx_slip_employee"}
}
```

---

## Appendix C — CEO Approval Artifact

**Artifact:** `docs/compliance/s207-ceo-approval-2026-04-19.md` (created by P0-T0 NEW — see below).

**Purpose:** Cold-start-accessible committed artifact capturing Sam's 7 CEO answers from 2026-04-19 chat. Agent cites THIS file (not the chat) in TP Policy v1.2 signature row and in PR body.

### P0-T0. Create CEO approval artifact

**MUST_MODIFY:** `docs/compliance/s207-ceo-approval-2026-04-19.md` (CREATE)

**MUST_CONTAIN:**
```markdown
# S207 CEO Approval — 2026-04-19

**Approver:** Sam Karazi (CEO, BEI Holding Group)
**Channel:** Claude Code chat session, 2026-04-19 (Sunday)
**Context:** 7 audit questions raised during S207 v1 audit. CEO answered each, enabling v2 rewrite.

## Q1. Frappe Select option choice for bimonthly cadence
**CEO answer:** "Yes use Bimonthly"
**Plan impact:** LD-1. Use stock Frappe `payroll_frequency='Bimonthly'` (= twice-a-month in Frappe's enum = industry "semi-monthly").

## Q2. 4-children COA fix approach
**CEO answer:** "Use /frappe-bulk-edits for this task and do it yourself"
**Plan impact:** LD-9. Phase 6 uses SSM bulk-edits pattern to create root groups + run seeder.

## Q3. Posting date behavior
**CEO answer:** "Correct it hits April P&L" (for March 16-31 work paid April 10)
**Plan impact:** LD-5. `posting_date_for_slip()` = 10th of next month for 16-end slips; 25th of same month for 1-15 slips. Matches CFO PNL-001.

## Q4. TP Policy v1.2 signature
**CEO answer:** "I approved it as a CEO you do not need Denise signature or approval just note my message as the proof of approval"
**Plan impact:** LD-12. TP Policy v1.2 Section 10 CEO row cites THIS file (not an imitated signature). Denise countersign gate from v1.1 is waived.

## Q5. Backward-compat (30-day deprecation shim)
**CEO answer:** "I need long term solution that is sustainable so do what ever align with my request, I might want to run April calculation though for q2 2026"
**Plan impact:** LD-4 + LD-13. Clean break — `(year, month)` signature dropped entirely; `(period_start, period_end)` is the only API. Engine supports ad-hoc full-month periods (Q2 2026 reporting use case).

## Q6. Phase ordering (cron vs Structures)
**CEO answer:** "That's up to you to decide, remember long term sustainable solution"
**Plan impact:** LD-10. Phase 4 (Structures) ships BEFORE Phase 5 (new cron). Old monthly cron removed in P0-T5 (before Phase 1 API refactor) to avoid concurrent-run race.

## Q7. Low-traffic window enforcement
**CEO answer:** "I do not know the answer to this you decide what is the best long term sustainable solution"
**Plan impact:** LD-11. No hard-coded window restriction. Phase 6 operations are savepoint-wrapped, idempotent, fast (<2s/Company) — safe to run any time by construction.

---

This file is the approval-proof artifact referenced by:
- `docs/compliance/s206-transfer-pricing-policy.md` Section 10 CEO signature row (v1.2)
- `docs/plans/2026-04-19-sprint-207-semi-monthly-allocation-and-coa-completion.md` YAML `ceo_approvals` field
- PR body for S207 closeout
```

**Verification:** `test -f docs/compliance/s207-ceo-approval-2026-04-19.md && grep -c "^## Q[1-7]\." docs/compliance/s207-ceo-approval-2026-04-19.md` returns 7.

**IMPORTANT:** P7-T4 TP Policy v1.2 signature line MUST reference THIS file, not "the 2026-04-19 Claude Code chat session":

```markdown
| CEO | Sam Karazi | Approved — see `docs/compliance/s207-ceo-approval-2026-04-19.md` (Q1-Q7). No rescind of 2026-04-18 v1.1 signature. | 2026-04-19 |
```

---

## Appendix D — L3-9 Expected Outcome Correction

Original L3-9 says: `Output contains "COMPLETE: 51/51"`.
Actual `scripts/s206_verify_all.py` output format: JSON with `"complete_count": 51, "incomplete_count": 0` OR summary table row `"1_coa_audit": "1. COA audit (51 Companies complete)"`.

**L3-9 corrected expected outcome:**
> Run `scripts/s206_verify_all.py`. Parse the JSON output block between `===RESULT_JSON_BEGIN===` and `===RESULT_JSON_END===`. Assert: `result["steps"]["1_coa_audit"]["complete_count"] == 51` AND `result["steps"]["1_coa_audit"]["incomplete_count"] == 0`.
