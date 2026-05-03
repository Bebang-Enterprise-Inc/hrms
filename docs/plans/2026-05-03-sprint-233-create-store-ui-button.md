---
sprint_id: S233
display: Sprint 233
title: Add "Create Store" UI button on Company Master + canonical create_new_store helper
status: PLANNED
version: v2
created_date: 2026-05-03
amended_date: 2026-05-03
completed_date: null
execution_summary: null
canonical_scope: in
canonical_model_reference: docs/STORE_COMPANY_CANONICAL.md
canonical_preflight: required
branch: s233-plan-v2-amendments
v1_branch: s233-create-store-ui-button (MERGED via PR #713 — DO NOT push to)
target_repos:
  - hrms (Bebang-Enterprise-Inc/hrms)
  - bei-tasks (Bebang-Enterprise-Inc/BEI-Tasks)
base_branch: production (hrms) / main (bei-tasks)
pr_url: null
v1_pr_url: https://github.com/Bebang-Enterprise-Inc/hrms/pull/713 (MERGED)
audit_pr_url: TBD (this v2 amendments PR)
audit_artifact: output/plan-audit/s233-create-store-ui-button/verified_blockers.md
depends_on:
  - PR #707 (S231 C-1 atomicity wrapper) — DEPLOYED
  - PR #711 (S231 D-5-1 get_fee_schedule endpoint) — DEPLOYED
  - s231_fix_bfi2_is_group.py — APPLIED (BFI2 is now is_group=1)
  - bki_markup_company_owned_percent set live to 2.75 — APPLIED
unit_budget: 46
unit_budget_rationale: |
  Six phases plus a Phase 0.5 (constant extraction for B-08 fix; +1u).
  Largest phase is Phase 3 frontend at 10u. Total 46u is well under
  the 80-unit S089 ceiling. Single-session execution feasible.
  No CEO override required. v1 was 45u; v2 adds 1u for B-08.
phase_unit_budget:
  Phase 0 — Boot, baselines, library audit: 4
  Phase 0.5 — Extract _S037_RELPATH to bei_config.py (B-08 fix): 1
  Phase 1 — Backend canonical helper script (now in hrms/api/): 8
  Phase 2 — Backend whitelisted API + RBAC: 5
  Phase 3 — Frontend dialog + button + hook: 10
  Phase 4 — Test library extensions (Page Object, fixture kind, mutation patterns): 6
  Phase 5 — L3 scenarios + browser E2E: 8
  Closeout — verifier post + plan/registry + worktree remove: 4
evidence_committed:
  - output/s233/SUMMARY.md
  - output/s233/DEFECTS.md
  - output/s233/RUN_STATUS.json
  - output/s233/verification/canonical_verifier_pre.txt
  - output/s233/verification/canonical_verifier_post.txt
  - output/s233/verification/library_audit.md
  - output/s233/verification/state_after.json
  - output/s233/state/PRETOUCH_BACKUP.json
  - output/l3/s233/form_submissions.json
  - output/l3/s233/api_mutations.json
  - output/l3/s233/state_verification.json
  - output/l3/s233/teardown_ledger.json
  - output/l3/s233/teardown_complete.json
  - output/l3/s233/SUMMARY.md
evidence_transient:
  - tmp/s233/probe_*.json
  - tmp/s233/playwright_trace_*.zip
  - tmp/s233/bench_migrate_*.log
  - tmp/s233/test_run_*.log
sentry_projects:
  - bei-hrms (slug: bei-hrms, platform: python)
  - bei-tasks (slug: bei-tasks, platform: javascript-nextjs)
hard_deadline: null
hard_deadline_rationale: |
  No external deadline. CEO requested feature after S231 L3 surfaced
  the gap (BD page has no Add Store button). Recommended ship within
  2 weeks so future store onboarding can use the UI instead of SSM
  scripts that have caused 4 known defect classes.
---

# Sprint 233 — Add "Create Store" UI button on Company Master

---

## ⚠️ v2 Amendment Log (2026-05-03)

This plan was amended after `/audit-plan-bei-erp` produced 7 CRITICAL + 2 WARNING + 2 INFO blockers (all independently verified by adversarial fact-check against actual source). v2 fixes every CRITICAL blocker. Audit report: `output/plan-audit/s233-create-store-ui-button/verified_blockers.md`.

### Amendments applied

| # | Blocker | v1 (broken) | v2 (fixed) | Affected sections |
|---|---|---|---|---|
| **A1** | B-01 import path | `from scripts.canonical.create_new_store import create_new_store` would throw `ModuleNotFoundError` (HOTFIX4 at `company_master.py:939–941` documents this trap) | Helper file moves to `hrms/api/create_new_store.py`. Endpoint imports `from hrms.api.create_new_store import create_new_store`. | Phase 1 file path, Phase 2 import, MUST_MODIFY paths, verify_phase scripts, Library Audit table |
| **A2** | B-02 savepoint order | `frappe.db.commit()` BEFORE `frappe.db.release_savepoint(sp)` defeats rollback | Remove `frappe.db.commit()` from inside savepoint. Let Frappe HTTP cycle commit. `release_savepoint` runs inside try; on exception, `rollback(save_point=sp)` is reachable. | Phase 1-3 code block |
| **A3** | B-03 CSV split-brain | `_append_s037_row()` (filesystem) called INSIDE savepoint try, before commit | Move CSV write to AFTER savepoint released, accept DB-atomic + CSV-best-effort. Add post-write verification step. | Phase 1-3 code block |
| **A4** | B-04 missing Customer fields | Both Customer inserts omit `customer_group`, `territory`, `customer_type` → `MandatoryError` | Both inserts now set `customer_type="Company"`, `customer_group="BKI Store"`, `territory="Philippines"` | Phase 1-3 code block |
| **A5** | B-05 RBAC role mismatch | Backend `allowed_roles` includes nonexistent `"BD User"` and lacks `"Business Development"`/`"HQ User"`/`"Accounts Manager"` (frontend-permitted) | Backend now matches frontend `MODULE_ACCESS[MODULES.COMPANY_MASTER]`: `{"Business Development", "BD Manager", "Accounts Manager", "HQ User", "System Manager", "Administrator"}`. Frontend RBAC guard wraps `add-store-button` on the same role union. | Phase 2-1 code, Phase 3-3 button guard, Phase 3-4 RBAC spec |
| **A6** | B-06 Ellipsis placeholder | `("rbac_guard_on_button", ...)` always-truthy via Python Ellipsis | Replaced with concrete grep-based check on the new `hasCompanyMasterRole` constant in page.tsx | Phase 3 verification script (verify_phase3.py) |
| **A7** | B-08 circular import | Helper top-level `from hrms.api.company_master import _S037_RELPATH` causes circular import after A1 fix | NEW Phase 0.5 (1u): extract `_S037_RELPATH` to `hrms/utils/bei_config.py`; both `company_master.py` and the new helper import from `bei_config`. No cycle. | YAML phase budget, NEW Phase 0.5, Phase 1 import |
| **A8** | B-09 S8 atomicity test | "test Company name=blank" rejected by precondition before savepoint entered | S8 induces failure inside the 4-record sequence: pass `customer_group="NONEXISTENT_GROUP_S233"` so the SECOND Customer insert raises a Customer.validate exception → savepoint rollback exercised → all 4 records absent verified | Phase 5 L3 scenario S8 spec |
| **A9** | B-10 split truncation | `companyName.split(" - ")[0]` truncates multi-hyphen labels | Replaced with `companyName.slice(0, companyName.lastIndexOf(" - "))` | Phase 3-3 page.tsx onCreated handler |
| **A10** | NG2 narrative error | Plan line 92 cited nonexistent `retire_warehouse_duplicate.py` | Removed the false reference; only `migrate_49_stores.py` cited | Triggering Incident section |
| **B-07** | Demoted | "Plan/registry not on production" framed as CRITICAL | DEMOTED to INFO — standard PR-Handoff workflow; v1 was merged via PR #713 | n/a |

### Net unit budget change
- v1: 45u across 6 phases
- v2: 46u across 7 phases (added Phase 0.5 = 1u for B-08 fix)
- Still well under S089 80-unit ceiling

### Where to find the audit evidence
- `output/plan-audit/s233-create-store-ui-button/verified_blockers.md` — final blocker list (7 CRITICAL + 2 WARNING)
- `output/plan-audit/s233-create-store-ui-button/code_verification.md` — source-grounded evidence per blocker
- `output/plan-audit/s233-create-store-ui-button/fact_check_verification.md` — adversarial review (8 SUPPORTED, 1 PARTIAL, 1 CONTRADICTED)
- 7 `*_findings.md` files — per-domain detail

---

## Sprint Registry Lock Evidence

Row added to `docs/plans/SPRINT_REGISTRY.md` 2026-05-03:

```
| `S233` | Sprint 233 | `s233-create-store-ui-button` (hrms backend + bei-tasks frontend) | TBD | PLANNED 2026-05-03 — Add "Create Store" UI button on BD Company Master + canonical create_new_store helper. ... ~45 work units across 6 phases. Depends on: PR #707, PR #711, s231_fix_bfi2_is_group, bki_markup_company_owned_percent live=2.75. | docs/plans/2026-05-03-sprint-233-create-store-ui-button.md |
```

Next Sprint Reservation bumped to `S234`.

---

## Triggering Incident

**2026-05-03 (Sunday).** During S231 L3 browser test execution, agent attempted to create a test Company under the new `BEBANG FT INC.` parent legal entity (BFI2). The BD Company Master page (`/dashboard/bd/companies`) has NO "Add Store" / "New Company" button — verified by source grep on `app/dashboard/bd/companies/page.tsx` (zero matches for Add/New/Create buttons). New stores are master data created via direct SSM `frappe.new_doc("Company")` calls.

That SSM-only path surfaced 4 defect classes during S231 Phase A:
1. **`BEBANG FT INC.` created with `is_group=0`** — blocked all child store creation under the new parent until `s231_fix_bfi2_is_group.py` retroactively set group=1 + rebuilt NestedSet.
2. **ERPNext chart-of-accounts importer bug** — clones existing Company's flat root accounts (e.g. `6020602 - ACCOUNTING FEES`) and fails `validate_root_details`. Workaround: `frappe.local.flags.ignore_chart_of_accounts = True`.
3. **Operational Status enum case mismatch** — payload `Pre-opening` rejected; must be `Pre-Opening`.
4. **`bki_markup_company_owned_percent` JSON default 2.75 didn't apply** to the pre-existing BEI Settings Single doc; live value stayed at `0.0` until `s231_set_co_owned_markup.py` set it manually.

Every BD user who tries to onboard a new store today must either (a) write a custom SSM script and rediscover these traps, or (b) ask an engineer to do it. The canonical model doc references `scripts/canonical/create_new_store.py` (line 92) but the script doesn't exist — only `migrate_49_stores.py` is in `scripts/canonical/`. Per v2 amendment A1, the new helper ships in `hrms/api/create_new_store.py` (NOT `scripts/`) so it imports cleanly from the Frappe HTTP request handler — `scripts/` is not on Frappe's `sys.path` (HOTFIX4 at `hrms/api/company_master.py:939–941` documents this trap).

---

## Canonical Model Preflight (Mandatory)

Executing agent MUST run before the first code change:
```
python scripts/verify_canonical_structure.py | tee output/s233/verification/canonical_verifier_pre.txt
```
If the verifier prints `[VIOLATION]`, STOP and ask the user. Do NOT add records, flip fields, or create customers/warehouses to paper over a violation — fix the master data with the canonical scripts.

**Canonical law (summary — full rules in `docs/STORE_COMPANY_CANONICAL.md`):**
- Every store has EXACTLY 1 per-store Company + 1 Warehouse + 1 billing Customer + 1 Internal Customer.
- All four share the same name string (e.g. `SM TANZA - BEBANG MEGA INC.`).
- Per-store Company's `parent_company` links to the legal entity parent (if any). Parent MUST be `is_group=1`.
- Warehouse.company = the per-store Company (NEVER the parent).
- Billing Customer: `customer_name` = per-store Company name, `is_internal_customer=0`, `tax_id` = legal entity BIR TIN (or own TIN if standalone).
- Internal Customer: `name` = `<store_label> (Internal)`, `represents_company` = per-store Company, `is_internal_customer=1`, no TIN. Used by S206 labor journals ONLY — never for regular SIs.

**Forbidden in this plan (without explicit CEO approval in-line):**
- Creating a second Warehouse/Company/Customer for an existing store.
- Ad-hoc SQL mutations on `tabCompany` / `tabWarehouse` / `tabCustomer`.
- Adding new fallback logic to `resolve_store_buyer_entity`.
- Using the parent Company's Customer for store-level billing.
- Reusing an Internal Customer for a regular SI.
- Deleting a master record with transactions.

**Scope claim:** This sprint creates Company + Warehouse + 2 Customers (billing + internal) per new-store invocation. All 4 records share the canonical name string. The S037 register CSV gets one new row per store. No mutations to existing stores' canonical structure.

---

## Canonical Model Binding

The new `create_store_company` API + helper bind to the canonical model as follows:

**Reads:**
- `Company.is_group` on the requested parent — REJECTS if `is_group != 1` (root cause of S231 BFI2 defect).
- `Company.tax_id` on the parent — used as billing Customer's tax_id when caller didn't provide own TIN.
- `Company.entity_category` on the parent — must be in `{"Head Office", "Holding Company"}` (canonical parents per `_NON_STORE_ENTITIES`).

**Writes (4 records per invocation, all in one savepoint):**
- `tabCompany`: per-store Company with `entity_category="Store"`, `store_ownership_type=<input>`, `parent_company=<input>`, `is_group=0`, `country="Philippines"`, `default_currency="PHP"`, `operational_status="Pre-Opening"`.
- `tabWarehouse`: docname = per-store Company name, `warehouse_name` = store label, `company` = per-store Company, `is_group=0`, `disabled=0`.
- `tabCustomer` (billing): `customer_name` = per-store Company name (same string as Company docname), `tax_id` from input or parent, `is_internal_customer=0`.
- `tabCustomer` (internal): `customer_name` = `<store_label> (Internal)`, `represents_company` = per-store Company, `is_internal_customer=1`, `tax_id=NULL`.

**Writes to S037 register:** appends one row to `hrms/data_seed/store_entity_mapping_<latest>.csv` so `list_stores` returns the new store. Atomic write via Python `csv.writer` + `os.rename` swap.

**Defect handling:**
- `frappe.local.flags.ignore_chart_of_accounts = True` during Company insert — bypasses ERPNext's broken CoA importer.
- `frappe.flags.in_install = True` during Company insert — bypasses BEI's `auto_provision_company` on the create call (operator clicks "Run First Provisioning" pill afterwards if they want CoA seeded).
- Operational Status enum case enforced: helper accepts `"Pre-Opening"` only.
- Parent `is_group=1` precondition checked BEFORE attempting any write (returns 400 otherwise).

**Does NOT:**
- Bypass `resolve_store_buyer_entity` (the new Customer is registered via canonical name match — no fallback hack needed).
- Hardcode parent Company names (parent comes from caller).
- Add a new store_id / branch_code field parallel to the canonical model.
- Modify existing Companies (idempotent on the new docname only).

---

## Library Audit (Phase 0 deliverable)

Per QA test library discipline (`.claude/docs/qa-test-library-discipline.md`), this sprint MUST extract reusable test infrastructure.

### Existing assets to reuse (no new code):

| Asset | Path | How this sprint uses it |
|---|---|---|
| `CompanyMasterPage` Page Object | `bei-tasks/tests/e2e/pages/CompanyMasterPage.ts` | Open list page, open Company detail post-create |
| `loggedInAsCEO` fixture | `bei-tasks/tests/e2e/fixtures/auth.ts:148` | Authenticate test runs (only role with full Company create permission for now) |
| `loggedInAsBdManager` (planned) | `bei-tasks/tests/e2e/fixtures/auth.ts` | NEW fixture this sprint adds (BD Manager role for RBAC test) |
| `CleanupLedger` | `bei-tasks/tests/e2e/fixtures/cleanup.ts` | Reverses test Company creation (NEW kind: `store-company-create`) |
| `frappeReadback.queryDocs` | `bei-tasks/tests/e2e/support/frappeReadback.ts` | Verifies the 4 canonical records exist post-create |
| `useUpdateCompanySection` mutation pattern | `bei-tasks/lib/queries/company-master.ts:389` | Template for new `useCreateStoreCompany` mutation hook |
| `SectionEditModal` component pattern | `bei-tasks/components/company-master/section-edit-modal.tsx` | Template for `CreateStoreDialog` form layout |
| `frappePost<T>` helper | `bei-tasks/lib/queries/company-master.ts:208` | Wrapper for the new POST endpoint |
| `STORE_OWNERSHIP_TYPE_OPTIONS` const | `bei-tasks/components/company-master/section-edit-modal.tsx` | Reused in CreateStoreDialog ownership Select |
| `ENTITY_CATEGORY_OPTIONS` const | same | Reused (we hardcode `Store` for new-store flow but constant is canonical) |
| `set_backend_observability_context` | `hrms/utils/sentry.py` | DM-7 Sentry instrumentation on new endpoint |
| `_NON_STORE_ENTITIES` constant | `hrms/api/company_master.py:503` | Source-of-truth for which Companies are valid parents |
| `ignore_chart_of_accounts` flag pattern | `scripts/s231_l3_seed_test_store.py` | Reused in canonical helper |

### Library contributions this sprint adds:

| New asset | Path | Reusable for |
|---|---|---|
| `hrms/api/create_new_store.py` (v2 A1: was `scripts/canonical/`) | NEW | All future programmatic store onboarding (replaces ad-hoc SSM patterns). Located in `hrms/api/` so it's importable from Frappe HTTP context — `scripts/` is not on Frappe's `sys.path` per HOTFIX4 at `company_master.py:939`. |
| `hrms/utils/bei_config.py::S037_REGISTER_RELPATH` (v2 A7: NEW constant) | EXTEND | Shared between `company_master.py` and `create_new_store.py` to prevent the circular import that would emerge from cross-module import of `_S037_RELPATH`. |
| `hrms/api/company_master.py::create_store_company` | EXTEND | The whitelisted endpoint (UI + future BD scripts) |
| `hrms/api/company_master.py::list_eligible_parent_companies` | NEW | Returns Companies with `is_group=1` AND `entity_category in ("Head Office","Holding Company")` for parent picker |
| `bei-tasks/lib/queries/company-master.ts::useCreateStoreCompany` | NEW | TanStack mutation hook with cache invalidation (CompanyList + CompanyDetail) |
| `bei-tasks/lib/queries/company-master.ts::useEligibleParents` | NEW | Query hook for the parent combobox |
| `bei-tasks/components/company-master/create-store-dialog.tsx` | NEW | Full creation form with field validation |
| `bei-tasks/tests/e2e/pages/CreateStoreDialog.ts` | NEW Page Object | Reusable for future store-create-related tests |
| `bei-tasks/tests/e2e/fixtures/cleanup.ts` extension | EXTEND | New `store-company-create` kind that reverses creation via SSM |
| `bei-tasks/tests/e2e/builders/store-create-payload.ts` | NEW | Test data builder for store-create payloads |
| `bei-tasks/tests/e2e/assertions/canonicalStoreShape.ts` | NEW | Asserts the 4 canonical records exist with correct field values post-create |
| `loggedInAsBdManager` fixture | EXTEND auth.ts | RBAC test for parent BD Manager role |
| `output/l3/s233/SUMMARY.md` | NEW | L3 closeout artifact |

### Three-uses rule check:
- "ignore_chart_of_accounts during Company insert" pattern appears in `s231_l3_seed_test_store.py`, `s231_create_bebang_ft_inc_parent.py`, `s231_recreate_bfc.py`. **3 uses → extract to `create_new_store.py` helper.** ✓ (this sprint does that)
- "Create 4 canonical records (Company + Warehouse + 2 Customers)" — currently appears nowhere as a single helper. New requirement; ship as the helper.

### `data-testid` check:
- Existing dialog has no `data-testid` on the dialog itself or section cards (verified during S231 L3). This sprint MUST add `data-testid="create-store-dialog"` + `data-testid="add-store-button"` + a `data-testid` on each field (`store-label-input`, `parent-company-select`, `abbr-input`, `ownership-type-select`, `tax-id-input`, `submit-create-store-button`).

---

## L3 Workflow Scenarios

| # | User | Action | Expected Outcome | Failure Means |
|---|---|---|---|---|
| S1 | sam@bebang.ph (CEO/SystemManager) | On `/dashboard/bd/companies` → click "+ Add Store" → fill form (Label="L3 Test Store 233", Parent="BEBANG FT INC.", Abbr="L3T233", Ownership="Managed Franchise", Tax ID blank → inherits parent, Status=Pre-Opening) → Submit | 200 OK; success toast "Store created"; dialog closes; new row appears in list within 3s; new Company has `parent_company="BEBANG FT INC."`, `entity_category="Store"`, `store_ownership_type="Managed Franchise"`, `tax_id` matches parent's TIN | Backend create_store_company endpoint missing/broken OR SSE refetch not wired |
| S2 | sam@bebang.ph | After S1, click on new row "L3 Test Store 233 - BEBANG FT INC." → detail dialog opens → verify FeePreviewPanel shows MF tier (markup 8.00%, all 4 fee rows, recipient=BEBANG FRANCHISE CORP.) | Detail renders correctly with seeded ownership_type | Detail wiring broken OR S037 register update didn't include new store |
| S3 | sam@bebang.ph | Open "+ Add Store" → fill form with Abbr="L3T233" again (duplicate) → Submit | 400 error; toast "Abbreviation L3T233 already exists"; dialog stays open; no new Company created | Duplicate-abbr precheck not implemented |
| S4 | sam@bebang.ph | Open "+ Add Store" → fill form but pick a Parent Company that is `is_group=0` (e.g. an existing per-store Company by typing its name manually) → Submit | 400 error; toast "Parent Company must be a group company"; no new records | `is_group=1` precondition not enforced |
| S5 | sam@bebang.ph | Open "+ Add Store" → leave Parent Company blank → click Submit | Form blocks submission; "Parent Legal Entity is required" inline validation; submit button disabled or click rejected | Required-field validation not wired |
| S6 | system (cleanup teardown) | Run `python scripts/s233_l3_teardown_test_store.py` | Test Company + Warehouse + 2 Customers + S037 row deleted; `frappe.db.exists("Company", "L3 Test Store 233 - BEBANG FT INC.") == False` | Teardown helper doesn't fully reverse the canonical creation |
| S7 | test.bd@bebang.ph (BD Manager — non-System Manager) | If BD Manager role has create permission per RBAC: open "+ Add Store" → form opens; If not: button is hidden/disabled with tooltip "Requires BD Manager role" | RBAC enforced consistently UI + backend | RBAC mismatch (UI shows but backend rejects, or vice versa) |
| S8 (v2 A8) | system (negative cleanup) | Savepoint atomicity test: invoke `create_store_company` with a payload that intentionally fails inside the 4-record sequence — set `customer_group="NONEXISTENT_GROUP_S233"` so the SECOND Customer.insert (billing customer) raises `frappe.LinkValidationError` AFTER the Company + Warehouse have been inserted but BEFORE all 4 are committed. Verify all 4 records absent post-failure (savepoint rolled back the Company + Warehouse + 1st Customer). Also verify NO row was added to the S037 register CSV (since CSV write happens AFTER savepoint per A3). | All 4 records absent (atomicity invariant) AND `s037_row_added=False` AND error message names `customer_group` | Savepoint ordering broken — partial create leaves orphan records OR CSV write fired despite DB rollback |

---

## Test Data Seeding Contract

Reference skill: `/frappe-bulk-edits` for SSM seeding/teardown.

### Records the scenarios depend on (preconditions — must exist BEFORE L3 runs):

| Record | Purpose | Scenario | Precondition source |
|---|---|---|---|
| Company `BEBANG FT INC.` with `is_group=1` | Parent for S1+S2+S3 test stores | S1, S2, S3 | Already in production (S231 Phase A + s231_fix_bfi2_is_group.py) — verifier checks |
| Company `BEBANG ENTERPRISE INC.` with `is_group=1` | Alt parent for negative test S4 needs a non-group Company too | S4 | Already in production |
| User `test.bd@bebang.ph` with role `BD Manager` | RBAC test | S7 | seed via `/frappe-bulk-edits` if missing |

### Records this sprint creates DURING L3 (must be torn down at closeout):

| Record | Created by | Teardown by |
|---|---|---|
| Company `L3 Test Store 233 - BEBANG FT INC.` | S1 (browser create) | `s233_l3_teardown_test_store.py` |
| Warehouse `L3 Test Store 233 - BEBANG FT INC.` | Created by helper as part of S1 | Same script |
| Customer `L3 Test Store 233 - BEBANG FT INC.` (billing) | Created by helper | Same script |
| Customer `L3 Test Store 233 (Internal)` | Created by helper | Same script |
| Row in `hrms/data_seed/store_entity_mapping_<latest>.csv` | Created by helper | Same script (rewrites CSV without test row) |

### Pre-test seeding script:

```python
# scripts/s233_l3_seed_preconditions.py
# Idempotent — verifies BFI2 is_group=1, creates test.bd@bebang.ph user
# if missing, asserts BEI Settings markup defaults are seeded.
# Runs ONCE before the L3 spec.
```

### Teardown script:

```python
# scripts/s233_l3_teardown_test_store.py
# Reads output/l3/s233/teardown_ledger.json
# Reverses every entry:
#   - Delete Customer (internal)
#   - Delete Customer (billing)
#   - Delete Warehouse
#   - Delete Company
#   - Strip the row from store_entity_mapping CSV (atomic file rewrite)
# Writes output/l3/s233/teardown_complete.json with {deleted: 4, csv_rows_removed: 1, remaining: 0}
```

### Forbidden patterns:
- L3 scenario "PRECONDITION_BLOCKED" — wrong; seed it
- "Test data setup is out of scope" — wrong; this plan owns it
- Manual `bench execute` snippets — use `/frappe-bulk-edits` per S229 rule

---

## Anti-Rewind / Concurrent-Run Protection Contract

| Element | Artifact | Rule |
|---|---|---|
| ownership_matrix | `output/s233/SURFACE_OWNERSHIP_MATRIX.csv` | This sprint owns (v2 paths): `hrms/api/company_master.py` (EXTEND with `create_store_company` + `list_eligible_parent_companies`; v2 A7 also alters `_S037_RELPATH` to import from `bei_config`), `hrms/api/create_new_store.py` (NEW — v2 A1: was `scripts/canonical/`), `hrms/utils/bei_config.py` (EXTEND with `S037_REGISTER_RELPATH` — v2 A7), `hrms/data_seed/store_entity_mapping_<latest>.csv` (APPEND — read-modify-write contract per row), `bei-tasks/app/dashboard/bd/companies/page.tsx` (EXTEND with header button + RBAC guard + lastIndexOf split — v2 A5/A9), `bei-tasks/components/company-master/create-store-dialog.tsx` (NEW), `bei-tasks/lib/queries/company-master.ts` (EXTEND with 2 new hooks), `bei-tasks/tests/e2e/pages/CreateStoreDialog.ts` (NEW), `bei-tasks/tests/e2e/specs/s233-create-store-ui.spec.ts` (NEW). |
| protected_surfaces | `output/s233/PROTECTED_SURFACE_REGISTRY.csv` | Do NOT modify: `update_company_section` whitelist (S231 owned), `EDITABLE_SECTIONS` constant, existing detail dialog sections (BIR, Operations, etc.), `auto_provision_company` (S181/S231 owned), C-1 atomicity wrapper, `null_out_dead_default_refs` hook, `validate_store_ownership_type` hook. |
| remote_truth_baseline | `output/s233/REMOTE_TRUTH_BASELINE.json` | Capture at Phase 0: `{repo: hrms, branch: production, head_sha: <git rev-parse origin/production>, capture_time: <ISO>}` and same for bei-tasks. |
| touched_file_routing | `output/s233/TOUCHED_FILE_ROUTING.csv` | Each touched file → required L3 scenario(s) it must satisfy + canonical verifier pass post-change. |
| active_run_coordination | `output/s233/state/ACTIVE_RUN_COORDINATION.json` | Claim on Phase 0 boot; release on closeout. |
| pretouch_backup | `output/s233/state/PRETOUCH_BACKUP.json` | Before any mutation: snapshot S037 register file + count of `tabCompany` rows. |
| supersession_map | n/a (greenfield feature) | — |
| touch_preservation | `output/s233/ledgers/TOUCH_PRESERVATION_LEDGER.csv` | Every Company touched (only the test Company in L3) gets a row with create + teardown timestamps. |

---

## Status Reconciliation Contract

Whenever counts, blockers, stage, or status changes, update in the same work unit:

1. `output/s233/RUN_STATUS.json`
2. `output/s233/SUMMARY.md`
3. `output/s233/DEFECTS.md`
4. `docs/plans/2026-05-03-sprint-233-create-store-ui-button.md` (this file — status field)
5. `docs/plans/SPRINT_REGISTRY.md` row for S233 (when status flips)
6. PR description checkbox table (one for hrms PR, one for bei-tasks PR)

---

## Signoff Model

- mode: `single-owner`
- approver_of_record: `Sam Karazi (CEO)` via PR review
- signoff_artifact: `output/s233/SUMMARY.md` final section "CEO Signoff Block" + GitHub PR APPROVE on both repos
- note: PR-Handoff workflow — agent creates PRs (one hrms, one bei-tasks) + provides PR URLs + STOPS. Sam reviews, runs Release Manager Gate, merges and deploys.

---

## Autonomous Execution Contract

- **completion_condition:**
  - All 6 phases (Phase 0 through Closeout) green per their gates
  - Canonical verifier post-execution shows zero NEW violations
  - All 8 L3 scenarios PASS with evidence in `output/l3/s233/`
  - Test Company + 4 records + S037 row torn down (`teardown_complete.json` shows 0 remaining)
  - hrms PR + bei-tasks PR created, PR numbers recorded in plan + registry
  - Worktrees removed; main checkouts clean
- **stop_only_for:**
  - Missing AWS SSM credentials or production DB access
  - Canonical verifier prints `[VIOLATION]` (existing or new) — pause
  - More than 0 unexpected Company/Warehouse/Customer rows present after teardown — pause (orphan)
  - L3 scenario S8 atomicity test shows partial-create persistence — STOP, this is a critical defect
  - Sentry shows >5 errors during L3 — pause
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
- **canonical_closeout_artifacts:** see `evidence_committed` YAML block above

---

## Phase Specifications

### Phase 0 — Boot, baselines, library audit (4 units)

#### 0-1. Worktree spawn

```bash
BR=s233-create-store-ui-button
WT_HRMS=F:/Dropbox/Projects/BEI-ERP-${BR##*/}
WT_BEITASKS=F:/Dropbox/Projects/bei-tasks-${BR##*/}
cd F:/Dropbox/Projects/BEI-ERP && git fetch origin --prune
git worktree add "$WT_HRMS" -B "$BR" origin/production
cd F:/Dropbox/Projects/bei-tasks && git fetch origin --prune
git worktree add "$WT_BEITASKS" -B "$BR" origin/main
```

#### 0-2. Capture baselines

- `output/s233/REMOTE_TRUTH_BASELINE.json` — head SHAs of both repos
- `output/s233/state/PRETOUCH_BACKUP.json` — current row count of `tabCompany` + content hash of `hrms/data_seed/store_entity_mapping_<latest>.csv`
- `python scripts/verify_canonical_structure.py | tee output/s233/verification/canonical_verifier_pre.txt`

#### 0-3. Library audit deliverable

Write `output/s233/verification/library_audit.md` with the table from "Library Audit" section above, plus a per-asset note confirming the asset still exists (path verified).

#### 0-4. Verify dependencies

Run via SSM (read-only):
```python
# scripts/s233_check_preconditions.py
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()

# 1. BFI2 is_group=1
bfi2 = frappe.db.get_value("Company", "BEBANG FT INC.", ["is_group", "abbr"], as_dict=True)
assert bfi2 and bfi2["is_group"] == 1, f"BFI2 not is_group=1: {bfi2}"

# 2. get_fee_schedule callable
from hrms.api.billing import get_fee_schedule
out = get_fee_schedule()
assert len(out["schedules"]) == 9, f"fee schedule rows wrong: {len(out['schedules'])}"
assert out["markup_rates"]["Company Owned"] == 2.75, f"Co-Owned markup: {out['markup_rates']['Company Owned']}"

# 3. C-1 atomicity wrapper deployed
import hrms.overrides.company as co
assert hasattr(co, "DEFAULT_FIELDS_TO_TRACK"), "C-1 wrapper not deployed"
assert callable(co.null_out_dead_default_refs), "C-2 hook not deployed"

print("All preconditions met")
```

**MUST_MODIFY (Phase 0):**
- `output/s233/REMOTE_TRUTH_BASELINE.json` (created)
- `output/s233/verification/canonical_verifier_pre.txt` (created)
- `output/s233/verification/library_audit.md` (created)
- `output/s233/state/PRETOUCH_BACKUP.json` (created)

**Verification script** (`output/s233/verify_phase0.py`):
```python
import os, json, subprocess
checks = []
checks.append(("worktree_hrms_exists", os.path.isdir("F:/Dropbox/Projects/BEI-ERP-s233-create-store-ui-button")))
checks.append(("worktree_beitasks_exists", os.path.isdir("F:/Dropbox/Projects/bei-tasks-s233-create-store-ui-button")))
checks.append(("baseline", os.path.exists("output/s233/REMOTE_TRUTH_BASELINE.json")))
checks.append(("library_audit", os.path.exists("output/s233/verification/library_audit.md")))
checks.append(("verifier_pre", os.path.exists("output/s233/verification/canonical_verifier_pre.txt")))
res = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True)
checks.append(("on_correct_branch", res.stdout.strip() == "s233-create-store-ui-button"))
fail = [c for c, ok in checks if not ok]
print("PASS" if not fail else f"FAIL: {fail}")
exit(0 if not fail else 1)
```

---

### Phase 0.5 — Extract _S037_RELPATH to bei_config.py (1 unit) — v2 A7

**Goal:** prevent the circular import that would emerge from Phase 1 if `create_new_store.py` (in `hrms/api/`) imported `_S037_RELPATH` from `company_master.py` while `company_master.py`'s endpoint imports from the helper.

#### 0.5-1. Add constant to bei_config.py

Append to `hrms/utils/bei_config.py`:
```python
# ── S037 store/entity register CSV ─────────────────────────────────────
# Extracted from hrms/api/company_master.py to break the circular import
# that would emerge when hrms/api/create_new_store.py needed to read it.
S037_REGISTER_RELPATH = ("data_seed", "store_entity_mapping_2026-04-13.csv")
```

#### 0.5-2. Update existing consumer in company_master.py

In `hrms/api/company_master.py`:
- Replace line 499 `_S037_RELPATH = ("data_seed", "store_entity_mapping_2026-04-13.csv")` with:
  ```python
  from hrms.utils.bei_config import S037_REGISTER_RELPATH as _S037_RELPATH  # back-compat alias
  ```
- All existing references to `_S037_RELPATH` in `company_master.py` continue to work (alias preserved). After this sprint, follow-up tasks may rename the alias away.

#### 0.5-3. Verification

```python
# output/s233/verify_phase0_5.py
src_bei = open("hrms/utils/bei_config.py").read()
src_cm = open("hrms/api/company_master.py").read()
checks = [
    ("constant_in_bei_config", "S037_REGISTER_RELPATH" in src_bei),
    ("path_unchanged", "store_entity_mapping_2026-04-13.csv" in src_bei),
    ("company_master_imports_from_bei_config", "from hrms.utils.bei_config import S037_REGISTER_RELPATH" in src_cm),
    ("no_dup_constant", src_cm.count('_S037_RELPATH = ("data_seed"') == 0),
]
fail = [c for c, ok in checks if not ok]
print("PASS" if not fail else f"FAIL: {fail}")
exit(0 if not fail else 1)
```

**MUST_MODIFY:** `hrms/utils/bei_config.py`, `hrms/api/company_master.py`
**MUST_CONTAIN:** `S037_REGISTER_RELPATH = ("data_seed", "store_entity_mapping_2026-04-13.csv")` in bei_config.py; `from hrms.utils.bei_config import S037_REGISTER_RELPATH` in company_master.py

---

### Phase 1 — Backend canonical helper script (8 units) — v2 A1

**Goal:** ship `hrms/api/create_new_store.py` (v2: relocated from `scripts/canonical/`) — the missing canonical creation script referenced in `docs/STORE_COMPANY_CANONICAL.md` line 92. Located in `hrms/api/` so it's importable from Frappe HTTP runtime; `scripts/` is not on Frappe's `sys.path` per HOTFIX4 in `company_master.py:939`.

#### 1-1. Helper signature + idempotency contract (1 unit)

```python
# hrms/api/create_new_store.py  (v2 A1: was scripts/canonical/create_new_store.py)
def create_new_store(
    store_label: str,           # "SM Tanza" — human-readable
    parent_company: str,         # "BEBANG MEGA INC." — must be is_group=1
    abbr: str,                   # "SMT" — 3-6 chars uppercase
    store_ownership_type: str,   # "JV" | "Managed Franchise" | "Full Franchise" | "Company Owned"
    tax_id: str | None = None,   # optional; falls back to parent's TIN
    operational_status: str = "Pre-Opening",
    region: str | None = None,
    province: str | None = None,
    city: str | None = None,
) -> dict:
    """Create the 4 canonical records for a new BEI store atomically.

    Returns {
        "company": "<store_label> - <parent_company>",
        "warehouse": "<store_label> - <parent_company>",
        "billing_customer": "<store_label> - <parent_company>",
        "internal_customer": "<store_label> (Internal)",
        "s037_row_added": True,
        "first_provision_done": 0,  # operator must click "Run First Provisioning"
    }
    """
```

**MUST_MODIFY:** `hrms/api/create_new_store.py` (NEW file — v2 A1: relocated from scripts/canonical/)
**MUST_CONTAIN:** `def create_new_store(`, `parent_company: str`, all 4 record-name keys in return dict

#### 1-2. Precondition validation (1 unit)

Before any write, validate:
- `parent_company` exists AND `is_group=1` AND `entity_category in ("Head Office", "Holding Company", "Franchisor", "Commissary")` (matches `_NON_STORE_ENTITIES` keys)
- `abbr` not already used by another Company (`frappe.db.exists("Company", {"abbr": abbr})`)
- `store_label` does NOT contain `" - "` (would conflict with naming convention)
- `store_ownership_type` in the canonical 4 values
- `operational_status == "Pre-Opening"` (case enforced)
- canonical Company name `<store_label> - <parent_company>` doesn't already exist

If any precondition fails, raise `frappe.ValidationError` with a specific message — do NOT attempt partial create.

**MUST_CONTAIN:** `_validate_preconditions(`, `frappe.ValidationError`, `is_group=1` check, abbr-uniqueness check

#### 1-3. Atomic 4-record creation in one savepoint (4 units) — v2 A2 + A3 + A4

```python
def create_new_store(...):
    _validate_preconditions(...)
    company_name = f"{store_label} - {parent_company}"
    sp = "create_new_store_" + abbr.lower()
    frappe.db.savepoint(sp)
    s037_row_added = False  # CSV write happens AFTER savepoint per v2 A3
    try:
        # 1. Per-store Company (with all defect handling)
        frappe.local.flags.ignore_chart_of_accounts = True
        frappe.flags.in_install = True  # skip auto_provision_company on first save
        try:
            co = frappe.new_doc("Company")
            co.company_name = company_name
            co.abbr = abbr
            co.country = "Philippines"
            co.default_currency = "PHP"
            co.tax_id = tax_id or frappe.db.get_value("Company", parent_company, "tax_id")
            co.parent_company = parent_company
            co.entity_category = "Store"
            co.store_ownership_type = store_ownership_type
            co.operational_status = operational_status
            co.is_group = 0
            if region: co.region = region
            if province: co.province = province
            if city: co.city = city
            co.flags.ignore_permissions = True
            co.insert()
        finally:
            frappe.local.flags.ignore_chart_of_accounts = False
            frappe.flags.in_install = False

        # 2. Warehouse — docname = company_name, warehouse_name = store_label
        wh = frappe.new_doc("Warehouse")
        wh.warehouse_name = store_label  # short label
        wh.company = company_name        # links to per-store Company (NOT parent)
        wh.is_group = 0
        wh.disabled = 0
        wh.flags.ignore_permissions = True
        wh.insert()
        # Frappe may auto-rename to add suffix; force the canonical docname:
        if wh.name != company_name:
            frappe.rename_doc("Warehouse", wh.name, company_name, force=True)

        # 3. Billing Customer (v2 A4: customer_type + customer_group + territory mandatory)
        bc = frappe.new_doc("Customer")
        bc.customer_name = company_name
        bc.customer_type = "Company"
        bc.customer_group = "BKI Store"   # canonical pattern from company.py:574
        bc.territory = "Philippines"      # canonical pattern from company.py:575
        bc.tax_id = co.tax_id  # same as Company's tax_id (inherited from parent if not given)
        bc.is_internal_customer = 0
        bc.flags.ignore_permissions = True
        bc.insert()
        if bc.name != company_name:
            frappe.rename_doc("Customer", bc.name, company_name, force=True)

        # 4. Internal Customer (S206 labor cost-sharing) — v2 A4: same mandatory fields
        ic = frappe.new_doc("Customer")
        ic.customer_name = f"{store_label} (Internal)"
        ic.customer_type = "Company"
        ic.customer_group = "BKI Store"   # v2 A4 — same as billing customer
        ic.territory = "Philippines"      # v2 A4
        ic.represents_company = company_name
        ic.is_internal_customer = 1
        ic.tax_id = None  # internal — no TIN
        ic.flags.ignore_permissions = True
        ic.insert()

        # v2 A2: release savepoint INSIDE try, BEFORE returning. Do NOT call
        # frappe.db.commit() here — Frappe's HTTP request handler commits on
        # successful return. Calling commit() here would end the transaction
        # before release_savepoint() and make the except-block rollback ineffective.
        # Pattern matches procurement.py:6607, billing.py:501,511, company.py:697.
        frappe.db.release_savepoint(sp)
    except Exception:
        # v2 A2: rollback is reachable because we did NOT manually commit
        frappe.db.rollback(save_point=sp)
        raise

    # v2 A3: CSV write happens AFTER savepoint released. Filesystem I/O is
    # non-transactional — keeping it inside the savepoint creates a DB↔file
    # split-brain on commit failure. Accept DB-atomic + CSV-best-effort:
    # if CSV write fails here, raise (caller sees clear error) — DB is already
    # consistent. Operator can retry _append_s037_row idempotently.
    try:
        _append_s037_row(
            store_name=store_label,
            buyer_entity=parent_company,
            store_type=store_ownership_type,
            frappe_warehouse_name=company_name,
            billing_policy="BKI_TO_STORE_INTERCOMPANY",
            active_status="active",
        )
        s037_row_added = True
    except Exception as csv_exc:
        # Surface the failure but don't roll back DB (canonical 4 records exist).
        # Operator must run scripts/canonical/repair_s037_for_company.py post-hoc.
        frappe.log_error(
            f"S233: Company {company_name} created in DB but S037 CSV append failed",
            f"create_new_store_csv_post_commit_failure: {csv_exc}",
        )
        raise

    return {
        "company": company_name,
        "warehouse": company_name,
        "billing_customer": company_name,
        "internal_customer": f"{store_label} (Internal)",
        "s037_row_added": s037_row_added,
        "first_provision_done": 0,
    }
```

**MUST_MODIFY:** `hrms/api/create_new_store.py` (v2 A1)
**MUST_CONTAIN:**
- `frappe.db.savepoint(`
- `ignore_chart_of_accounts = True`
- `frappe.flags.in_install = True`
- `co.is_group = 0`
- All 4 `frappe.new_doc(` calls (Company / Warehouse / Customer ×2)
- `_append_s037_row(` (NOTE: must appear AFTER `release_savepoint`, NOT inside try block — v2 A3)
- Both Customer inserts must contain `customer_type = "Company"`, `customer_group = "BKI Store"`, `territory = "Philippines"` (v2 A4)
- `frappe.db.release_savepoint(sp)` INSIDE try, no `frappe.db.commit()` inside try (v2 A2)
- `frappe.db.rollback(save_point=`

**MUST_NOT_CONTAIN:**
- `frappe.db.commit()` anywhere inside the savepoint try block (v2 A2)
- `_append_s037_row(` inside the savepoint try block (v2 A3)

#### 1-4. S037 register atomic-write helper (1 unit) — v2 A7

```python
def _append_s037_row(store_name, buyer_entity, store_type, frappe_warehouse_name, billing_policy, active_status):
    """Append a row to the latest store_entity_mapping CSV. Atomic via temp + rename.

    v2 A7: imports the constant from hrms/utils/bei_config (Phase 0.5)
    instead of from hrms/api/company_master to avoid circular import.
    """
    import csv, os, tempfile
    from hrms.utils.bei_config import S037_REGISTER_RELPATH  # v2 A7 — was: hrms.api.company_master._S037_RELPATH
    s037_path = os.path.normpath(os.path.join(frappe.get_app_path("hrms"), *S037_REGISTER_RELPATH))
    with open(s037_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    rows.append([store_name, buyer_entity, store_type, frappe_warehouse_name, billing_policy, active_status])
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(s037_path), text=True)
    os.close(fd)
    with open(tmp_path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)
    os.replace(tmp_path, s037_path)  # atomic on POSIX + NTFS
```

**MUST_CONTAIN:** `_append_s037_row(`, `tempfile.mkstemp`, `os.replace(tmp_path, s037_path)`, `from hrms.utils.bei_config import S037_REGISTER_RELPATH` (v2 A7)
**MUST_NOT_CONTAIN:** `from hrms.api.company_master import _S037_RELPATH` (v2 A7 — circular import trap)

#### 1-5. CLI wrapper for SSM use (1 unit)

```python
if __name__ == "__main__":
    import argparse, json, sys
    p = argparse.ArgumentParser()
    p.add_argument("--store-label", required=True)
    p.add_argument("--parent-company", required=True)
    p.add_argument("--abbr", required=True)
    p.add_argument("--store-ownership-type", required=True,
                   choices=["JV", "Managed Franchise", "Full Franchise", "Company Owned"])
    p.add_argument("--tax-id", default=None)
    p.add_argument("--region", default=None)
    p.add_argument("--province", default=None)
    p.add_argument("--city", default=None)
    args = p.parse_args()
    # Frappe init expected (script run via bench execute or from container)
    out = create_new_store(
        store_label=args.store_label,
        parent_company=args.parent_company,
        abbr=args.abbr,
        store_ownership_type=args.store_ownership_type,
        tax_id=args.tax_id,
        region=args.region,
        province=args.province,
        city=args.city,
    )
    print(json.dumps(out, indent=2))
```

**MUST_CONTAIN:** `if __name__ == "__main__":`, `argparse`, all 4 ownership choices in `choices=`

**Verification (`output/s233/verify_phase1.py`) — v2 A1 + A2 + A3 + A4 + A7:**
```python
import os
checks = []
HELPER_PATH = "hrms/api/create_new_store.py"  # v2 A1: was scripts/canonical/
src = open(HELPER_PATH).read()

# A1 — file path
checks.append(("v2_a1_file_in_hrms_api", os.path.exists(HELPER_PATH)))
checks.append(("v2_a1_no_old_path", not os.path.exists("scripts/canonical/create_new_store.py")))
checks.append(("create_new_store_def", "def create_new_store(" in src))
checks.append(("preconditions", "_validate_preconditions(" in src))
checks.append(("savepoint", "frappe.db.savepoint(" in src))
checks.append(("ignore_coa_flag", "ignore_chart_of_accounts = True" in src))
checks.append(("in_install_flag", "frappe.flags.in_install = True" in src))
checks.append(("4_records", src.count("frappe.new_doc(") >= 4))
checks.append(("s037_helper", "_append_s037_row(" in src))
checks.append(("atomic_csv_write", "os.replace(tmp_path" in src))
checks.append(("rollback_savepoint", "frappe.db.rollback(save_point=" in src))
checks.append(("cli_wrapper", "if __name__ ==" in src and "argparse" in src))

# A2 — savepoint must be released INSIDE try, no commit() inside try block
try_block_lines = src[src.index("frappe.db.savepoint("):src.index("except Exception:")]
checks.append(("v2_a2_release_savepoint_in_try", "frappe.db.release_savepoint(sp)" in try_block_lines))
checks.append(("v2_a2_no_manual_commit_in_try", "frappe.db.commit()" not in try_block_lines))

# A3 — CSV write must be AFTER except block, NOT inside try
post_except = src[src.index("raise"):]  # after except: ... raise
checks.append(("v2_a3_csv_after_savepoint", "_append_s037_row(" in post_except))
checks.append(("v2_a3_csv_not_in_try", src[:src.index("except Exception:")].count("_append_s037_row(") == 0))

# A4 — both Customer inserts must set customer_type, customer_group, territory
customer_block_count = src.count('customer_type = "Company"')
checks.append(("v2_a4_two_customer_type_assignments", customer_block_count >= 2))
checks.append(("v2_a4_two_customer_group_assignments", src.count('customer_group = "BKI Store"') >= 2))
checks.append(("v2_a4_two_territory_assignments", src.count('territory = "Philippines"') >= 2))

# A7 — bei_config import (no circular import from company_master)
checks.append(("v2_a7_imports_from_bei_config", "from hrms.utils.bei_config import S037_REGISTER_RELPATH" in src))
checks.append(("v2_a7_no_circular_import", "from hrms.api.company_master import _S037_RELPATH" not in src))

fail = [c for c, ok in checks if not ok]
print("PASS" if not fail else f"FAIL: {fail}")
exit(0 if not fail else 1)
```

---

### Phase 2 — Backend whitelisted API + RBAC (5 units)

**Goal:** ship `hrms.api.company_master.create_store_company` whitelisted endpoint that wraps the canonical helper.

#### 2-1. Endpoint signature + RBAC (2 units)

```python
# hrms/api/company_master.py — append at end

@frappe.whitelist()
def create_store_company(
    store_label: str,
    parent_company: str,
    abbr: str,
    store_ownership_type: str,
    tax_id: str | None = None,
    region: str | None = None,
    province: str | None = None,
    city: str | None = None,
) -> dict:
    """S233: BD UI endpoint — wraps scripts/canonical/create_new_store.py.

    Permission: requires Frappe `create` perm on Company doctype +
    one of [BD Manager, BD User, System Manager, Administrator] roles.
    Defense-in-depth — UI hides the button for unauthorized roles too.
    """
    set_backend_observability_context(
        module="company",
        action="create_store_company",
        mutation_type="create",
        extras={
            "store_label": store_label,
            "parent_company": parent_company,
            "abbr": abbr,
            "store_ownership_type": store_ownership_type,
        },
    )

    if not frappe.has_permission("Company", "create"):
        frappe.throw(_("Not permitted to create Company"))

    # v2 A5: RBAC roles MUST match bei-tasks/lib/roles.ts MODULE_ACCESS[MODULES.COMPANY_MASTER].
    # Removed nonexistent "BD User" (zero occurrences in repo). Added "Business Development",
    # "Accounts Manager", "HQ User" to mirror the frontend grant list. Keep both ends in sync;
    # divergence creates false-affordance dead-CTA bugs (S233 audit Blocker B-05).
    allowed_roles = {
        "Business Development",
        "BD Manager",
        "Accounts Manager",
        "HQ User",
        "System Manager",
        "Administrator",
    }
    user_roles = set(frappe.get_roles())
    if not (allowed_roles & user_roles):
        frappe.throw(_(
            "S233: create_store_company requires one of: {0}. You have: {1}"
        ).format(", ".join(sorted(allowed_roles)), ", ".join(sorted(user_roles))))

    # v2 A1: helper now lives in hrms/api/ (importable from Frappe HTTP context).
    # `scripts/` is not on Frappe's sys.path — see HOTFIX4 at company_master.py:939.
    from hrms.api.create_new_store import create_new_store
    return create_new_store(
        store_label=store_label,
        parent_company=parent_company,
        abbr=abbr,
        store_ownership_type=store_ownership_type,
        tax_id=tax_id,
        region=region,
        province=province,
        city=city,
    )
```

**MUST_MODIFY:** `hrms/api/company_master.py`
**MUST_CONTAIN (v2 A1 + A5):**
- `def create_store_company(`
- `set_backend_observability_context(module="company"`
- `frappe.has_permission("Company", "create")`
- `"Business Development"` AND `"BD Manager"` AND `"Accounts Manager"` AND `"HQ User"` AND `"System Manager"` AND `"Administrator"` in the `allowed_roles` set (v2 A5)
- `from hrms.api.create_new_store import create_new_store` (v2 A1)
**MUST_NOT_CONTAIN:**
- `"BD User"` (does not exist in BEI role taxonomy — v2 A5)
- `from scripts.canonical.create_new_store import` (v2 A1 trap)

#### 2-2. Eligible parents endpoint (1 unit)

```python
@frappe.whitelist()
def list_eligible_parent_companies() -> list[dict]:
    """S233: returns Companies that can be parent_company for a new store.

    Filters: is_group=1 AND entity_category in canonical non-store types.
    Used by the CreateStoreDialog parent picker combobox.
    """
    set_backend_observability_context(
        module="company",
        action="list_eligible_parent_companies",
        mutation_type="read",
    )
    rows = frappe.db.sql("""
        SELECT name, abbr, entity_category, tax_id
        FROM `tabCompany`
        WHERE is_group = 1
          AND entity_category IN ('Head Office', 'Holding Company', 'Franchisor', 'Commissary')
        ORDER BY name
    """, as_dict=True)
    return rows
```

**MUST_MODIFY:** `hrms/api/company_master.py`
**MUST_CONTAIN:** `def list_eligible_parent_companies(`, `is_group = 1`, `entity_category IN`

#### 2-3. Unit tests (2 units)

```python
# hrms/tests/test_s233_create_store_company.py
import unittest
from unittest.mock import patch
import frappe

from hrms.api.company_master import (
    create_store_company,
    list_eligible_parent_companies,
)


class TestS233CreateStoreCompany(unittest.TestCase):
    TEST_STORE_LABEL = "S233-TEST-UNIT"
    TEST_PARENT = "BEBANG FT INC."  # is_group=1 since s231_fix_bfi2_is_group
    TEST_ABBR = "S233UNIT"
    TEST_COMPANY_NAME = f"{TEST_STORE_LABEL} - {TEST_PARENT}"

    def tearDown(self):
        for dt, name in [
            ("Customer", f"{self.TEST_STORE_LABEL} (Internal)"),
            ("Customer", self.TEST_COMPANY_NAME),
            ("Warehouse", self.TEST_COMPANY_NAME),
            ("Company", self.TEST_COMPANY_NAME),
        ]:
            if frappe.db.exists(dt, name):
                try:
                    frappe.delete_doc(dt, name, force=True, ignore_permissions=True, ignore_on_trash=True)
                except Exception:
                    pass
        frappe.db.commit()

    def test_happy_path_creates_4_canonical_records(self): ...
    def test_rejects_non_group_parent(self): ...
    def test_rejects_duplicate_abbr(self): ...
    def test_rejects_existing_company_name(self): ...
    def test_rejects_unauthorized_user(self): ...
    def test_atomicity_partial_failure_rolls_back_all_4(self): ...
    def test_list_eligible_parents_returns_only_group_companies(self): ...
```

**MUST_MODIFY:** `hrms/tests/test_s233_create_store_company.py` (NEW)
**MUST_CONTAIN:** all 7 test method names listed above

Run via: `bench --site hq.bebang.ph run-tests --module hrms.tests.test_s233_create_store_company`. Expected: 7 PASS.

**Verification (`output/s233/verify_phase2.py`):**
```python
src = open("hrms/api/company_master.py").read()
checks = [
    ("create_store_company", "def create_store_company(" in src),
    ("create_observability", 'action="create_store_company"' in src),
    ("rbac_check", '"BD Manager"' in src and "frappe.get_roles()" in src),
    ("list_eligible", "def list_eligible_parent_companies(" in src),
    ("test_file", os.path.exists("hrms/tests/test_s233_create_store_company.py")),
]
# ... grep test methods
```

---

### Phase 3 — Frontend dialog + button + hook (10 units)

**Goal:** ship the bei-tasks UI surface.

#### 3-1. TanStack mutation hook + parent query hook (2 units)

```typescript
// bei-tasks/lib/queries/company-master.ts — append

export interface CreateStoreCompanyInput {
  store_label: string;
  parent_company: string;
  abbr: string;
  store_ownership_type: "JV" | "Managed Franchise" | "Full Franchise" | "Company Owned";
  tax_id?: string;
  region?: string;
  province?: string;
  city?: string;
}

export interface CreateStoreCompanyResult {
  company: string;
  warehouse: string;
  billing_customer: string;
  internal_customer: string;
  s037_row_added: boolean;
  first_provision_done: 0 | 1;
}

export interface EligibleParent {
  name: string;
  abbr: string;
  entity_category: string;
  tax_id: string | null;
}

export const companyMasterQueries = {
  // ... existing
  eligibleParents: () => ({
    queryKey: ["company-master", "eligible-parents"] as const,
    queryFn: () => frappeGet<EligibleParent[]>("list_eligible_parent_companies"),
    staleTime: 5 * 60 * 1000,
  }),
};

export function useEligibleParents() {
  return useQuery(companyMasterQueries.eligibleParents());
}

export function useCreateStoreCompany() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateStoreCompanyInput) =>
      frappePost<CreateStoreCompanyResult>("create_store_company", input),
    onSuccess: (result) => {
      // S233 D-5-2: invalidate the BD list so the new store appears
      queryClient.invalidateQueries({ queryKey: ["company-master", "list"] });
      queryClient.invalidateQueries({ queryKey: ["company-master", "stores"] });
      // Pre-warm the detail query so opening the new Company is instant
      queryClient.invalidateQueries({
        queryKey: ["company-master", "detail", result.company],
      });
    },
  });
}
```

**MUST_MODIFY:** `bei-tasks/lib/queries/company-master.ts`
**MUST_CONTAIN:** `useCreateStoreCompany`, `useEligibleParents`, `invalidateQueries({ queryKey: ["company-master", "list"]`, `frappePost<CreateStoreCompanyResult>("create_store_company"`

#### 3-2. CreateStoreDialog component (5 units)

```tsx
// bei-tasks/components/company-master/create-store-dialog.tsx
"use client";

import { useState } from "react";
import { useCreateStoreCompany, useEligibleParents } from "@/lib/queries/company-master";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

const OWNERSHIP_OPTIONS = ["JV", "Managed Franchise", "Full Franchise", "Company Owned"] as const;

interface CreateStoreDialogProps {
  open: boolean;
  onClose: () => void;
  onCreated?: (companyName: string) => void;
}

export function CreateStoreDialog({ open, onClose, onCreated }: CreateStoreDialogProps) {
  const [storeLabel, setStoreLabel] = useState("");
  const [parentCompany, setParentCompany] = useState<string>("");
  const [abbr, setAbbr] = useState("");
  const [ownership, setOwnership] = useState<typeof OWNERSHIP_OPTIONS[number]>("Managed Franchise");
  const [taxId, setTaxId] = useState("");

  const parents = useEligibleParents();
  const create = useCreateStoreCompany();

  // Auto-suggest abbr from store label (first letters of each word, uppercase, ≤6)
  function suggestAbbr(label: string): string {
    return label
      .split(/\s+/)
      .map((w) => w[0]?.toUpperCase() ?? "")
      .join("")
      .slice(0, 6);
  }

  const handleSubmit = async () => {
    if (!storeLabel.trim()) return toast.error("Store Label is required");
    if (!parentCompany) return toast.error("Parent Legal Entity is required");
    if (!abbr.trim()) return toast.error("Abbreviation is required");
    try {
      const result = await create.mutateAsync({
        store_label: storeLabel.trim(),
        parent_company: parentCompany,
        abbr: abbr.trim().toUpperCase(),
        store_ownership_type: ownership,
        tax_id: taxId.trim() || undefined,
      });
      toast.success(`Store created: ${result.company}`);
      onCreated?.(result.company);
      onClose();
    } catch (err: any) {
      toast.error(`Create failed: ${err?.message ?? "unknown"}`);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="create-store-dialog">
        <DialogTitle>+ Create New Store</DialogTitle>
        <DialogDescription>
          Adds a per-store Company + Warehouse + Billing Customer + Internal Customer
          atomically. The store will appear "Pre-Opening"; click "Run First Provisioning"
          on the detail dialog to seed the chart of accounts.
        </DialogDescription>
        <div className="grid gap-4 py-4">
          <div>
            <Label htmlFor="store-label-input">Store Label</Label>
            <Input
              id="store-label-input"
              data-testid="store-label-input"
              value={storeLabel}
              onChange={(e) => {
                setStoreLabel(e.target.value);
                if (!abbr) setAbbr(suggestAbbr(e.target.value));
              }}
              placeholder="e.g. SM Tanza"
            />
          </div>
          <div>
            <Label>Parent Legal Entity</Label>
            <Select value={parentCompany} onValueChange={setParentCompany}>
              <SelectTrigger data-testid="parent-company-select">
                <SelectValue placeholder="Pick a parent..." />
              </SelectTrigger>
              <SelectContent>
                {parents.data?.map((p) => (
                  <SelectItem key={p.name} value={p.name}>
                    {p.name} ({p.abbr})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="abbr-input">Abbreviation (3-6 chars)</Label>
            <Input
              id="abbr-input"
              data-testid="abbr-input"
              value={abbr}
              onChange={(e) => setAbbr(e.target.value.toUpperCase().slice(0, 6))}
              maxLength={6}
            />
          </div>
          <div>
            <Label>Ownership Type</Label>
            <Select value={ownership} onValueChange={(v) => setOwnership(v as any)}>
              <SelectTrigger data-testid="ownership-type-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {OWNERSHIP_OPTIONS.map((o) => (
                  <SelectItem key={o} value={o}>{o}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="tax-id-input">Tax ID (optional — inherits from parent)</Label>
            <Input
              id="tax-id-input"
              data-testid="tax-id-input"
              value={taxId}
              onChange={(e) => setTaxId(e.target.value)}
              placeholder="000-000-000-00000"
            />
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button
            data-testid="submit-create-store-button"
            onClick={handleSubmit}
            disabled={create.isPending || !storeLabel.trim() || !parentCompany || !abbr.trim()}
          >
            {create.isPending ? "Creating..." : "Create Store"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

**MUST_MODIFY:** `bei-tasks/components/company-master/create-store-dialog.tsx` (NEW)
**MUST_CONTAIN:** `data-testid="create-store-dialog"`, `data-testid="store-label-input"`, `data-testid="parent-company-select"`, `data-testid="abbr-input"`, `data-testid="ownership-type-select"`, `data-testid="tax-id-input"`, `data-testid="submit-create-store-button"`, `useCreateStoreCompany`, `useEligibleParents`

#### 3-3. Wire button into BD page header (2 units) — v2 A5 + A9

```tsx
// bei-tasks/app/dashboard/bd/companies/page.tsx — add import + state + button + dialog mount

import { CreateStoreDialog } from "@/components/company-master/create-store-dialog";
import { Plus } from "lucide-react";
import { useUserRoles } from "@/hooks/use-user-roles"; // existing hook
import { MODULES, MODULE_ACCESS } from "@/lib/roles";

// Inside the page component:
const [createStoreOpen, setCreateStoreOpen] = useState(false);

// v2 A5: Guard variable — must match backend allowed_roles (Phase 2-1).
// Source of truth: bei-tasks/lib/roles.ts MODULE_ACCESS[MODULES.COMPANY_MASTER].
// If divergence creeps in, the backend will silently 403 grant-only-frontend roles.
const userRoles = useUserRoles();
const hasCompanyMasterRole = MODULE_ACCESS[MODULES.COMPANY_MASTER].some(
  (role) => userRoles.includes(role)
);

// In the header area near the title, add:
{hasCompanyMasterRole && (
  <Button
    data-testid="add-store-button"
    size="sm"
    onClick={() => setCreateStoreOpen(true)}
  >
    <Plus className="h-4 w-4 mr-1" /> Add Store
  </Button>
)}

// At the end of the component, mount the dialog:
<CreateStoreDialog
  open={createStoreOpen}
  onClose={() => setCreateStoreOpen(false)}
  onCreated={(companyName) => {
    // v2 A9: use lastIndexOf so multi-hyphen store labels survive
    // (e.g., "SM North - Annex - BEBANG MEGA INC." → store label "SM North - Annex").
    // The server precondition forbids " - " in store_label today, but defense
    // in depth costs nothing.
    const lastSepIdx = companyName.lastIndexOf(" - ");
    const storeName = lastSepIdx > 0 ? companyName.slice(0, lastSepIdx) : companyName;
    setSelected({ company: companyName, storeName });
  }}
/>
```

**MUST_MODIFY:** `bei-tasks/app/dashboard/bd/companies/page.tsx`
**MUST_CONTAIN (v2 A5 + A9):**
- `data-testid="add-store-button"`
- `<CreateStoreDialog`
- `setCreateStoreOpen`
- `import { CreateStoreDialog }`
- `hasCompanyMasterRole` (the v2 A5 guard variable name — also referenced by verify_phase3.py)
- `MODULE_ACCESS[MODULES.COMPANY_MASTER]` import + usage (v2 A5)
- `companyName.lastIndexOf(" - ")` (v2 A9)
**MUST_NOT_CONTAIN:**
- `companyName.split(" - ")[0]` (v2 A9 truncation bug)

#### 3-4. RBAC role check + button visibility (1 unit) — v2 A5

`bei-tasks/lib/roles.ts` already exposes `MODULE_ACCESS[MODULES.COMPANY_MASTER]` (verified at line 920 of `roles.ts` in v2 audit). Phase 3-3 wires `hasCompanyMasterRole = MODULE_ACCESS[MODULES.COMPANY_MASTER].some((role) => userRoles.includes(role))`. The same role union is enforced backend-side per Phase 2-1 (`allowed_roles` set must match exactly). If backend and frontend diverge, the audit will flag a Blocker B-05-class issue.

**MUST_CONTAIN:** `hasCompanyMasterRole` AND `MODULE_ACCESS[MODULES.COMPANY_MASTER]` in page.tsx

**Verification (`output/s233/verify_phase3.py`) — v2 A5 + A6 + A9:**
```python
import os
page_src = open("bei-tasks/app/dashboard/bd/companies/page.tsx").read()
backend_src = open("hrms/api/company_master.py").read()
checks = [
    ("dialog_file", os.path.exists("bei-tasks/components/company-master/create-store-dialog.tsx")),
    ("hook_in_queries", "useCreateStoreCompany" in open("bei-tasks/lib/queries/company-master.ts").read()),
    ("button_in_page", "add-store-button" in page_src),
    ("dialog_mount", "CreateStoreDialog" in page_src),
    # v2 A6 — concrete check, not Ellipsis placeholder
    ("v2_a6_rbac_guard_var", "hasCompanyMasterRole" in page_src),
    ("v2_a6_rbac_guard_uses_module_access", "MODULE_ACCESS[MODULES.COMPANY_MASTER]" in page_src),
    # v2 A5 — backend role set must match frontend MODULE_ACCESS
    ("v2_a5_business_development_in_backend", '"Business Development"' in backend_src),
    ("v2_a5_bd_manager_in_backend", '"BD Manager"' in backend_src),
    ("v2_a5_accounts_manager_in_backend", '"Accounts Manager"' in backend_src),
    ("v2_a5_hq_user_in_backend", '"HQ User"' in backend_src),
    ("v2_a5_no_bd_user_in_backend", '"BD User"' not in backend_src),  # nonexistent role
    # v2 A9 — split truncation fix
    ("v2_a9_uses_lastIndexOf", 'lastIndexOf(" - ")' in page_src),
    ("v2_a9_no_split_truncation", 'companyName.split(" - ")[0]' not in page_src),
]
fail = [c for c, ok in checks if not ok]
print("PASS" if not fail else f"FAIL: {fail}")
exit(0 if not fail else 1)
```

---

### Phase 4 — Test library extensions (6 units)

**Goal:** add reusable Page Object, builder, assertion helper, fixture extension, and BD Manager auth fixture.

#### 4-1. CreateStoreDialog Page Object (2 units)

```typescript
// bei-tasks/tests/e2e/pages/CreateStoreDialog.ts
import { expect, type Page } from "@playwright/test";
import { BasePage } from "./BasePage";

export class CreateStoreDialog extends BasePage {
  async openFromCompanyMaster() {
    const btn = this.page.getByTestId("add-store-button");
    await expect(btn).toBeVisible({ timeout: 10_000 });
    await btn.click();
    await expect(this.page.getByTestId("create-store-dialog")).toBeVisible({ timeout: 10_000 });
  }
  async fillStoreLabel(value: string) { await this.page.getByTestId("store-label-input").fill(value); }
  async pickParent(parentName: string) {
    await this.page.getByTestId("parent-company-select").click();
    await this.page.getByRole("option", { name: parentName, exact: false }).first().click();
  }
  async fillAbbr(value: string) { await this.page.getByTestId("abbr-input").fill(value); }
  async pickOwnership(value: "JV" | "Managed Franchise" | "Full Franchise" | "Company Owned") {
    await this.page.getByTestId("ownership-type-select").click();
    await this.page.getByRole("option", { name: value, exact: true }).click();
  }
  async fillTaxId(value: string) { await this.page.getByTestId("tax-id-input").fill(value); }
  async submit() { await this.page.getByTestId("submit-create-store-button").click(); }
  async cancel() { await this.page.keyboard.press("Escape"); }
  async expectFormError(needle: RegExp | string) {
    return this.waitForToast(needle);
  }
}
```

**MUST_MODIFY:** `bei-tasks/tests/e2e/pages/CreateStoreDialog.ts` (NEW)
**MUST_CONTAIN:** all 8 method names listed

#### 4-2. Builder + assertion + cleanup-kind extension (2 units)

```typescript
// bei-tasks/tests/e2e/builders/store-create-payload.ts
export function buildStoreCreatePayload(overrides: Partial<{
  storeLabel: string; parent: string; abbr: string;
  ownership: "JV" | "Managed Franchise" | "Full Franchise" | "Company Owned";
  taxId: string;
}> = {}) { /* returns sane defaults + applies overrides */ }

// bei-tasks/tests/e2e/assertions/canonicalStoreShape.ts
export async function assertCanonicalStoreShape(api, expected: {
  company: string; warehouse: string; billingCustomer: string; internalCustomer: string;
}) { /* reads each via frappe.client.get_value, asserts each exists + correct fields */ }

// bei-tasks/tests/e2e/fixtures/cleanup.ts — extend CleanupKind
| "store-company-create"
// + reverse handler that deletes the 4 records via SSM cancelDoc
```

**MUST_MODIFY:** 3 files above
**MUST_CONTAIN:** `buildStoreCreatePayload(`, `assertCanonicalStoreShape(`, `"store-company-create"` in CleanupKind union, reverse handler in cleanup.ts switch

#### 4-3. loggedInAsBdManager fixture (1 unit)

```typescript
// bei-tasks/tests/e2e/fixtures/auth.ts — append
export interface S233Fixtures extends S192Fixtures {
  loggedInAsBdManager: Page;
}

// In test.extend:
loggedInAsBdManager: async ({ browser }, use) => {
  const { context, page } = await loggedInContextFor(
    process.env.E2E_BD_MANAGER_EMAIL || "test.bd@bebang.ph",
    browser,
    "bd-manager",
  );
  await use(page);
  await safeCloseContext(context);
},
```

**MUST_MODIFY:** `bei-tasks/tests/e2e/fixtures/auth.ts`
**MUST_CONTAIN:** `loggedInAsBdManager: Page`, `"bd-manager"`

#### 4-4. SSM seed/teardown scripts (1 unit)

```bash
scripts/s233_l3_seed_preconditions.py    # check BFI2 is_group=1, seed test.bd@bebang.ph user if missing
scripts/s233_l3_teardown_test_store.py   # delete the 4 records + strip S037 row
```

**MUST_MODIFY:** both scripts NEW
**MUST_CONTAIN (teardown):** SQL/ORM delete for Company + Warehouse + 2 Customers + S037 row removal

---

### Phase 5 — L3 scenarios + browser E2E (8 units)

**Goal:** ship `bei-tasks/tests/e2e/specs/s233-create-store-ui.spec.ts` covering all 8 L3 scenarios.

#### 5-1. Spec scaffold + happy path (S1, S2) (3 units)

```typescript
// bei-tasks/tests/e2e/specs/s233-create-store-ui.spec.ts
import { test, expect } from "../fixtures";
import { CompanyMasterPage } from "../pages/CompanyMasterPage";
import { CreateStoreDialog } from "../pages/CreateStoreDialog";
import { CleanupLedger } from "../fixtures/cleanup";
import { buildStoreCreatePayload } from "../builders/store-create-payload";
import { assertCanonicalStoreShape } from "../assertions/canonicalStoreShape";

const TEST_PARENT = "BEBANG FT INC.";
const TEST_LABEL = "S233 L3 Test Store";
const TEST_ABBR = "S233T";

test.describe("S233 L3 — Create Store UI", () => {
  test("S1+S2: happy path creates 4 canonical records + detail renders", async ({ loggedInAsCEO, request }) => {
    const cmp = new CompanyMasterPage(loggedInAsCEO);
    const dlg = new CreateStoreDialog(loggedInAsCEO);
    const cleanup = new CleanupLedger("output/l3/s233/teardown_ledger.json");
    await cleanup.load();

    await cmp.gotoCompanyList();
    await dlg.openFromCompanyMaster();
    await dlg.fillStoreLabel(TEST_LABEL);
    await dlg.pickParent(TEST_PARENT);
    await dlg.fillAbbr(TEST_ABBR);
    await dlg.pickOwnership("Managed Franchise");
    await dlg.submit();

    // Toast + dialog closes + new row appears
    await cmp.waitForToast(/Store created/i);
    const expectedCompanyName = `${TEST_LABEL} - ${TEST_PARENT}`;
    await cleanup.record("store-company-create", { name: expectedCompanyName });

    // S2: open detail + verify
    await cmp.openCompany(TEST_LABEL);
    // ... assert FeePreviewPanel renders MF tier
    await assertCanonicalStoreShape(request, {
      company: expectedCompanyName,
      warehouse: expectedCompanyName,
      billingCustomer: expectedCompanyName,
      internalCustomer: `${TEST_LABEL} (Internal)`,
    });
  });
  // ... S3 (duplicate abbr), S4 (non-group parent), S5 (missing parent), S7 (RBAC), S8 (atomicity)
});
```

#### 5-2. Negative scenarios S3, S4, S5 (2 units)

#### 5-3. RBAC scenario S7 (1 unit)

#### 5-4. Atomicity scenario S8 (2 units) — verify partial-create rollback (v2 A8)

S8 induces a failure INSIDE the savepoint (not before) so the rollback is actually exercised.

```typescript
test("S8 (v2 A8): savepoint atomicity — invalid customer_group rolls back all 4 records", async ({ loggedInAsCEO, request }) => {
  const cmp = new CompanyMasterPage(loggedInAsCEO);
  const dlg = new CreateStoreDialog(loggedInAsCEO);
  const TEST_LABEL = "S233-L3-ATOMICITY-S8";
  const TEST_ABBR = "S8ATOM";
  const expectedCompanyName = `${TEST_LABEL} - ${TEST_PARENT}`;

  // Pre-test invariant: none of the 4 canonical records exist
  for (const [dt, name] of [
    ["Company", expectedCompanyName],
    ["Warehouse", expectedCompanyName],
    ["Customer", expectedCompanyName],
    ["Customer", `${TEST_LABEL} (Internal)`],
  ] as const) {
    const exists = await frappeReadback.docExists(request, dt, name);
    expect(exists, `Pre-test: ${dt}:${name} must not exist`).toBe(false);
  }

  // To force a savepoint-internal failure, we monkey-patch BEI's BKI_STORE
  // customer_group to a name that won't exist. The Customer.validate hook on
  // the SECOND insert (billing customer) raises LinkValidationError, which
  // happens AFTER Company + Warehouse are inserted INSIDE the savepoint.
  // SSM helper applies the patch + reverts after the test.
  await ssmRun(`
    import frappe
    frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
    frappe.connect()
    # Temporarily mark BKI Store group as disabled — Customer.validate will reject
    frappe.db.set_value("Customer Group", "BKI Store", "disabled", 1)
    frappe.db.commit()
    frappe.destroy()
  `);

  try {
    await cmp.gotoCompanyList();
    await dlg.openFromCompanyMaster();
    await dlg.fillStoreLabel(TEST_LABEL);
    await dlg.pickParent(TEST_PARENT);
    await dlg.fillAbbr(TEST_ABBR);
    await dlg.pickOwnership("Managed Franchise");
    await dlg.submit();

    // Expect failure toast naming customer_group / customer
    await cmp.waitForToast(/customer/i);

    // INVARIANT: all 4 records absent (savepoint rolled back)
    for (const [dt, name] of [
      ["Company", expectedCompanyName],
      ["Warehouse", expectedCompanyName],
      ["Customer", expectedCompanyName],
      ["Customer", `${TEST_LABEL} (Internal)`],
    ] as const) {
      const exists = await frappeReadback.docExists(request, dt, name);
      expect(exists, `Post-failure: ${dt}:${name} MUST be absent (savepoint rollback)`).toBe(false);
    }

    // INVARIANT: S037 register CSV does NOT contain the test row
    // (CSV write is post-savepoint per A3, so it should never have fired)
    const csvRows = await ssmRun(`
      import csv, os
      from frappe.utils import get_app_path
      path = os.path.join(get_app_path("hrms"), "data_seed", "store_entity_mapping_2026-04-13.csv")
      with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
      print(any(r[0] == "${TEST_LABEL}" for r in rows))
    `);
    expect(csvRows.trim(), "Post-failure: S037 CSV must NOT contain test row").toBe("False");
  } finally {
    // Always restore Customer Group regardless of test outcome
    await ssmRun(`
      import frappe
      frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
      frappe.connect()
      frappe.db.set_value("Customer Group", "BKI Store", "disabled", 0)
      frappe.db.commit()
      frappe.destroy()
    `);
  }
});
```

**Why this design works (v2 A8 rationale):**
- v1 attempted to test atomicity by passing `store_label=""`, but `_validate_preconditions` rejects that BEFORE `frappe.db.savepoint()` is even called (Phase 1-2 precondition guard runs first). No savepoint = no rollback to verify.
- v2 chooses a payload that passes preconditions (valid label/abbr/parent) but fails INSIDE the savepoint at the second Customer insert. This exercises the rollback path that B-02 (commit ordering) and B-03 (CSV placement) fixes are about.
- Restore of `Customer Group.disabled=0` in `finally` is mandatory — without it, the entire BKI Store customer group is broken for production.

**MUST_CONTAIN (v2 A8):**
- `set_value("Customer Group", "BKI Store", "disabled", 1)` (the failure-inducing patch)
- `set_value("Customer Group", "BKI Store", "disabled", 0)` (the cleanup in finally)
- `frappeReadback.docExists` checks for all 4 records post-failure
- S037 CSV row absence check post-failure

**MUST_MODIFY:** `bei-tasks/tests/e2e/specs/s233-create-store-ui.spec.ts` (NEW)
**MUST_CONTAIN:** all 8 scenario test names, `cleanupLedger.record("store-company-create"`, `assertCanonicalStoreShape(`

---

### Closeout — verifier post + plan/registry + worktree remove (4 units)

#### C-1. Run all phase verification scripts

```bash
python output/s233/verify_phase0.py
python output/s233/verify_phase0_5.py    # v2 A7 — constant extraction
python output/s233/verify_phase1.py
python output/s233/verify_phase2.py
python output/s233/verify_phase3.py
```

#### C-2. Run unit tests

```bash
docker exec frappe_backend bench --site hq.bebang.ph run-tests --module hrms.tests.test_s233_create_store_company
```

Expected: 7 PASS.

#### C-3. Run L3 scenarios

```bash
cd F:/Dropbox/Projects/bei-tasks-s233-create-store-ui-button
npx playwright test tests/e2e/specs/s233-create-store-ui.spec.ts --reporter=list
```

Expected: 8 PASS.

#### C-4. Run teardown

```bash
python scripts/s233_l3_teardown_test_store.py
```

Verify `output/l3/s233/teardown_complete.json` shows `{remaining: 0}`.

#### C-5. Canonical verifier post

```bash
python scripts/verify_canonical_structure.py | tee output/s233/verification/canonical_verifier_post.txt
```

Must show 0 NEW violations vs preflight.

#### C-6. Update plan + registry status

- Plan YAML: `status: PLANNED → COMPLETED`, add `completed_date`, fill `execution_summary`.
- `SPRINT_REGISTRY.md`: flip S233 row status to COMPLETED + add PR numbers.
- `git add -f` for both files.

#### C-7. Create PRs

- hrms PR: against `production` branch.
- bei-tasks PR: against `main` branch.
- Each PR description includes per-phase status table + L3 scenario results.

#### C-8. Worktree closeout

```bash
git -C F:/Dropbox/Projects/BEI-ERP-s233-create-store-ui-button status --short  # must be clean
cd F:/Dropbox/Projects/BEI-ERP && git worktree remove F:/Dropbox/Projects/BEI-ERP-s233-create-store-ui-button
git -C F:/Dropbox/Projects/bei-tasks-s233-create-store-ui-button status --short
cd F:/Dropbox/Projects/bei-tasks && git worktree remove F:/Dropbox/Projects/bei-tasks-s233-create-store-ui-button
```

---

## Failure Response

Per QA test library discipline:

- **Mode A (app bug):** New Company creation fails for an unforeseen Frappe-side reason. File a [BUG], do NOT touch test or library, re-run after fix.
- **Mode B (test bug):** A specific assertion misreads the DOM. Fix the test; if the fix helps other tests, promote to `CompanyMasterPage` / `CreateStoreDialog` Page Object.
- **Mode C (brittleness/flakiness):** Save+wait race fails intermittently. Fix the LIBRARY, not the spec. No `waitForTimeout`, no `retry(3)` masking.

If ≥3 library fixes happen during execution, agent emits `output/l3/s233/LIBRARY_IMPROVEMENTS.md` as a closeout artifact.

---

## Requirements Regression Checklist

Before any code change, the executing agent must verify YES for every item:

- [ ] Have I read `docs/STORE_COMPANY_CANONICAL.md` end-to-end?
- [ ] Did I run `scripts/verify_canonical_structure.py` and capture to `output/s233/verification/canonical_verifier_pre.txt`?
- [ ] Am I working in the `F:/Dropbox/Projects/BEI-ERP-s233-create-store-ui-button` and `bei-tasks-s233-create-store-ui-button` worktrees, NOT the main checkouts?
- [ ] Are my branches `s233-create-store-ui-button` in both repos, branched from `origin/production` / `origin/main`?
- [ ] Does the canonical helper create EXACTLY 4 records per invocation (1 Company + 1 Warehouse + 1 billing Customer + 1 internal Customer)?
- [ ] Do all 4 records share the same canonical name string `<store_label> - <parent_company>` (except Internal Customer = `<store_label> (Internal)`)?
- [ ] Does the helper enforce parent `is_group=1` BEFORE attempting any write? (HARD BLOCKER per Phase A defect)
- [ ] Does the helper use `frappe.local.flags.ignore_chart_of_accounts = True`? (HARD BLOCKER per S231 chart bug)
- [ ] Does the helper use `frappe.flags.in_install = True`? (skip auto_provision_company so first_provision_done stays 0)
- [ ] Does the helper accept ONLY `"Pre-Opening"` (capital O) for operational_status?
- [ ] **v2 A1:** Does the helper file live at `hrms/api/create_new_store.py` (NOT `scripts/canonical/`)? `scripts/` is not on Frappe's `sys.path` per HOTFIX4 at `company_master.py:939`.
- [ ] **v2 A2:** Does the helper call `frappe.db.release_savepoint(sp)` INSIDE try with NO `frappe.db.commit()` inside the savepoint scope? (Frappe's HTTP cycle commits)
- [ ] **v2 A3:** Is `_append_s037_row(...)` called AFTER `release_savepoint` (outside the try block, post-success), NOT inside the savepoint?
- [ ] **v2 A4:** Do BOTH Customer inserts set `customer_type="Company"`, `customer_group="BKI Store"`, `territory="Philippines"`? (Without these, Customer.validate raises MandatoryError → savepoint rolls back → helper fails)
- [ ] **v2 A7:** Does the helper import `from hrms.utils.bei_config import S037_REGISTER_RELPATH` (NOT from `hrms.api.company_master`)? (Phase 0.5 extracted the constant to break circular import)
- [ ] Does the helper append a row to the latest S037 register CSV atomically (tempfile + os.replace)?
- [ ] **v2 A5:** Does `create_store_company` whitelisted endpoint require role from `{Business Development, BD Manager, Accounts Manager, HQ User, System Manager, Administrator}` (matching frontend `MODULE_ACCESS[MODULES.COMPANY_MASTER]`)? `"BD User"` MUST NOT appear (does not exist in BEI role taxonomy).
- [ ] Does `create_store_company` call `set_backend_observability_context(module="company", action="create_store_company", mutation_type="create")` per DM-7?
- [ ] Does `list_eligible_parent_companies` filter by `is_group=1 AND entity_category in (Head Office, Holding Company, Franchisor, Commissary)`?
- [ ] Does the frontend dialog have `data-testid` on the dialog root + every form field + submit button?
- [ ] Does the BD page header button have `data-testid="add-store-button"` + RBAC visibility guard wrapped in `{hasCompanyMasterRole && ...}`?
- [ ] **v2 A5:** Does the frontend `hasCompanyMasterRole` use `MODULE_ACCESS[MODULES.COMPANY_MASTER]` from `lib/roles.ts`, and does the backend `allowed_roles` set match the same role union?
- [ ] **v2 A9:** Does the page.tsx `onCreated` handler use `companyName.lastIndexOf(" - ")` instead of `companyName.split(" - ")[0]` to derive store label?
- [ ] **v2 A6:** Does `verify_phase3.py` use a concrete check for `hasCompanyMasterRole` (NOT `...` Ellipsis)?
- [ ] Does `useCreateStoreCompany` invalidate BOTH `["company-master", "list"]` AND `["company-master", "stores"]` queries on success?
- [ ] Does the L3 cleanupLedger reverse handler delete all 4 records + strip the S037 row?
- [ ] Are the 8 L3 scenarios written as separate `test()` blocks (not one mega-test)?
- [ ] **v2 A8:** Does S8 atomicity scenario disable `Customer Group "BKI Store"` to induce failure inside the savepoint, verify all 4 records absent post-failure, AND restore the Customer Group in `finally`?
- [ ] Did I commit evidence to `output/s233/` (committed) AND transient logs to `tmp/s233/` (gitignored)?
- [ ] At closeout, did I run `git worktree remove` on BOTH worktrees?

---

## Test Maintenance Library Discipline

Per `.claude/docs/qa-test-library-discipline.md`:

- **Library-first:** Every test task references the library audit table.
- **Real-browser only for workflow ops:** Forbidden in spec body — `page.request.*`, `fetch(`, `curl`. SSM allowed for setup/teardown only.
- **Cleanup via cleanupLedger fixture:** every mutation in S1 routes through `cleanup.record("store-company-create", ...)`.
- **Three-uses rule:** `ignore_chart_of_accounts` pattern hits 3+ uses across the codebase → extracted to canonical helper. ✓
- **`data-testid` everywhere:** 7 new testids on the dialog + button surface.

**Closeout review gates:**
- `rg 'page\.request|fetch\(' output/l3/s233/` returns 0 hits in workflow specs
- `rg 'page\.click\("button:has-text|page\.locator\("button' tests/e2e/specs/s233*` returns 0 hits
- Every test uses at least one `loggedInAs*` fixture
- `cleanupLedger.pendingEntries === 0` assertion in `afterEach` passes

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

S231 L3 (2026-05-03) discovered the BD Company Master page has no "Add Store" UI button. CEO directive: build it. The SSM-only path that exists today caused 4 production defects in S231 Phase A (BFI2 is_group=0, chart of accounts importer bug, enum case mismatch, missing markup default). All 4 were fixed reactively after they bit. A first-class UI flow that handles them by construction prevents the next round.

### Why this architecture (not alternatives)

**Option A (chosen): canonical helper script + thin whitelisted API + dedicated dialog.** Three-layer separation matches existing BEI patterns (S168 billing, S206 labor cost-sharing, S231 fee preview). Canonical helper is reusable from CLI (current SSM workflow) AND from the API. The script is testable in isolation without Frappe permissions.

**Option B (rejected): inline the logic in the whitelisted API only.** Loses CLI reuse — future BD bulk-onboarding scripts would have to call the HTTP endpoint instead of the helper directly.

**Option C (rejected): use Frappe's built-in Company doctype's New form via Desk.** Would expose every Frappe Company field including dangerous internals. The CEO's UI directive specifically said "for Sam and BD users on my.bebang.ph" — desk is admin-only.

**Option D (rejected): add a "Stub Company" mode that creates Company + Warehouse only, defer Customers to first SI.** Breaks the canonical model rule "every store has EXACTLY 1 of each of the 4 records." Late Customer creation is exactly the drift S188-S206 incident fixed.

### Key trade-off decisions

| Decision | Alternative | Why chosen |
|---|---|---|
| Skip auto_provision_company (set first_provision_done=0) on creation; operator clicks "Run First Provisioning" pill afterwards | Run auto_provision during create | S181 templates have a known structural bug (validate_root_details on flat root accounts). Decoupling create from provisioning means create succeeds even when CoA seeding would fail. Operator gets a clear retry button. |
| S037 register auto-append on create | Manual S037 update post-create | Forgetting the S037 row is a known foot-gun (the new Company exists in tabCompany but doesn't appear in BD list). Auto-appending closes the loop. |
| Tax ID inherits from parent when blank | Always require explicit tax ID | Most stores share their parent's BIR TIN. Making it optional reduces form friction for the common case while still allowing override for standalone-OPC stores. |
| RBAC hardcoded list of allowed roles | Frappe DocType-level permissions only | Hardcoded list is auditable in source + immune to runtime perm-doc tampering. Backed up by Frappe `has_permission` check anyway (defense in depth). |
| One unified mutation hook + dialog | Wizard with multiple steps | 5 fields fit comfortably in one dialog; wizard would add complexity without UX benefit. |

### Known limitations and mitigations

- **No "edit + then create dependent stores" flow.** Once created, the BD user must use existing section-edit-modal to update operational_status, region, etc. Mitigation: documented in dialog description.
- **Helper does NOT seed Cost Centers.** Auto-provision will create them when operator clicks the retry pill. Mitigation: operator pill has been working since S181.
- **S037 CSV is not git-versioned write target** — every store-create is a new commit-able row. Mitigation: the CSV is already committed; new rows accumulate. Sprint plan acknowledges Periodic CSV cleanup is out of scope.
- **No bulk import.** Only one store per call. Mitigation: bulk import is a separate sprint if needed.

### Source references

- `docs/STORE_COMPANY_CANONICAL.md` — canonical model (SSOT)
- `hrms/api/company_master.py:503` — `_NON_STORE_ENTITIES` (canonical parents)
- `hrms/api/company_master.py:230` — `update_company_section` (existing pattern to follow)
- `hrms/api/company_master.py:209` — `get_company` (existing pattern)
- `hrms/api/company_master.py:668` — `list_stores` (where new store appears post-create)
- `hrms/overrides/company.py:592` — `auto_provision_company` (the function we DON'T want firing on create)
- `hrms/overrides/company.py:31` — `DEFAULT_FIELDS_TO_TRACK` + S231 C-1 wrapper (already deployed)
- `scripts/canonical/migrate_49_stores.py` — reference for atomic multi-record write (CLI-only — runs via `bench execute`, NOT importable from Frappe HTTP context)
- `scripts/s231_l3_seed_test_store.py` — reference for ignore_chart_of_accounts pattern (this sprint extracts it to canonical helper)
- `hrms/api/company_master.py:939–941` — **HOTFIX4 comment documents the `from scripts/` import trap**. This is exactly why v2 A1 puts the helper at `hrms/api/create_new_store.py` instead.
- `hrms/utils/bei_config.py` — receives the v2 A7 extracted constant `S037_REGISTER_RELPATH`
- `hrms/overrides/company.py:572–575` — canonical Customer-creation pattern with `customer_type`/`customer_group`/`territory` (v2 A4 source)
- `hrms/on_demand/s206_seed_intercompany_accounts.py:264–266` — alternate Customer-creation pattern using `_best_customer_group()` + `_best_territory()` helpers
- `hrms/api/procurement.py:6607` — canonical savepoint pattern: `release_savepoint` BEFORE commit, commit OUTSIDE try (v2 A2 source)
- `bei-tasks/lib/roles.ts:920` — `MODULE_ACCESS[MODULES.COMPANY_MASTER]` (v2 A5 source of truth for backend `allowed_roles`)
- `bei-tasks/lib/queries/company-master.ts:208-243` — `frappePost`/`frappeGet` helpers (template for new endpoints)
- `bei-tasks/components/company-master/section-edit-modal.tsx` — dialog component pattern
- `bei-tasks/tests/e2e/pages/CompanyMasterPage.ts` — Page Object pattern
- `bei-tasks/tests/e2e/fixtures/cleanup.ts` — CleanupLedger pattern
- `bei-tasks/tests/e2e/specs/s209-all-stores.spec.ts` — full E2E pattern with seed/teardown

### Reference incidents

- 2026-05-02 S231 Phase A defects (4 classes) — drove this sprint
- 2026-04-19 canonical model consolidation (PR #638) — drove the canonical model SSOT
- S168 / S206 — established the per-store billing + labor pattern this depends on

---

## Phase Budget Contract (v2)

| Phase | Units | Notes |
|---|---|---|
| Phase 0 — Boot | 4 | Baselines, library audit, dependency check |
| Phase 0.5 — Constant extract (v2 A7) | 1 | Extract `_S037_RELPATH` to `hrms/utils/bei_config.py` to break circular import |
| Phase 1 — Canonical helper (in hrms/api/) | 8 | NEW helper at `hrms/api/create_new_store.py` (v2 A1) + atomic 4-record write (v2 A2/A3/A4) + S037 append + CLI wrapper |
| Phase 2 — Whitelisted API + tests | 5 | 2 endpoints + RBAC matching frontend MODULE_ACCESS (v2 A5) + 7 unit tests |
| Phase 3 — Frontend | 10 | Hook + dialog + button + RBAC guard (v2 A5) + lastIndexOf split (v2 A9) |
| Phase 4 — Test library | 6 | Page Object + builder + assertion + cleanup-kind + auth fixture + SSM scripts |
| Phase 5 — L3 spec | 8 | 8 scenarios in browser-only spec, S8 atomicity uses customer_group disable trick (v2 A8) |
| Closeout | 4 | Verifiers, teardown, plan/registry, PRs, worktree remove |
| **Total** | **46** | v1 was 45; v2 adds 1u for B-08 fix. Under 80-unit S089 cap |

Hard limit per phase: 15. Preferred split threshold: 12. Largest phase (Phase 3) is 10 units — within threshold.

---

## Execution Workflow

- Test Python changes: `/local-frappe`
- Deploy hrms backend: `/deploy-frappe` (Sam handles via PR-Handoff)
- Test bei-tasks changes locally: `cd bei-tasks-s233-create-store-ui-button && npm run dev` then visit localhost
- Browser E2E: `npx playwright test tests/e2e/specs/s233-create-store-ui.spec.ts`
- Full workflow: `/agent-kickoff` to read all skills, then `/execute-plan-bei-erp` for autonomous execution

> **PR-Handoff:** Agent creates 2 PRs (hrms + bei-tasks). Sam handles merge + deploy. Agent does NOT call deploy workflows.
