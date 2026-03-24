---
canonical_sprint_id: S116
display: Sprint 116
status: GO
branch: s116-procurement-defect-fixes
lane: single
created_date: 2026-03-24
completed_date:
deployed_at:
backend_pr:
frontend_pr:
l3_result:
execution_summary:
depends_on: S108
---

# S116 — Fix ALL Procurement Defects + Unblock Payment Request

**Goal:** Fix every defect found in S109 comprehensive L3 testing, seed the data needed to test Payment Request end-to-end, and retest ALL forms until zero defects remain. The agent must do whatever it takes — create invoices, approve them, verify them — to make Payment Request testable.

**Origin:** S109 L3 (2026-03-24) found 6 defects across procurement. Full evidence in `output/l3/S109/DEFECTS.md` and `output/l3/S109/results.json`.

**Deadline:** Must be deployed tonight (2026-03-24). Luwi trains tomorrow.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists
S109 tested all procurement forms and found 6 defects. 5 forms passed, 1 was blocked (Payment Request — no verified invoices exist). The defects range from a redirect to `/undefined` (DEFECT-1) to RBAC dialog issues (DEFECT-2) to data formatting bugs (DEFECT-3). All must be fixed before Luwi's training tomorrow.

### Defect Root Causes (researched from source)

| # | Defect | Root Cause | File | Fix |
|---|--------|-----------|------|-----|
| D1 | Invoice redirect to `/invoices/undefined` | `result.name` is undefined — response structure mismatch | `bei-tasks/app/dashboard/procurement/invoices/new/page.tsx:249` | Null-check `result.name`, fall back to `result.data?.name` |
| D2 | PO approval dialog stays open on error | `setApprovalDialogOpen(false)` only called in success path | `bei-tasks/app/dashboard/procurement/purchase-orders/[id]/page.tsx:377-379` | Add `setApprovalDialogOpen(false)` in catch block |
| D3 | Supplier "Total Orders" shows PNaN | `supplier.total_orders` is undefined, no null coalesce | `bei-tasks/app/dashboard/procurement/suppliers/[id]/page.tsx:229` | Add `?? 0` or `?? 'P0.00'` |
| D4 | Payments page 500 on load | **AUDIT: Original diagnosis WRONG.** SQL alias `gr.gr_no` IS correct (field confirmed in DocType). Real cause unknown — must reproduce via curl and read traceback. S112 may have already fixed this. | `hrms/api/procurement.py:~2041` | Verify if S112 fixed it. If not, reproduce 500, read traceback, fix actual cause. |
| D5 | Payment Request blocked — no verified invoices | Data dependency — need full chain PR→PO→GR→Invoice→Verify | Multiple | Seed data via API calls |
| D6 | GR no warning on over-delivery | NOT A DEFECT — over-delivery protection EXISTS at `procurement.py:1539-1566` with 5% tolerance. Test script used qty within tolerance. | N/A | Close as working-as-designed |

### Key trade-offs
- **D5 seed data:** Must create the FULL procurement chain via API to get a verified invoice. Steps: find existing approved PO with GR, or create new PO → approve → create GR → create invoice → verify invoice. Only then can Payment Request be tested.
- **D6 closed:** Over-delivery protection exists and works. The S109 test used qty=100 which was within tolerance. Not a bug.

### Known limitations
- Python Playwright is broken. Use Node.js Playwright.
- sam@bebang.ph triggers Google OAuth in headless mode. For PO approval testing, use `test.hr@bebang.ph` and expect the RBAC rejection — or call the approve API directly with a session that has CPO role.

---

## Scope

### Phase A: Frontend Fixes — 4 defects in bei-tasks (5 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| A1 | FIX | `invoices/new/page.tsx` | **D1 fix:** In the onSubmit success handler (~line 249), change `result.name` to `result.name \|\| result.data?.name \|\| 'unknown'`. Add null check before redirect. If name is still undefined, show toast with "Invoice created" and redirect to invoice list instead. | 1 |
| A2 | FIX | `purchase-orders/[id]/page.tsx` | **D2 fix:** In the `handleApprove` catch block (~line 377-379), add `setApprovalDialogOpen(false)` and `setComment('')` so the dialog closes on RBAC error. | 1 |
| A3 | FIX | `suppliers/[id]/page.tsx` | **D3 fix:** At ~line 229 where `supplier.total_orders` renders, add null coalesce: `formatCurrency(supplier.total_orders ?? 0)` or wrap in a safe formatter. Check all other stat cards on the same page for similar `PNaN`/`undefined` issues. | 1 |
| A4 | VERIFY | Terminal | Run `npx tsc --noEmit` — zero TS errors on modified files. **HARD BLOCKER.** | 1 |
| A5 | BUILD | Terminal | Commit all frontend fixes to `s116-procurement-defect-fixes` branch and push. | 1 |

### Phase B: Backend Fix — Payments 500 (3 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| B1 | FIX | `hrms/api/procurement.py` | **D4 fix:** Debug the Payments page 500 error. **AUDIT WARNING (2026-03-24):** The original diagnosis (`gr.gr_no` should be `gr.gr_number`) was WRONG — code verification confirmed the field IS `gr_no` in the DocType and the SQL alias is correct. The real 500 cause is elsewhere. Steps: (1) First verify by checking the BEI Goods Receipt DocType JSON to confirm `gr_no` is the correct field. (2) If SQL is correct, reproduce the 500 by calling `get_payment_requests` directly via curl and reading the full traceback. (3) Check if S112 already fixed this — if so, verify the fix on live and close. (4) If unfixed, debug the actual traceback, fix, add Sentry instrumentation (DM-7). | 2 |
| B2 | BUILD | Terminal | Commit backend fix to branch and push. | 1 |

### Phase C: Seed Data — Create Verified Invoice for Payment Test (6 units)

**Purpose:** Create the full procurement chain so a "Verified" invoice exists, unblocking Payment Request testing.

| Task | Type | Description | Units |
|------|------|-------------|-------|
| C1 | BUILD | Login to hq.bebang.ph as test.hr@bebang.ph. Find an existing approved PO that has a matching GR. If none exists, create: (1) PO via API, (2) Approve PO via API (may need Mae's session or system-level call), (3) GR via API against that PO. Record all created records in `output/l3/S116/seed_data.json`. | 3 |
| C2 | BUILD | Create an invoice against the PO+GR pair from C1. Then call `verify_invoice_match` API to move the invoice to "Verified" status. If verification fails (3-way match issue), debug and fix. The invoice MUST reach "Verified" status. Record in seed_data.json. | 2 |
| C3 | VERIFY | Confirm the verified invoice appears in the Payment Request form's invoice dropdown. If it doesn't, debug the frontend query that populates the dropdown. | 1 |

### Phase D: Deploy + Full L3 Retest (8 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| D1 | BUILD | Create PRs for both repos. Merge (governor or `gh api .../merge`). Trigger deploy workflow for hrms (ID: 226200303). Wait for completion. | 2 |
| D2 | VERIFY | **L3 Retest — ALL 6 forms must be submitted with POST captured:** | |
| | | (1) PR creation as luwi@bebang.ph → PASS | |
| | | (2) PO creation as test.hr@bebang.ph → PASS | |
| | | (3) GR creation as test.hr@bebang.ph → PASS | |
| | | (4) Invoice creation → redirect goes to correct URL (not /undefined) → PASS | |
| | | (5) **Payment Request creation** → select verified invoice → submit → PASS | |
| | | (6) Supplier creation → PASS | 4 |
| D3 | VERIFY | Verify D1-D3 defects fixed: (1) Invoice redirect works, (2) PO approval dialog closes on error, (3) Supplier Total Orders shows number not PNaN, (4) Payments page loads without 500. | 1 |
| D4 | BUILD | Closeout: update plan YAML status to COMPLETED, update SPRINT_REGISTRY.md, `git add -f docs/plans/ output/l3/S116/` and push to production. | 1 |

**Total: 22 units.**

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| luwi@bebang.ph | Create PR: dept=Commissary, item=Sago, qty=3, UOM=Kg, rate=84, purpose="S116 retest" | PR created, success toast, redirect to PR detail | S107/S108 regression |
| test.hr@bebang.ph | Create PO: supplier=first available, item=FG009, qty=1, rate=100 | PO created, redirect to PO detail | PO form broken |
| test.hr@bebang.ph | Create GR: select PO, receipt date >= PO date, DN="DN-S116" | GR created, redirect to GR detail | GR form broken |
| test.hr@bebang.ph | Create Invoice: select PO, invoice_no="INV-S116-TEST", dates filled | Invoice created, **redirect to /invoices/INV-XXXX** (NOT /undefined) | D1 not fixed |
| test.hr@bebang.ph | Create Payment Request: select verified invoice from dropdown, amount, mode=Bank Transfer | Payment request created (POST 200) | D5 seed data missing or D4 payments 500 |
| test.hr@bebang.ph | Create Supplier: name="TEST-S116", code auto-gen or manual | Supplier created | Supplier form broken |
| test.hr@bebang.ph | Open PO detail → click Approve → error dialog → dialog closes | Dialog closes after error, page interactive | D2 not fixed |
| test.hr@bebang.ph | Open Supplier detail | Total Orders shows "P0.00" or real amount, NOT "PNaN" | D3 not fixed |
| test.hr@bebang.ph | Open Payments page | No 500 console error, page loads with data | D4 not fixed |

Evidence files required before closeout:
```
output/l3/S116/form_submissions.json  (>= 6 entries — one per form)
output/l3/S116/api_mutations.json     (>= 6 POST captures)
output/l3/S116/state_verification.json
output/l3/S116/seed_data.json         (verified invoice chain)
output/l3/S116/DEFECT_REGISTER.csv    (all 6 defects with status FIXED or CLOSED)
```

---

## Requirements Regression Checklist

- [ ] Does invoice creation redirect to the correct detail URL (not /undefined)?
- [ ] Does PO approval error dialog close after RBAC rejection?
- [ ] Does Supplier detail "Total Orders" show a number (not PNaN)?
- [ ] Does Payments page load without 500 error?
- [ ] Does a verified invoice exist in the system for Payment Request testing?
- [ ] Does Payment Request creation succeed with the verified invoice?
- [ ] Is D6 (GR over-delivery) confirmed working-as-designed and closed?
- [ ] Does `npx tsc --noEmit` pass with zero errors?
- [ ] Does every new/modified @frappe.whitelist() endpoint have Sentry instrumentation?
- [ ] Does PR creation still work (S107/S108 regression)?
- [ ] Does item_code onBlur still auto-fill price (S107 regression)?

---

## Remote-Truth Baseline

| Repo | Branch | HEAD SHA |
|------|--------|---------|
| hrms | production | `6b5a94214` |
| bei-tasks | main | `19ee69a` |

---

## Autonomous Execution Contract

- **completion_condition:**
  - All 6 defects resolved (5 FIXED + 1 CLOSED as working-as-designed)
  - All 6 procurement forms submit successfully on live (POST captured, 2xx response)
  - Payment Request specifically creates with a real verified invoice
  - DEFECT_REGISTER.csv shows zero open defects
  - Evidence files exist with matching entry counts
  - Plan YAML status = COMPLETED, pushed to production
  - SPRINT_REGISTRY.md updated

- **stop_only_for:**
  - Missing credentials/access
  - Cannot approve PO or verify invoice via any available method (RBAC wall with no workaround)

- **continue_without_pause_through:**
  - code → seed data → deploy → L3 retest → closeout

- **blocker_policy:**
  - programmatic → fix and continue
  - TS type error → fix before pushing
  - Invoice won't verify → debug 3-way match logic, create matching GR if needed
  - PO won't approve → try API-level approval with admin/system user
  - business-data → pause

- **signoff_authority:** single-owner (Sam Karazi, CEO)

---

## Agent Boot Sequence

1. Read this plan fully — including the defect root causes table and L3 scenarios.
2. **Create sprint branches:**
   - hrms: `git fetch origin production && git checkout -b s116-procurement-defect-fixes origin/production`
   - bei-tasks: `cd ../bei-tasks && git fetch origin main && git checkout -b s116-procurement-defect-fixes origin/main`
3. Read `output/l3/S109/DEFECTS.md` — the defect descriptions.
4. Read `bei-tasks/app/dashboard/procurement/invoices/new/page.tsx` — D1 fix target.
5. Read `bei-tasks/app/dashboard/procurement/purchase-orders/[id]/page.tsx` — D2 fix target.
6. Read `bei-tasks/app/dashboard/procurement/suppliers/[id]/page.tsx` — D3 fix target.
7. Read `hrms/api/procurement.py` around line 2041 — D4 fix target.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.
Do whatever it takes to get all 6 forms passing — create test data, approve POs, verify invoices.

## Execution Workflow
- Test Python changes: `/local-frappe`
- Deploy backend: create hrms PR → merge → trigger deploy workflow (ID: 226200303)
- Deploy frontend: push bei-tasks → merge to main → Vercel auto-deploys
- E2E testing: Node.js Playwright (`node script.cjs`). Python Playwright is broken.
