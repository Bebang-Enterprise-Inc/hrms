---
sprint_id: S231
display: Sprint 231
title: Defaults Defense + Atomicity + Pricing Coupling + Monthly Billing Extension + Naming Canonicalization (v2 — Combined Sprint per CEO directive)
status: IN-PROGRESS
version: v2
v2_supersedes_v1: true
created_date: 2026-05-02
completed_date: null
execution_summary: |
  2026-05-02 PHT — All 99 units of code + production execution shipped:
  
  Pre-Phase-0 PR #706 — MERGED + DEPLOYED 10:49 UTC. Cron enable-gate live.
  Main code PR #707 (hrms) — MERGED + DEPLOYED 12:56 UTC. C-1/C-2/D-1/D-2/D-3
  /D-4/E-2/E-5 + 28 unit tests + 8 SSM scripts.
  
  Phase A SSM — BEBANG FT INC. parent Company shell created (ignore_chart_of_
  accounts flag bypasses S181 chart import bug). Ayala Fairview Terraces' 13
  dead `- BFI2` refs cleared. CEO save unblocked.
  Phase B SSM — 44 broken Companies swept; broken_companies_after = 0.
  Phase E-3 SSM — BFC duplicate retired; canonical recreated cleanly.
  Phase E-4 SSM — 1 Customer renamed FTE→FT INC.
  Seed scripts — 9 BEI Fee Schedule rows seeded; Vista Mall carveout skipped
  (Department not yet created — by design).
  
  bei-tasks PR #458 (D-5 + TM-1..5,7) — OPEN. FeePreviewPanel + Page Object
  + assertion helper + 5 new CleanupKinds + s231-fee-preview.spec.ts +
  pre-fixed s37 + s27 math + type drift fix.
  
  L3 testing pending #458 merge + fresh L3 session run.
deployment_status: |
  Pre-Phase-0 PR #706 (cron gate):           MERGED + DEPLOYED 2026-05-02 10:49 UTC
  Main code PR #707 (hrms):                  MERGED + DEPLOYED 2026-05-02 12:56 UTC
  Phase A SSM (BFI2 + Ayala Fairview):       EXECUTED 2026-05-02 21:30 UTC
  Phase B SSM (sweep 44 Companies):          EXECUTED 2026-05-02 22:00 UTC
  Phase E-3 SSM (BFC dedup):                 EXECUTED 2026-05-02 22:15 UTC
  Phase E-4 SSM (FTE production rename):     EXECUTED 2026-05-02 22:30 UTC
  Seed BEI Fee Schedule (9 rows):            EXECUTED 2026-05-02 22:45 UTC
  Seed BEI Fee Carveout (Vista Mall):        SKIPPED (Department not yet created)
  bei-tasks PR #458 (D-5 + TM):              OPEN — awaiting Sam merge
  L3 scenarios S1-S10:                       PENDING — fresh L3 session after #458 merge
  Plan status flip to COMPLETED:             PENDING L3 verification
canonical_scope: in
canonical_model_reference: docs/STORE_COMPANY_CANONICAL.md
canonical_preflight: required
branch: s231-pricing-coupling-and-defaults-defense
target_repos:
  - hrms (Bebang-Enterprise-Inc/hrms)
  - bei-tasks (Bebang-Enterprise-Inc/BEI-Tasks)
base_branch: production (hrms) / main (bei-tasks)
pr_url: null
depends_on: []
unit_budget: 99
unit_budget_rationale: |
  CEO authorized exceeding the 80-unit S089 ceiling on 2026-05-02 to combine S231 + S232 + pre-hotfix into one sprint. v1 was 78 units; v2 expanded to 99 after dependency mapping discovered 14 additional items (BFC dedup, BEBANG FT INC. parent creation, BEI Billing Schedule DocType migration, monthly billing extension via existing function, test maintenance for 2 high-risk E2E tests + 14 new Python tests + 1 new E2E spec, Page Object + assertion helper creation, schema migration scripts, type drift fixes, mystery 0.04 rate investigation). v2 verified safe via 5 dependency probes — see "v2 Authoritative Scope" section below.
phase_unit_budget:
  Pre-Phase-0 — Emergency Cron Enable-Gate Hotfix: 4
  Phase 0 — Boot: 4
  Phase A — Probe + Unblock Ayala Fairview Terraces (incl. BEBANG FT INC. parent creation): 12
  Phase B — Audit + Sweep 44 Broken Companies: 10
  Phase C — Permanent Atomicity Fix (Full 10-Step) + Null-Out Validate Hook: 12
  Phase D-1 — Markup Field + 4 Missing BEI Settings Fields: 6
  Phase D-2 — Live Coupling Verify (4 ownership types) + N-8 Default Reconcile: 4
  Phase D-3 — Monthly Billing Extension (existing function) + DM-1 + Mystery 0.04 + VAT/EWT + Savepoint + Mutex + OR Precondition: 18
  Phase D-4 — Recipient Routing (BEI vs BFC SI Company): 4
  Phase D-5 — FeePreviewPanel + get_fee_schedule API + Type Drift Fix: 8
  Phase E — BFC Dedup + BEBANG FT INC. Cleanup + _NON_STORE_ENTITIES DRY: 9
  Pre-deploy Test Maintenance (s37-live + s27-billing-live + 14 new Python + 1 new E2E + Page Object + assertion helper): 12
  Closeout: 6
evidence_committed:
  - output/s231/SUMMARY.md
  - output/s231/DEFECTS.md
  - output/s231/RUN_STATUS.json
  - output/s231/verification/state_after.json
  - output/s231/verification/canonical_verifier_pre.txt
  - output/s231/verification/canonical_verifier_post.txt
  - output/s231/verification/broken_defaults_inventory.csv
  - output/s231/verification/broken_defaults_inventory_AFTER.csv
  - output/s231/verification/sweep_report.json
  - output/s231/verification/markup_settings_before.json
  - output/s231/verification/markup_settings_after.json
  - output/s231/verification/markup_coupling_test.json
  - output/s231/verification/monthly_billing_test_invoices.json
  - output/s231/verification/recipient_routing_test.json
  - output/s231/verification/bfc_dedup_log.json
  - output/s231/verification/bebang_ft_inc_creation_log.json
  - output/s231/verification/naming_rename_log.json
  - output/s231/verification/fte_references_AFTER.txt
  - output/s231/verification/migration_scripts_run.json
  - output/s231/verification/test_maintenance_log.json
  - output/s231/state/PRETOUCH_BACKUP.json
  - output/s231/state/ACTIVE_RUN_COORDINATION.json
  - output/s231/ledgers/TOUCH_PRESERVATION_LEDGER.csv
  - output/s231/MIGRATION_NOTES.md
  - output/s231/PRE_HOTFIX_DEPLOY_LOG.md
  - output/l3/s231/form_submissions.json
  - output/l3/s231/api_mutations.json
  - output/l3/s231/state_verification.json
  - output/l3/s231/teardown_ledger.json
  - output/l3/s231/teardown_complete.json
  - output/l3/s231/SUMMARY.md
evidence_transient:
  - tmp/s231/probe_*.json
  - tmp/s231/sweep_run_*.log
  - tmp/s231/ssm_command_*.txt
  - tmp/s231/traceback_*.txt
  - tmp/s231/playwright_trace_*.zip
  - tmp/s231/bench_migrate_*.log
  - tmp/s231/test_maintenance_*.log
sentry_projects:
  - bei-hrms (slug: bei-hrms, platform: python)
  - bei-tasks (slug: bei-tasks, platform: javascript-nextjs)
research_artifact: tmp/sprint-pricing-coupling-research/01_FINDINGS.md
source_session_jsonl: ~/.claude/projects/F--Dropbox-Projects-BEI-ERP/3cb6b2f5-4590-412d-a67f-a2d53a0f72f7.jsonl
source_session_id: 3cb6b2f5-4590-412d-a67f-a2d53a0f72f7
source_session_resume_command: claude --resume 3cb6b2f5-4590-412d-a67f-a2d53a0f72f7
source_session_started: 2026-05-02 00:53 PHT
source_session_purpose: |
  This session captured the full S231 sprint planning + audit + dependency mapping cycle on 2026-05-02 with CEO Sam Karazi. Includes verbatim CEO directives that became the cleanroom approvals memo, all 9 audit domain findings, all 5 dependency probe results, and the v2 plan synthesis. Future cold-start agents executing this plan can resume the session for full context if any decision needs verification beyond what is captured in cleanroom memos and probe artifacts.
ceo_approvals_memo: data/_CLEANROOM/2026-04-09_franchise_agreements/06_CEO_Approvals_2026-05-02.md
fee_carveouts_registry: data/_CLEANROOM/2026-04-09_franchise_agreements/05_Per_Store_Fee_Carveouts.md
v2_design_synthesis: output/plan-audit/sprint-231-pricing-coupling-and-defaults-defense/v2_DESIGN_SYNTHESIS.md
verified_blockers: output/plan-audit/sprint-231-pricing-coupling-and-defaults-defense/verified_blockers.md
dependency_probes:
  - output/plan-audit/sprint-231-pricing-coupling-and-defaults-defense/dep_production_state.json
  - output/plan-audit/sprint-231-pricing-coupling-and-defaults-defense/dep_production_state.md
  - output/plan-audit/sprint-231-pricing-coupling-and-defaults-defense/dep_backend_map.md
  - output/plan-audit/sprint-231-pricing-coupling-and-defaults-defense/dep_frontend_map.md
  - output/plan-audit/sprint-231-pricing-coupling-and-defaults-defense/dep_existing_billing_flow.md
  - output/plan-audit/sprint-231-pricing-coupling-and-defaults-defense/dep_test_coverage_map.md
  - output/plan-audit/sprint-231-pricing-coupling-and-defaults-defense/dep_schema_migration.md
hard_deadline: 2026-05-30
hard_deadline_rationale: |
  Existing `0 6 1 * *` cron (`hrms.api.billing.scheduled_monthly_billing`) fires next on 2026-06-01. Currently silently erroring because `tabBEI Billing Schedule` table is not migrated to production AND `bki_sales_vat_template` is empty. S231 v2 must EITHER ship before 2026-05-31 with all fixes in place OR Pre-Phase-0 hotfix must ship FIRST (cron enable-gate set to 0) so the June firing is safely no-op until full sprint deploys.
---

# Sprint 231 v2 — Combined Sprint (per CEO directive 2026-05-02)

## v2 Authoritative Scope (SUPERSEDES v1 body where conflicts)

**Per S028 ground-truth lock rule: this v2 section is authoritative for execution. The v1 phases (A-E) below are kept as reference but where v2 changes a phase's scope or budget, v2 wins.**

### What changed v1 → v2 (after 9-domain audit + 5 dependency probes)

| Item | v1 | v2 (authoritative) |
|---|---|---|
| Total scope | S231 (78u, defaults defense + pricing) | Combined: S231 + S232 + pre-hotfix in one sprint (~99u) |
| Sweep population | "all 49 stores" | 44 of 57 Companies (production probe confirmed) |
| Phase B payroll risk | Block if `default_payroll_payable_account` would be nulled on a Company with active payroll | MOOT — zero broken Companies have active Salary Structures (probe confirmed) |
| Phase C atomicity scope | Step 0 only (`create_default_accounts`) | All 10 steps (Steps 0-9) of `auto_provision_company` |
| D-3 monthly billing | Write new `run_monthly_franchise_billing` + new daily cron | EXTEND existing `_create_fee_sales_invoice_for_billing` (line 525) + `calculate_fees` + `_create_gl_entries` gate; KEEP existing `0 6 1 * *` cron unchanged |
| Recipient routing | Hardcoded "Bebang Franchise Corp." | Read from BEI Settings field `bfc_revenue_company` (config-as-data); production canonical is `BEBANG FRANCHISE CORP.` (uppercase, matches abbr=BFC) |
| Phase E scope | Rename Bebang FTE Inc. → BEBANG FT INC. in 4 seed CSVs | Same PLUS: dedup duplicate BFC Companies in production (`Bebang Franchise Corp.` AND `BEBANG FRANCHISE CORP.` both exist); CREATE `BEBANG FT INC.` parent legal entity Company from scratch (production probe: it doesn't exist); DRY `_NON_STORE_ENTITIES` (duplicated at company_master.py:507 + 1161) |
| BEI Billing Schedule DocType | Assumed to exist | NOT migrated to production (`billing_table_exists: false`) — Phase 0 must include `bench migrate` to create the table; existing cron silently erroring today |
| BEI Settings fields | Add `bki_markup_company_owned_percent` only | Add 4 missing fields: `bki_markup_company_owned_percent` (default 2.75), `bki_billing_cron_enabled` (default 0), `bki_sales_debit_to_account`, `bki_sales_naming_series`; configure existing `bki_sales_vat_template` (currently empty) |
| Test maintenance | 3 unit tests for atomicity | 3 atomicity unit tests + 14 new Python tests + 1 new E2E spec + new `CompanyMasterPage.ts` Page Object + new `assertFranchiseFeeSI` assertion helper + pre-fix 2 high-risk existing E2E tests (`s37-live.spec.ts:2182` JV markup, `s27-billing-live.spec.ts:792-802` math) |
| Frontend D-5 | Hardcoded `markupRates` prop + ambiguous wiring | New `get_fee_schedule()` whitelisted API + `useFeeSchedule()` hook; FeePreviewPanel slots between OperationsSection and PeopleSection in `company-detail-dialog.tsx:484-504`; type drift `_fee` vs `_amount` reconciled (frontend probe N-13) |
| RBAC for FeePreviewPanel | Listed as required fix | Already correct — STORE_PARTNER explicitly excluded from `MODULES.COMPANY_MASTER` per S227 (verified `bei-tasks/lib/roles.ts:920-927`) |
| Hook ordering | "Reorder validate hooks" | `Company.validate` becomes a list: `[null_out_dead_default_refs, validate_default_accounts]` (the new hook FIRST); guard `null_out_dead_default_refs` by `first_provision_done==1` so it doesn't null fields the orchestrator just set on a fresh Company |
| Mystery 0.04 rate | Not addressed | Phase D-3 task: investigate the existing `0.04` constant in `calculate_fees`, document its purpose, replace with config |
| Pre-hotfix | Was a separate sprint | Pre-Phase-0 inside this sprint: ship `bki_billing_cron_enabled` field + cron gate first, in a separate small PR before main S231 PR; protects June 1 firing |

### v2 Phase Map (8 phases)

| Phase | Units | Output |
|---|---|---|
| **Pre-Phase-0** Emergency Cron Enable-Gate Hotfix | 4 | Add `bki_billing_cron_enabled` field (default 0) + gate `scheduled_monthly_billing`; ship as PR-1 of the sprint, merge + deploy fast (~30 min). Protects 2026-06-01 cron firing while remaining sprint work proceeds. |
| **Phase 0** Boot | 4 | Worktree spawn, baseline capture, canonical verifier-pre, `bench migrate` confirms `tabBEI Billing Schedule` is created |
| **Phase A** Probe + Unblock Ayala Fairview Terraces | 12 | Read-only probe → classify → create `BEBANG FT INC.` parent Company + run `_s181_apply_balance_sheet_template` for its CoA → fix Ayala Fairview defaults to point at parent's accounts → verify save (S1 + S2 L3 scenarios) |
| **Phase B** Audit + Sweep 44 Broken Companies | 10 | Inventory script (44 confirmed) → pre-touch backup → per-Company savepoint fix loop (decision tree: create missing accounts via `_s181_apply_balance_sheet_template` for the company; only null as last resort with active-Salary-Structure precheck — moot per probe but coded defensively) → re-audit → S3 L3 |
| **Phase C** Permanent Atomicity Fix + Validate Hook | 12 | C-1 (full 10-step `auto_provision_company` wrapper with explicit per-step preservation list — no ellipsis) + C-2 (`null_out_dead_default_refs` validate hook with `first_provision_done==1` guard) + C-3 (3 unit tests using `unittest.TestCase` base) + S9 L3 |
| **Phase D-1** Markup Field + 4 BEI Settings Fields | 6 | Add to `bei_settings.json`: `bki_markup_company_owned_percent` (Float, default 2.75), `bki_billing_cron_enabled` (Check, default 0), `bki_sales_debit_to_account`, `bki_sales_naming_series`; SSM-set production values; verify S10 L3 |
| **Phase D-2** Live Coupling Verify + N-8 Default Reconcile | 4 | Test BKI delivery markup applies for all 4 ownership types; reconcile `supply_chain_contracts.py:225` ("Company Owned") vs `sales_location_mapping.py:77` ("Managed Franchise") to one default + reject blank at validate level |
| **Phase D-3** Monthly Billing Extension | 18 | Extend `_create_fee_sales_invoice_for_billing` Monthly Fees branch (party_type/party fix per DM-1) + per-store rate override in `calculate_fees` reading from new `BEI Fee Schedule` + `BEI Fee Carveout` DocTypes + investigate + replace mystery `0.04` rate + gate `_create_gl_entries` to billing_type=Delivery + per-store savepoint inside cron loop + Redis mutex for cron-vs-manual-run + `_assert_bfc_billing_ready()` precondition + VAT template wiring + EWT line for Top 20,000 franchisees + S5/S6/S7 L3 |
| **Phase D-4** Recipient Routing | 4 | Read SI.company from `BEI Settings.jv_revenue_company` (BEI) and `bfc_revenue_company` (BFC); JV → BEI revenue PERMANENTLY; MF/FF → BFC; verify recipient correct in S7 L3 |
| **Phase D-5** FeePreviewPanel + API + Type Drift | 8 | New `@frappe.whitelist() get_fee_schedule()` returning all rates from `BEI Fee Schedule` DocType; new `useFeeSchedule()` TanStack hook; new `<FeePreviewPanel>` slotted between Operations and People sections in `company-detail-dialog.tsx:484-504`; type drift fix (`_fee` vs `_amount`); S4 L3 |
| **Phase E** BFC Dedup + BEBANG FT INC. Cleanup + DRY | 9 | (1) Pick `BEBANG FRANCHISE CORP.` (uppercase, matches abbr=BFC) as canonical; migrate transactions from `Bebang Franchise Corp.` via `frappe.rename_doc`; retire mixed-case duplicate via `disabled=1` + remove from active resolvers. (2) Confirm `BEBANG FT INC.` was created in Phase A; backfill `bir_entity_register_2026-04-13.csv`, `store_entity_mapping_2026-04-14.csv`, `store_buyer_entity_register_2026-03-12.csv` to use `BEBANG FT INC.` (not `Bebang FTE Inc.`). (3) DRY refactor: extract `_NON_STORE_ENTITIES` to module-level constant in `hrms/api/company_master.py` (currently duplicated at lines 507 + 1161). (4) S8 L3. |
| **Pre-deploy Test Maintenance** | 12 | Pre-fix `bei-tasks/tests/e2e/s37-live.spec.ts:2182` (JV markup 2.5 → 2.75) + `bei-tasks/tests/e2e/s27-billing-live.spec.ts:792-802` (rewrite math expectations). Build new `CompanyMasterPage.ts` Page Object. Build new `assertFranchiseFeeSI(store, period, expected)` assertion helper. Add 14 new Python tests (post-sweep regression, markup coupling per type, monthly fee math per type, idempotency, recipient routing, Co-Owned skip, e-com 5% × website-only, rename verifier, teardown verifier, atomicity full-step, hook ordering with first_provision guard). Add 1 new E2E spec `s231-fee-preview.spec.ts` for D-5 UI. Extend `CleanupLedger` with 5 new entry kinds. |
| **Closeout** | 6 | Run all phase verification scripts; tear down test fixtures; canonical verifier post; SUMMARY.md + DEFECTS.md + RUN_STATUS.json; PR creation hrms + bei-tasks; plan + registry update; worktree remove |
| **Total** | **99** | Over 80-unit S089 cap — explicit CEO override 2026-05-02 |

### v2 Authoritative References

- **Source session JSONL** (full conversation transcript with CEO 2026-05-02 — fact-check anything here): `~/.claude/projects/F--Dropbox-Projects-BEI-ERP/3cb6b2f5-4590-412d-a67f-a2d53a0f72f7.jsonl` — resume via `claude --resume 3cb6b2f5-4590-412d-a67f-a2d53a0f72f7`
- **CEO approvals memo** (Layer-1 fact-checked): `data/_CLEANROOM/2026-04-09_franchise_agreements/06_CEO_Approvals_2026-05-02.md`
- **Per-store fee carve-outs registry** (Vista Mall + future): `data/_CLEANROOM/2026-04-09_franchise_agreements/05_Per_Store_Fee_Carveouts.md`
- **v2 design synthesis** (full dependency map + decisions): `output/plan-audit/sprint-231-pricing-coupling-and-defaults-defense/v2_DESIGN_SYNTHESIS.md`
- **Verified blockers** (audit + post-probe): `output/plan-audit/sprint-231-pricing-coupling-and-defaults-defense/verified_blockers.md`
- **Production state probe** (BFC dup, BFI2 missing, 44 broken count, billing_table_exists=false): `output/plan-audit/sprint-231-pricing-coupling-and-defaults-defense/dep_production_state.json`
- **Backend dependency map** (every reader/writer of touched fields): `output/plan-audit/sprint-231-pricing-coupling-and-defaults-defense/dep_backend_map.md`
- **Frontend dependency map** (5 production files touch ownership_type; STORE_PARTNER excluded): `output/plan-audit/sprint-231-pricing-coupling-and-defaults-defense/dep_frontend_map.md`
- **Existing billing flow analysis** (Stream A 90% built, extend not replace): `output/plan-audit/sprint-231-pricing-coupling-and-defaults-defense/dep_existing_billing_flow.md`
- **Schema migration safety** (all 8 changes additive): `output/plan-audit/sprint-231-pricing-coupling-and-defaults-defense/dep_schema_migration.md`
- **Test coverage map** (2 high-risk pre-fixes + 14 new + 1 new E2E + Page Object): `output/plan-audit/sprint-231-pricing-coupling-and-defaults-defense/dep_test_coverage_map.md`

### Hard Deadline

**2026-05-30 (Saturday).** The existing `0 6 1 * *` cron fires next on 2026-06-01 (Sunday). Currently silently erroring (`tabBEI Billing Schedule` not migrated + VAT template empty). After Pre-Phase-0 hotfix lands (~30 min from PR), the June firing is safe (cron disabled). Main sprint then ships at proper pace; flips `bki_billing_cron_enabled=1` only after Finance ratifies dry-run.

### v2 Plan Verification (Layer 1 fact-check, 2026-05-02)

All v2 claims verified against:
- 13 verbatim CEO quotes — matched against chat transcript ✓
- BFC duplicate Companies in production — confirmed via `dep_production_state.json.bfc_check` ✓
- BEBANG FT INC. doesn't exist — confirmed via `dep_production_state.json.fti_check` (all 3 variants false) ✓
- Production markup values (JV 2.75, MF 8.0, FF 8.0, Co-Owned field missing) — confirmed ✓
- 44 broken Companies, 0 with active payroll — confirmed ✓
- 23 JV / 2 CO / 27 MF / 2 FF — confirmed ✓
- `tabBEI Billing Schedule` not migrated — confirmed (`billing_table_exists: false`) ✓
- Vista Mall 2.00% Mgmt — confirmed via Nov 2025 actuals back-calc ✓
- All 18 stores at 7.00% royalty — confirmed ✓
- All cited code lines (`billing.py:1001`, `store.py:7576`, `commissary.py:1077`, `roles.ts:920`) — confirmed via grep ✓
- All cited file paths exist — confirmed ✓

---

## Phase Specifications — v2 Cold-Start Detail (AUTHORITATIVE)

> **Cold-start contract:** every phase below names exact files, line numbers, DocType field schemas, SSM pattern paths, MUST_MODIFY assertions, MUST_CONTAIN strings, verification scripts, and L3 scenarios. An agent reading ONLY this document with zero prior context can execute every decision correctly.

### Pre-Phase-0 — Emergency Cron Enable-Gate Hotfix (4 units)

**Why first:** `hrms.api.billing.scheduled_monthly_billing` is wired in `hrms/hooks.py` `scheduler_events.cron` at `0 6 1 * *`. Today it silently errors because `tabBEI Billing Schedule` is not migrated to production AND `bki_sales_vat_template` is empty. Once main S231 deploys, the cron starts WORKING — so we need a kill-switch in production BEFORE the main sprint ships.

**Tasks:**

**PH-1.** Add `bki_billing_cron_enabled` field to `hrms/hr/doctype/bei_settings/bei_settings.json`:
- Insert after `bki_markup_full_franchise_percent` field (per `dep_schema_migration.md` recommendation: BEI-owned in-tree DocType pattern, NOT custom_field.json)
- Field spec:
  ```json
  {
    "fieldname": "bki_billing_cron_enabled",
    "fieldtype": "Check",
    "label": "BKI Monthly Billing Cron Enabled",
    "default": "0",
    "description": "S231 Pre-Phase-0: kill-switch for `scheduled_monthly_billing` cron. Default 0 = cron is no-op. Finance flips to 1 only after ratifying dry-run output."
  }
  ```
- Also append `"bki_billing_cron_enabled"` to the field list at top of `bei_settings.json`.
- **MUST_MODIFY:** `hrms/hr/doctype/bei_settings/bei_settings.json`
- **MUST_CONTAIN:** `"bki_billing_cron_enabled"`, `"default": "0"`

**PH-2.** Gate `scheduled_monthly_billing` in `hrms/api/billing.py:1426`:
```python
def scheduled_monthly_billing():
    """S231 Pre-Phase-0: gated by BEI Settings.bki_billing_cron_enabled."""
    if not frappe.db.get_single_value("BEI Settings", "bki_billing_cron_enabled"):
        return
    return generate_monthly_billing()  # existing call signature
```
- **MUST_MODIFY:** `hrms/api/billing.py`
- **MUST_CONTAIN:** `"S231 Pre-Phase-0"`, `"bki_billing_cron_enabled"`

**PH-3.** Ship as separate PR (PR-1 of the sprint), merge + deploy fast (~30 min). Sam reviews + merges + deploys; agent does NOT proceed to Phase 0 until production reports `bki_billing_cron_enabled=0` is live.

**Verification (post-deploy via SSM):**
```python
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
val = frappe.db.get_single_value("BEI Settings", "bki_billing_cron_enabled")
assert val == 0, f"Expected 0, got {val}"
print("PRE-PHASE-0 GATE LIVE")
```

Capture proof to `output/s231/PRE_HOTFIX_DEPLOY_LOG.md`.

---

### Phase 0 — Boot (4 units, unchanged from v1 + DocType migration)

Per v1 Phase 0 with one addition: confirm `bench migrate` runs and creates the `tabBEI Billing Schedule` table in production (currently `billing_table_exists: false` per probe).

**0-1 through 0-5:** as v1 (worktree spawn, baseline, canonical verifier-pre, MUST_MODIFY assertions, verify_phase0.py).

**0-6 (NEW):** Confirm `tabBEI Billing Schedule` table exists post-migrate via SSM:
```python
exists = frappe.db.sql("SHOW TABLES LIKE 'tabBEI Billing Schedule'")
assert exists, "tabBEI Billing Schedule not migrated"
```

---

### Phase A — Probe + Unblock Ayala Fairview Terraces + Create BEBANG FT INC. Parent (12 units)

**Major v2 change:** v1 assumed BEBANG FT INC. existed as a Company. Production probe confirmed it does NOT (`fti_check.BEBANG FT INC._exists: false`). Phase A v2 must CREATE it from scratch as a parent legal entity Company with full CoA before fixing Ayala Fairview's defaults.

**Tasks:**

**A-1.** Read-only probe (as v1) — confirm Ayala Fairview state + missing-refs map. **MUST_MODIFY:** `scripts/s231_probe_ayala_fairview.py`, `output/s231/verification/ayala_fairview_probe.json`.

**A-2.** Classify per v1 + ADD: confirm probe shows `parent_company` of `AYALA FAIRVIEW TERRACES - BEBANG FT INC.` is empty/missing/non-existent. Document in `output/s231/verification/ayala_fairview_classification.md`.

**A-3 (NEW).** Create `BEBANG FT INC.` parent Company via SSM. Use the canonical seed CSV row 12 for source data (`hrms/data_seed/company_register_2026-04-14.csv`):
- name: `BEBANG FT INC.`
- abbr: `BFI2`
- tax_id: `663-440-106-00000`
- entity_category: `Holding Company` (or whatever matches the canonical model for "Store Corporation")
- default_currency: `PHP`
- country: `Philippines`
- parent_company: `Bebang Enterprise Inc.` (per `parent_should_be` column in CSV)

```python
# Via SSM (bench python):
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

if frappe.db.exists("Company", "BEBANG FT INC."):
    print("BEBANG FT INC. already exists — skipping creation")
else:
    co = frappe.new_doc("Company")
    co.company_name = "BEBANG FT INC."
    co.abbr = "BFI2"
    co.country = "Philippines"
    co.default_currency = "PHP"
    co.tax_id = "663-440-106-00000"
    co.parent_company = "Bebang Enterprise Inc."  # exact match required — verify via probe
    co.flags.ignore_permissions = True
    co.insert()
    # auto_provision_company will fire via on_update hook and run S181 templates for CoA
    frappe.db.commit()

print(f"Created: {frappe.db.exists('Company', 'BEBANG FT INC.')}")
print(f"first_provision_done: {frappe.db.get_value('Company', 'BEBANG FT INC.', 'first_provision_done')}")
```

**Sentry observability:** This invokes `auto_provision_company` which already calls `set_backend_observability_context(module='company', action='auto_provision_company', mutation_type='create')` per existing wiring.

**MUST_MODIFY:** `scripts/s231_create_bebang_ft_inc_parent.py`, `output/s231/verification/bebang_ft_inc_creation_log.json`
**MUST_CONTAIN (in log):** `"company": "BEBANG FT INC."`, `"abbr": "BFI2"`, `"first_provision_done": 1`

**A-4.** Verify the creation produced a complete CoA via `_s181_apply_balance_sheet_template` + `_s181_apply_sales_template`:
```python
# Confirm key accounts exist:
required = [
    f"{n} - BFI2" for n in
    ["Stock In Hand", "Payroll Payable", "Employee Advances",
     "Cash on Hand", "Debtors", "Creditors", "Cost of Goods Sold",
     "IN-STORE SALES", "Round Off"]
]
missing = [a for a in required if not frappe.db.exists("Account", a)]
assert not missing, f"Missing accounts post-provision: {missing}"
```

If anything is missing, run `retry_provision_company('BEBANG FT INC.')` and re-verify. STOP if still missing.

**A-5.** Now fix Ayala Fairview Terraces. The classification step (A-2) showed which approach (retry_provision OR null defaults). Apply per v1 A-3 logic. Capture before/after to `output/s231/verification/ayala_fairview_fix_log.json`.

**A-6 (NEW).** Verify Ayala Fairview's `parent_company` is now correctly set to `BEBANG FT INC.` if not already:
```python
ayala = frappe.db.get_value("Company", "AYALA FAIRVIEW TERRACES - BEBANG FT INC.", "parent_company")
if ayala != "BEBANG FT INC.":
    frappe.db.set_value("Company", "AYALA FAIRVIEW TERRACES - BEBANG FT INC.", "parent_company", "BEBANG FT INC.")
    frappe.db.commit()
```

**A-7.** Run S1 + S2 L3 scenarios (browser, real session) — capture to `output/l3/s231/form_submissions.json`.

**Verification script (`output/s231/verify_phaseA.py`):**
```python
import os, json
checks = []
# Probe ran
checks.append(("probe_ran", os.path.exists("output/s231/verification/ayala_fairview_probe.json")))
# BEBANG FT INC. exists post-creation (verify via SSM probe output)
log = json.load(open("output/s231/verification/bebang_ft_inc_creation_log.json"))
checks.append(("bfi2_company_created", log.get("company") == "BEBANG FT INC."))
checks.append(("bfi2_abbr_correct", log.get("abbr") == "BFI2"))
checks.append(("bfi2_provisioned", log.get("first_provision_done") == 1))
# Ayala Fairview fix applied
checks.append(("ayala_fix_log", os.path.exists("output/s231/verification/ayala_fairview_fix_log.json")))
# S1 + S2 passed
fs = json.load(open("output/l3/s231/form_submissions.json"))
s1 = next((s for s in fs if s.get("scenario") == "S1"), None)
s2 = next((s for s in fs if s.get("scenario") == "S2"), None)
checks.append(("S1_passed", s1 and s1.get("status_code") == 200))
checks.append(("S2_passed", s2 and s2.get("status_code") == 200))

fail = [c for c, ok in checks if not ok]
print("PASS" if not fail else f"FAIL: {fail}")
exit(0 if not fail else 1)
```

---

### Phase B — Audit + Sweep 44 Broken Companies (10 units)

**v2 change:** count is 44 not 49 (production probe confirmed). Zero have active Salary Structures so payroll-cascade risk is moot — null is safe.

Per v1 Phase B with the count update. The decision tree from v1 still applies:
1. If first_provision_done=0 OR all 15 fields broken → `retry_provision_company`
2. Otherwise null only the broken fields
3. Log to DEFECTS for manual review if both fail

Tasks B-1 through B-5 unchanged from v1 plus:
- **B-1 update:** `scripts/s231_audit_broken_defaults.py` should report `broken_companies_count` matches the `dep_production_state.json` ground truth of 44.
- **B-3 update:** Per `dep_production_state.json.broken_companies_with_active_payroll_count: 0`, the active-Salary-Structure precheck is moot but include defensively for future drift.

---

### Phase C — Permanent Atomicity Fix (Full 10-Step) + Validate Hook (12 units)

**v2 changes:** widen atomicity wrapper to cover Steps 0-9 of `auto_provision_company` (not just Step 0); explicit MUST_CONTAIN list of all S181/S184 helper calls (no `# ... S181 templates ...` ellipsis); test class uses `unittest.TestCase` base.

**Tasks:**

**C-1 (REVISED).** Atomicity wrapper covering ALL 10 steps. Read `hrms/overrides/company.py:592-723` end-to-end. Capture pre_state for ALL DEFAULT_FIELDS_TO_TRACK BEFORE any step. On any exception, restore pre_state via `db.set_value(..., update_modified=False)`. Then sentinel `first_provision_done` only flips if ALL steps succeeded.

**Required helper preservation list** (must appear via MUST_CONTAIN in the modified function):
```
_s181_apply_sales_template(doc)
_s181_apply_balance_sheet_template(doc)
_s181_set_default_accounts(doc)
_s181_ensure_warehouse(doc)
_s181_ensure_cost_center(doc)
_s181_ensure_bki_customer(doc)
_s184_create_default_bank_accounts(doc)
_s184_assign_adms_device(doc)
_s184_pull_gps(doc)
frappe.local.flags.ignore_root_company_validation = True
```

All 10 calls + the flag must appear in the modified function. NO ellipsis. NO comment-as-placeholder.

**MUST_MODIFY:** `hrms/overrides/company.py`
**MUST_CONTAIN:** `"S231-C1"`, `DEFAULT_FIELDS_TO_TRACK`, all 10 helper calls listed above, `ignore_root_company_validation`, the `pre_state` restore loop, the `invalid_after` clear loop.

**C-2 (UPDATED).** Add `null_out_dead_default_refs` validate hook to `hrms/overrides/company.py`. Wire into `hrms/hooks.py` `Company.validate` chain. **Hook ordering: `null_out_dead_default_refs` FIRST, then `validate_default_accounts`** (per dep_backend_map confirmation).

```python
# hrms/hooks.py
"Company": {
    "validate": [
        "hrms.overrides.company.null_out_dead_default_refs",  # S231-C2 — runs FIRST
        "hrms.overrides.company.validate_default_accounts",
    ],
    "on_update": [...],  # unchanged
    ...
}
```

Add `first_provision_done==1` guard to the function body — don't null fields on a fresh Company that's mid-provisioning:

```python
def null_out_dead_default_refs(doc, method=None):
    """S231-C2: defense-in-depth. Null any default_*/round_off_*/etc field
    whose referenced Account/Cost Center no longer exists.
    Guard: only operates on Companies where first_provision_done=1, so we
    don't clobber fields auto_provision_company is mid-setting on a fresh save.
    """
    if not doc.get("first_provision_done"):
        return
    DEFAULT_FIELDS_TO_TRACK = [...]  # same list as C-1
    cleared = []
    for f in DEFAULT_FIELDS_TO_TRACK:
        v = doc.get(f)
        if v:
            target_dt = "Cost Center" if "cost_center" in f else "Account"
            if not frappe.db.exists(target_dt, v):
                doc.set(f, None)
                cleared.append((f, v))
    if cleared:
        frappe.log_error(
            title=f"S231-C2: cleared {len(cleared)} dead default refs on {doc.name}",
            message=str(cleared),
        )
```

**MUST_MODIFY:** `hrms/overrides/company.py`, `hrms/hooks.py`
**MUST_CONTAIN (hooks.py):** `"hrms.overrides.company.null_out_dead_default_refs"` BEFORE `"hrms.overrides.company.validate_default_accounts"` in the Company.validate list

**C-3 (REVISED).** Unit tests with `unittest.TestCase` base:

```python
# hrms/tests/test_s231_atomicity.py
import unittest
import frappe
from unittest.mock import patch

class TestS231Atomicity(unittest.TestCase):
    def test_partial_create_default_accounts_failure_rolls_back_field_writes(self):
        ...
    def test_invalid_after_check_clears_dead_refs(self):
        ...
    def test_validate_hook_clears_dead_refs_on_save(self):
        ...
    def test_validate_hook_skips_when_first_provision_pending(self):
        # NEW: confirm first_provision_done=0 means hook is no-op
        ...
```

**MUST_MODIFY:** `hrms/tests/test_s231_atomicity.py`
**MUST_CONTAIN:** `"class TestS231Atomicity(unittest.TestCase)"`, all 4 test method names

Run via: `bench --site hq.bebang.ph run-tests --module hrms.tests.test_s231_atomicity --verbose`. Expected: 4 PASS.

---

### Phase D-1 — Markup Field + 4 BEI Settings Fields (6 units)

**Tasks:**

**D1-1.** Add 4 fields to `hrms/hr/doctype/bei_settings/bei_settings.json`. Match the existing `bki_markup_jv_percent` pattern (Float, precision 4):

```json
{
  "fieldname": "bki_markup_company_owned_percent",
  "fieldtype": "Float",
  "label": "BKI Markup % — Company Owned",
  "precision": "4",
  "default": "2.75",
  "description": "S231 D-1: BKI intercompany markup applied to deliveries to Company-owned stores. Per CEO 2026-05-02: same rate as JV (2.75%)."
}
```

Plus `bki_billing_cron_enabled` (already added in Pre-Phase-0), `bki_sales_debit_to_account` (Link → Account), `bki_sales_naming_series` (Data).

**MUST_MODIFY:** `hrms/hr/doctype/bei_settings/bei_settings.json`
**MUST_CONTAIN:** all 4 fieldnames listed above + correct types/defaults

**D1-2.** SSM-set production values post-deploy:
```python
frappe.db.set_single_value("BEI Settings", "bki_markup_company_owned_percent", 2.75)
frappe.db.set_single_value("BEI Settings", "bki_sales_vat_template", "Philippines Tax - 12% Output VAT - BKI")
# Note: bki_sales_debit_to_account + bki_sales_naming_series get set by Finance per their data
frappe.db.commit()
```
Capture to `output/s231/verification/markup_settings_after.json`.

**MUST_MODIFY:** `output/s231/verification/markup_settings_after.json`
**MUST_CONTAIN:** all 4 field values verified live in production

---

### Phase D-2 — Live Coupling Verify + N-8 Default Reconcile (4 units)

**D2-1.** Test BKI delivery markup applies for all 4 ownership types — pick one representative store per type from `dep_production_state.json.stores_by_owner`. Simulate Material Issue Stock Entry → call `create_draft_store_sale_invoices` → verify SI rate = base × (1 + markup_rate).

**Test stores:**
- Company Owned: pick from `dep_production_state.json.stores_by_owner["Company Owned"]` (2 stores listed)
- JV: `AYALA FAIRVIEW TERRACES - BEBANG FT INC.` (post Phase A fix)
- Managed Franchise: pick from `stores_by_owner["Managed Franchise"]` (27 stores)
- Full Franchise: pick from `stores_by_owner["Full Franchise"]` (2 stores: Ever Gotesco, THE GRID)

**MUST_MODIFY:** `scripts/s231_verify_markup_coupling.py`, `output/s231/verification/markup_coupling_test.json`

**D2-2 (N-8 fix).** Reconcile silent ownership-type default inconsistency:
- `hrms/utils/supply_chain_contracts.py:225` — defaults blank to `"Company Owned"`
- `hrms/utils/sales_location_mapping.py:77` — defaults blank to `"Managed Franchise"`

Choose `"Company Owned"` as canonical default (matches probe-confirmed convention). Update `sales_location_mapping.py:77`. Add a `validate` rule on Company that rejects empty `store_ownership_type` for entity_category='Store' Companies (forces explicit classification at save time).

**MUST_MODIFY:** `hrms/utils/sales_location_mapping.py`
**MUST_CONTAIN:** `"Company Owned"` as the default; remove `"Managed Franchise"` default

---

### Phase D-3 — Monthly Billing Extension (18 units)

**v2: extend existing `_create_fee_sales_invoice_for_billing` (line 525) — DO NOT add a parallel function.**

**Tasks:**

**D3-1.** Investigate the mystery `0.04` rate in `hrms/api/billing.py calculate_fees`. Read the function. Document its purpose. Replace with a config-driven rate. Output: `output/s231/verification/mystery_004_investigation.md`.

**D3-2.** Create new DocType `BEI Fee Schedule` keyed by `(ownership_type, fee_type)`:
```
hrms/hr/doctype/bei_fee_schedule/bei_fee_schedule.json
```
Fields: `ownership_type` (Select: "Company Owned"/"JV"/"Managed Franchise"/"Full Franchise"), `fee_type` (Select: "Royalty"/"Marketing"/"Management"/"E-commerce"), `rate` (Float prec 4), `base_field` (Select: "gross_sales"/"net_sales"/"website_sales"/"online_sales"), `recipient_company` (Link → Company), `applies_to` (Data).

**MUST_MODIFY:** the JSON file + a new `bei_fee_schedule.py` controller

**D3-3.** Create new DocType `BEI Fee Carveout` keyed by `(store, fee_type)`:
```
hrms/hr/doctype/bei_fee_carveout/bei_fee_carveout.json
```
Fields: `store` (Link → Department, matches existing schema), `fee_type` (Select), `rate_override` (Float prec 4), `effective_from` (Date), `notes` (Small Text).

**D3-4.** Seed scripts:
- `hrms/on_demand/s231_seed_fee_schedule.py` — seeds the 9 (ownership × fee) rows. Skip Co-Owned (no fees). JV: Marketing 5% gross, E-com 5% website. MF: Royalty 7% net_ex_vat, Marketing 5% net_ex_vat, Management 2.5% gross, E-com 5% website. FF: Royalty 7% net_ex_vat, Marketing 5% net_ex_vat, E-com 5% website.
- `hrms/on_demand/s231_seed_fee_carveouts.py` — seeds Vista Mall row (store="Vista Mall", fee_type="Management", rate_override=0.02, notes="Per CEO directive 2026-05-02; reason: Vista Mall handles own accounting + taxes").

**D3-5.** Extend `calculate_fees` in `hrms/api/billing.py` to read from BEI Fee Schedule + apply carveouts:
```python
def calculate_fees(billing):
    """S231 D-3: rates from BEI Fee Schedule (per ownership_type × fee_type) +
    per-store overrides from BEI Fee Carveout. Replaces hardcoded 0.07/0.025/0.05/0.04."""
    ot = billing.store_type  # JV / Managed Franchise / Full Franchise / Company Owned
    if ot == "Company Owned":
        return  # no fees
    schedules = frappe.get_all("BEI Fee Schedule",
        filters={"ownership_type": ot},
        fields=["fee_type", "rate", "base_field", "recipient_company"])
    for s in schedules:
        # Check carveout first
        co = frappe.db.get_value("BEI Fee Carveout",
            {"store": billing.store, "fee_type": s["fee_type"]}, "rate_override")
        rate = co if co is not None else s["rate"]
        base = billing.get(s["base_field"]) or 0
        amount = round(base * rate, 2)
        # Set the right field on billing
        field_map = {"Royalty": "royalty_fee", "Marketing": "marketing_fee",
                     "Management": "management_fee", "E-commerce": "ecommerce_fee"}
        billing.set(field_map[s["fee_type"]], amount)
```

**MUST_MODIFY:** `hrms/api/billing.py`
**MUST_CONTAIN:** `"S231 D-3"`, `BEI Fee Schedule` query, `BEI Fee Carveout` carveout-first lookup, removal of hardcoded `0.07`, `0.025`, `0.05`, `0.04`

**D3-6.** Extend `_create_fee_sales_invoice_for_billing` (line 525) with Monthly Fees branch + DM-1 fix (party_type/party on AR rows) + VAT template + EWT line per BIR Form 2307:

```python
def _create_fee_sales_invoice_for_billing(billing):
    """S231 D-3 + DM-1: extended for Monthly Fees billing_type with
    party_type/party on AR rows + VAT template + EWT for Top 20,000 franchisees."""
    ...
    if billing.billing_type == "Monthly Fees":
        # Per ownership type, route SI to BEI or BFC company
        recipient = _resolve_fee_recipient_company(billing.store_type)  # see D-4
        si.company = recipient
        si.taxes_and_charges = frappe.db.get_single_value("BEI Settings",
            "bfc_sales_vat_template" if recipient == "BEBANG FRANCHISE CORP."
            else "jv_sales_vat_template")
        # ... fee line items ...
        # DM-1 fix: party on debit_to row
        si.debit_to_party_type = "Customer"
        si.debit_to_party = billing.customer  # via resolve_store_buyer_entity
        # EWT line if franchisee is Top 20,000
        if frappe.db.get_value("Customer", billing.customer, "is_top_20000_corp"):
            ewt_rate = frappe.db.get_single_value("BEI Settings", "default_ewt_rate")
            si.append("taxes", {
                "charge_type": "Actual",
                "account_head": frappe.db.get_single_value("BEI Settings", "ewt_payable_account"),
                "description": f"EWT {ewt_rate}% (BIR Form 2307)",
                "rate": -abs(ewt_rate),
            })
    ...
```

**MUST_MODIFY:** `hrms/api/billing.py`
**MUST_CONTAIN:** `"if billing.billing_type == \"Monthly Fees\""`, `"_resolve_fee_recipient_company"`, `"DM-1 fix"`, `"BIR Form 2307"`

**D3-7.** Gate `_create_gl_entries` in `hrms/hr/doctype/bei_billing_schedule/bei_billing_schedule.py` to billing_type='Delivery' only (prevent double-posting once SI path lights up for Monthly Fees):

```python
def _create_gl_entries(self):
    """S231 D-3: gate to Delivery billing only. Monthly Fees post via SI path."""
    if self.billing_type != "Delivery":
        return
    # ... existing inline JE logic ...
```

**MUST_MODIFY:** `hrms/hr/doctype/bei_billing_schedule/bei_billing_schedule.py`
**MUST_CONTAIN:** `"S231 D-3: gate to Delivery billing only"`, `"if self.billing_type != \"Delivery\""`

**D3-8.** Add per-store savepoint in `generate_monthly_billing` loop (`hrms/api/billing.py:1001`):

```python
def generate_monthly_billing(...):
    ...
    for store in stores:
        try:
            frappe.db.savepoint(f"s231_bill_{store}")
            # existing per-store billing logic
            frappe.db.release_savepoint(f"s231_bill_{store}")
        except Exception as e:
            frappe.db.rollback(save_point=f"s231_bill_{store}")
            failed_stores.append({"store": store, "error": str(e)})
            frappe.log_error(...)
```

**MUST_MODIFY:** `hrms/api/billing.py`
**MUST_CONTAIN:** `"frappe.db.savepoint(f\"s231_bill_"`, `"failed_stores"`

**D3-9.** Add Redis concurrency mutex (cron + manual run can't collide):
```python
def generate_monthly_billing(billing_period=None, ...):
    period = billing_period or _previous_month()
    lock_key = f"s231_billing_lock_{period}"
    if not frappe.cache().setnx(lock_key, 1):
        frappe.log_error(f"S231 billing already running for {period}; manual call skipped")
        return {"skipped": True, "reason": "concurrent_run"}
    try:
        frappe.cache().expire(lock_key, 3600)  # 1 hour TTL
        # existing logic
    finally:
        frappe.cache().delete_value(lock_key)
```

**MUST_MODIFY:** `hrms/api/billing.py`
**MUST_CONTAIN:** `"setnx(lock_key, 1)"`, `"s231_billing_lock_"`

**D3-10.** Add `_assert_bfc_billing_ready()` precondition function. Throws if BFC OR booklet/VAT registration not configured:
```python
def _assert_bfc_billing_ready():
    """S231 D-3: precondition for BFC franchise SI creation."""
    if not frappe.db.get_single_value("BEI Settings", "bfc_or_active"):
        frappe.throw("BFC OR booklet not active — Finance must flip bfc_or_active in BEI Settings")
    if not frappe.db.get_single_value("BEI Settings", "bfc_vat_registration_active"):
        frappe.throw("BFC VAT registration not active — Finance must flip bfc_vat_registration_active in BEI Settings")
    if not frappe.db.get_single_value("BEI Settings", "bfc_sales_naming_series"):
        frappe.throw("BFC sales naming series not set — Finance must set bfc_sales_naming_series")
```

Add 3 fields to `bei_settings.json`: `bfc_or_active` (Check, default 0), `bfc_vat_registration_active` (Check, default 0), `bfc_sales_naming_series` (Data).

**MUST_MODIFY:** `hrms/api/billing.py`, `hrms/hr/doctype/bei_settings/bei_settings.json`
**MUST_CONTAIN:** `"_assert_bfc_billing_ready"`, all 3 BEI Settings fields

**D3-11.** Sentry observability — `set_backend_observability_context` calls in:
- `generate_monthly_billing` (extended) — `module="billing", action="generate_monthly_billing", mutation_type="create"`
- `_create_fee_sales_invoice_for_billing` (extended) — `module="billing", action="create_fee_si", mutation_type="create"`

**MUST_CONTAIN:** `set_backend_observability_context(module="billing"` in both functions

**D3-12.** L3 scenarios S5, S6, S7 — capture form_submissions.json + api_mutations.json + state_verification.json.

**Verification:** `output/s231/verify_phaseD3.py` checks all D3-1 through D3-12 outputs + L3 scenarios.

---

### Phase D-4 — Recipient Routing (4 units)

**D4-1.** Add 2 fields to `bei_settings.json`:
- `jv_revenue_company` (Link → Company, default "Bebang Enterprise Inc." — needs CEO confirm of exact case)
- `bfc_revenue_company` (Link → Company, default "BEBANG FRANCHISE CORP." — uppercase canonical per CEO 2026-05-02)

**D4-2.** Implement `_resolve_fee_recipient_company`:
```python
def _resolve_fee_recipient_company(ownership_type: str) -> str:
    """S231 D-4: recipient by type. Per CEO 2026-05-02:
    JV → BEI revenue PERMANENTLY (not BFC).
    Managed/Full Franchise → BFC revenue (collected by BEI as agent during interim
    per Collection Agent Letter)."""
    if ownership_type == "JV":
        return frappe.db.get_single_value("BEI Settings", "jv_revenue_company")
    if ownership_type in ("Managed Franchise", "Full Franchise"):
        return frappe.db.get_single_value("BEI Settings", "bfc_revenue_company")
    if ownership_type == "Company Owned":
        return None  # no fee billing
    raise ValueError(f"S231 D-4: unknown ownership_type {ownership_type!r}")
```

**MUST_MODIFY:** `hrms/api/billing.py`, `hrms/hr/doctype/bei_settings/bei_settings.json`
**MUST_CONTAIN:** `"_resolve_fee_recipient_company"`, `"jv_revenue_company"`, `"bfc_revenue_company"`

---

### Phase D-5 — FeePreviewPanel + API + Type Drift (8 units)

**D5-1.** New whitelisted API `get_fee_schedule()`:
```python
@frappe.whitelist()
def get_fee_schedule():
    """S231 D-5: returns fee schedule for FeePreviewPanel UI.
    Reads BEI Fee Schedule + BEI Fee Carveout DocTypes (single source of truth)."""
    set_backend_observability_context(module="billing", action="get_fee_schedule", mutation_type="read")
    schedules = frappe.get_all("BEI Fee Schedule",
        fields=["ownership_type", "fee_type", "rate", "base_field", "recipient_company"])
    carveouts = frappe.get_all("BEI Fee Carveout",
        fields=["store", "fee_type", "rate_override", "effective_from", "notes"])
    markup_rates = {
        "Company Owned": frappe.db.get_single_value("BEI Settings", "bki_markup_company_owned_percent"),
        "JV": frappe.db.get_single_value("BEI Settings", "bki_markup_jv_percent"),
        "Managed Franchise": frappe.db.get_single_value("BEI Settings", "bki_markup_managed_franchise_percent"),
        "Full Franchise": frappe.db.get_single_value("BEI Settings", "bki_markup_full_franchise_percent"),
    }
    return {"schedules": schedules, "carveouts": carveouts, "markup_rates": markup_rates}
```

Add to `hrms/api/billing.py`. **MUST_CONTAIN:** `"get_fee_schedule"`, `set_backend_observability_context(module="billing"`

**D5-2.** New TanStack Query hook `useFeeSchedule()` in `bei-tasks/lib/queries/billing.ts`:
```typescript
export function useFeeSchedule() {
  return useQuery({
    queryKey: ["fee-schedule"],
    queryFn: async () => {
      const res = await frappeApiCall<FeeScheduleResponse>("hrms.api.billing.get_fee_schedule");
      return res.message;
    },
  });
}
```

**MUST_MODIFY:** `bei-tasks/lib/queries/billing.ts` (or wherever queries live; verify path with frontend dep map)

**D5-3.** New `<FeePreviewPanel>` component in `bei-tasks/components/company-master/fee-preview-panel.tsx` with:
- `data-testid="fee-preview-panel"`
- Reads from `useFeeSchedule()` hook
- Renders markup rate + fee schedule table per ownership_type
- Renders carveout note if `useFeeSchedule().carveouts` has match for current store

**MUST_MODIFY:** `bei-tasks/components/company-master/fee-preview-panel.tsx`
**MUST_CONTAIN:** `data-testid="fee-preview-panel"`, `useFeeSchedule`, all 4 ownership types

**D5-4.** Wire into `bei-tasks/app/dashboard/bd/companies/company-detail-dialog.tsx` between OperationsSection and PeopleSection (line ~484-504 per frontend dep map):

```tsx
<OperationsSection ... />
<FeePreviewPanel ownershipType={detail.store_ownership_type} storeName={detail.name} />
<PeopleSection ... />
```

**MUST_MODIFY:** `bei-tasks/app/dashboard/bd/companies/company-detail-dialog.tsx`
**MUST_CONTAIN:** `<FeePreviewPanel`, `ownershipType=`, `storeName=`

**D5-5.** Type drift fix — reconcile `_fee` vs `_amount` suffixes:
- `bei-tasks/types/billing.ts` uses `_fee` suffixes (`royalty_fee`, etc.)
- `bei-tasks/hooks/use-accounting.ts:68-82` uses `_amount` suffixes (`royalty_amount`, etc.)
- Decision: keep `_fee` (matches backend DocType field names per `bei_billing_schedule.json`); update `use-accounting.ts` to match.

**MUST_MODIFY:** `bei-tasks/hooks/use-accounting.ts`
**MUST_CONTAIN:** zero references to `royalty_amount`, `marketing_fee_amount`, `management_fee_amount`, `ecommerce_fee_amount`

**D5-6.** L3 scenario S4 — capture to `output/l3/s231/form_submissions.json`.

---

### Phase E — BFC Dedup + BEBANG FT INC. Cleanup + DRY (9 units)

**v2 changes:** added BFC dedup + `_NON_STORE_ENTITIES` DRY refactor.

**E-1.** Inventory `Bebang FTE Inc.` references (as v1) + ALSO inventory `Bebang Franchise Corp.` (mixed case) references that need to retire to `BEBANG FRANCHISE CORP.`:
```bash
grep -rln "Bebang FTE Inc\.\|BEBANG FTE INC\." . > output/s231/verification/fte_references.txt
grep -rln "Bebang Franchise Corp\." --include="*.py" --include="*.ts" --include="*.csv" --include="*.md" . > output/s231/verification/bfc_mixedcase_references.txt
```
Plus production DB scan for both.

**E-2.** Rename in seed CSVs (as v1) — `Bebang FTE Inc.` → `BEBANG FT INC.` in 4 files.

**E-3 (NEW).** BFC dedup in production via SSM:
```python
# Migrate transactions from "Bebang Franchise Corp." → "BEBANG FRANCHISE CORP." (canonical uppercase)
canonical = "BEBANG FRANCHISE CORP."
duplicate = "Bebang Franchise Corp."

# Pre-check
assert frappe.db.exists("Company", canonical), f"Canonical {canonical} missing"
assert frappe.db.exists("Company", duplicate), f"Duplicate {duplicate} missing"

# Get transaction count under duplicate (informational)
si_count = frappe.db.count("Sales Invoice", {"company": duplicate})
gl_count = frappe.db.count("GL Entry", {"company": duplicate})
print(f"Transactions under duplicate: SI={si_count}, GL={gl_count}")

# Use frappe.rename_doc with merge=True to merge duplicate into canonical
# This automatically updates all linked documents
frappe.rename_doc("Company", duplicate, canonical, merge=True, force=True)
frappe.db.commit()
```

**HARD BLOCKER:** if `si_count + gl_count > 100`, STOP and ask CEO. (Source: CEO directive 2026-05-02 — naming canonicalization should not silently rewrite >100 records without review.)

**MUST_MODIFY:** `scripts/s231_dedup_bfc.py`, `output/s231/verification/bfc_dedup_log.json`
**MUST_CONTAIN (log):** `"canonical": "BEBANG FRANCHISE CORP."`, `"duplicate_retired": "Bebang Franchise Corp."`, `"transactions_migrated": N`

**E-4.** Bebang FTE Inc. references rename in production records (as v1 E-3) — same pattern but for FTE.

**E-5 (NEW).** DRY refactor `_NON_STORE_ENTITIES`:
- Currently duplicated at `hrms/api/company_master.py:507` AND `hrms/api/company_master.py:1161`
- Extract to module-level constant near top of file (after imports)
- Update both call sites to reference the constant
- **MUST_MODIFY:** `hrms/api/company_master.py`
- **MUST_CONTAIN:** exactly ONE `_NON_STORE_ENTITIES =` definition (grep -c == 1)

**E-6.** Verify (as v1) — re-run inventory greps. Result must show zero `Bebang FTE Inc.` and zero `Bebang Franchise Corp.` references in code. DB scan must show both retired.

---

### Pre-deploy Test Maintenance (12 units)

**TM-1.** Pre-fix `bei-tasks/tests/e2e/s37-live.spec.ts:2182`: change hardcoded `custom_markup_percent: 2.5` to read from `useFeeSchedule()` markup_rates.JV (= 2.75 post-D-1). Test commits the new expected value 2.75 inline with a comment referencing S231 D-1.
- **MUST_MODIFY:** `bei-tasks/tests/e2e/s37-live.spec.ts`
- **MUST_CONTAIN:** `"S231 D-1"`, `2.75`

**TM-2.** Rewrite `bei-tasks/tests/e2e/s27-billing-live.spec.ts:792-802`: replace hardcoded fee math (`royalty_fee=78400`, etc.) with computed expected values based on `useFeeSchedule()`.
- **MUST_MODIFY:** `bei-tasks/tests/e2e/s27-billing-live.spec.ts`
- **MUST_CONTAIN:** `"S231 D-3"`, removal of hardcoded fee literals

**TM-3.** Build `bei-tasks/tests/e2e/pages/CompanyMasterPage.ts` Page Object (planned but doesn't exist per dep_test_coverage_map):
- Methods: `openCompany(name)`, `clickEditOperationsSection()`, `selectOwnershipType(type)`, `clickSave()`, `getFeePreviewMarkup()`, `getFeePreviewFees()`
- **MUST_MODIFY:** new file at `bei-tasks/tests/e2e/pages/CompanyMasterPage.ts`

**TM-4.** Build `bei-tasks/tests/e2e/assertions/franchise-fee-si.ts`:
- Function: `assertFranchiseFeeSI(store, period, expected: { royalty?, marketing?, management?, ecommerce? })`
- Reads SI via `frappeReadback.queryDocs` filtering by company + customer + posting_date
- Asserts each fee line item matches expected
- **MUST_MODIFY:** new file at `bei-tasks/tests/e2e/assertions/franchise-fee-si.ts`

**TM-5.** Extend `CleanupLedger` with 5 new entry kinds (per dep_test_coverage_map): `company-create`, `billing-schedule-create`, `bei-sales-daily-create`, `pos-sales-create`, `bei-settings-mutate`. Each gets a reverse handler.
- **MUST_MODIFY:** `bei-tasks/tests/e2e/fixtures/cleanup.ts` (verify exact path)
- **MUST_CONTAIN:** all 5 new kind strings

**TM-6.** Add 14 new Python unit tests under `hrms/tests/test_s231_*.py`:
1. `test_post_sweep_44_companies_have_valid_defaults` (reads `s204_all_stores.json` fixture)
2. `test_markup_coupling_company_owned`
3. `test_markup_coupling_jv`
4. `test_markup_coupling_managed_franchise`
5. `test_markup_coupling_full_franchise`
6. `test_monthly_billing_jv_marketing_5pct`
7. `test_monthly_billing_mf_full_fee_set`
8. `test_monthly_billing_ff_no_management_fee`
9. `test_monthly_billing_co_owned_skipped`
10. `test_monthly_billing_idempotent_per_period`
11. `test_recipient_routing_jv_to_bei`
12. `test_recipient_routing_mf_to_bfc`
13. `test_ecom_fee_uses_website_sales_only` (NOT online_sales which includes FoodPanda/Grab)
14. `test_vista_mall_carveout_2pct_management`
- All use `unittest.TestCase` base
- **MUST_MODIFY:** new files

**TM-7.** Add new E2E spec `bei-tasks/tests/e2e/specs/s231-fee-preview.spec.ts`:
- Uses `loggedInAsCEO` fixture
- Uses `CompanyMasterPage` Page Object
- Tests S4: open company → edit ownership → preview updates → save → reopen → verifies persisted
- Uses `cleanupLedger` fixture for any state mutations
- **MUST_MODIFY:** new file
- **MUST_CONTAIN:** `loggedInAsCEO`, `CompanyMasterPage`, `cleanupLedger`, no `page.request` / `fetch(` / `curl`

---

### Closeout (6 units, as v1 + plan/registry update)

Same as v1 Closeout phase. Add explicit task to update plan YAML status COMPLETED + completed_date + execution_summary AND update SPRINT_REGISTRY.md S231 row using `git add -f` for both.

---

## Cold-Start Verification Checklist (v2)

Per S091 + S154 cold-start rules. The executing agent must verify YES for every item before starting code:

### External dependencies (every one resolved with concrete details)

- [ ] Production DocType for sales: `tabBEI Store Closing Report` (NOT `tabBEI Sales Daily`). Verified via `dep_production_state.json` + `dep_existing_billing_flow.md`.
- [ ] Production billing DocType: `tabBEI Billing Schedule` — does NOT exist yet, requires `bench migrate` in Phase 0.
- [ ] BFC canonical Company name: `BEBANG FRANCHISE CORP.` (uppercase, matches abbr=BFC). Verified `dep_production_state.json.bfc_check.any_BFC_abbr`.
- [ ] BEBANG FT INC. parent legal entity: does NOT exist; CREATE in Phase A-3 with abbr=BFI2, tax_id=663-440-106-00000.
- [ ] SSM access: AWS region `ap-southeast-1`, instance `i-026b7477d27bd46d6`. Pattern from `scripts/s212_probe_frappe_errors.py`.
- [ ] Frappe site: `hq.bebang.ph`, sites_path `/home/frappe/frappe-bench/sites`.
- [ ] Backend container name: `frappe_backend` (per `scripts/s212_probe_frappe_errors.py:67`).

### Files the agent must read before code

- [ ] `~/.claude/projects/F--Dropbox-Projects-BEI-ERP/3cb6b2f5-4590-412d-a67f-a2d53a0f72f7.jsonl` — full source-session transcript (CEO chat 2026-05-02 that produced this plan); read on demand if any decision needs cross-verification beyond what's in the cleanroom memo
- [ ] `data/_CLEANROOM/2026-04-09_franchise_agreements/06_CEO_Approvals_2026-05-02.md` — CEO decisions, fact-checked
- [ ] `data/_CLEANROOM/2026-04-09_franchise_agreements/05_Per_Store_Fee_Carveouts.md` — Vista Mall 2.0%
- [ ] `output/plan-audit/sprint-231-pricing-coupling-and-defaults-defense/dep_production_state.json` — live data
- [ ] `output/plan-audit/sprint-231-pricing-coupling-and-defaults-defense/dep_existing_billing_flow.md` — Stream A 90% built
- [ ] `output/plan-audit/sprint-231-pricing-coupling-and-defaults-defense/dep_backend_map.md` — every reader/writer
- [ ] `output/plan-audit/sprint-231-pricing-coupling-and-defaults-defense/dep_frontend_map.md` — frontend dep map
- [ ] `output/plan-audit/sprint-231-pricing-coupling-and-defaults-defense/dep_schema_migration.md` — additive changes
- [ ] `output/plan-audit/sprint-231-pricing-coupling-and-defaults-defense/dep_test_coverage_map.md` — test maintenance
- [ ] `docs/STORE_COMPANY_CANONICAL.md` — canonical model (THE LAW)

### Functions that must NOT break (line numbers)

- [ ] `auto_provision_company` at `hrms/overrides/company.py:592-723` — Phase C-1 wraps; preserves all 10 steps + `ignore_root_company_validation` flag
- [ ] `markup_by_type` at `hrms/api/commissary.py:1077-1099` — read-only verify in Phase D-2; do not modify
- [ ] `_build_company_first_entity_row` at `hrms/utils/supply_chain_contracts.py:201-233` — read-only verify
- [ ] `resolve_store_buyer_entity` at `hrms/utils/supply_chain_contracts.py:319-368` — do NOT add fallbacks (canonical Rule 4)
- [ ] `validate_default_accounts` at `hrms/overrides/company.py:121-136` — kept; reordered AFTER `null_out_dead_default_refs`
- [ ] `set_default_hr_accounts` at `hrms/overrides/company.py:102-118` — kept; interacts with C-2 hook (NG-2 noted)
- [ ] `_create_delivery_fee_billing_on_acceptance` at `hrms/api/store.py:7576-area` — Stream B; do not modify
- [ ] `_NON_STORE_ENTITIES` at `hrms/api/company_master.py:507` AND `:1161` — DRY refactor in Phase E-5; both call sites become single constant reference

### Frontend routes / RBAC

- [ ] Route: `/dashboard/bd/companies` (page.tsx + company-detail-dialog.tsx)
- [ ] RBAC: `MODULES.COMPANY_MASTER` at `bei-tasks/lib/roles.ts:920-927` — BD/BD-Manager/Accounts-Manager/HQ-User/SystemManager/Admin only. STORE_PARTNER excluded (S227 directive). No additional RBAC fix needed in Phase D-5.
- [ ] Pattern to follow: existing `<OperationsSection>` and `<PeopleSection>` slot pattern in `company-detail-dialog.tsx:484-504`

### Branch state

- [ ] Branch `s231-pricing-coupling-and-defaults-defense` reserved in registry. NOT yet created on origin. Phase 0 spawns worktree.
- [ ] Pre-Phase-0 hotfix is FIRST PR in the sprint. Subsequent commits go in same branch.
- [ ] No prior commits on this branch.

### Schema additions (additive, no downtime)

- [ ] `bei_settings.json` adds: `bki_billing_cron_enabled` (Pre-Phase-0), `bki_markup_company_owned_percent`, `bki_sales_debit_to_account`, `bki_sales_naming_series` (D-1), `bfc_or_active`, `bfc_vat_registration_active`, `bfc_sales_naming_series`, `bfc_sales_vat_template`, `jv_sales_vat_template`, `jv_revenue_company`, `bfc_revenue_company` (D-3 + D-4)
- [ ] New DocType: `BEI Fee Schedule` (D-3-2)
- [ ] New DocType: `BEI Fee Carveout` (D-3-3)
- [ ] New custom field on `BEI Billing Schedule`: `company` (Link → Company) — backfilled from store→Department→Company per `dep_schema_migration.md`
- [ ] All schema changes deploy via `bench migrate`. No SQL DDL.

### Test infrastructure

- [ ] Existing reusable: `loggedInAsCEO` fixture in `bei-tasks/tests/e2e/fixtures/auth.ts:148`. Password `PASSWORDS.ceo`.
- [ ] Existing reusable: `CleanupLedger` in `bei-tasks/tests/e2e/fixtures/cleanup.ts` — extend with 5 new kinds (TM-5).
- [ ] Existing reusable: `frappeReadback.readDoc` / `queryDocs` for Frappe DocType verification.
- [ ] Existing reusable: `s204_all_stores.json` fixture has 49 stores' `store_ownership_type` for post-sweep regression assertion.
- [ ] New asset: `CompanyMasterPage.ts` Page Object (TM-3)
- [ ] New asset: `assertFranchiseFeeSI` helper (TM-4)
- [ ] New asset: `s231-fee-preview.spec.ts` E2E spec (TM-7)
- [ ] Pre-fix existing: `s37-live.spec.ts:2182`, `s27-billing-live.spec.ts:792-802` (TM-1, TM-2)

### Production data state at sprint start (probe-confirmed)

- [ ] BKI markup rates: JV=2.75 ✓, MF=8.0 ✓, FF=8.0 ✓, Co-Owned field=missing (D-1 adds; default 2.75)
- [ ] Ownership distribution: 23 JV / 2 CO / 27 MF / 2 FF / 3 holdings = 57 Companies
- [ ] Broken Companies: 44 of 57 have at least one broken `default_*` ref
- [ ] Active Salary Structures on broken Companies: 0 (B-21 moot)
- [ ] BFC dup: BOTH `Bebang Franchise Corp.` AND `BEBANG FRANCHISE CORP.` exist (Phase E-3 dedups)
- [ ] BEBANG FT INC.: does NOT exist (Phase A-3 creates)
- [ ] `tabBEI Billing Schedule`: does NOT exist as table (Phase 0 `bench migrate` creates)
- [ ] `bki_sales_vat_template`: empty (Phase D-1 sets)

If ANY checklist item is unverified at agent boot, STOP and re-read the source artifact.

## Sprint Registry Lock Evidence

Row added to `docs/plans/SPRINT_REGISTRY.md` 2026-05-02:

```
| `S231` | Sprint 231 | `s231-pricing-coupling-and-defaults-defense` (hrms backend + bei-tasks frontend) | TBD | PLANNED 2026-05-02 — Permanent ownership-type→pricing coupling + Company defaults validation defense. ... ~78 work units across 6 phases. | `docs/plans/2026-05-02-sprint-231-pricing-coupling-and-defaults-defense.md` |
```

Next Sprint Reservation bumped to `S232`.

---

## Triggering Incident

**2026-05-02 (Saturday).** CEO opened `https://my.bebang.ph/dashboard/bd/companies`, opened Ayala Fairview Terraces detail, clicked Edit on Operations section, changed `store_ownership_type` from "Company Owned" to "JV", clicked Save. Server returned `frappe.exceptions.LinkValidationError`:

```
Could not find Exchange Gain / Loss Account: Exchange Gain/Loss - BFI2,
Round Off Cost Center: Main - BFI2, Accumulated Depreciation Account:
Accumulated Depreciation - BFI2, Depreciation Expense Account: Depreciation - BFI2,
Expenses Included In Asset Valuation: Expenses Included In Asset Valuation - BFI2,
Gain/Loss Account on Asset Disposal: Gain/Loss on Asset Disposal - BFI2,
Asset Depreciation Cost Center: Main - BFI2, Capital Work In Progress Account: CWIP Account - BFI2,
Asset Received But Not Billed: Asset Received But Not Billed - BFI2,
Default Inventory Account: Stock In Hand - BFI2, Stock Adjustment Account: Stock Adjustment - BFI2,
Stock Received But Not Billed: Stock Received But Not Billed - BFI2,
Expenses Included In Valuation: Expenses Included In Valuation - BFI2,
Default Payroll Payable Account: Payroll Payable - BFI2,
Default Employee Advance Account: Employee Advances - BFI2
```

15 dead `- BFI2` Account references on the Company doc. Save path: `hrms/api/company_master.py:266` → `doc.save()` → `_validate_links()` (Frappe re-validates ALL Link fields on save, not only changed ones).

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

`auto_provision_company` in `hrms/overrides/company.py:638` calls ERPNext's `doc.create_default_accounts()` inside a try/except that **swallows the exception and continues**. ERPNext's `create_default_accounts` is a two-phase operation: (a) `db_set`s `default_*` field VALUES on the Company doc (commits immediately), then (b) creates the actual Account records via Chart of Accounts Importer. If phase (b) fails partway, phase (a) has already committed but the accounts don't exist. The exception handler at `hrms/overrides/company.py:657-663` logs and continues, the outer savepoint releases anyway, and `first_provision_done=1` flips at line 693. Result: Company is permanently in a state where any future save fails because Frappe's `_validate_links()` checks ALL `default_*` Link fields and 15 of them point to ghost accounts.

This is invisible until something forces a re-save. Sam's JV change forced one. The same trap is almost certainly waiting on other Companies that ran through `auto_provision_company` over S181-S206 — we just haven't tripped them yet.

### Why this architecture (not alternatives)

**Option A (chosen): Fix the atomicity bug + sweep + add pricing coupling.** Atomicity fix prevents recurrence. Sweep cleans the existing broken population. Pricing coupling completes the work the CEO actually wants — ownership-type changes should propagate to inventory markup, billing, and UI preview.

**Option B (rejected): Just clear the broken Company's defaults and ship.** Doesn't address recurrence; leaves the latent bug for the next time `auto_provision_company` partially fails. Doesn't address the CEO's pricing-coupling ask.

**Option C (rejected): Bypass `_validate_links()` in `update_company_section`.** Masks the real issue. Future code that depends on those defaults (inventory accounting, payroll posting) breaks silently in production. Violates BEI's "Correct Over Fast" rule.

**Option D (rejected): Skip `create_default_accounts()` entirely; let S181 templates handle it.** ERPNext's defaults cover fields S181 templates don't (Exchange Gain/Loss, Asset accounts, CWIP, etc.). Removing the call leaves payroll and asset depreciation broken on every new Company.

### Key trade-off decisions

| Decision | Alternative | Why chosen |
|---|---|---|
| Single consolidated monthly billing per store | Separate billing rows per fee type | CEO directive 2026-05-02: "1 billing for all". Simpler reconciliation; one due date; one OR per store per month. |
| Compute monthly fees server-side at month-end | Frontend-triggered on-demand computation | Server-side cron is auditable, idempotent, and BIR-aligned (fees due dates are policy not user-driven). |
| Live-read `Company.store_ownership_type` for billing | Snapshot at month-start | Live-read matches existing BKI markup logic (S190 retired the CSV register); single source of truth. Risk: ownership flip mid-month → use the value AT month-end. |
| Add `bki_markup_company_owned_percent` field with default 2.75% | Code-only fallback to 0% (current state) | CEO 2026-05-02: Co-Owned = same rate as JV. Configurable in BEI Settings without redeploy. |
| Skip JV profit share automation | Automate phased recovery + quarterly JE | CEO 2026-05-02: "Do not automate the JV profit share it should part of the P&L". Keeps complex business logic out of code. |
| Sweep all 49 stores | Only fix Ayala Fairview | CEO 2026-05-02: "Sweep all 49". Almost certainly more than one Company has the same trap. |
| Fee-preview UI in detail dialog | Separate page or report | CEO 2026-05-02: "add fee preview to the UI". Inline in the detail dialog gives instant before/after when ownership type changes. |
| `BEBANG FT INC.` as canonical name (not `Bebang FTE Inc.`) | Keep both, alias one | CEO 2026-05-02 confirmed BEBANG FT INC. matches abbr=BFI2 in `company_register_2026-04-14.csv` and the production accounts naming. |
| E-commerce fee scope: `website_sales` only (not FoodPanda/Grab) | Apply 5% to all digital channels | CEO 2026-05-02: "Ecommerce charge is only on sales generated through bebang.ph website and not Foodpanda and Grab". Matches BFC Franchise Agreement §XI.I and JV Agreement §9.1 contract language. |

### Known limitations and mitigations

- **`update_company_section` re-validates ALL link fields, not just changed ones.** Cannot bypass without violating ERPNext semantics. Mitigation: Phase C nulls out broken defaults proactively at validate time.
- **`create_default_accounts()` is ERPNext source code, not BEI's.** Cannot wrap atomicity inside the upstream function. Mitigation: wrap the CALLER (Phase C — capture defaults set, on rollback null them via `db.set_value`).
- **JV agreement Section 17 vs Section 24 conflict** (2-year voluntary exit vs 3-year lock-in) — irrelevant to ERP coupling; carried forward as legal note.
- **Vista Mall management fee shows 2.00% in Nov 2025 actuals** (not 2.5%) — Phase D auto-billing must use the stored rate from `BEI Billing Schedule` template per store, not a hardcoded constant. Or surface as a documented carve-out.
- **Bebang FTE Inc. references** appear in 3 seed CSVs and possibly Customer/Supplier/Address records — Phase E must rename comprehensively.
- **Ownership flip mid-month** — billing automation uses month-end `Company.store_ownership_type`. Documented in fee-preview UI tooltip ("rate locks at month-end").

### Source references

- `data/_CLEANROOM/2026-04-09_franchise_agreements/01_JV_Agreement_Grand_Central_Gabaldon.md` — JV fee structure (5% mkt + 5% e-com to BEI; phased profit share)
- `data/_CLEANROOM/2026-04-09_franchise_agreements/02_Franchise_Management_Agreement_BFC.md` — 2.5% Mgmt Fee (Managed Franchise only)
- `data/_CLEANROOM/2026-04-09_franchise_agreements/03_Franchise_Agreement_BFC.md` — 7% Royalty + 5% Mkt + 5% E-com → BFC
- `data/_CLEANROOM/2026-04-09_franchise_agreements/04_BEI_BFC_Collection_Agent_Letter_DRAFT.md` — BEI as disclosed agent for BFC fees during interim
- `data/_CONSOLIDATED/08_BUSINESS_DEV/source_documents/FRANCHISE_BILLING_SUMMARY.txt` — Nov 2025 actuals; 7% royalty back-calculated and verified across 18 stores
- `data/_CONSOLIDATED/08_BUSINESS_DEV/source_documents/FRANCHISE_STORES_DATA_NOV2025.csv` — 18-store fee actuals
- `hrms/api/company_master.py:230-267` — `update_company_section` (the failing endpoint)
- `hrms/overrides/company.py:592-723` — `auto_provision_company` (root cause)
- `hrms/overrides/company.py:638-714` — try/except swallowing `create_default_accounts` failure
- `hrms/api/commissary.py:1077-1099` — `markup_by_type` already implements ownership-type→markup
- `hrms/utils/supply_chain_contracts.py:200-225` — `_build_company_first_entity_row` reads live `store_ownership_type`
- `hrms/utils/supply_chain_contracts.py:187-198` — S037 register CSV RETIRED (S190 Phase 5)
- `hrms/hr/doctype/bei_settings/bei_settings.json:56-58, 360-378` — markup fields (no Company Owned field yet)
- `hrms/hr/doctype/bei_billing_schedule/bei_billing_schedule.json` — DocType structure (royalty/marketing/management/ecommerce fields exist)
- `hrms/api/billing.py:1230-1286` — `get_billing_detail` returns fee breakdown (mostly read-only today)
- `bei-tasks/app/dashboard/bd/companies/company-detail-dialog.tsx` — UI we extend with fee preview
- Research: `tmp/sprint-pricing-coupling-research/01_FINDINGS.md`

---

## Canonical Model Preflight (Mandatory)

Executing agent MUST run before any code change:

```bash
python scripts/verify_canonical_structure.py | tee output/s231/verification/canonical_verifier_pre.txt
```

If the verifier prints `[VIOLATION]`, STOP and ask the CEO. Do NOT add records, flip fields, or create customers/warehouses to paper over a violation — fix the master data with the canonical scripts.

**Canonical law (summary — full rules in `docs/STORE_COMPANY_CANONICAL.md`):**
- Every store has EXACTLY 1 per-store Company + 1 Warehouse + 1 billing Customer + 1 Internal Customer.
- All four share the same name string (e.g. `SM TANZA - BEBANG MEGA INC.`).
- Per-store Company's `parent_company` links to the legal entity parent (if any).
- Warehouse.company = the per-store Company (NEVER the parent).
- Billing Customer: `customer_name` = per-store Company name, `is_internal_customer=0`.
- Internal Customer: `represents_company` = per-store Company, `is_internal_customer=1`. Used by S206 labor journals ONLY — never for regular SIs.

**Forbidden in this plan (without explicit CEO approval in-line):**
- Creating a second Warehouse/Company/Customer for an existing store.
- Ad-hoc SQL mutations on `tabCompany` / `tabWarehouse` / `tabCustomer` outside the canonical scripts. Phase A/B clears `default_*` fields via `frappe.db.set_value("Company", ..., "default_inventory_account", None)` — that's a defaults-cleanup, not a master-data reshape.
- Adding new fallback logic to `resolve_store_buyer_entity`.
- Renaming a per-store Company name (Phase E renames `Bebang FTE Inc.` references — that's a legal entity name in seed CSVs and Customer/Supplier records, NOT a per-store Company rename).
- Reusing an Internal Customer for a regular SI.
- Deleting a master record with transactions.

**Scope claim:**

| Record | Action | Reason |
|---|---|---|
| Per-store Companies (49 in registry) | UPDATE `default_*` fields (null-out broken refs) | Phase A/B/C — defaults cleanup; no schema/name change |
| Frappe Companies named `Bebang FTE Inc.` (legal entity, may not exist as Company) | Rename to `BEBANG FT INC.` if it exists | Phase E — legal entity name canonicalization |
| Customers / Suppliers / Addresses with `Bebang FTE Inc.` in any field | UPDATE field value to `BEBANG FT INC.` | Phase E — referential consistency |
| `BEI Settings` (Single doctype) | INSERT new field `bki_markup_company_owned_percent` (default 2.75%) | Phase D — completes ownership-type→markup matrix |
| `BEI Billing Schedule` rows | INSERT auto-generated monthly rows (cron) | Phase D — single billing per store/month |
| Sales Invoice (BFC fees collected by BEI as agent) | INSERT monthly SIs per JV/MF/FF store on `Company = Bebang Franchise Corp.` (MF/FF) or `Company = Bebang Enterprise Inc.` (JV) | Phase D — fee invoicing |

No `tabCompany.name`, `tabWarehouse.name`, `tabCustomer.name` (per-store) renames.

---

## Canonical Model Binding

This sprint binds to the canonical model:
- **Reads `Company.store_ownership_type`** (live) → resolves markup rate AND fee schedule.
- **Reads `Warehouse.company` → Company.parent_company chain** to determine fee recipient (BFC vs BEI for franchise/JV billing).
- **Reads `resolve_store_buyer_entity(warehouse_docname)`** for billing customer lookup (no new fallbacks added).
- **Writes Sales Invoice with `customer = <per-store billing Customer>`** — never the parent — for monthly franchise fee SIs.
- **Cost centers** for fee SIs resolve via existing `_resolve_store_cost_center(target_warehouse, entity_row)`.

Does NOT:
- Infer store identity from warehouse_name string parsing (uses Warehouse.company).
- Hardcode parent Company names.
- Add its own store_id / branch_code field parallel to canonical model.
- Bypass `_resolve_buyer_customer_for_company` 4-step lookup.

---

## Requirements Regression Checklist

Before any code change in this sprint, the executing agent must be able to assert YES for every item:

- [ ] Have I read `docs/STORE_COMPANY_CANONICAL.md` end-to-end?
- [ ] Have I read `tmp/sprint-pricing-coupling-research/01_FINDINGS.md` (research)?
- [ ] Did I run `scripts/verify_canonical_structure.py` and capture the output to `output/s231/verification/canonical_verifier_pre.txt`?
- [ ] Am I working in `F:/Dropbox/Projects/BEI-ERP-s231-pricing-coupling-and-defaults-defense/` (the worktree), NOT the main checkout?
- [ ] Is my branch `s231-pricing-coupling-and-defaults-defense`, branched from `origin/production`?
- [ ] Are markup rates: JV 2.75%, Managed Franchise 8%, Full Franchise 8%, Company Owned 2.75% (the new field default)? *(CEO 2026-05-02: Co-Owned same as JV)*
- [ ] Is the royalty rate 7% (NOT 8%)? *(BFC Franchise Agreement §XIII.A; verified across 18 stores Nov 2025)*
- [ ] Is the e-commerce fee 5% applied ONLY to `website_sales` (NOT FoodPanda/Grab)? *(CEO 2026-05-02 explicit confirmation)*
- [ ] Does the monthly billing automation produce ONE consolidated `BEI Billing Schedule` row per store per month? *(CEO 2026-05-02: "1 billing for all")*
- [ ] Are JV fees (5% mkt + 5% e-com) routed to BEI revenue, NOT BFC? *(per Collection Agent Letter §"What this letter does NOT cover" item 4)*
- [ ] Are MF/FF fees (Royalty/Mkt/Mgmt/E-com) routed to BFC revenue (collected by BEI as agent during interim)? *(per Collection Agent Letter §1-3)*
- [ ] Am I NOT automating JV profit share (60/40 → 50/50 → 40/60 phased)? *(CEO 2026-05-02: keep manual P&L)*
- [ ] Is the Phase C atomicity fix wrapping the CALLER of `create_default_accounts`, NOT modifying ERPNext upstream code?
- [ ] Does Phase C null-out-broken-defaults validate hook check `frappe.db.exists("Account", value)` before allowing the Link, and `db.set_value(..., None)` if missing?
- [ ] Does every new/modified `@frappe.whitelist()` endpoint call `set_backend_observability_context(module="company"|"billing"|"commissary", action=..., mutation_type=...)`?
- [ ] Is the canonical name `BEBANG FT INC.` (NOT `Bebang FTE Inc.`)? *(CEO 2026-05-02)*
- [ ] Have I committed evidence to `output/s231/` (committed) AND transient logs to `tmp/s231/` (gitignored)?
- [ ] At closeout, did I run `git worktree remove F:/Dropbox/Projects/BEI-ERP-s231-pricing-coupling-and-defaults-defense`?

---

## L3 Workflow Scenarios

| # | User | Action | Expected Outcome | Failure Means |
|---|---|---|---|---|
| S1 | sam@bebang.ph | Open `/dashboard/bd/companies` → click "Ayala Fairview Terraces" → Operations card → Edit → change `store_ownership_type` to "JV" → Save | 200 OK, success toast "Operations updated"; backend response `{ok: true, updated_fields: ["store_ownership_type"]}`; reload shows JV; no LinkValidationError | Phase A fix didn't actually clear/recreate the broken accounts on this Company |
| S2 | sam@bebang.ph | After S1, on detail dialog change ownership type back to "Company Owned", verify save still succeeds | 200 OK; Co-Owned saved | Save path still validates against bad defaults |
| S3 | sam@bebang.ph | On any other Company (pick `Robinsons Imus`) → Operations → Edit → toggle `store_ownership_type` Co-Owned → Managed Franchise → Co-Owned (no real change) | All three saves succeed | Phase B sweep missed this Company |
| S4 | sam@bebang.ph | On `/dashboard/bd/companies` detail dialog for any store, change ownership type → fee preview panel shows updated markup rate + fee schedule BEFORE save | Preview component displays: markup % (per BEI Settings), Royalty/Mkt/Mgmt/E-com applicability per type | Phase D-5 UI not wired |
| S5 | system (cron, end-of-month simulation) | Trigger `hrms.api.billing.run_monthly_franchise_billing(period="2026-05")` for a Managed Franchise store with seeded POS sales of ₱1,571,252.40 net + ₱49,310 website_sales | One `BEI Billing Schedule` row created with: Royalty ₱109,987.67, Marketing ₱78,562.62, Management ₱39,281.31, E-com ₱2,465.50 (5% × ₱49,310), total subtotal ₱230,297.10 + VAT | Phase D-3 billing math wrong OR multiple rows created instead of one |
| S6 | system | Same as S5 but for a JV store (Ayala Fairview Terraces) with ₱2M POS + ₱100K website | One row: Marketing ₱100,000 (5% × ₱2M gross), E-com ₱5,000 (5% × ₱100K), Royalty=0, Management=0, recipient=BEI | Phase D-4 routing wrong; JV fees going to BFC |
| S7 | system | After S5+S6, query SI created → MF SI has `company=Bebang Franchise Corp.`; JV SI has `company=Bebang Enterprise Inc.` | Recipient routing correct | Phase D-4 broken |
| S8 | system | Run `python scripts/s231_audit_broken_defaults.py --verify-after` post-sweep | Returns `{broken_companies: 0}` for all 49 store companies | Phase B sweep incomplete |
| S9 | system | Provoke `auto_provision_company` failure on a fresh test Company (mock ERPNext to throw inside `create_default_accounts`) | All `default_*` fields are NULL after rollback (not pointing at non-existent accounts); `first_provision_done` stays 0 (not flipped); next save attempt does not raise LinkValidationError | Phase C atomicity fix not effective |
| S10 | system | Verify `BEI Settings.bki_markup_company_owned_percent` field exists and = 2.75 | Field present, value 2.75 | Phase D-1 missed |

---

## Test Data Seeding Contract

Reference skill: `/frappe-bulk-edits` for seeding/teardown.

**Records the scenarios depend on:**

| Record | Purpose | Scenario |
|---|---|---|
| Test Company `S231-TEST-COA-FAILURE - BEBANG ENTERPRISE INC.` | Provoke `auto_provision_company` failure | S9 |
| Test SI items: 5 Stock Entry rows from BKI to a target Managed Franchise store totaling ₱1,571,252.40 ex-VAT, posting_date=2026-05-30 | Trigger Phase D billing computation | S5 |
| Test website_sales row in `tabBEI Sales Daily` (or equivalent) for store + period: ₱49,310 (Managed Franchise), ₱100,000 (JV) | Provide ecommerce_fee base | S5, S6 |
| Test POS sales row: ₱2M gross, ₱2M net for Ayala Fairview Terraces, period 2026-05 | Provide JV gross sales for marketing fee | S6 |
| Confirm test accounts exist (already seeded for L3): test.scm@bebang.ph, test.warehouse@bebang.ph; sam@bebang.ph as CEO | Detail dialog access | S1-S4 |

**Pre-test seeding plan:**

```python
# /frappe-bulk-edits seeding script: scripts/s231_seed_l3_fixtures.py
# Operates only in non-production-data scope: creates fixtures with names prefixed `S231-TEST-`
# All ledger entries logged to output/l3/s231/teardown_ledger.json

INSERTS = [
    {
        "doctype": "Company",
        "company_name": "S231-TEST-COA-FAILURE - BEBANG ENTERPRISE INC.",
        "abbr": "S231TEST",
        "default_currency": "PHP",
        "country": "Philippines",
        "store_ownership_type": "Company Owned",
        "first_provision_done": 0,
        # Mock ERPNext create_default_accounts failure via flags before insert
    },
    # (POS sales / website sales seeded via direct INSERT into tabBEI Sales Daily — see script)
    # (Stock Entry seeded via Stock Entry doctype create with set_posting_time=1)
]
```

**Teardown plan:**

```python
# scripts/s231_teardown_l3_fixtures.py
# Reads output/l3/s231/teardown_ledger.json, reverses every entry
# Writes output/l3/s231/teardown_complete.json with deletion proof

TEARDOWN_RULES = [
    ("BEI Billing Schedule", "name LIKE 'S231-TEST-%' OR (billing_period='2026-05-S231-TEST')", "DELETE"),
    ("Sales Invoice", "naming_series LIKE 'S231-TEST-%'", "CANCEL+DELETE"),
    ("Stock Entry", "remarks LIKE '%S231 fixture%'", "CANCEL+DELETE"),
    ("Company", "name LIKE 'S231-TEST-%'", "DELETE_AFTER_CHILDREN"),
    ("BEI Sales Daily", "name LIKE 'S231-TEST-%'", "DELETE"),
]
```

**Teardown ledger path:** `output/l3/s231/teardown_ledger.json` with entries `{doctype, name, action, original_values}`.

**Teardown verification:** Closeout phase task — run teardown script, then run `frappe.db.count` on each test pattern, assert 0; write `output/l3/s231/teardown_complete.json` with `{deleted: <counts>, remaining: 0}`.

---

## Anti-Rewind / Concurrent-Run Protection Contract

| Element | Artifact | Rule |
|---|---|---|
| ownership_matrix | `output/s231/SURFACE_OWNERSHIP_MATRIX.csv` | This sprint owns: `hrms/overrides/company.py`, `hrms/api/company_master.py`, `hrms/api/billing.py` (new fns only — see `protected_surfaces`), `hrms/api/commissary.py` (read-only verification), `hrms/utils/supply_chain_contracts.py` (read-only verification), `hrms/hr/doctype/bei_settings/bei_settings.json` (add field), `bei-tasks/app/dashboard/bd/companies/*`, `scripts/s231_*.py` |
| protected_surfaces | `output/s231/PROTECTED_SURFACE_REGISTRY.csv` | Do NOT modify: existing `markup_by_type` block in `commissary.py:1077-1099` (read-only verify); existing `_build_company_first_entity_row` (read-only verify); existing `BEI Billing Schedule` field schema (only ADD computed-rate field if needed); existing `update_company_section` allowlist (Phase D-5 may extend `operations` section if preview needs it) |
| remote_truth_baseline | `output/s231/REMOTE_TRUTH_BASELINE.json` | Capture at Phase 0: `{repo: hrms, branch: production, head_sha: <git rev-parse origin/production>, capture_time: <ISO>}` and same for bei-tasks. |
| touched_file_routing | `output/s231/TOUCHED_FILE_ROUTING.csv` | Each touched file → required L3 scenario(s) it must satisfy + canonical verifier pass post-change |
| active_run_coordination | `output/s231/state/ACTIVE_RUN_COORDINATION.json` | Claim on Phase 0 boot; release on closeout; if S232+ also claims overlapping files, blocker. |
| pretouch_backup | `output/s231/state/PRETOUCH_BACKUP.json` | Before Phase B sweep mutation: snapshot of `tabCompany` `default_*` columns + `first_provision_done` for all 49 stores. |
| supersession_map | n/a (not a recovery sprint) | — |
| touch_preservation | `output/s231/ledgers/TOUCH_PRESERVATION_LEDGER.csv` | Every Company touched in Phase B has a row: company_name, fields_cleared, accounts_created, ts |

---

## Status Reconciliation Contract

Whenever counts, blockers, stage, or status changes, update in the same work unit:

1. `output/s231/RUN_STATUS.json`
2. `output/s231/SUMMARY.md`
3. `output/s231/DEFECTS.md`
4. `output/s231/verification/sweep_report.json` (if Phase B counts changed)
5. `docs/plans/2026-05-02-sprint-231-pricing-coupling-and-defaults-defense.md` (this file — status field)
6. `docs/plans/SPRINT_REGISTRY.md` row for S231 (when status flips)
7. PR description checkbox table

---

## Signoff Model

- mode: `single-owner`
- approver_of_record: `Sam Karazi (CEO)` via PR review
- signoff_artifact: `output/s231/SUMMARY.md` final section "CEO Signoff Block" + GitHub PR APPROVE
- note: PR-Handoff workflow — agent creates PR + provides PR URL + STOPS. Sam reviews, runs Release Manager Gate, merges and deploys.

---

## Autonomous Execution Contract

- **completion_condition:**
  - All 6 phases (Phase 0 through Closeout) green per their gates
  - Canonical verifier post-execution shows zero NEW violations
  - All 10 L3 scenarios PASS with evidence in `output/l3/s231/`
  - Sweep report shows 0 broken Companies after Phase B (`output/s231/verification/sweep_report.json` `broken_companies_after=0`)
  - `BEI Settings.bki_markup_company_owned_percent` exists with value 2.75
  - 1 monthly billing row produced per store-month for the L3 test period (S5+S6 verified)
  - Recipient routing verified: JV→BEI, MF/FF→BFC (S7 verified)
  - PR created, PR number recorded in plan + registry
  - Test fixtures torn down (`output/l3/s231/teardown_complete.json` shows 0 remaining)
  - Worktree removed; main checkout clean
- **stop_only_for:**
  - Missing AWS SSM credentials or production DB access
  - Canonical verifier prints `[VIOLATION]` (existing or new) — pause to ask CEO
  - More than 5 Companies in Phase B sweep have COMPLETELY missing CoA (suggests S181 systemic failure, not recoverable by null-out) — pause to ask CEO
  - Phase D recipient-routing: a Company has no `parent_company` AND ownership_type ∈ {Managed Franchise, Full Franchise} (no path to BFC) — pause
  - Existing BFC Customer record missing or has wrong TIN — pause
  - Bebang FTE Inc. rename in Phase E touches more than 50 records — pause to confirm
  - Sentry shows >10 errors during Phase D billing test — pause
- **continue_without_pause_through:**
  - audit
  - execute (all phases)
  - PR creation
  - L3 evidence capture
  - closeout teardown
- **blocker_policy:**
  - programmatic → fix and continue
  - evidence mismatch / stale authoritative section → normalize plan and continue
  - repeated technical failure ×3 → grounded research, then continue
  - business-data/policy → pause
- **canonical_closeout_artifacts:**
  - `output/s231/RUN_STATUS.json`
  - `output/s231/SUMMARY.md`
  - `output/s231/DEFECTS.md`
  - `output/s231/verification/sweep_report.json`
  - `output/s231/verification/canonical_verifier_post.txt`
  - `output/s231/verification/state_after.json`
  - `output/l3/s231/SUMMARY.md`
  - `output/l3/s231/teardown_complete.json`
  - `docs/plans/2026-05-02-sprint-231-pricing-coupling-and-defaults-defense.md` (status flipped to COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (S231 row updated to COMPLETED + PR number)

---

## Phase Budget Contract

| Phase | Units | Notes |
|---|---|---|
| Phase 0 — Boot | 4 | Worktree, branch, registry verification, baseline captures |
| Phase A — Probe + Unblock Ayala Fairview | 8 | Read-only probe, classify, fix, verify save works |
| Phase B — Audit + Sweep 49 Stores | 12 | Inventory script, classify, mass-fix, post-verify |
| Phase C — Permanent Atomicity Fix | 12 | Atomicity wrapper + null-out validate hook + unit tests |
| Phase D — Pricing Coupling Completion | 30 (split into D1-D5 below) | Largest phase; if any sub-phase exceeds 12 units it splits further |
| Phase E — Naming Canonicalization | 6 | Targeted rename across seed CSVs + Customer/Supplier/Address |
| Closeout | 6 | Teardown + PR + plan/registry update + worktree remove |
| **Total** | **78** | Under 80-unit ceiling (S089 rule) |

**Phase D sub-budget (each ≤12):**
- D1 — Add `bki_markup_company_owned_percent` field: 4
- D2 — Verify ownership-type→markup live coupling for all 4 types: 4
- D3 — Monthly billing automation (cron + computation + SI creation): 12
- D4 — Recipient routing (BEI vs BFC) + Collection Agent JE pattern: 6
- D5 — Frontend fee-impact preview UI: 4

Hard limit per phase: 15. Preferred split threshold: 12. Phase D-3 sits exactly at 12; if discovery during execution shows it must grow, split into D3a (computation engine) + D3b (SI creation/dispatch) before continuing.

---

## Phase 0 — Agent Boot Sequence (4 units)

1. **Read this plan in full.** Then read `tmp/sprint-pricing-coupling-research/01_FINDINGS.md` and `docs/STORE_COMPANY_CANONICAL.md`.

2. **Spawn the worktree** (NOT a branch in main checkout):

```bash
BR=s231-pricing-coupling-and-defaults-defense
WT=F:/Dropbox/Projects/BEI-ERP-${BR##*/}
cd F:/Dropbox/Projects/BEI-ERP && git fetch origin --prune
git worktree add "$WT" -B "$BR" origin/production
cd "$WT"
```

For bei-tasks frontend work in Phase D-5:
```bash
BR=s231-fee-preview-ui
WT2=F:/Dropbox/Projects/bei-tasks-${BR##*/}
cd F:/Dropbox/Projects/bei-tasks && git fetch origin --prune
git worktree add "$WT2" -B "$BR" origin/main
```

3. **Verify registry row + PR baseline:**
```bash
grep -A1 "S231" docs/plans/SPRINT_REGISTRY.md | head -10
git log --oneline origin/production -5 > output/s231/REMOTE_TRUTH_BASELINE.json.head
```

Write `output/s231/REMOTE_TRUTH_BASELINE.json`:
```json
{
  "captured_at": "<ISO>",
  "hrms_branch": "production",
  "hrms_head_sha": "<git rev-parse origin/production>",
  "bei_tasks_branch": "main",
  "bei_tasks_head_sha": "<git rev-parse origin/main from bei-tasks>",
  "active_run_id": "S231-2026-05-02"
}
```

4. **Run canonical verifier** (read-only; pre-state):
```bash
mkdir -p output/s231/verification
python scripts/verify_canonical_structure.py 2>&1 | tee output/s231/verification/canonical_verifier_pre.txt
```

If ANY `[VIOLATION]` lines, STOP and ask CEO. Existing violations are not this sprint's to fix unless explicitly approved.

5. **MUST_MODIFY assertions for Phase 0:**
   - `MUST_MODIFY: output/s231/REMOTE_TRUTH_BASELINE.json (created)`
   - `MUST_MODIFY: output/s231/verification/canonical_verifier_pre.txt (created)`
   - `MUST_MODIFY: output/s231/state/ACTIVE_RUN_COORDINATION.json (created with claim)`

**Verification script (write before Phase A; run after Phase 0):**

```python
# output/s231/verify_phase0.py
import os, json, subprocess
checks = []
checks.append(("worktree_exists", os.path.isdir("F:/Dropbox/Projects/BEI-ERP-s231-pricing-coupling-and-defaults-defense")))
checks.append(("baseline_captured", os.path.exists("output/s231/REMOTE_TRUTH_BASELINE.json")))
checks.append(("verifier_pre_run", os.path.exists("output/s231/verification/canonical_verifier_pre.txt")))
res = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True)
checks.append(("on_correct_branch", res.stdout.strip() == "s231-pricing-coupling-and-defaults-defense"))
fail = [c for c, ok in checks if not ok]
print("PASS" if not fail else f"FAIL: {fail}")
exit(0 if not fail else 1)
```

---

## Phase A — Probe + Unblock Ayala Fairview Terraces (8 units)

**Goal:** Get the CEO's JV save working today by fixing this one Company.

### A-1. Read-only probe via SSM (2 units)

Write `scripts/s231_probe_ayala_fairview.py` mirroring the SSM pattern in `scripts/s212_probe_frappe_errors.py`. Send a Python payload to the Frappe backend container that queries:

```python
# Inside container
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

candidates = frappe.db.sql("""
    SELECT name, abbr, store_ownership_type, parent_company, first_provision_done,
           default_inventory_account, default_payable_account, default_receivable_account,
           default_payroll_payable_account, default_employee_advance_account,
           default_expense_account, default_income_account,
           round_off_account, round_off_cost_center,
           default_cash_account, exchange_gain_loss_account,
           accumulated_depreciation_account, depreciation_expense_account,
           expenses_included_in_asset_valuation, disposal_account,
           depreciation_cost_center, capital_work_in_progress_account,
           asset_received_but_not_billed, stock_adjustment_account,
           stock_received_but_not_billed, expenses_included_in_valuation
    FROM `tabCompany`
    WHERE name LIKE '%Ayala Fairview%' OR name LIKE '%FT INC%' OR abbr = 'BFI2'
""", as_dict=True)

# For each candidate, check which referenced accounts exist
for c in candidates:
    missing = {}
    for field, value in c.items():
        if value and field.startswith(("default_", "round_off_", "exchange_", "accumulated_",
                                        "depreciation_", "expenses_", "disposal_", "capital_",
                                        "asset_", "stock_")):
            if field.endswith("_account") or field.endswith("_cost_center") or "_in_" in field:
                target_dt = "Cost Center" if "cost_center" in field else "Account"
                if not frappe.db.exists(target_dt, value):
                    missing[field] = value
    c["missing_refs"] = missing
```

Output: `output/s231/verification/ayala_fairview_probe.json` with full company state + missing-refs map.

**MUST_MODIFY:** `scripts/s231_probe_ayala_fairview.py`, `output/s231/verification/ayala_fairview_probe.json`
**MUST_CONTAIN (in probe JSON):** `"abbr"`, `"missing_refs"`, at least 1 entry per broken Company.

### A-2. Classify the broken Company (1 unit)

Based on probe output, decide:
- **Class 1:** `abbr=BFI2`, default_* fields point at `- BFI2` accounts that don't exist → CoA never seeded; need to create accounts under BFI2 OR null the defaults.
- **Class 2:** `abbr` ≠ `BFI2` but defaults point at `- BFI2` (cross-Company contamination) → must null the defaults; can't create cross-Company accounts.
- **Class 3:** Defaults point at accounts that DO exist but the linked accounts have `disabled=1` → un-disable or null.

Write `output/s231/verification/ayala_fairview_classification.md` documenting which class.

**MUST_MODIFY:** `output/s231/verification/ayala_fairview_classification.md`

### A-3. Apply fix (3 units)

**If Class 1 or 3:** decide based on probe — if accounts can be cheaply re-created via `retry_provision_company`, prefer that path:

```python
# Via SSM:
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")
from hrms.overrides.company import retry_provision_company
result = retry_provision_company(company_name="<exact docname>")
print(result)
frappe.db.commit()
```

**If Class 2 or `retry_provision_company` fails:** null the broken refs:

```python
fields_to_check = [
    "default_inventory_account", "default_payable_account", "default_receivable_account",
    "default_payroll_payable_account", "default_employee_advance_account",
    "default_expense_account", "default_income_account",
    "round_off_account", "round_off_cost_center",
    "default_cash_account", "exchange_gain_loss_account",
    "accumulated_depreciation_account", "depreciation_expense_account",
    "expenses_included_in_asset_valuation", "disposal_account",
    "depreciation_cost_center", "capital_work_in_progress_account",
    "asset_received_but_not_billed", "stock_adjustment_account",
    "stock_received_but_not_billed", "expenses_included_in_valuation",
]
for field in fields_to_check:
    value = frappe.db.get_value("Company", company_name, field)
    if value and not frappe.db.exists("Account", value) and not frappe.db.exists("Cost Center", value):
        frappe.db.set_value("Company", company_name, field, None, update_modified=False)
        # Log to ledger
frappe.db.commit()
```

Capture before/after in `output/s231/verification/ayala_fairview_fix_log.json`.

**MUST_MODIFY:** `scripts/s231_fix_company_defaults.py`, `output/s231/verification/ayala_fairview_fix_log.json`
**MUST_CONTAIN (in fix log):** `"company_name"`, `"fields_cleared"` OR `"accounts_created"`, `"timestamp"`

### A-4. Verify save works (2 units)

Run S1 + S2 from L3 Workflow Scenarios in a real browser via Playwright. Capture form_submission entries. The first save flips Co-Owned → JV; the second flips back; both must return 200.

Write to `output/l3/s231/form_submissions.json` (S1 + S2 entries) and `output/l3/s231/state_verification.json`.

**MUST_MODIFY:** `output/l3/s231/form_submissions.json`, `output/l3/s231/state_verification.json`
**MUST_CONTAIN (form_submissions.json):** `"scenario": "S1"`, `"scenario": "S2"`, both with `"status_code": 200`.

### Phase A verification script

```python
# output/s231/verify_phaseA.py
import json, os, subprocess
checks = []

# A-1
p = "output/s231/verification/ayala_fairview_probe.json"
checks.append(("probe_ran", os.path.exists(p)))
if os.path.exists(p):
    data = json.load(open(p))
    checks.append(("probe_found_company", len(data.get("candidates", [])) > 0))

# A-2
checks.append(("classification_written", os.path.exists("output/s231/verification/ayala_fairview_classification.md")))

# A-3
fix_log = "output/s231/verification/ayala_fairview_fix_log.json"
checks.append(("fix_applied", os.path.exists(fix_log)))

# A-4
fs = "output/l3/s231/form_submissions.json"
if os.path.exists(fs):
    submissions = json.load(open(fs))
    s1 = [s for s in submissions if s.get("scenario") == "S1"]
    s2 = [s for s in submissions if s.get("scenario") == "S2"]
    checks.append(("S1_passed", len(s1) > 0 and s1[0].get("status_code") == 200))
    checks.append(("S2_passed", len(s2) > 0 and s2[0].get("status_code") == 200))
else:
    checks.append(("S1_passed", False))

fail = [c for c, ok in checks if not ok]
print("PASS" if not fail else f"FAIL: {fail}")
exit(0 if not fail else 1)
```

If FAIL → fix root cause before Phase B. Do not skip.

---

## Phase B — Audit + Sweep All 49 Stores (12 units)

**Goal:** Find every store Company with the same broken-defaults pattern; fix them all in one pass.

### B-1. Build inventory script (3 units)

Write `scripts/s231_audit_broken_defaults.py`:

```python
# Operates via SSM. For every Company in tabCompany where entity_category = 'Store':
#   For each of the 21 default_* / round_off_* / depreciation_* fields:
#     If field has value AND target Account/Cost Center does NOT exist:
#       Mark field as broken; capture the orphan reference name.
# Output: output/s231/verification/broken_defaults_inventory.csv
# Columns: company_name, abbr, store_ownership_type, parent_company, first_provision_done,
#          field_name, current_value, target_doctype, ref_exists, action_recommended
```

The action_recommended column per row:
- `null_field` if the orphan has the company's own abbr → fix means accounts were never created
- `null_field` if the orphan has a different company's abbr → cross-contamination
- `enable_account` if the target exists but disabled=1
- `no_action` if reference is valid

Run dry-run first:
```bash
python scripts/s231_audit_broken_defaults.py --dry-run > output/s231/verification/broken_defaults_inventory.csv
```

**MUST_MODIFY:** `scripts/s231_audit_broken_defaults.py`, `output/s231/verification/broken_defaults_inventory.csv`

### B-2. Capture pre-touch backup (1 unit)

Before any mutation, snapshot all 49 Companies' default_* state:

```python
# scripts/s231_snapshot_defaults_pretouch.py — captures all 49 Companies' default_* fields
# Output: output/s231/state/PRETOUCH_BACKUP.json
```

**MUST_MODIFY:** `output/s231/state/PRETOUCH_BACKUP.json`
**MUST_CONTAIN:** `"companies"` array with ≥40 entries (49 stores ± inactive ones).

### B-3. Apply mass fix (4 units)

Run the fix in a savepoint per Company:

```python
# scripts/s231_fix_all_broken_defaults.py
# For each row in broken_defaults_inventory.csv where action_recommended != "no_action":
#   try: frappe.db.savepoint("s231_fix_<company>")
#         apply fix
#         frappe.db.release_savepoint(...)
#         append to TOUCH_PRESERVATION_LEDGER
#   except Exception:
#         frappe.db.rollback(save_point="s231_fix_<company>")
#         append to DEFECTS

# Strategy preference order per Company:
#   1. If first_provision_done=0 OR all 15 fields broken: try retry_provision_company
#   2. Otherwise: null only the broken fields
#   3. If retry fails AND nulling fails: log to DEFECTS for manual review
```

**MUST_MODIFY:** `scripts/s231_fix_all_broken_defaults.py`, `output/s231/ledgers/TOUCH_PRESERVATION_LEDGER.csv`, `output/s231/DEFECTS.md`
**MUST_CONTAIN (ledger):** at least one row per Company touched.

### B-4. Re-audit + sweep report (3 units)

Run the audit script again post-fix:

```bash
python scripts/s231_audit_broken_defaults.py --verify-after | tee output/s231/verification/broken_defaults_inventory_AFTER.csv
```

Compute sweep_report.json:
```python
{
  "scanned_companies": <n>,
  "broken_companies_before": <n>,
  "broken_companies_after": <expected: 0>,
  "fields_cleared": <n>,
  "accounts_created": <n>,
  "manual_review_required": <n; should be 0>,
  "samples_before": [...],
  "samples_after": [...],
}
```

**MUST_MODIFY:** `output/s231/verification/sweep_report.json`, `output/s231/verification/broken_defaults_inventory_AFTER.csv`
**MUST_CONTAIN (sweep_report):** `"broken_companies_after": 0`

### B-5. L3 scenario S3 (1 unit)

Browser test: pick `Robinsons Imus` (or any Managed Franchise from the broken list). Open detail dialog → Operations → toggle ownership type → save. Capture S3 to `form_submissions.json`.

**MUST_CONTAIN:** `"scenario": "S3"`, `"status_code": 200`

### Phase B verification script

```python
# output/s231/verify_phaseB.py
import json, os
sweep = json.load(open("output/s231/verification/sweep_report.json"))
checks = [
    ("scan_ran", sweep.get("scanned_companies", 0) >= 40),
    ("zero_broken_after", sweep.get("broken_companies_after") == 0),
    ("ledger_has_entries", os.path.getsize("output/s231/ledgers/TOUCH_PRESERVATION_LEDGER.csv") > 100),
]
fs = json.load(open("output/l3/s231/form_submissions.json"))
s3 = [s for s in fs if s.get("scenario") == "S3"]
checks.append(("S3_passed", len(s3) > 0 and s3[0].get("status_code") == 200))
fail = [c for c, ok in checks if not ok]
print("PASS" if not fail else f"FAIL: {fail}")
exit(0 if not fail else 1)
```

---

## Phase C — Permanent Atomicity Fix (12 units)

**Goal:** Make `auto_provision_company` so that a partial `create_default_accounts()` failure cannot leave defaults orphaned again.

### C-1. Atomicity wrapper (5 units)

Modify `hrms/overrides/company.py:638-714` (`auto_provision_company`):

**Current flawed pattern:**
```python
try:
    frappe.db.savepoint("s181_auto_provision")
    try:
        if hasattr(doc, "create_default_accounts"):
            doc.create_default_accounts()
        ...
    except Exception as erpnext_err:
        frappe.log_error(...)  # ← swallowed; field-value writes survive
    # ... continues even after partial failure
    _s181_apply_balance_sheet_template(doc)
    ...
    frappe.db.set_value("Company", doc.name, "first_provision_done", 1)  # ← flips even on partial
    frappe.db.release_savepoint("s181_auto_provision")
except Exception:
    frappe.db.rollback(save_point="s181_auto_provision")
```

**Fixed pattern (S231-C1):**
```python
DEFAULT_FIELDS_TO_TRACK = [
    "default_inventory_account", "default_payable_account", "default_receivable_account",
    "default_payroll_payable_account", "default_employee_advance_account",
    "default_expense_account", "default_income_account",
    "round_off_account", "round_off_cost_center",
    "default_cash_account", "exchange_gain_loss_account",
    "accumulated_depreciation_account", "depreciation_expense_account",
    "expenses_included_in_asset_valuation", "disposal_account",
    "depreciation_cost_center", "capital_work_in_progress_account",
    "asset_received_but_not_billed", "stock_adjustment_account",
    "stock_received_but_not_billed", "expenses_included_in_valuation",
]

try:
    frappe.db.savepoint("s181_auto_provision")
    pre_state = {f: frappe.db.get_value("Company", doc.name, f) for f in DEFAULT_FIELDS_TO_TRACK}

    erpnext_succeeded = True
    try:
        if hasattr(doc, "create_default_accounts"):
            doc.create_default_accounts()
        if hasattr(doc, "create_default_warehouses"):
            doc.create_default_warehouses()
        if hasattr(doc, "create_default_cost_center"):
            doc.create_default_cost_center()
    except Exception as erpnext_err:
        erpnext_succeeded = False
        frappe.log_error(
            title=f"S181 ERPNext default seeding failed for {doc.name} (S231-C1: rolling back field writes)",
            message=str(erpnext_err),
        )

    if not erpnext_succeeded:
        # S231-C1: Restore pre_state values so partial-failure doesn't leave dead refs
        for f, v in pre_state.items():
            current = frappe.db.get_value("Company", doc.name, f)
            if current != v:
                frappe.db.set_value("Company", doc.name, f, v, update_modified=False)
        # Continue with S181 templates — they don't depend on ERPNext defaults completing

    # ... S181 templates ...

    # S231-C1: Verify all default_* fields point at existing Accounts before flipping sentinel
    invalid_after = []
    for f in DEFAULT_FIELDS_TO_TRACK:
        v = frappe.db.get_value("Company", doc.name, f)
        if v:
            target_dt = "Cost Center" if "cost_center" in f else "Account"
            if not frappe.db.exists(target_dt, v):
                invalid_after.append((f, v))
                frappe.db.set_value("Company", doc.name, f, None, update_modified=False)

    if invalid_after:
        frappe.log_error(
            title=f"S231-C1 cleared {len(invalid_after)} dead defaults on {doc.name} after provision",
            message=str(invalid_after),
        )

    frappe.db.set_value("Company", doc.name, "first_provision_done", 1, update_modified=False)
    frappe.db.release_savepoint("s181_auto_provision")
    # ... msgprint ...
except Exception:
    frappe.db.rollback(save_point="s181_auto_provision")
    # ... existing logic ...
```

**MUST_MODIFY:** `hrms/overrides/company.py`
**MUST_CONTAIN:** `"S231-C1"`, `DEFAULT_FIELDS_TO_TRACK`, the `erpnext_succeeded = False` restore loop, the `invalid_after` clear loop.

### C-2. Defense-in-depth validate hook (4 units)

Add a new validate-time function that nulls bogus defaults proactively, so legacy Companies that bypass auto_provision (or future regressions) don't trigger LinkValidationError on save:

```python
# hrms/overrides/company.py — new function
def null_out_dead_default_refs(doc, method=None):
    """S231-C2: At validate time, null any default_*/round_off_*/etc field whose
    referenced Account/Cost Center no longer exists. Defense-in-depth so a
    user editing a Company never trips _validate_links() on dead refs that
    create_default_accounts orphaned in the past."""
    DEFAULT_FIELDS_TO_TRACK = [...]  # same list as C-1
    cleared = []
    for f in DEFAULT_FIELDS_TO_TRACK:
        v = doc.get(f)
        if v:
            target_dt = "Cost Center" if "cost_center" in f else "Account"
            if not frappe.db.exists(target_dt, v):
                doc.set(f, None)
                cleared.append((f, v))
    if cleared:
        frappe.log_error(
            title=f"S231-C2: cleared {len(cleared)} dead default refs on {doc.name}",
            message=str(cleared),
        )
```

Wire it into `hooks.py` `Company.validate` chain:

```python
# hrms/hooks.py — line 181-200
"Company": {
    "validate": [
        "hrms.overrides.company.validate_default_accounts",
        "hrms.overrides.company.null_out_dead_default_refs",  # S231-C2
    ],
    ...
}
```

**MUST_MODIFY:** `hrms/overrides/company.py`, `hrms/hooks.py`
**MUST_CONTAIN (hooks.py):** `"hrms.overrides.company.null_out_dead_default_refs"` in the Company validate list.

### C-3. Unit tests (3 units)

Write `hrms/tests/test_s231_atomicity.py`:

```python
import frappe
from unittest.mock import patch

class TestS231Atomicity:
    def test_partial_create_default_accounts_failure_rolls_back_field_writes(self):
        # Create a fresh Company without first_provision_done set
        # Mock doc.create_default_accounts to set default_inventory_account then raise
        # Assert: after auto_provision_company, default_inventory_account is None
        # Assert: first_provision_done is still 0 (so retry_provision_company can re-run)
        ...

    def test_invalid_after_check_clears_dead_refs(self):
        # Set default_inventory_account to a non-existent Account
        # Run auto_provision_company
        # Assert: field is None after
        ...

    def test_validate_hook_clears_dead_refs_on_save(self):
        # Set default_inventory_account to "FakeAccount - X"
        # Save the Company doc
        # Assert: save succeeds (no LinkValidationError)
        # Assert: default_inventory_account is None after
        ...
```

**MUST_MODIFY:** `hrms/tests/test_s231_atomicity.py`
**MUST_CONTAIN:** `test_partial_create_default_accounts_failure_rolls_back_field_writes`, `test_invalid_after_check_clears_dead_refs`, `test_validate_hook_clears_dead_refs_on_save`

Run via `bench --site hq.bebang.ph run-tests --module hrms.tests.test_s231_atomicity`.

### Phase C verification script

```python
# output/s231/verify_phaseC.py
import subprocess, os
checks = []

# C-1
co = open("hrms/overrides/company.py").read()
checks.append(("C1_marker_present", "S231-C1" in co))
checks.append(("C1_default_fields_constant", "DEFAULT_FIELDS_TO_TRACK" in co))
checks.append(("C1_pre_state_capture", "pre_state =" in co))
checks.append(("C1_invalid_after_clear", "invalid_after" in co))

# C-2
checks.append(("C2_validate_fn", "null_out_dead_default_refs" in co))
hooks = open("hrms/hooks.py").read()
checks.append(("C2_hook_wired", "null_out_dead_default_refs" in hooks))

# C-3
test_file = "hrms/tests/test_s231_atomicity.py"
checks.append(("C3_tests_exist", os.path.exists(test_file)))
if os.path.exists(test_file):
    t = open(test_file).read()
    checks.append(("C3_partial_test", "test_partial_create_default_accounts_failure" in t))
    checks.append(("C3_invalid_test", "test_invalid_after_check_clears_dead_refs" in t))
    checks.append(("C3_validate_test", "test_validate_hook_clears_dead_refs_on_save" in t))

# S9 L3 scenario must pass after deploy
fs = open("output/l3/s231/form_submissions.json").read()
checks.append(("S9_in_evidence", '"scenario": "S9"' in fs))

fail = [c for c, ok in checks if not ok]
print("PASS" if not fail else f"FAIL: {fail}")
exit(0 if not fail else 1)
```

---

## Phase D — Pricing Coupling Completion (30 units, split D1-D5)

### D-1. Add `bki_markup_company_owned_percent` field (4 units)

Edit `hrms/hr/doctype/bei_settings/bei_settings.json`:
- Add to fields array after `bki_markup_full_franchise_percent`:
  ```json
  {
    "fieldname": "bki_markup_company_owned_percent",
    "fieldtype": "Percent",
    "label": "BKI Markup % — Company Owned",
    "default": "2.75",
    "description": "S231 D-1: intercompany markup applied when BKI delivers to a Company-owned store. Per CEO 2026-05-02: Co-Owned = same rate as JV (2.75%)."
  }
  ```
- Add `bki_markup_company_owned_percent` to the field list at top.

After deploy, set the value on the live BEI Settings via SSM:
```python
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.db.set_single_value("BEI Settings", "bki_markup_company_owned_percent", 2.75)
frappe.db.commit()
```

**MUST_MODIFY:** `hrms/hr/doctype/bei_settings/bei_settings.json`, `output/s231/verification/markup_settings_after.json` (post-deploy capture)
**MUST_CONTAIN (settings JSON):** `"bki_markup_company_owned_percent"`, `"default": "2.75"`

### D-2. Verify ownership-type→markup live coupling (4 units)

For each ownership type (Co-Owned, JV, Managed Franchise, Full Franchise), pick a representative store, simulate a BKI Material Issue Stock Entry to that store's warehouse, run `create_draft_store_sale_invoices(stock_entry)`, and verify the resulting SI's `items[0].rate = basic_rate × (1 + markup_rate)`.

Write `scripts/s231_verify_markup_coupling.py`:

```python
TEST_STORES = {
    "Company Owned": "<pick one>",
    "JV": "Ayala Fairview Terraces",  # post-Phase A
    "Managed Franchise": "SM San Jose Del Monte - <parent>",
    "Full Franchise": "Ever Gotesco - DLS Dessert Craft Inc.",
}
expected_markup = {
    "Company Owned": 0.0275,
    "JV": 0.0275,
    "Managed Franchise": 0.08,
    "Full Franchise": 0.08,
}

# For each store: create test SE, call create_draft_store_sale_invoices, verify SI rate
```

Output: `output/s231/verification/markup_coupling_test.json`.

**MUST_MODIFY:** `scripts/s231_verify_markup_coupling.py`, `output/s231/verification/markup_coupling_test.json`
**MUST_CONTAIN:** all 4 ownership types tested with `expected_markup` matching `actual_markup` to within 0.01%.

### D-3. Monthly billing automation (12 units)

Add `hrms/api/billing.py` function:

```python
@frappe.whitelist()
def run_monthly_franchise_billing(period: str, dry_run: int = 0) -> dict:
    """S231-D3: Generate ONE consolidated BEI Billing Schedule row per store
    per month covering Royalty + Marketing + Management + E-commerce.
    Computed from the store's POS sales (via existing aggregator) × rate.

    period: "YYYY-MM"
    Rate per ownership type:
      JV:                Marketing 5% (gross), E-com 5% (website_sales only)
      Managed Franchise: Royalty 7% (net ex-VAT), Marketing 5% (net ex-VAT),
                         Management 2.5% (gross), E-com 5% (website_sales)
      Full Franchise:    Royalty 7%, Marketing 5%, E-com 5% (NO Management)
      Company Owned:     no fees (skip)

    Recipient:
      JV:                BEI revenue (per JV agreement Sec 8.1, 9.1)
      Managed/Full:      BFC revenue (collected by BEI as agent during interim
                         per Collection Agent Letter; SI.company = BFC)

    Idempotent: if a BEI Billing Schedule row already exists for (store, period),
    skip and log; do NOT create duplicates.

    Returns: {created: <n>, skipped: <n>, errors: <list>, total_billed: <PHP>}
    """
    set_backend_observability_context(
        module="billing",
        action="run_monthly_franchise_billing",
        mutation_type="create",
        extras={"period": period, "dry_run": bool(dry_run)},
    )
    # ... implementation
```

Helper functions:

```python
def _get_store_period_sales(company_name: str, period: str) -> dict:
    """Returns {gross_sales, net_sales_ex_vat, website_sales} for the period.
    Sources: existing tabBEI Sales Daily aggregation (or whatever the canonical
    aggregator is — verify in research)."""

def _compute_fee_lines(ownership_type: str, sales: dict) -> list[dict]:
    """Returns [{fee_type, rate, base, amount}, ...] per ownership type."""

def _resolve_fee_recipient(ownership_type: str) -> tuple[str, str]:
    """Returns (recipient_company, recipient_customer_relationship_pattern)."""

def _create_or_update_billing_schedule(store, period, fee_lines, recipient):
    """Creates BEI Billing Schedule (or updates existing for idempotency).
    Also creates the underlying Sales Invoice for the period."""
```

Schedule a daily cron that fires on the 1st of each month for the previous month's billing:

```python
# hrms/hooks.py scheduler_events
"daily": [
    ...,
    "hrms.api.billing.run_monthly_franchise_billing_cron",  # S231-D3
],
```

```python
def run_monthly_franchise_billing_cron():
    """S231-D3 daily cron — fires on 1st of each month at scheduled time;
    other days no-op."""
    today = frappe.utils.getdate()
    if today.day != 1:
        return
    prev = today.replace(day=1) - frappe.utils.timedelta(days=1)
    period = prev.strftime("%Y-%m")
    run_monthly_franchise_billing(period=period, dry_run=0)
```

**MUST_MODIFY:** `hrms/api/billing.py`, `hrms/hooks.py`
**MUST_CONTAIN (billing.py):** `run_monthly_franchise_billing`, `_get_store_period_sales`, `_compute_fee_lines`, `_resolve_fee_recipient`, `set_backend_observability_context(module="billing"`
**MUST_CONTAIN (hooks.py):** `"hrms.api.billing.run_monthly_franchise_billing_cron"` in scheduler_events

### D-4. Recipient routing (BEI vs BFC) + Collection Agent JE (6 units)

In `_resolve_fee_recipient`:

```python
def _resolve_fee_recipient(ownership_type: str) -> dict:
    """S231-D4: Returns {company, customer_for_si, intercompany_pattern}.

    Per CEO 2026-05-02 + Collection Agent Letter draft:
    - JV:                  BEI revenue PERMANENTLY. SI.company = "Bebang Enterprise Inc."
                           SI.customer = the per-store billing Customer.
                           Fee accounts: 4000231-4000235 ON BEI (not BFC).
    - Managed Franchise:   BFC revenue (collected by BEI as agent during interim).
                           SI.company = "Bebang Franchise Corp." (the FRANCHISOR per the agreement).
                           SI.customer = the per-store billing Customer (same as JV).
                           Fee accounts: 4000231-4000235 ON BFC.
                           BEI books no revenue; if BEI receives the cash physically,
                           it credits "DUE TO BFC" liability (Collection Agent Letter §3).
    - Full Franchise:      Same as Managed Franchise but NO Management fee.
    """
    if ownership_type == "JV":
        return {"company": "Bebang Enterprise Inc.", "intercompany": False}
    if ownership_type in ("Managed Franchise", "Full Franchise"):
        return {"company": "Bebang Franchise Corp.", "intercompany": True}
    if ownership_type == "Company Owned":
        return {"company": None, "intercompany": False}  # skip billing entirely
    raise ValueError(f"S231-D4: unknown ownership_type {ownership_type!r}")
```

For `intercompany=True`, the Collection Agent JE (when BEI physically receives cash from franchisee but title belongs to BFC) is **out of scope for this sprint** — that's a future cash-handling sprint. This sprint creates the SI on BFC's books only; cash flow is handled in the next operational sprint when BFC's bank account opens.

Document this in a `MIGRATION_NOTES.md` for the eventual cash-handling sprint:

```markdown
# output/s231/MIGRATION_NOTES.md

After S231 ships, monthly franchise SIs are created on BFC company. To complete the
BEI-as-collection-agent flow described in `04_BEI_BFC_Collection_Agent_Letter_DRAFT.md`,
a future sprint must:
1. Print BFC's BIR-registered OR booklet on each SI payment.
2. Implement BEI's `2104200 DUE TO BFC` liability account JE pattern when cash
   is received in BEI's bank on BFC's behalf.
3. Implement the cash sweep entry from BEI to BFC at month cutover.
```

**MUST_MODIFY:** `hrms/api/billing.py` (with `_resolve_fee_recipient` per spec), `output/s231/MIGRATION_NOTES.md`

### D-5. Frontend fee-impact preview UI (4 units)

Modify `bei-tasks/app/dashboard/bd/companies/company-detail-dialog.tsx`:

Add a `<FeePreviewPanel>` component that renders inside the Operations section card. When the user opens the SectionEditModal for `operations` and changes the `store_ownership_type` Select, the panel updates in real time showing:
- BKI delivery markup % (read from BEI Settings via existing API or hardcoded as currently configured)
- Monthly fee schedule applicable: Royalty / Marketing / Management / E-commerce, with rate + base + recipient (BEI vs BFC)
- "Effective on save" hint

```tsx
// New file: bei-tasks/components/company-master/fee-preview-panel.tsx
"use client";
import { Badge } from "@/components/ui/badge";

interface FeePreviewPanelProps {
  ownershipType: string | null;
  markupRates: { jv: number; managed: number; full: number; co: number };
}

const FEE_MATRIX = {
  "Company Owned": {
    fees: [],
    note: "Internal entity — no royalty, marketing, or management fees.",
  },
  "JV": {
    fees: [
      { name: "Marketing", rate: "5% of gross sales", recipient: "BEI", base: "All sales" },
      { name: "E-commerce", rate: "5% of website sales", recipient: "BEI", base: "bebang.ph + app only" },
    ],
    note: "Profit share (60/40 → 50/50 → 40/60 phased) handled manually in P&L.",
  },
  "Managed Franchise": {
    fees: [
      { name: "Royalty", rate: "7% of net ex-VAT", recipient: "BFC", base: "Gross sales − VAT" },
      { name: "Marketing", rate: "5% of net ex-VAT", recipient: "BFC", base: "Gross sales − VAT" },
      { name: "Management", rate: "2.5% of gross", recipient: "BFC", base: "All sales" },
      { name: "E-commerce", rate: "5% of website sales", recipient: "BFC", base: "bebang.ph + app only" },
    ],
    note: "Single consolidated monthly billing on the 1st of each month.",
  },
  "Full Franchise": {
    fees: [
      { name: "Royalty", rate: "7% of net ex-VAT", recipient: "BFC", base: "Gross sales − VAT" },
      { name: "Marketing", rate: "5% of net ex-VAT", recipient: "BFC", base: "Gross sales − VAT" },
      { name: "E-commerce", rate: "5% of website sales", recipient: "BFC", base: "bebang.ph + app only" },
    ],
    note: "No Management Fee — franchisee runs operations.",
  },
};

export function FeePreviewPanel({ ownershipType, markupRates }: FeePreviewPanelProps) {
  if (!ownershipType) return null;
  const data = FEE_MATRIX[ownershipType];
  const markupKey = ownershipType === "Company Owned" ? "co" : ownershipType === "JV" ? "jv" : ownershipType === "Managed Franchise" ? "managed" : "full";
  const markup = markupRates[markupKey];
  return (
    <div data-testid="fee-preview-panel" className="mt-3 rounded border p-3 bg-muted/20">
      <h4 className="text-sm font-semibold">Fee Impact Preview — {ownershipType}</h4>
      <p className="text-xs text-muted-foreground">BKI inventory delivery markup: <strong>{(markup * 100).toFixed(2)}%</strong></p>
      {data?.fees.length === 0 ? (
        <p className="text-xs italic">{data.note}</p>
      ) : (
        <table className="mt-2 w-full text-xs">
          <thead><tr><th className="text-left">Fee</th><th className="text-left">Rate</th><th className="text-left">Recipient</th></tr></thead>
          <tbody>
            {data?.fees.map((f) => (
              <tr key={f.name}>
                <td className="py-1">{f.name}</td>
                <td>{f.rate}</td>
                <td><Badge variant="outline">{f.recipient}</Badge></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="mt-2 text-xs italic text-muted-foreground">{data?.note}</p>
      <p className="mt-1 text-xs italic">Rates lock at month-end — mid-month flips apply to the next month's bill.</p>
    </div>
  );
}
```

Wire it inside `SectionEditModal` (or `company-detail-dialog.tsx`) so when the user is editing the operations section and changes the ownership type Select, the panel re-renders with the new type.

**MUST_MODIFY:** `bei-tasks/components/company-master/fee-preview-panel.tsx` (new), `bei-tasks/app/dashboard/bd/companies/company-detail-dialog.tsx` OR `bei-tasks/components/company-master/section-edit-modal.tsx` (whichever owns the ownership-type Select)
**MUST_CONTAIN:** `data-testid="fee-preview-panel"`, `FEE_MATRIX`, all 4 ownership types as keys in FEE_MATRIX

### Phase D verification script

```python
# output/s231/verify_phaseD.py
import json, os, subprocess
checks = []

# D-1
settings = open("hrms/hr/doctype/bei_settings/bei_settings.json").read()
checks.append(("D1_field_added", '"bki_markup_company_owned_percent"' in settings))
checks.append(("D1_default_2.75", '"default": "2.75"' in settings))

# D-2
mc = open("output/s231/verification/markup_coupling_test.json")
data = json.load(mc)
for ot in ["Company Owned", "JV", "Managed Franchise", "Full Franchise"]:
    rec = next((r for r in data["results"] if r["ownership_type"] == ot), None)
    checks.append((f"D2_{ot}_tested", rec is not None and rec.get("match") is True))

# D-3
billing = open("hrms/api/billing.py").read()
checks.append(("D3_fn_added", "run_monthly_franchise_billing" in billing))
checks.append(("D3_helpers", all(h in billing for h in ["_get_store_period_sales", "_compute_fee_lines", "_resolve_fee_recipient"])))
checks.append(("D3_observability", 'set_backend_observability_context(module="billing"' in billing))
hooks = open("hrms/hooks.py").read()
checks.append(("D3_cron_wired", "run_monthly_franchise_billing_cron" in hooks))

# D-4
checks.append(("D4_routing", '"Bebang Enterprise Inc."' in billing and '"Bebang Franchise Corp."' in billing))
checks.append(("D4_migration_notes", os.path.exists("output/s231/MIGRATION_NOTES.md")))

# D-5
preview = "../bei-tasks-s231-fee-preview-ui/components/company-master/fee-preview-panel.tsx"
checks.append(("D5_panel_exists", os.path.exists(preview)))
if os.path.exists(preview):
    p = open(preview).read()
    checks.append(("D5_testid", 'data-testid="fee-preview-panel"' in p))
    checks.append(("D5_all_types", all(t in p for t in ["Company Owned", "JV", "Managed Franchise", "Full Franchise"])))

# L3 scenarios S4, S5, S6, S7, S10
fs = json.load(open("output/l3/s231/form_submissions.json"))
for s in ["S4", "S5", "S6", "S7", "S10"]:
    rec = next((x for x in fs if x.get("scenario") == s), None)
    checks.append((f"{s}_passed", rec is not None and rec.get("status_code") in (200, 201)))

fail = [c for c, ok in checks if not ok]
print("PASS" if not fail else f"FAIL: {fail}")
exit(0 if not fail else 1)
```

---

## Phase E — Naming Canonicalization (6 units)

**Goal:** Replace `Bebang FTE Inc.` references with `BEBANG FT INC.` everywhere.

### E-1. Inventory of `Bebang FTE Inc.` references (1 unit)

```bash
# In worktree:
grep -rln "Bebang FTE Inc\." . > output/s231/verification/fte_references.txt 2>/dev/null
grep -rln "BEBANG FTE INC\." . >> output/s231/verification/fte_references.txt 2>/dev/null
# Plus production DB scan via SSM
```

Production DB scan:
```python
# Search tabCustomer, tabSupplier, tabAddress, tabContact for "Bebang FTE Inc."
for dt in ["Customer", "Supplier", "Address", "Contact"]:
    rows = frappe.db.sql(f"SELECT name, * FROM `tab{dt}` WHERE name LIKE '%FTE Inc%' OR ...", as_dict=True)
```

**MUST_MODIFY:** `output/s231/verification/fte_references.txt`, `output/s231/verification/fte_db_scan.json`

### E-2. Rename in seed CSVs (2 units)

Replace `Bebang FTE Inc.` → `BEBANG FT INC.` in:
- `hrms/data_seed/store_entity_mapping_2026-04-14.csv`
- `hrms/data_seed/store_entity_mapping_2026-04-13.csv`
- `hrms/data_seed/bir_entity_register_2026-04-13.csv`
- `hrms/data_seed/store_buyer_entity_register_2026-03-12.csv`

(do this with surgical Edit, not a sed run, so we can verify each row).

**MUST_MODIFY:** above 4 files
**MUST_CONTAIN (after edit):** zero occurrences of `Bebang FTE Inc.` in those files (`grep -c` returns 0).

### E-3. Rename in production records (2 units)

Build `scripts/s231_rename_fte_references.py` (uses `/frappe-bulk-edits` SSM pattern):

```python
# Idempotent: only rename rows where current value matches source pattern.
# Capture before/after to output/s231/verification/naming_rename_log.json.

RENAME_RULES = [
    ("Customer", "customer_name", "Bebang FTE Inc.", "BEBANG FT INC."),
    ("Supplier", "supplier_name", "Bebang FTE Inc.", "BEBANG FT INC."),
    ("Customer", "customer_name", "BEBANG FTE INC.", "BEBANG FT INC."),
    # ... per discovery results
]

# If the Frappe Company "Bebang FTE Inc." exists separately from "BEBANG FT INC.",
# DO NOT rename it. STOP and ask the CEO whether to merge or keep separate.
```

If audit shows >50 records to rename, STOP per Autonomous Execution Contract.

**MUST_MODIFY:** `scripts/s231_rename_fte_references.py`, `output/s231/verification/naming_rename_log.json`

### E-4. Verify (1 unit)

Re-run E-1 inventory. Result must show zero `Bebang FTE Inc.` references in the codebase. DB scan must show zero in renamed doctypes.

**MUST_MODIFY:** `output/s231/verification/fte_references_AFTER.txt`
**MUST_CONTAIN:** `0 references` OR file empty

### Phase E verification script

```python
# output/s231/verify_phaseE.py
import os, json, subprocess
checks = []

# E-1
checks.append(("inventory_done", os.path.exists("output/s231/verification/fte_references.txt")))
checks.append(("db_scan_done", os.path.exists("output/s231/verification/fte_db_scan.json")))

# E-2
for f in [
    "hrms/data_seed/store_entity_mapping_2026-04-14.csv",
    "hrms/data_seed/store_entity_mapping_2026-04-13.csv",
    "hrms/data_seed/bir_entity_register_2026-04-13.csv",
    "hrms/data_seed/store_buyer_entity_register_2026-03-12.csv",
]:
    if os.path.exists(f):
        content = open(f).read()
        checks.append((f"E2_{os.path.basename(f)}_clean", "Bebang FTE Inc." not in content and "BEBANG FTE INC." not in content))

# E-3
checks.append(("E3_log_exists", os.path.exists("output/s231/verification/naming_rename_log.json")))

# E-4
after = "output/s231/verification/fte_references_AFTER.txt"
if os.path.exists(after):
    checks.append(("E4_zero_refs", os.path.getsize(after) == 0 or "0 references" in open(after).read()))

fail = [c for c, ok in checks if not ok]
print("PASS" if not fail else f"FAIL: {fail}")
exit(0 if not fail else 1)
```

---

## Closeout Phase (6 units)

### CL-1. Run final canonical verifier (1 unit)
```bash
python scripts/verify_canonical_structure.py 2>&1 | tee output/s231/verification/canonical_verifier_post.txt
```
Diff vs pre — only acceptable difference: violations that were pre-existing AND unrelated to S231 scope.

**MUST_MODIFY:** `output/s231/verification/canonical_verifier_post.txt`

### CL-2. Run all phase verification scripts (1 unit)
```bash
for p in 0 A B C D E; do
  python output/s231/verify_phase${p}.py
done
```
All must print PASS.

### CL-3. Tear down test fixtures (1 unit)
```bash
python scripts/s231_teardown_l3_fixtures.py
```

**MUST_MODIFY:** `output/l3/s231/teardown_complete.json`
**MUST_CONTAIN:** `"remaining": 0`

### CL-4. Write SUMMARY.md + DEFECTS.md (1 unit)

Format:
```markdown
# S231 Closeout Summary

**Status:** COMPLETED 2026-05-XX
**Branches:** s231-pricing-coupling-and-defaults-defense (hrms), s231-fee-preview-ui (bei-tasks)
**PRs:** hrms #XXX, bei-tasks #YYY

## Phases Completed
- Phase 0 — Boot ✓
- Phase A — Probe + Fix Ayala Fairview ✓ (1 Company fixed)
- Phase B — Audit + Sweep 49 Stores ✓ (N companies cleaned)
- Phase C — Atomicity Fix ✓ (3 unit tests pass)
- Phase D — Pricing Coupling ✓
- Phase E — Naming Canonicalization ✓

## L3 Scenarios — 10/10 PASS

## Defects Found During Execution
(see DEFECTS.md)

## CEO Signoff Block
- [ ] Reviewed both PRs
- [ ] Verified L3 evidence
- [ ] Approved markup rate (Co-Owned 2.75%)
```

**MUST_MODIFY:** `output/s231/SUMMARY.md`, `output/s231/DEFECTS.md`, `output/s231/RUN_STATUS.json`, `output/l3/s231/SUMMARY.md`

### CL-5. Create PRs + update plan/registry (1 unit)

**hrms PR** (`s231-pricing-coupling-and-defaults-defense` → `production`):
```bash
GH_TOKEN="" gh pr create \
  --repo Bebang-Enterprise-Inc/hrms \
  --base production \
  --head s231-pricing-coupling-and-defaults-defense \
  --title "S231: Pricing Coupling + Defaults Validation Defense" \
  --body "$(cat output/s231/SUMMARY.md)"
```

**bei-tasks PR** (`s231-fee-preview-ui` → `main`).

Update plan YAML:
```yaml
status: PR_CREATED
completed_date: 2026-05-XX
pr_url: https://github.com/Bebang-Enterprise-Inc/hrms/pull/XXX
execution_summary: |
  ...
```

Update SPRINT_REGISTRY.md row for S231: `PLANNED 2026-05-02` → `PR_CREATED 2026-05-XX — hrms #XXX, bei-tasks #YYY`.

```bash
git add -f docs/plans/2026-05-02-sprint-231-pricing-coupling-and-defaults-defense.md
git add -f docs/plans/SPRINT_REGISTRY.md
git add -f output/s231/ output/l3/s231/
git commit -m "S231 closeout — PRs created, plan + registry updated"
git push origin s231-pricing-coupling-and-defaults-defense
```

**MUST_MODIFY:** plan file YAML, `docs/plans/SPRINT_REGISTRY.md`
**STOP HERE — PR HANDOFF.** Do NOT merge. Do NOT deploy. Sam reviews + Release Manager Gate + merge.

### CL-6. Remove worktree (1 unit)

After PRs created and Sam acknowledges:
```bash
cd F:/Dropbox/Projects/BEI-ERP-s231-pricing-coupling-and-defaults-defense
git status --short  # MUST be clean
cd F:/Dropbox/Projects/BEI-ERP
git worktree remove F:/Dropbox/Projects/BEI-ERP-s231-pricing-coupling-and-defaults-defense
git worktree list  # confirm removed

cd F:/Dropbox/Projects/bei-tasks-s231-fee-preview-ui
git status --short
cd F:/Dropbox/Projects/bei-tasks
git worktree remove F:/Dropbox/Projects/bei-tasks-s231-fee-preview-ui
```

If any uncommitted: commit to a follow-up branch (per the "every new fix = new branch" rule), don't `--force` remove.

---

## Sentry Observability (DM-7)

Required `set_backend_observability_context()` calls:

| Function | module | action | mutation_type |
|---|---|---|---|
| `null_out_dead_default_refs` (Phase C-2) | `company` | `null_out_dead_default_refs` | `update` |
| `run_monthly_franchise_billing` (Phase D-3) | `billing` | `run_monthly_franchise_billing` | `create` |
| `run_monthly_franchise_billing_cron` (Phase D-3) | `billing` | `run_monthly_franchise_billing_cron` | `create` |

Frontend — no manual instrumentation (Next.js auto-instruments via `@sentry/nextjs`).

---

## Forbidden Agent Behaviors (Zero-Skip Enforcement)

The executing agent MUST NOT:

- Skip Phase B sweep because "Phase A already fixed Ayala Fairview"
- Mark Phase C as DONE if any of the 3 unit tests fail (test failures ARE blockers)
- Replace the `null_out_dead_default_refs` validate hook with a simpler version that doesn't actually check `frappe.db.exists`
- Combine the cron + the manual API into one — they MUST be two separate functions (cron is the daily firing, API is the runner)
- Skip recipient routing in Phase D-4 by always using BEI as company (would route franchise revenue wrong)
- Skip the fee preview UI because "the rates can be looked up elsewhere"
- Use a hardcoded markup rate constant in `commissary.py` instead of reading from BEI Settings (S190 retired the CSV — Settings is the SSOT)
- Modify the existing `markup_by_type` block at `commissary.py:1077-1099` (already shipped in S168/S212 — read-only verify only)
- Bypass `_validate_links()` in `update_company_section` (would mask the real issue)
- Comment out or remove the `_validate_links()` call (Frappe upstream — out of scope)
- Run `git push --force` to production
- Merge any PR
- Skip teardown ("we'll clean up later")
- Mark teardown complete without verifying counts == 0

If any of these is the only path forward, STOP per Autonomous Execution Contract.

---

## Execution Skills Reference

- Test Python changes: `/local-frappe`
- Bulk edit production data: `/frappe-bulk-edits` (S229 contract)
- Deploy: out of scope — Sam handles via `/deploy-frappe` after PR merge
- Multi-agent coordination if needed: `/teammates`

---

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.
After PRs are created and registry updated, **STOP at PR handoff**. Sam handles merge + deploy + L1 smoke.

---

## Final Plan Checklist

- [x] `canonical_scope: in` declared with full Preflight + Binding sections
- [x] Branch `s231-pricing-coupling-and-defaults-defense` reserved in registry
- [x] Plan filename matches policy: `docs/plans/2026-05-02-sprint-231-pricing-coupling-and-defaults-defense.md`
- [x] YAML evidence_committed + evidence_transient declared
- [x] Phase 0 spawns worktree from origin/production
- [x] Closeout removes worktree
- [x] Total work units 78 (under 80 ceiling)
- [x] No phase exceeds 12 units (Phase D split into D1-D5; D3 sits at 12 with split rule documented)
- [x] L3 Workflow Scenarios table (10 scenarios)
- [x] Test Data Seeding Contract present
- [x] Requirements Regression Checklist (16 items)
- [x] Design Rationale section (cold-start friendly)
- [x] Sentry observability tasks named per DM-7
- [x] Anti-Rewind / Concurrent-Run Protection contract
- [x] Status Reconciliation contract
- [x] Signoff Model named (single-owner — Sam)
- [x] Autonomous Execution Contract with stop_only_for list
- [x] MUST_MODIFY assertions on every file-touching task
- [x] MUST_CONTAIN assertions for content-bearing artifacts
- [x] Verification scripts per phase (Phase 0 + A + B + C + D + E)
- [x] Phase E rename uses 4 named seed files
- [x] PR-Handoff: agent stops at PR creation; Sam merges + deploys
- [x] Cold-start test: every external table/field/path/route/command is concrete
- [x] Forbidden Agent Behaviors section explicit
