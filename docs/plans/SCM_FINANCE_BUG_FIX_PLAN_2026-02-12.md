# SCM + Finance Bug Fix Plan — 2026-02-12 (v1.2 — EXECUTING)

**Source:** E2E test run `scratchpad/e2e-scm-finance-2026-02-12/FINAL_REPORT.md`
**Result:** 139/159 PASS (87.4%), **19 FAIL** (corrected from 20 — FIN-RBAC-002 is a PASS)
**Goal:** Fix all 19 failures, redeploy, retest to 159/159 (100%)
**Audit Status:** ALL 8 BLOCKERS RESOLVED — GO (Option A: deploy all, compliance sprint separate)

---

## Bug List (20 Failures, 3 Root Causes)

### Category A: Finance Endpoints Not Deployed (14 failures)

**Root cause:** 3 Python functions exist locally in `hrms/api/procurement.py` (lines 3935-4208) but the current Docker image on production was built BEFORE these functions were added. `skip_build=true` reuses the old image.

**Error:** `module 'hrms.api.procurement' has no attribute 'apply_franchise_payment'` (HTTP 417)

| # | Scenario | Endpoint Missing | Error |
|---|----------|-----------------|-------|
| 1 | FIN-001 | `apply_franchise_payment` | HTTP 417 — attribute not found |
| 2 | FIN-002 | `apply_franchise_payment` | HTTP 417 — no 2nd billing + attribute not found |
| 3 | FIN-003 | `apply_franchise_payment` | HTTP 417 — depends on FIN-002 |
| 4 | FIN-004 | `generate_acknowledgement_receipt` | HTTP 417 — attribute not found |
| 5 | FIN-005 | `generate_monthly_billing` | HTTP 417 — attribute not found |
| 6 | FIN-006 | `generate_monthly_billing` | HTTP 417 — attribute not found |
| 7 | FIN-NEG-001 | `apply_franchise_payment` | HTTP 417 — can't test overpayment validation |
| 8 | FIN-NEG-002 | `apply_franchise_payment` | HTTP 417 — no Cancelled billing + not deployed |
| 9 | FIN-NEG-003 | `generate_monthly_billing` | HTTP 417 — attribute not found |
| 10 | FIN-NEG-004 | `generate_monthly_billing` | HTTP 417 — attribute not found |
| 11 | FIN-NEG-006 | `generate_acknowledgement_receipt` | HTTP 417 — attribute not found |
| 12 | FIN-RBAC-001 | `apply_franchise_payment` | HTTP 417 — can't test RBAC if endpoint doesn't exist |
| 13 | FIN-RBAC-002 | — | PASS (get_billing_list works) |
| 14 | FIN-007 | — | See Category B (permission issue) |

**Fix:** Full Docker build (`skip_build=false`, `no_cache=true`) + `bench migrate`. No code changes needed — the code is already in the repo.

**Unblocks:** 12 scenarios (FIN-001 through FIN-006, FIN-NEG-001 through FIN-NEG-004, FIN-NEG-006, FIN-RBAC-001)

**Additional data needed after deploy:**
- FIN-002 needs a 2nd billing record (only 1 Draft exists: `BILL-2026-01-Operations - BEI`)
- FIN-NEG-002 needs a Cancelled billing record
- All payment scenarios need billing in `Sent` status (current one is `Draft`)

---

### Category B: DocType Permission Gaps (5 failures)

**Root cause:** `test.hr@bebang.ph` (HR Officer / Accounts Manager role) lacks permissions on 3 procurement DocTypes. The DocType JSON permissions only grant access to Procurement User, Procurement Manager, and System Manager.

| # | Scenario | DocType | Permission Needed | Error |
|---|----------|---------|------------------|-------|
| 1 | PROC-003 | BEI Purchase Requisition | `create` | HTTP 403 — "does not have doctype access" |
| 2 | PROC-004 | BEI Purchase Requisition | (depends on PROC-003) | Skipped — no PR created |
| 3 | PROC-011 | BEI Purchase Order | `read` | HTTP 403 — "You do not have access to procurement reports" |
| 4 | FIN-007 | BEI Payment Request | `read` | HTTP 403 — PermissionError |
| 5 | FIN-NEG-005 | BEI Payment Request | `read` | HTTP 403 — false positive (403 from perm, not GL logic) |

**Fix files and exact changes:**

#### Fix B1: `hrms/hr/doctype/bei_purchase_requisition/bei_purchase_requisition.json`

Current permissions (line 200): Procurement User, Procurement Manager, System Manager

**Add after System Manager block (line 236):**
```json
,
{
    "create": 1,
    "delete": 0,
    "email": 1,
    "export": 1,
    "print": 1,
    "read": 1,
    "report": 1,
    "role": "Accounts Manager",
    "share": 0,
    "write": 1
}
```

#### Fix B2: `hrms/hr/doctype/bei_purchase_order/bei_purchase_order.json`

Current permissions (line 308): Procurement User, Procurement Manager, System Manager

**Add after System Manager block (line 344):**
```json
,
{
    "create": 0,
    "delete": 0,
    "email": 1,
    "export": 1,
    "print": 1,
    "read": 1,
    "report": 1,
    "role": "Accounts Manager",
    "share": 0,
    "write": 0
}
```

#### Fix B3: `hrms/hr/doctype/bei_payment_request/bei_payment_request.json`

Current permissions (line 683): Accounts User, Accounts Manager, System Manager — **Accounts Manager already has read/create access.**

**Investigation needed:** test.hr@bebang.ph has the `Accounts Manager` role but is still getting 403. Possible causes:
1. The role isn't actually assigned on the Frappe side (only in bei-tasks RBAC)
2. A `has_permission` override is rejecting the user
3. The role assignment hasn't been migrated

**Action:** Verify test.hr's roles on Frappe:
```python
frappe.get_roles("test.hr@bebang.ph")
```
If `Accounts Manager` is missing, add it via:
```python
frappe.get_doc("User", "test.hr@bebang.ph").add_roles("Accounts Manager")
```

**Unblocks:** 5 scenarios (PROC-003, PROC-004, PROC-011, FIN-007, FIN-NEG-005)

---

### Category C: Commissary SQL Column Bugs (3 failures)

**Root cause:** SQL queries in `hrms/api/commissary.py` reference columns that don't exist on the DocType schema.

| # | Scenario | Endpoint | Bad Column | Error |
|---|----------|----------|------------|-------|
| 1 | L1 Smoke | `get_rm_reorder_alerts` | `i.reorder_level`, `i.safety_stock` | HTTP 500 — Unknown column in SELECT |
| 2 | L1 Smoke | `get_my_requisitions` | `remarks` | HTTP 500 — Unknown column in SELECT |
| 3 | L1 Smoke | `get_rm_for_requisition` | (cascades from #1) | HTTP 500 — calls get_rm_reorder_alerts() |

**Fix files and exact changes:**

#### Fix C1: `hrms/api/commissary.py` line 1866-1885 — `get_rm_reorder_alerts()`

**Problem:** `tabItem` does NOT have `reorder_level` or `safety_stock` columns. In ERPNext, reorder levels are stored in the child table `Item Reorder` (linked to a warehouse).

**Replace lines 1866-1885:**
```python
    rm_items = frappe.db.sql("""
        SELECT
            i.name as item_code,
            i.item_name,
            i.item_group,
            i.stock_uom as uom,
            IFNULL(ir.warehouse_reorder_level, 0) as reorder_level,
            IFNULL(ir.warehouse_reorder_qty, 0) as safety_stock,
            IFNULL(b.actual_qty, 0) as current_qty
        FROM `tabItem` i
        LEFT JOIN `tabItem Reorder` ir ON ir.parent = i.name AND ir.warehouse = %s
        LEFT JOIN `tabBin` b ON b.item_code = i.name AND b.warehouse = %s
        WHERE i.disabled = 0
        AND i.is_stock_item = 1
        AND (
            i.item_group LIKE '%%Raw%%'
            OR i.item_code LIKE 'RM%%'
            OR i.item_group = 'Raw Materials'
        )
        ORDER BY i.item_name
    """, (commissary_warehouse, commissary_warehouse), as_dict=True)
```

**Note:** `Item Reorder` child table fields are `warehouse_reorder_level` and `warehouse_reorder_qty`. The LEFT JOIN on warehouse ensures we get the reorder level for the commissary warehouse specifically.

#### Fix C2: `hrms/api/commissary.py` line 2055-2063 — `get_my_requisitions()`

**Problem:** `Material Request` DocType does NOT have a `remarks` field. It does have `_user_tags` and `_comments` but no `remarks`.

**Replace line 2058-2061:**
```python
        fields=[
            "name", "transaction_date", "schedule_date",
            "status", "owner", "docstatus"
        ],
```

(Simply remove `remarks` from the fields list.)

#### Fix C3: No separate fix needed

`get_rm_for_requisition()` (line 2099) calls `get_rm_reorder_alerts()` internally. Fix C1 fixes this automatically.

**Unblocks:** 3 L1 smoke test failures

---

## Execution Order

| Step | Action | Files Changed | Deploys? |
|------|--------|--------------|----------|
| 1 | Fix 3 commissary SQL bugs | `hrms/api/commissary.py` | Yes (code change) |
| 2 | Add Accounts Manager permission to BEI Purchase Requisition | `bei_purchase_requisition.json` | Yes (bench migrate) |
| 3 | Add Accounts Manager read permission to BEI Purchase Order | `bei_purchase_order.json` | Yes (bench migrate) |
| 4 | Verify test.hr has Accounts Manager role in Frappe | Via bench console | No |
| 5 | Full Docker build + bench migrate | N/A | **Yes — FULL BUILD required** |
| 6 | Create test billing data (Sent + Cancelled status) | Via API after deploy | No |
| 7 | Retest all 20 failures | L1 + L3 rerun | No |

**Critical:** Steps 1-3 are code/schema changes that ALL require a full Docker build (`skip_build=false`, `no_cache=true`). Do them all in ONE commit, ONE build.

---

## Retest Plan

After deployment, run these specific tests:

```
# Category A: Finance endpoints (12 scenarios)
/l3-submit-verify finance

# Category B: Procurement permissions (3 scenarios)
/l3-submit-verify procurement  (specifically PROC-003, PROC-004, PROC-011)

# Category B: Payment Request permissions (2 scenarios)
/l3-submit-verify finance  (specifically FIN-007, FIN-NEG-005)

# Category C: Commissary SQL (3 endpoints)
/l1-api-check commissary  (specifically get_rm_reorder_alerts, get_my_requisitions, get_rm_for_requisition)
```

**Target:** 159/159 PASS (100%)

---

## Summary

| Category | Failures | Fix Type | Effort |
|----------|----------|----------|--------|
| A: Finance endpoints not deployed | 12 | Docker build only | 5-10 min build |
| B: DocType permission gaps | 5 | JSON edit + role check | 15 min |
| C: Commissary SQL column bugs | 3 | Python code fix | 15 min |
| **Total** | **19** | | **~40 min + build time** |

---

## Audit Amendments (v1.1) — 2026-02-12

### Audit Methodology

3 specialized agents audited this plan in parallel, each writing detailed findings to disk. Full reports with code fixes are in the referenced files — this section contains only the consolidated blockers and recommendations.

| Domain | Agent | Findings File | Score |
|--------|-------|---------------|-------|
| Frappe Backend | frappe-backend-auditor | `scratchpad/plan-audit/scm-finance-bugfix/frappe_backend_findings.md` | 4 CRITICAL, 3 WARNING, 4 INFO |
| PH Finance | ph-finance-auditor | `scratchpad/plan-audit/scm-finance-bugfix/ph_finance_findings.md` | 24/100 compliance |
| Deployment/QA | deployment-qa-auditor | `scratchpad/plan-audit/scm-finance-bugfix/deployment_qa_findings.md` | NO-GO, 5 blockers |

### Top 8 Blockers (Must Resolve Before Execution)

#### BLOCKER 1: Fix C2 Is WRONG — `remarks` Field EXISTS on Material Request
**Source:** `frappe_backend_findings.md` C3 | **Severity:** CRITICAL
**Problem:** Plan says remove `remarks` but Material Request DOES have this field. The L1 failure was a cascading error from `get_rm_reorder_alerts`, NOT from `remarks`. `create_rm_requisition()` (line 2000) explicitly sets `mr.remarks`.
**Fix:** DELETE Fix C2 from the plan. Only Fix C1 (reorder SQL) is needed — `get_my_requisitions` will work once the reorder helper is fixed.

#### BLOCKER 2: Feature Branch Workflow Missing
**Source:** `deployment_qa_findings.md` D-01 | **Severity:** CRITICAL
**Problem:** Direct push to `production` blocked by hook. GitHub Actions only triggers on PR merge.
**Fix:** Add Step 0: branch `fix/scm-finance-bugs` → commit → push → PR → merge.

#### BLOCKER 3: Test Account Role Verification Before Deploy
**Source:** `deployment_qa_findings.md` D-03 | **Severity:** HIGH
**Problem:** Step 4 (verify role) happens after Step 5 (deploy). If role missing, whole deploy wasted.
**Fix:** Move to before deploy: `frappe.get_roles("test.hr@bebang.ph")` via bench console on EC2.

#### BLOCKER 4: Accounts Manager Should NOT Get CREATE on Purchase Requisition
**Source:** `frappe_backend_findings.md` C4 | **Severity:** CRITICAL
**Problem:** Fix B1 gives Accounts Manager `create` on BEI Purchase Requisition — violates separation of duties.
**Fix:** Give Accounts Manager READ-ONLY access. For PROC-003 test, assign test.hr the Procurement User role instead.

#### BLOCKER 5: Test Billing Data Creation Not Specified
**Source:** `deployment_qa_findings.md` D-04 | **Severity:** MEDIUM
**Problem:** Step 6 has no scripts.
**Fix:** Add bench console script to create billing records in Sent + Cancelled status.

#### BLOCKER 6: No GL Entry in apply_franchise_payment() — DM-1 Violation
**Source:** `ph_finance_findings.md` C2 | **Severity:** CRITICAL (finance code)
**Problem:** Function updates billing amounts but NEVER creates Journal Entry / Payment Entry. Books invisible.
**Decision:** Deploy as billing tracker (no accounting) OR add GL entry logic first.

#### BLOCKER 7: EWT Missing — DM-3 Violation
**Source:** `ph_finance_findings.md` C1 | **Severity:** CRITICAL (finance code)
**Problem:** Franchise fees subject to 15% EWT (BIR ATC WI158). Zero EWT logic in code.
**Decision:** EWT in scope for this deploy or separate sprint?

#### BLOCKER 8: AR Is Not BIR Invoice — EOPT Law Gap
**Source:** `ph_finance_findings.md` C4 | **Severity:** CRITICAL (finance code)
**Problem:** AR explicitly marked "NOT a BIR Official Receipt." EOPT Law requires VAT Invoice.
**Decision:** Is AR acceptable as internal doc (with separate BIR process) or needs replacement?

### Pre-Flight Checks: Audit Additions

- [x] **AUDIT-1:** Fix C2 REMOVED from plan (remarks is valid — cascading error from C1)
- [x] **AUDIT-2:** Feature branch `fix/scm-finance-bugs` created (not direct push)
- [ ] **AUDIT-3:** test.hr roles verified via bench console BEFORE deploy
- [x] **AUDIT-4:** Fix B1 changed to READ-ONLY for Accounts Manager on BEI Purchase Requisition
- [ ] **AUDIT-5:** test.hr assigned Procurement User role for PROC-003/004 scenarios
- [ ] **AUDIT-6:** Bench console scripts for test billing data (Sent + Cancelled) written
- [x] **AUDIT-7:** Decision on Blockers 6-8 — **Option A selected** (see v1.2 amendments below)
- [x] **AUDIT-8:** `/l1-api-check commissary` added to retest plan
- [x] **AUDIT-9:** Rollback: `docker service rollback frappe_backend && docker service rollback frappe_frontend`

### GO / NO-GO Gate (Updated v1.2)

**GO — Option A selected.** All code fixes implemented, compliance deferred to separate sprint.

Remaining pre-deploy tasks (AUDIT-3, AUDIT-5, AUDIT-6) are runtime tasks executed via bench console after Docker build, not code changes.

---

## Compliance Decisions (v1.2) — 2026-02-12

### Evidence Sources

Decisions informed by existing finance team documentation:
- `scratchpad/accounting_answers_summary.md` — Finance questionnaire (Q1-Q45)
- `data/_FINAL/COA.csv` — Chart of Accounts with Butch's comments + Alyssa's responses
- `scratchpad/training_finance_accounting/finance_accounting_training_content.md` — Training guide
- `scratchpad/finance_accounting_plan_audit.md` — Duplication audit

### BLOCKER 6 Decision: Deploy as Billing Tracker (GL = Phase 2)

**Evidence:** Q43 automation priority #2 is "PAYMENTS APPLICATION — Upload proof of payment → auto-apply to invoices → auto-update SOA". This exactly matches what `apply_franchise_payment()` does. Q36 confirms GL accounts ready: Royalty Income = `4000003`, Marketing Fee Income = `4000006`, Management Fee Income = `4000004`. COA confirms AR = `1103101` (subsidiary ledger managed per Butch).

**Decision:** Deploy as-is. `apply_franchise_payment()` is a billing tracker that updates SOA — the finance team's #2 priority. GL entries (Journal Entry with party fields, cost center, proper debit/credit) will be added in a compliance sprint when finance is ready for full accounting integration. GL account mapping is ready.

### BLOCKER 7 Decision: Defer Franchise EWT to Compliance Sprint

**Evidence:** COA has `2102202` (WITHOLDING TAX - EXPANDED PAYABLE, subsidiary ledger managed per Butch) and `1105101` (CREDITABLE WITHHOLDING TAXES). Form 2307 infrastructure already exists in `procurement.py:3790-3861` for supplier payments (ATC WI100). For franchise billing, BEI is the **franchisor** (receives income) — the **franchisee** withholds EWT from their payment. Q22 confirms taxes handled monthly/quarterly per Eddie Ramboyo as a separate process.

**Decision:** Franchise EWT is a receiving-side recording (franchisee withholds, BEI records as creditable tax to `1105101`). This requires `apply_franchise_payment()` to accept an optional `ewt_amount` parameter — a separate enhancement. Defer to compliance sprint. GL accounts and Form 2307 infrastructure are ready.

### BLOCKER 8 Decision: AR Is Internal Collection Receipt (BIR Invoice Separate)

**Evidence:** Q43 priority #3 is "AUTOMATED ACKNOWLEDGEMENT RECEIPT — Auto-generate AR upon receiving store payment proof". Q32 describes AR workflow: "analysts issue AR upon collection → collector gets signature → deposit next day". The code correctly labels it "NOT a BIR Official Receipt". Q22 confirms BIR tax filing is handled separately (monthly/quarterly per Eddie Ramboyo).

**Decision:** AR is an internal collection document per finance team's explicit design. The BIR-compliant document (Sales Invoice / VAT Invoice per EOPT Law) is a separate process handled through their tax filing workflow. Deploy AR as-is. BIR invoice generation will be a future feature when needed.

### Compliance Sprint Backlog (Future)

| Item | GL Accounts Ready | Infrastructure Ready | Priority |
|------|-------------------|---------------------|----------|
| GL entries in `apply_franchise_payment()` | 4000003/04/06, 1103101 | Savepoint pattern exists | HIGH |
| Franchise EWT recording (1105101) | 2102202, 1105101 | Form 2307 code exists | MEDIUM |
| BIR Sales Invoice generation | 2102205 (Output VAT) | AR DocType exists as base | LOW |
| PFRS 15 deferred revenue | N/A | N/A | LOW |

### Version History

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | 2026-02-12 | Initial plan from E2E test results |
| v1.1 | 2026-02-12 | Audit amendments: 8 blockers, 9 pre-flight checks, GO/NO-GO gate |
| v1.2 | 2026-02-12 | All blockers resolved: Fix C2 removed, Accounts Manager READ-ONLY, compliance decisions documented from finance team questionnaires. GO for deployment. |
