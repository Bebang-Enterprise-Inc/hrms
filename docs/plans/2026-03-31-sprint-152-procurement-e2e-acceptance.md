# Sprint S152 — Full Procurement E2E Browser Acceptance Testing

```yaml
sprint: S152
branch: s152-procurement-e2e-acceptance
status: GO
plan_file: docs/plans/2026-03-31-sprint-152-procurement-e2e-acceptance.md
depends_on: S147, S141, S144
registry_row: "| S152 | Sprint 152 | s152-procurement-e2e-acceptance | — | GO — Full procurement E2E browser acceptance testing |"
completed_date:
execution_summary:
```

---

## Why This Exists

The procurement module has been built across 20+ sprints but has NEVER had a full end-to-end browser acceptance test covering the complete workflow: **PR → PO → GR → Invoice → Payment Request (RFP) → 4-Level Approval → OR**. Individual sprints tested their own features but nobody has verified the full chain works as a real user would experience it — clicking through every form, creating real documents, converting between stages, approving at every level, and verifying data flows correctly across all dashboard views.

This sprint is a **testing and UI/UX audit sprint** — NOT a feature sprint. It creates test data via `/frappe-bulk-edits`, executes full browser E2E acceptance tests via `/playwright-bei-erp` and `/l3-v2-bei-erp`, audits every page for UI/UX issues, and fixes any defects found.

---

## Design Rationale (For Cold-Start Agents)

### Why full-chain browser testing now
- Finance team starts using AP Command Center (S147) daily — broken flows will be discovered by real users
- Individual sprint L3 tests only cover isolated features — nobody verified the chain connects
- The 4-level RFP approval has never been tested E2E in the browser with real form submissions
- OR upload flow has never been browser-tested

### Why three separate workflow chains
- **Chain A (≤P500K):** Tests the simplest PO path (Mae-only) and 3-level RFP (Reviewer→Budget→CFO) — most common scenario
- **Chain B (>P500K, <P1M):** Tests dual PO approval (Mae + Butch) — important for large orders
- **Chain C (>P1M):** Tests CEO approval on BOTH PO (new vendor) AND RFP (>P1M threshold) — highest-risk path, uses `sam@bebang.ph` (password: `2289454`)

### Approval thresholds (from code)
| Threshold | PO Approval Path | RFP Approval Path |
|-----------|-----------------|-------------------|
| **≤P500K** | Mae only → Approved | Reviewer → Budget → CFO → Approved |
| **>P500K** | Mae → Butch → Approved | Reviewer → Budget → CFO → Approved |
| **New Vendor (any amount)** | Mae → Butch → CEO → Approved | — |
| **>P1M** | Same as amount tier | Reviewer → Budget → CFO → **CEO** → Approved |
| **New Supplier (any amount)** | — | Reviewer → Budget → CFO → **CEO** → Approved |

### CRITICAL: PO approvals use EXACT EMAIL MATCH (not roles)
PO approval functions in `bei_purchase_order.py:318-365` check `frappe.session.user != cpo_email` — there is NO System Manager bypass, NO role-based fallback. The ONLY user who can approve is the one configured in BEI Settings:

```python
# bei_purchase_order.py:325-327
cpo_email = settings.get("cpo_approver_email")  # = mae@bebang.ph
if cpo_email and frappe.session.user != cpo_email:
    frappe.throw("Only mae@bebang.ph can approve as CPO")
```

### CRITICAL: RFP approvals use ROLE-BASED checks (different from PO!)
Payment Request approval in `bei_payment_request.py:216-225` uses `_check_role()`:
- L1 Review: `["Accounts User", "Accounts Manager", "System Manager"]`
- L2 Budget: `["Accounts Manager", "System Manager"]`
- L3 CFO: `["Accounts Manager", "System Manager"]`
- L4 CEO: `["Accounts Manager", "System Manager"]`

Any user with the right role can approve. `sam@bebang.ph` (System Manager) can approve ALL 4 levels.

### Source references
- PO Mae check: `bei_purchase_order.py:325` — `if cpo_email and frappe.session.user != cpo_email`
- PO Butch check: `bei_purchase_order.py:364` — same pattern with `cfo_approver_email`
- PO CEO check: `bei_purchase_order.py` — same pattern with `ceo_approver_email`
- BEI Settings seed: `s099_seed_procurement_settings.py:34-36` — mae/butch/sam emails
- RFP role check: `bei_payment_request.py:216-225` — `_check_role(allowed_roles)`
- PO dual threshold: `procurement.py:1174` — `500000`
- RFP CEO trigger: `procurement.py:2925` — ">1M or new supplier"
- DocType fields: `hrms/hr/doctype/bei_purchase_requisition/`, `bei_purchase_order/`, `bei_goods_receipt/`, `bei_invoice/`, `bei_payment_request/`
- API endpoints: `hrms/api/procurement.py` (7334+ lines, 132 endpoints)
- Frontend routes: `bei-tasks/app/dashboard/procurement/` and `bei-tasks/app/dashboard/accounting/`
- Test accounts: `memory/testing-accounts.md`

---

## Complete Page Inventory (Certified Universe)

### Procurement Module Pages (20 pages)

| # | Route | Page Type | Has Form? | Covered In |
|---|-------|-----------|-----------|------------|
| P1 | `/dashboard/procurement` | Dashboard (KPIs, charts) | No | Phase 4.1 |
| P2 | `/dashboard/procurement/purchase-requisitions` | List + approval actions | Dialog | Phase 1 |
| P3 | `/dashboard/procurement/purchase-requisitions/new` | **Create PR form** | **Full form** | Phase 1.1 |
| P4 | `/dashboard/procurement/purchase-requisitions/[id]` | Detail + approve/reject/convert | Dialog | Phase 1.2 |
| P5 | `/dashboard/procurement/purchase-orders` | List + filters + batch approve | Dialog | Phase 4.2 |
| P6 | `/dashboard/procurement/purchase-orders/new` | **Create PO form** | **Full form** | Phase 1.3 |
| P7 | `/dashboard/procurement/purchase-orders/[id]` | Detail + approve/price edit/GR/Invoice links | Dialog + inline | Phase 1.4, 2.1 |
| P8 | `/dashboard/procurement/goods-receipts` | List + inspection | Dialog | Phase 4.3 |
| P9 | `/dashboard/procurement/goods-receipts/new` | **Create GR form** | **Full form** | Phase 2.2 |
| P10 | `/dashboard/procurement/goods-receipts/[id]` | Detail + inspection workflow | Dialog | Phase 2.3 |
| P11 | `/dashboard/procurement/invoices` | List + variance + payment status | Dialog | Phase 4.4 |
| P12 | `/dashboard/procurement/invoices/new` | **Create Invoice form** | **Full form** | Phase 2.4 |
| P13 | `/dashboard/procurement/invoices/[id]` | Detail + 3-way match + variance approval | Dialog | Phase 2.5 |
| P14 | `/dashboard/procurement/payments` | List + 4-level approval | Dialog | Phase 4.5 |
| P15 | `/dashboard/procurement/payments/new` | **Create Payment Request form** | **Full form** | Phase 3.1 |
| P16 | `/dashboard/procurement/payments/[id]` | Detail + approval per level + OR upload | Dialog | Phase 3.2-3.6 |
| P17 | `/dashboard/procurement/suppliers` | List + search + status | — | Phase 4.6 |
| P18 | `/dashboard/procurement/suppliers/new` | **Create Supplier form** | **Full form** | Phase 0.3 |
| P19 | `/dashboard/procurement/suppliers/[id]` | Detail + edit + documents + POs/Invoices tabs | Dialog | Phase 4.6 |
| P20 | `/dashboard/procurement/approvals` | Hub → PO queue + Payment queue | — | Phase 4.7 |

### Procurement Support Pages (8 pages)

| # | Route | Page Type | Covered In |
|---|-------|-----------|------------|
| P21 | `/dashboard/procurement/or-follow-up` | OR aging + follow-up send | Phase 4.8 |
| P22 | `/dashboard/procurement/settings` | Config | Phase 5 (audit only) |
| P23 | `/dashboard/procurement/audit/aging` | AP aging analysis | Phase 5 (audit only) |
| P24 | `/dashboard/procurement/audit/price-history` | Price tracking | Phase 5 (audit only) |
| P25 | `/dashboard/procurement/reports` | Report hub | Phase 5 (audit only) |
| P26 | `/dashboard/procurement/reports/monthly-spend` | Report | Phase 5 (audit only) |
| P27 | `/dashboard/procurement/reports/supplier-performance` | Report | Phase 5 (audit only) |
| P28 | `/dashboard/procurement/reports/three-way-match` | Report | Phase 5 (audit only) |

### Accounting Module Pages (10 pages)

| # | Route | Page Type | Covered In |
|---|-------|-----------|------------|
| A1 | `/dashboard/accounting/ap-command-center` (Overview) | KPI dashboard | Phase 5.1 |
| A2 | `/dashboard/accounting/ap-command-center` (Invoices) | Invoice list + bulk + CSV | Phase 5.2 |
| A3 | `/dashboard/accounting/ap-command-center` (Payments) | Payment list + approval icons | Phase 5.3 |
| A4 | `/dashboard/accounting/ap-command-center` (Aging) | Aging matrix pivot | Phase 5.4 |
| A5 | `/dashboard/accounting/ap-command-center` (Supplier Ledger) | Timeline + search | Phase 5.5 |
| A6 | `/dashboard/accounting/awaiting-or` | OR tracking + upload + follow-up | Phase 5.6 |
| A7 | `/dashboard/accounting/exceptions` | Variance approval | Phase 5.7 |
| A8 | `/dashboard/accounting/outstanding-advances` | Advance tracking | Phase 5 (audit only) |
| A9 | `/dashboard/accounting/pending-payments` | CFO payment queue | Phase 5 (audit only) |
| A10 | `/dashboard/accounting/soa` | Statement of Account | Phase 5 (audit only) |

**Total certified universe: 38 pages** (20 procurement core + 8 procurement support + 10 accounting)

---

## Credential Matrix (CRITICAL — Read Before Executing)

### PO Approval Credentials (EMAIL-MATCHED, no role bypass)

| Action | Required User | Email | Password | Source |
|--------|--------------|-------|----------|--------|
| Mae PO Approval (all POs) | Mae Karazi (CPO) | `mae@bebang.ph` | `BeiTest2026!` | `BEI Settings.cpo_approver_email` |
| Butch PO Approval (>P500K) | Alessandro Rey Formoso (CFO) | `butch@bebang.ph` | `BeiTest2026!` | `BEI Settings.cfo_approver_email` |
| CEO PO Approval (new vendor) | Sam Karazi (CEO) | `sam@bebang.ph` | `2289454` | `BEI Settings.ceo_approver_email` |

**If mae or butch login fails:** Reset password via `/frappe-bulk-edits`: `bench --site bei.localhost set-password mae@bebang.ph BeiTest2026!`

### RFP Approval Credentials (ROLE-BASED)

| Action | Required Role | Test User | Email | Password |
|--------|-------------|-----------|-------|----------|
| L1 Review | Accounts User OR Accounts Manager OR System Manager | Finance test account | `test.finance@bebang.ph` | `BeiTest2026!` |
| L2 Budget | Accounts Manager OR System Manager | Finance test account | `test.finance@bebang.ph` | `BeiTest2026!` |
| L3 CFO | Accounts Manager OR System Manager | Sam (System Manager) | `sam@bebang.ph` | `2289454` |
| L4 CEO | Accounts Manager OR System Manager | Sam (System Manager) | `sam@bebang.ph` | `2289454` |

**PRE-REQUISITE CHECK:** Verify `test.finance@bebang.ph` has the `Accounts Manager` role in Frappe. If not, the agent MUST add it via `/frappe-bulk-edits` before proceeding.

### Other Operation Credentials

| Action | Test User | Email | Password | Role Needed |
|--------|-----------|-------|----------|-------------|
| PR Creation | Finance | `test.finance@bebang.ph` | `BeiTest2026!` | Any (no role check) |
| PR Approval | System Manager | `sam@bebang.ph` | `2289454` | Any (no role check in code) |
| PO Creation | Finance | `test.finance@bebang.ph` | `BeiTest2026!` | Any (no role check) |
| GR Creation | Warehouse | `test.warehouse@bebang.ph` | `BeiTest2026!` | Any (no role check) |
| GR Validation | Ian (hardcoded) | `ian@bebang.ph` | `BeiTest2026!` (reset if needed via `/frappe-bulk-edits`) | Hardcoded email in code |
| Invoice Creation | Finance | `test.finance@bebang.ph` | `BeiTest2026!` | Any (no role check) |
| Invoice Duplicate Override | Procurement Mgr | Needs `Procurement Manager` role | — | `Procurement Manager` or `System Manager` |
| OR Upload | Finance | `test.finance@bebang.ph` | `BeiTest2026!` | Any (no role check) |
| Supplier Exception | Finance | `test.finance@bebang.ph` | `BeiTest2026!` | `Procurement Manager` or `Accounts Manager` or `System Manager` |

### Frontend Visibility Credentials

| Page/Button | Visible To Roles | Best Test User |
|-------------|-----------------|----------------|
| Procurement pages | Procurement User, Procurement Manager, HQ User, Warehouse User, System Manager | `test.finance` or `sam` |
| Accounting pages | Accounts Manager, HQ Finance, HQ User, System Manager | `test.finance` or `sam` |
| Mae "Approve" button on PO | **Only if logged-in email = mae@bebang.ph** | `mae@bebang.ph` |
| Butch "Approve" button on PO | **Only if logged-in email = butch@bebang.ph** | `butch@bebang.ph` |
| CEO "Approve" button on PO | **Only if logged-in email = sam@bebang.ph** | `sam@bebang.ph` |
| RFP approval buttons | Users with Accounts User/Manager/System Manager role | `test.finance` or `sam` |

### Complete User Matrix for All 40 L3 Scenarios

| Scenario | User | Why This User |
|----------|------|---------------|
| L3-01 to L3-03 (PR create/submit/approve) | `test.finance`, then `sam` | Any user creates; sam approves |
| L3-04 (PR→PO convert) | `test.finance` | Any user creates PO |
| **L3-05 (Mae PO approve ≤500K)** | **`mae@bebang.ph`** | **EMAIL MATCH REQUIRED** |
| L3-06 (Send to supplier) | `test.finance` or `mae` | Any user |
| L3-07 (GR create) | `test.warehouse` | Warehouse operation |
| L3-08 (Invoice create) | `test.finance` | Finance operation |
| L3-09-L3-11 (RFP L1-L2) | `test.finance` | Accounts Manager role |
| **L3-12 (RFP L3 CFO)** | **`sam@bebang.ph`** | System Manager role |
| L3-13 (OR upload) | `test.finance` | Any user |
| **L3-14 (PO >500K create)** | `test.finance` | Any user creates |
| **L3-15 (Mae approve >500K PO)** | **`mae@bebang.ph`** | **EMAIL MATCH REQUIRED** |
| **L3-16 (Butch approve >500K PO)** | **`butch@bebang.ph`** | **EMAIL MATCH REQUIRED** |
| L3-17 (Chain B GR→Invoice→RFP→OR) | Various | Same as Chain A |
| **L3-18 (PO new vendor >1M)** | `test.finance` | Any user creates |
| **L3-19 (Mae approve new vendor PO)** | **`mae@bebang.ph`** | **EMAIL MATCH REQUIRED** |
| **L3-20 (Butch approve new vendor PO)** | **`butch@bebang.ph`** | **EMAIL MATCH REQUIRED** |
| **L3-21 (CEO approve new vendor PO)** | **`sam@bebang.ph`** | **EMAIL MATCH REQUIRED** |
| L3-22-L3-23 (Chain C GR+Invoice) | `test.warehouse`, `test.finance` | Standard users |
| L3-24 (RFP >1M create) | `test.finance` | Any user |
| L3-25-L3-26 (RFP L1-L2) | `test.finance` | Accounts Manager role |
| **L3-27 (RFP L3 CFO for >1M)** | **`sam@bebang.ph`** | System Manager role |
| **L3-28 (RFP L4 CEO for >1M)** | **`sam@bebang.ph`** | System Manager role |
| **L3-29 (PO rejection by Mae)** | **`mae@bebang.ph`** | **EMAIL MATCH — Mae rejects** |
| L3-30 (RFP rejection at L2) | `test.finance` | Accounts Manager role |
| L3-31 (Partial GR) | `test.warehouse` | Warehouse operation |
| L3-32-L3-33 (Invoice variance) | `test.finance` | Finance operation |
| L3-34-L3-40 (Dashboard checks) | `test.finance` | Accounts Manager role |

**Summary of required credentials:**
- `mae@bebang.ph` — used in **6 scenarios** (L3-05, L3-15, L3-19, L3-29 + frontend button visibility)
- `butch@bebang.ph` — used in **2 scenarios** (L3-16, L3-20)
- `sam@bebang.ph` / `2289454` — used in **6 scenarios** (L3-03, L3-12, L3-21, L3-27, L3-28 + CEO PO)
- `test.finance@bebang.ph` / `BeiTest2026!` — used in **~25 scenarios** (creation, RFP L1/L2, dashboards)
- `test.warehouse@bebang.ph` / `BeiTest2026!` — used in **3 scenarios** (GR creation)

---

## Phase Budget

| Phase | Units | Description |
|-------|-------|-------------|
| Phase 0: Test Data Setup | 6 | Verify/create test items, suppliers, prices via `/frappe-bulk-edits` |
| Phase 1: Chain A — PR → PO (≤P500K, Mae-only) | 10 | Full form submissions: PR/new, PR approve, PO/new, PO Mae approve |
| Phase 2: Chain A — GR → Invoice | 8 | GR/new, GR inspect, Invoice/new, 3-way match verify |
| Phase 3: Chain A — RFP 3-Level → OR | 10 | Payment/new, Reviewer→Budget→CFO approve, OR upload |
| Phase 4: Chain B — PO Dual Approval (>P500K) | 6 | PO >P500K, Mae→Butch dual path |
| Phase 5: Chain C — CEO Approval (>P1M + new vendor) | 10 | PO CEO path (new vendor), RFP >P1M CEO path (sam@bebang.ph) |
| Phase 6: Rejection & Edge Cases | 6 | PO rejection, RFP rejection, partial GR, invoice variance |
| Phase 7: Dashboard Validation — Procurement Pages | 10 | All 20 procurement pages verified |
| Phase 8: Dashboard Validation — AP Command Center + Accounting | 8 | All 5 AP tabs + accounting pages |
| Phase 9: UI/UX Audit & Defect Remediation | 10 | Cross-page audit, defect fix, re-verify |
| Phase 10: Closeout & Evidence | 4 | L3 evidence, plan update, registry update |
| **TOTAL** | **88** | |

### Scope Size Warning

Total units (88) exceed the 80-unit ceiling. However, this is a **testing-only sprint** (no feature development) and the work is highly parallelizable across agents. Splitting would break the E2E chain validation. Recommend executing as-is with `/teammates` parallelism in Phases 7-8.

---

## Execution Skills Reference

| Skill | When to Use |
|-------|-------------|
| `/frappe-bulk-edits` | Phase 0: Create test items, suppliers, contracted prices in Frappe |
| `/playwright-bei-erp` | Phases 1-9: Browser automation for form submissions and navigation |
| `/l3-v2-bei-erp` | Phases 1-9: L3 scenario execution with evidence capture |
| `/teammates` | Phases 7-8: Spawn parallel agents for independent page verification |
| `/deploy-frappe` | Phase 9: Deploy backend fixes if defects found |

---

## Agent Boot Sequence

1. Read this plan fully — especially the **Credential Matrix** section.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s152-procurement-e2e-acceptance origin/production`. NEVER write code on production.
3. Read `docs/plans/SPRINT_REGISTRY.md` for cross-sprint context.
4. Read `memory/testing-accounts.md` for test credentials.
5. Read `memory/e2e-testing.md` for Playwright patterns and lessons.
6. Verify deployment: smoke-check `https://my.bebang.ph/dashboard/procurement/purchase-orders` returns 200.
7. **CREDENTIAL GATE (MUST PASS BEFORE PHASE 1):**
   a. **Verify mae@bebang.ph login works** — navigate to `https://my.bebang.ph/login`, enter `mae@bebang.ph` + password, verify login succeeds. If password unknown → STOP, ask Sam.
   b. **Verify butch@bebang.ph login works** — same process. If password unknown → STOP, ask Sam.
   c. **Verify sam@bebang.ph / 2289454 login works** — must succeed.
   d. **Verify test.finance@bebang.ph has Accounts Manager role** — login as sam, check via API: `GET /api/resource/User/test.finance@bebang.ph` → verify `roles` array includes `Accounts Manager`. If missing → add via `/frappe-bulk-edits`.
   e. **Verify test.warehouse@bebang.ph login works** — must succeed.
   f. **Verify BEI Settings approver emails** — check via API: `GET /api/resource/BEI Settings` → confirm `cpo_approver_email=mae@bebang.ph`, `cfo_approver_email=butch@bebang.ph`, `ceo_approver_email=sam@bebang.ph`.
8. Begin Phase 0.

---

## Phase 0: Test Data Setup (6 units) — `/frappe-bulk-edits`

### 0.1: Verify existing test data — 2 units [VERIFY]

Check what already exists via API:
- Active items with contracted prices (need ≥5)
- Active suppliers (need ≥3, including at least 1 "new" supplier for CEO trigger)
- Warehouses for GR receiving
- Test user roles correct for approval chain

### 0.2: Create test items if needed — 2 units [BUILD]

Use `/frappe-bulk-edits` to ensure at least 5 items exist with contracted prices:

| Item Code | Item Name | UOM | Price (PHP) | Purpose |
|-----------|-----------|-----|-------------|---------|
| TEST-ITEM-001 | Test Sugar 50kg | Bag | 2,500.00 | Chain A (low value) |
| TEST-ITEM-002 | Test Condensed Milk | Case | 1,800.00 | Chain A |
| TEST-ITEM-003 | Test Plastic Cup 16oz | Pack | 350.00 | Chain A |
| TEST-ITEM-004 | Test Equipment Set | Set | 180,000.00 | Chain B (>P500K when qty=3) |
| TEST-ITEM-005 | Test Industrial Freezer | Unit | 350,000.00 | Chain C (>P1M when qty=3) |

### 0.3: Create test supplier (new vendor) — 2 units [BUILD]

Use `/frappe-bulk-edits` OR the **Supplier New page** (`/dashboard/procurement/suppliers/new`) to create:

| Supplier | Status | Purpose |
|----------|--------|---------|
| S152-NEW-VENDOR-TEST | Active, `is_new_supplier=1` | Triggers CEO approval on PO + RFP |

**Browser test (P18):** Navigate to `/dashboard/procurement/suppliers/new`, fill form:
- Supplier Name: "S152 Test Vendor (New)"
- TIN, email, phone, bank details
- Submit → verify supplier created

**HARD BLOCKER:** If item creation fails or no suppliers exist, STOP. Fix via `/frappe-bulk-edits` before proceeding.

---

## Phase 1: Chain A — PR → PO ≤P500K, Mae-Only Approval (10 units)

### 1.1: Create PR via /new form — 3 units [L3]

**User:** `test.finance@bebang.ph` / `BeiTest2026!`
**Page (P3):** `/dashboard/procurement/purchase-requisitions/new`

**Actions in browser:**
1. Navigate to PR new page
2. Fill form:
   - Department: select "Operations" from dropdown
   - Delivery To: select warehouse
   - Date Required: tomorrow
   - Purpose/Justification: "S152 Chain A — E2E acceptance test"
   - Add items: TEST-ITEM-001 (qty=10), TEST-ITEM-002 (qty=5), TEST-ITEM-003 (qty=20)
   - Verify prices auto-fill from contracted prices
   - Verify line totals calculate correctly
   - Verify grand total = sum of line totals
3. Click "Create PR" submit button
4. Capture PR number (e.g., `PR-2026-XXXXX`)

**Expected:** PR created, status = Draft

**UI/UX Audit (P3):**
- [ ] Item picker searchable and responsive?
- [ ] Prices auto-fill on item selection?
- [ ] UOM dropdown populated from API (29 UOMs, not 14 hardcoded)?
- [ ] Line totals calculate in real-time?
- [ ] Validation errors clear when fixed?

### 1.2: Submit PR and Approve via detail page — 3 units [L3]

**User:** `test.finance@bebang.ph` then `sam@bebang.ph` / `2289454`
**Page (P2):** `/dashboard/procurement/purchase-requisitions` (list)
**Page (P4):** `/dashboard/procurement/purchase-requisitions/[id]` (detail)

**Actions:**
1. On PR list page (P2): find the PR, click to open detail
2. On PR detail page (P4): click "Submit for Approval"
3. Verify status → "Pending Approval"
4. **Switch user to `sam@bebang.ph`** (CEO — has approval authority)
5. Navigate to PR detail page
6. Review: verify all items, quantities, estimated costs visible
7. Click "Approve" → enter comment "S152 Chain A approved"
8. Verify status → "Approved"
9. Verify `approved_by` = sam, `approval_date` set

**UI/UX Audit (P4):**
- [ ] All items visible with quantities and amounts?
- [ ] Approval/rejection buttons clearly visible?
- [ ] Comment field available on approve dialog?
- [ ] Status badge updates immediately after action?

### 1.3: Convert PR to PO — 2 units [L3]

**Page (P4):** PR detail page → Convert to PO action
**Page (P6):** `/dashboard/procurement/purchase-orders/new`

**Actions:**
1. On approved PR detail, click "Convert to PO"
2. On PO creation form (P6):
   - Select supplier from dropdown (use an existing active supplier, NOT the new vendor)
   - Verify items auto-populated from PR
   - Enter/confirm prices for each item
   - Set delivery date
   - Verify VAT auto-calculation (12%)
   - Verify grand_total = subtotal + VAT - discount + delivery_fee
   - **Ensure total ≤ P500K** (adjust quantities if needed)
3. Click "Create PO"
4. Capture PO number

**Expected:** PO created with `pr_reference` linking to PR. `requires_dual_approval = 0`. Grand total ≤ P500K.

### 1.4: Submit PO and Mae-Only Approval — 2 units [L3]

**User:** `test.finance@bebang.ph` (submit), then **`mae@bebang.ph`** (approve — EMAIL MATCH REQUIRED)
**Page (P7):** `/dashboard/procurement/purchase-orders/[id]`

**Actions:**
1. As `test.finance`: Navigate to PO detail page (P7), click "Submit for Approval"
2. Verify status → "Pending Mae Approval"
3. **SWITCH TO `mae@bebang.ph`** — login with Mae's credentials
4. Navigate to same PO detail page
5. Verify the "Approve" button IS VISIBLE (frontend checks email match)
6. Click "Approve" → enter comment "S152 Chain A — Mae approved"
7. Verify status → "Approved" (SKIPS Butch since ≤P500K)
8. Verify `mae_approval = "Approved"`, `mae_approval_date` set
9. Verify `requires_dual_approval = 0` — Butch step was NOT required

**UI/UX Audit (P7):**
- [ ] Dual approval status component shows Mae approved, Butch N/A?
- [ ] "Send to Supplier" action visible after approval?
- [ ] Items tab shows all line items with correct amounts?
- [ ] Linked GR and Invoice sections visible (empty at this stage)?
- [ ] Price edit inline works (click rate cell, change, save)?

---

## Phase 2: Chain A — GR → Invoice (8 units)

### 2.1: Send PO to Supplier — 1 unit [L3]

**Page (P7):** PO detail page

**Actions:**
1. Click "Send to Supplier" action
2. Verify PO status → "Sent to Supplier"
3. Verify `distribution_status`, `sent_to_supplier_date` fields set

### 2.2: Create GR via /new form — 2 units [L3]

**User:** `test.warehouse@bebang.ph` / `BeiTest2026!`
**Page (P9):** `/dashboard/procurement/goods-receipts/new`

**Actions:**
1. Navigate to GR new page
2. Select Purchase Order from dropdown (the PO from Phase 1)
3. Verify items auto-populated from PO with ordered quantities
4. Set receipt_date = today
5. For each item: set accepted_qty = ordered_qty (full receipt)
6. Upload supplier invoice photo (attach test image file)
7. Click "Create GR"
8. Capture GR number

**Expected:** GR created linked to PO. Status: "Accepted" or "Pending Inspection".

**UI/UX Audit (P9):**
- [ ] PO dropdown searchable and shows PO# + supplier + status?
- [ ] Items auto-populate with correct quantities and rates?
- [ ] File upload drag-drop works?
- [ ] Received Qty defaults to Ordered Qty?

### 2.3: Verify GR Detail — 1 unit [L3]

**Page (P10):** `/dashboard/procurement/goods-receipts/[id]`

**Actions:**
1. Navigate to GR detail page
2. Verify all fields: items, quantities (ordered vs received vs accepted)
3. Verify PO link clickable and opens PO detail
4. Verify uploaded document visible/downloadable
5. If "Pending Inspection": complete inspection → status "Accepted"
6. Verify PO status updated to "Fully Received"

### 2.4: Create Invoice via /new form — 2 units [L3]

**User:** `test.finance@bebang.ph`
**Page (P12):** `/dashboard/procurement/invoices/new`

**Actions:**
1. Navigate to Invoice new page
2. Select Purchase Order from dropdown
3. Verify GR auto-populated
4. Enter supplier_invoice_no = "SI-S152-CHAIN-A-001"
5. Enter invoice_date = today, due_date = today + 30
6. Verify amounts auto-populated from PO/GR
7. Click "Create Invoice"
8. Capture invoice number

**Expected:** Invoice created with PO + GR references. match_status should be "Matched" (full receipt, amounts match).

### 2.5: Verify Invoice Detail & 3-Way Match — 2 units [L3]

**Page (P13):** `/dashboard/procurement/invoices/[id]`

**Actions:**
1. Navigate to invoice detail
2. Verify 3-way match comparison cards: PO amount = GR amount = Invoice amount
3. Verify match_status = "Matched"
4. Click "Submit for Verification"
5. Verify status → "Verified"
6. Verify "Create Payment Request" action is now visible

**UI/UX Audit (P13):**
- [ ] 3-way match visualization clearly shows PO vs GR vs Invoice amounts?
- [ ] Variance percentage shown when mismatch exists?
- [ ] PO and GR links clickable?
- [ ] Approval timeline shows history?

---

## Phase 3: Chain A — RFP 3-Level Approval → OR (10 units)

This chain tests the standard 3-level RFP approval (≤P1M, existing supplier → no CEO needed).

### 3.1: Create Payment Request via /new form — 2 units [L3]

**User:** `test.finance@bebang.ph`
**Page (P15):** `/dashboard/procurement/payments/new`

**Actions:**
1. Navigate to Payment Request new page
2. Select Invoice from dropdown (the invoice from Phase 2)
3. Verify auto-populated: supplier, payment_amount = invoice grand_total
4. Select rfp_type = "Vendor Invoice" from dropdown
5. Verify account_code auto-assigned
6. Set payment_mode = "Bank Transfer"
7. Click "Create Payment Request"
8. Capture payment request number

**Expected:** RFP created. Status = "Draft". `ceo_required = 0` (amount ≤P1M, existing supplier).

**UI/UX Audit (P15):**
- [ ] Invoice dropdown shows invoice # + supplier + amount?
- [ ] Payment amount auto-fills from invoice balance?
- [ ] RFP Type dropdown has all 8 options?
- [ ] CEO approval badge shown when >P1M?

### 3.2: Submit and Level 1 — Reviewer Approval — 2 units [L3]

**User:** `test.finance@bebang.ph`
**Page (P16):** `/dashboard/procurement/payments/[id]`

**Actions:**
1. Navigate to payment detail page
2. Click "Submit for Approval"
3. Verify status → "Pending Review"
4. Review: verify supplier, invoice, PO, GR, amount ALL visible
5. Click "Approve" at Level 1 (Reviewer)
6. Enter comment: "S152 L1 — documents complete, amounts verified"
7. Verify `reviewer_status` → "Approved", `reviewer_date` set
8. Verify status → "Pending Budget Approval"

**UI/UX Audit (P16):**
- [ ] All linked documents (PO, GR, Invoice) visible without leaving page?
- [ ] Payment amount prominently displayed?
- [ ] Current approval level clearly indicated?
- [ ] Previous approval levels shown with approver name + date?
- [ ] 4-level approval progress component renders correctly?

### 3.3: Level 2 — Budget Approval — 1 unit [L3]

**User:** `test.finance@bebang.ph`

**Actions:**
1. On same payment detail, click Approve at Level 2
2. Comment: "S152 L2 — budget confirmed"
3. Verify `budget_status` → "Approved"
4. Verify status → "Pending CFO Approval"

### 3.4: Level 3 — CFO Approval — 1 unit [L3]

**User:** `sam@bebang.ph` / `2289454` (CEO has CFO-level access)

**Actions:**
1. Login as Sam
2. Navigate to payment detail
3. Click Approve at Level 3 (CFO)
4. Comment: "S152 L3 CFO — approved for disbursement"
5. Verify `cfo_status` → "Approved"
6. Verify status → "Approved" (NOT "Pending CEO" since amount ≤P1M and existing supplier)
7. **CONFIRM: CEO step was NOT shown/required**

### 3.5: Mark Paid — 1 unit [L3]

**Actions:**
1. After approval, mark payment as "Processing" → "Paid"
2. Verify status flow: Approved → Processing → Paid → "Paid - Awaiting OR" (if or_required=1)

### 3.6: Upload Official Receipt — 2 units [L3]

**User:** `test.finance@bebang.ph`
**Page (A6):** `/dashboard/accounting/awaiting-or` OR payment detail page

**Actions:**
1. Navigate to the payment in awaiting OR list
2. Click "Upload OR"
3. Fill OR dialog:
   - OR Number: "OR-S152-CHAIN-A-001"
   - OR Date: today
   - OR Amount: = payment_amount
   - Attach test image file
4. Submit
5. Verify `or_status` → "OR Received"
6. Verify RFP status → "Closed"

### 3.7: Verify Chain A end state — 1 unit [VERIFY]

**Cross-check via API:**
- PR status = "Converted to PO" or "Approved"
- PO status = "Fully Received"
- GR status = "Accepted"
- Invoice status = "Paid"
- RFP status = "Closed"
- OR status = "OR Received"
- All document links intact (PR→PO→GR→Invoice→RFP)

---

## Phase 4: Chain B — PO Dual Approval >P500K (6 units)

### 4.1: Create PO >P500K directly (no PR) — 2 units [L3]

**User:** `test.finance@bebang.ph`
**Page (P6):** `/dashboard/procurement/purchase-orders/new`

A PO does NOT always need a PR. Test standalone PO creation.

**Actions:**
1. Navigate to PO new page directly
2. Select supplier (existing, NOT new vendor)
3. Add items:
   - TEST-ITEM-004 (Equipment Set, P180,000) × qty 3 = **P540,000** (>P500K)
4. Set delivery date
5. Verify: "Requires dual approval (Mae + Butch)" badge shown
6. Verify `requires_dual_approval = 1` auto-set
7. Click "Create PO"
8. Capture PO number

**Expected:** PO total > P500K. `requires_dual_approval = 1`.

### 4.2: Dual approval: Mae → Butch — 2 units [L3]

**Page (P7):** PO detail page

**Actions:**
1. As `test.finance`: Submit PO for approval → status "Pending Mae Approval"
2. **SWITCH TO `mae@bebang.ph`** (EMAIL MATCH REQUIRED)
3. Navigate to PO, verify "Approve" button visible
4. **Mae approves** → status "Pending Butch Approval" (NOT "Approved")
5. Verify `mae_approval = "Approved"`
6. **SWITCH TO `butch@bebang.ph`** (EMAIL MATCH REQUIRED)
7. Navigate to PO, verify "Approve" button visible
8. **Butch (CFO) approves** → status "Approved"
9. Verify `butch_approval = "Approved"`, `butch_approval_date` set
10. Verify the dual approval status component shows BOTH checkmarks

**CRITICAL CHECK:** After Mae approval, status MUST be "Pending Butch" (not "Approved"). This is the dual approval path.

### 4.3: Complete Chain B (GR → Invoice → RFP) — 2 units [L3]

Follow same pattern as Chain A (Phases 2-3) but abbreviated — verify the chain works with the dual-approved PO:
1. Create GR from PO (full receipt)
2. Create Invoice from PO+GR
3. Create Payment Request from Invoice
4. Approve RFP through 3 levels (Reviewer → Budget → CFO)
5. **CONFIRM: CEO step NOT required** (amount >P500K but <P1M, existing supplier)

---

## Phase 5: Chain C — CEO Approval on PO + RFP >P1M (10 units)

**This is the highest-risk path. Uses `sam@bebang.ph` (password: `2289454`) for CEO approval.**

### 5.1: Create PO with new vendor (triggers CEO on PO) — 2 units [L3]

**User:** `test.finance@bebang.ph`
**Page (P6):** PO new page

**Actions:**
1. Select the new vendor created in Phase 0.3 ("S152 Test Vendor (New)")
2. Add items:
   - TEST-ITEM-005 (Industrial Freezer, P350,000) × qty 4 = **P1,400,000** (>P1M)
3. Verify BOTH badges: "Requires dual approval" AND "Requires CEO approval"
4. Create PO
5. Capture PO number

**Expected:** `requires_dual_approval = 1`, `requires_ceo_approval = 1`. Grand total > P1M.

### 5.2: Triple PO approval: Mae → Butch → CEO — 3 units [L3]

**Actions:**
1. As `test.finance`: Submit PO → "Pending Mae Approval"
2. **SWITCH TO `mae@bebang.ph`** (EMAIL MATCH)
3. Navigate to PO, **Mae approves** → "Pending Butch Approval"
4. **SWITCH TO `butch@bebang.ph`** (EMAIL MATCH)
5. Navigate to PO, **Butch approves** → "Pending CEO Approval"
6. **SWITCH TO `sam@bebang.ph` / `2289454`** (EMAIL MATCH)
7. Navigate to PO detail
8. **CEO approves** with comment: "S152 CEO PO approved — new vendor + >1M"
9. Verify `ceo_approval = "Approved"`, `ceo_approval_date` set
10. Verify status → "Approved"

**CRITICAL:** The PO must pass through ALL THREE approval levels before reaching "Approved". Each level requires logging in as the SPECIFIC configured email — there is no bypass.

### 5.3: Chain C — GR + Invoice — 2 units [L3]

1. Create GR from the >P1M PO (full receipt)
2. Create Invoice (supplier_invoice_no = "SI-S152-CHAIN-C-001")
3. Verify 3-way match passes
4. Submit for verification → status "Verified"

### 5.4: Create RFP >P1M (triggers CEO on RFP) — 1 unit [L3]

**User:** `test.finance@bebang.ph`
**Page (P15):** Payment new page

**Actions:**
1. Create Payment Request from the >P1M invoice
2. Set rfp_type = "Vendor Invoice"
3. Verify `payment_amount` > P1M
4. Verify "Requires CEO approval" badge shown
5. Verify `ceo_required = 1` (triggered by amount >P1M AND/OR new supplier)
6. Submit

### 5.5: 4-Level RFP Approval with CEO — 2 units [L3]

**This is the critical path: Reviewer → Budget → CFO → CEO**

**Actions:**
1. **Level 1 (Reviewer):** `test.finance` approves → "Pending Budget"
2. **Level 2 (Budget):** `test.finance` approves → "Pending CFO"
3. **Level 3 (CFO):** `sam@bebang.ph` approves → **"Pending CEO Approval"** (NOT "Approved")
4. **Level 4 (CEO):** `sam@bebang.ph` approves with comment: "S152 CEO RFP approved — >P1M disbursement authorized"
5. Verify `ceo_status = "Approved"`, `ceo_approver = sam`, `ceo_date` set
6. Verify status → "Approved"

**CRITICAL CHECK:** After CFO approval, status MUST be "Pending CEO Approval" (not "Approved"). This proves the P1M threshold triggers the 4th level.

---

## Phase 6: Rejection & Edge Cases (6 units)

### 6.1: PO Rejection — 2 units [L3]

**Actions:**
1. Create a new small PO (any amount)
2. Submit for Mae approval
3. **Mae rejects** with reason: "S152 test — vendor pricing too high"
4. Verify status → "Rejected"
5. Verify `rejection_reason` recorded
6. Verify the PO can be re-edited and re-submitted (if supported)

### 6.2: RFP Rejection at Level 2 — 2 units [L3]

**Actions:**
1. Create Invoice + Payment Request from a verified invoice
2. Submit → L1 Reviewer approves
3. **L2 Budget rejects** with reason: "S152 test — budget exceeded for this quarter"
4. Verify status → "Rejected"
5. Verify rejection level, rejector, and reason recorded
6. Verify the RFP can be re-submitted (if supported)

### 6.3: Partial GR (received < ordered) — 1 unit [L3]

**Actions:**
1. Create GR from an approved PO
2. Set accepted_qty = 50% of ordered qty for each item
3. Submit GR
4. Verify GR status = "Partially Accepted" or "Accepted"
5. Verify PO status → "Partially Received" (NOT "Fully Received")

### 6.4: Invoice Variance (3-way match fails) — 1 unit [L3]

**Actions:**
1. Create Invoice where amount differs from PO/GR amount
2. Submit for verification
3. Verify match_status = "Variance Detected"
4. Navigate to variance approval
5. Approve variance with notes: "S152 test — vendor applied bulk discount"
6. Verify status → "Verified" after variance approval

---

## Phase 7: Dashboard Validation — Procurement Pages (10 units) — `/teammates`

**Execute in parallel using `/teammates` — 4 agents simultaneously.**

### Agent 1: List Pages (P1, P2, P5)

#### 7.1: Procurement Dashboard (P1) — 2 units
**Page:** `/dashboard/procurement`
- [ ] All KPI cards show non-zero values
- [ ] AP Aging Analysis chart renders
- [ ] Monthly PO trends chart renders
- [ ] Outstanding by Supplier bar chart shows data
- [ ] Quick action links work (Create PR, Create PO, Create GR, Create Invoice, Request Payment)
- [ ] Pending Approvals section shows PO + Payment counts

#### 7.2: PR List (P2) — 1 unit
- [ ] PRs from Phase 1 appear
- [ ] Status filters work (all statuses)
- [ ] Search by PR# works
- [ ] Stats cards show correct counts
- [ ] Approval/Convert actions in row dropdowns

#### 7.3: PO List (P5) — 2 units
- [ ] POs from all chains appear
- [ ] Status filters: Draft, Pending Mae, Pending Butch, Pending CEO, Approved, Sent, Received
- [ ] "Approved" tab shows 543+ POs (per S141)
- [ ] Pagination works (577+ total POs)
- [ ] Batch approve checkbox selection works
- [ ] Search by PO# and supplier works
- [ ] PO batch approve dialog functional

### Agent 2: Receipt & Invoice Pages (P8, P11)

#### 7.4: GR List (P8) — 2 units
- [ ] GRs from test chains appear
- [ ] PO reference displayed
- [ ] Status filter works
- [ ] Variance badge shown where applicable
- [ ] Search works

#### 7.5: Invoice List (P11) — 2 units
- [ ] Invoices from test chains appear
- [ ] 3-way match status visible per invoice
- [ ] Payment status visible
- [ ] Overdue indicator (red badge) for past-due invoices
- [ ] "Variance" tab shows variance invoices
- [ ] Create Payment Request action on verified invoices

### Agent 3: Payment & Supplier Pages (P14, P17, P19)

#### 7.6: Payment List (P14) — 2 units
- [ ] RFPs from all chains appear
- [ ] 4-level approval progress indicator visible
- [ ] Status filters work
- [ ] "Pending My Approval" tab shows correct items for logged-in user
- [ ] Bulk approve works

#### 7.7: Supplier List + Detail (P17, P19) — 2 units
- [ ] 100+ suppliers in list
- [ ] Search by supplier name works
- [ ] Status filter (Active/Inactive/Blacklisted)
- [ ] Supplier detail (P19): Overview, POs tab, Invoices tab, Items tab all load
- [ ] Document status (BIR/SEC) indicators visible
- [ ] The new vendor from Phase 0.3 appears

### Agent 4: Approvals & OR Pages (P20, P21)

#### 7.8: Approvals Hub (P20) — 1 unit
- [ ] PO approval count matches `get_pending_po_approvals` API
- [ ] Payment approval count matches `get_pending_payment_approvals` API
- [ ] Links to PO queue and Payment queue work

#### 7.9: OR Follow-Up (P21) — 1 unit
- [ ] Overdue ORs listed with days overdue
- [ ] Follow-up send button works
- [ ] Notification delivery status shown

---

## Phase 8: Dashboard Validation — AP Command Center + Accounting (8 units) — `/teammates`

**Execute in parallel using `/teammates` — 3 agents simultaneously.**

### Agent 5: AP Overview + Invoices (A1, A2)

#### 8.1: AP Overview Tab (A1) — 2 units
- [ ] 6 KPI cards populated with real data (not 0 or NaN)
- [ ] Outstanding AP total cross-checks against SUM(balance_due WHERE payment_status != 'Paid')
- [ ] Overdue count cross-checks against COUNT(due_date < today AND status = 'Unpaid')
- [ ] AP Aging Distribution bars render correctly
- [ ] Outstanding by Supplier list shows 3+ suppliers
- [ ] Quick Actions (SOA, Form 2307) clickable

#### 8.2: AP Invoices Tab (A2) — 2 units
- [ ] Pagination controls present (not just 20 rows)
- [ ] Status filter works for all statuses
- [ ] Invoice Date column visible
- [ ] Aging badges color-coded
- [ ] Inline status dropdown works
- [ ] Checkbox selection + "Transfer to Finance" bulk action
- [ ] **CSV Export downloads ALL rows** (verify: export count = API total count, should be 714+)
- [ ] Search by supplier/invoice# works

### Agent 6: AP Payments + Aging (A3, A4)

#### 8.3: AP Payments Tab (A3) — 2 units
- [ ] RFPs from all 3 chains visible
- [ ] 4-level approval icons render correctly:
  - Green CheckCircle2 = Approved
  - Yellow CircleDot = Pending
  - Red XCircle = Rejected
  - Gray Circle = Not Required
- [ ] Chain A RFP: 3 green checks, 1 gray (CEO not required)
- [ ] Chain C RFP: 4 green checks (all levels including CEO)
- [ ] Rejected RFP from Phase 6.2: red X at rejection level
- [ ] RFP Type, OR Status columns correct

#### 8.4: AP Aging Tab (A4) — 2 units
- [ ] Aging matrix shows **multi-supplier grid** (NOT single row — this was a S147 bug)
- [ ] Buckets: Current, 1-30, 31-60, 61-90, 90+
- [ ] Per-supplier totals sum correctly across buckets
- [ ] Column totals sum all suppliers per bucket
- [ ] Grand total matches Overview tab Outstanding AP
- [ ] CSV export includes all suppliers

### Agent 7: AP Supplier Ledger + Accounting Pages (A5, A6, A7)

#### 8.5: AP Supplier Ledger Tab (A5) — 1 unit
- [ ] **100+ suppliers in list** (NOT 3 — this was a S147 bug)
- [ ] Search/filter works
- [ ] Selecting supplier loads transaction timeline
- [ ] Timeline shows POs (blue), GRs (green), Invoices (amber), Payments (red)
- [ ] Dates, amounts, reference numbers correct

#### 8.6: Awaiting OR Page (A6) — 1 unit
- [ ] Payments awaiting OR listed
- [ ] Upload OR dialog works
- [ ] "Mark Not Required" action available
- [ ] Send Follow-Up button works

#### 8.7: Exceptions Page (A7) — 1 unit
- [ ] Variance exceptions listed (from Phase 6.4)
- [ ] Approval action works

---

## Phase 9: UI/UX Audit & Defect Remediation (10 units)

### 9.1: Cross-page UX Audit — 4 units [AUDIT]

| Criterion | Check Every Page For |
|-----------|---------------------|
| **Information completeness** | Can user approve/act WITHOUT opening another page? |
| **Amount formatting** | All PHP amounts: `P` prefix, comma separators, 2 decimals |
| **Date formatting** | Consistent format (e.g., "Mar 31, 2026") |
| **Status clarity** | Color-coded badges with text (not color alone) |
| **Empty states** | Informative message when no data (not blank) |
| **Error states** | Network error / permission denied handled gracefully |
| **Loading states** | Skeleton/spinner during data fetch |
| **Action visibility** | Primary actions (Create, Approve, Export) immediately visible |
| **Link integrity** | PO→GR→Invoice→RFP links bidirectional and working |
| **Sorting** | Can sort by amount, date, status on list pages |
| **Approval info** | At every approval step: amount, supplier, all linked docs visible |

### 9.2: Defect Catalog & Fix — 6 units [FIX]

Log every defect in `output/l3/s152/defects/DEFECT_REGISTER.csv`:
- `defect_id`, `severity` (CRITICAL/HIGH/MEDIUM/LOW), `page`, `description`, `screenshot`, `fix_status`

**Fix priority:**
- CRITICAL: Fix immediately (blocks workflow)
- HIGH: Fix in sprint (data accuracy, missing info for approvers)
- MEDIUM: Fix if time permits
- LOW: Log for future sprint

**Fix workflow:**
- Backend: edit `hrms/api/procurement.py` → commit to branch
- Frontend: edit in `bei-tasks/` repo → commit → Vercel auto-deploys
- Re-verify fix in browser

---

## Phase 10: Closeout & Evidence (4 units)

### 10.1: Capture L3 Evidence — 2 units

```
output/l3/s152/form_submissions.json    — every form submitted (PR, PO×3, GR×3, Invoice×3, RFP×3, OR)
output/l3/s152/api_mutations.json       — every API call with response codes
output/l3/s152/state_verification.json  — every status assertion with before/after
output/l3/s152/screenshots/             — key screenshots per phase
output/l3/s152/defects/DEFECT_REGISTER.csv — all defects, severity, fix status
```

### 10.2: Plan & Registry Closeout — 2 units

1. Update this plan: `status: GO` → `status: COMPLETED`, add `completed_date` and `execution_summary`
2. Update `docs/plans/SPRINT_REGISTRY.md`: row status → COMPLETED
3. `git add -f output/l3/s152/ docs/plans/` and push

---

## L3 Workflow Scenarios (Complete)

### Chain A: Standard Flow (≤P500K, Mae-only PO, 3-level RFP)

| # | User | Action | Expected Outcome | Failure Means |
|---|------|--------|-------------------|---------------|
| L3-01 | test.finance | Navigate to `/procurement/purchase-requisitions/new`, fill form: 3 items (TEST-ITEM-001 qty=10, TEST-ITEM-002 qty=5, TEST-ITEM-003 qty=20), dept=Operations → submit | PR created, status=Draft, total calculated | PR creation form broken |
| L3-02 | test.finance | Open PR detail, click "Submit for Approval" | Status → "Pending Approval" | PR submit broken |
| L3-03 | sam (CEO) | Open PR detail, click "Approve", comment="S152 approved" | Status → "Approved", approved_by=sam | PR approval broken |
| L3-04 | test.finance | On approved PR, click "Convert to PO" → PO form: select supplier, verify items, total ≤P500K → create | PO created with pr_reference, requires_dual_approval=0 | PR→PO conversion broken |
| L3-05 | **mae@bebang.ph** | Submit PO (as test.finance) → **login as Mae** → Mae approves ≤P500K PO | Status → "Approved" (skips Butch) | Mae-only threshold broken OR Mae credential issue |
| L3-06 | test.finance | Send PO to supplier | Status → "Sent to Supplier" | Send action broken |
| L3-07 | test.warehouse | `/goods-receipts/new`: select PO, full receipt (all accepted_qty=ordered_qty), upload photo → submit | GR created, PO→"Fully Received" | GR creation broken |
| L3-08 | test.finance | `/invoices/new`: select PO, enter supplier invoice#, verify 3-way match → submit | Invoice created, match_status=Matched, status=Verified | Invoice/3-way match broken |
| L3-09 | test.finance | `/payments/new`: select invoice, rfp_type=Vendor Invoice, payment_mode=Bank Transfer → create | RFP created, ceo_required=0 | RFP creation broken |
| L3-10 | test.finance | Submit RFP → L1 Reviewer approves | reviewer_status=Approved, status→"Pending Budget" | L1 broken |
| L3-11 | test.finance | L2 Budget approves | budget_status=Approved, status→"Pending CFO" | L2 broken |
| L3-12 | sam (CEO) | L3 CFO approves | cfo_status=Approved, status→"Approved" (NO CEO step) | L3 or threshold broken |
| L3-13 | test.finance | Upload OR: number=OR-S152-A-001, date=today, amount=payment | or_status="OR Received", status→"Closed" | OR upload broken |

### Chain B: Dual PO Approval (>P500K)

| # | User | Action | Expected Outcome | Failure Means |
|---|------|--------|-------------------|---------------|
| L3-14 | test.finance | `/purchase-orders/new`: existing supplier, TEST-ITEM-004 qty=3 (P540K total) → create | PO created, requires_dual_approval=1, badge shown | Threshold detection broken |
| L3-15 | **mae@bebang.ph** | Login as Mae → approve >P500K PO | Status → "Pending Butch Approval" (NOT "Approved") | Dual path skipped OR Mae credential issue |
| L3-16 | **butch@bebang.ph** | Login as Butch → approve >P500K PO | Status → "Approved", butch_approval=Approved | Butch approval broken OR Butch credential issue |
| L3-17 | various | Full chain: GR (test.warehouse) → Invoice (test.finance) → RFP → 3-level approve (test.finance + sam) → OR | All documents created and closed | Chain B linkage broken |

### Chain C: CEO Approval on PO (new vendor) + RFP (>P1M)

| # | User | Action | Expected Outcome | Failure Means |
|---|------|--------|-------------------|---------------|
| L3-18 | test.finance | `/purchase-orders/new`: new vendor (S152-NEW), TEST-ITEM-005 qty=4 (P1.4M) → create | requires_dual_approval=1, requires_ceo_approval=1 | CEO PO trigger broken |
| L3-19 | **mae@bebang.ph** | Login as Mae → approve new vendor PO | Status → "Pending Butch Approval" | Mae email match broken |
| L3-20 | **butch@bebang.ph** | Login as Butch → approve new vendor PO | Status → "Pending CEO Approval" (NOT "Approved") | Butch email match broken |
| L3-21 | **sam@bebang.ph** (pw: 2289454) | Login as CEO → **approve new vendor PO** | ceo_approval=Approved, status→"Approved" | **CEO PO email match broken** |
| L3-22 | test.warehouse | GR from >P1M PO → full receipt → submit | GR created, PO→"Fully Received" | GR for large PO broken |
| L3-23 | test.finance | Invoice from PO+GR, 3-way match → verified | Invoice verified, amount >P1M | Invoice for large amount broken |
| L3-24 | test.finance | `/payments/new`: from >P1M invoice → create RFP | ceo_required=1, badge "Requires CEO approval" | RFP CEO trigger broken |
| L3-25 | test.finance | Submit RFP → L1 Reviewer approves | Status → "Pending Budget" | L1 broken for >P1M |
| L3-26 | test.finance | L2 Budget approves | Status → "Pending CFO" | L2 broken for >P1M |
| L3-27 | sam (CEO) | L3 CFO approves | Status → **"Pending CEO Approval"** (NOT "Approved") | **CFO→CEO threshold broken** |
| L3-28 | **sam@bebang.ph** | **L4 CEO approves RFP** with comment: "P1.4M disbursement authorized" | ceo_status=Approved, ceo_approver=sam, status→"Approved" | **CEO RFP approval broken** |

### Rejection & Edge Cases

| # | User | Action | Expected Outcome | Failure Means |
|---|------|--------|-------------------|---------------|
| L3-29 | **mae@bebang.ph** | Create PO (as test.finance), submit, **login as Mae** → reject with reason | Status → "Rejected", rejection_reason recorded | PO rejection broken OR Mae credential issue |
| L3-30 | test.finance | Create RFP, submit, L1 approves, L2 rejects with reason | Status → "Rejected", rejection level+reason recorded | RFP rejection broken |
| L3-31 | test.warehouse | GR with accepted_qty = 50% of ordered_qty → submit | GR accepted, PO → "Partially Received" | Partial receipt broken |
| L3-32 | test.finance | Invoice with different amount than PO/GR → submit | match_status="Variance Detected", needs approval | 3-way match variance broken |
| L3-33 | test.finance | Approve invoice variance with notes | Status → "Verified" after variance approval | Variance approval broken |

### Dashboard Verification

| # | User | Action | Expected Outcome | Failure Means |
|---|------|--------|-------------------|---------------|
| L3-34 | test.finance | AP Overview: verify 6 KPI cards | All non-zero, Outstanding matches SUM(balance_due) | AP Overview data broken |
| L3-35 | test.finance | AP Invoices: CSV export, count rows | Row count = API total (714+) | CSV export broken |
| L3-36 | test.finance | AP Aging: verify multi-supplier matrix | Multi-row grid, column totals correct | Aging pivot broken |
| L3-37 | test.finance | AP Supplier Ledger: select supplier, verify timeline | Timeline shows POs+GRs+Invoices with dates+amounts | Timeline API broken |
| L3-38 | test.finance | AP Payments: verify Chain A RFP (3 green, 1 gray) | Correct approval icons per chain | Approval icons broken |
| L3-39 | test.finance | AP Payments: verify Chain C RFP (4 green checks) | All 4 levels shown as approved | CEO icon not rendering |
| L3-40 | test.finance | PO list: search for Chain B PO, verify dual approval badge | PO found, dual approval visible | PO search/badge broken |

**Total: 40 L3 scenarios** — every form, every approval path, every threshold, every rejection, every dashboard.

---

## Parallel Execution Plan (`/teammates`)

### Wave 1: Sequential (must complete in order)
**Single agent: workflow-runner**
- L3-01 through L3-33 (all 3 chains + rejections + edge cases)
- Each chain step depends on the previous step's output

### Wave 2: Parallel (after Wave 1 completes)
Launch 4 agents via `/teammates`:

| Agent | Scope | Scenarios |
|-------|-------|-----------|
| **dashboard-procurement** | Phase 7: PO, PR, GR, Invoice, Supplier, Approvals, OR pages | L3-40 + Phase 7 audits |
| **dashboard-ap-overview** | Phase 8.1-8.2: AP Overview + Invoices | L3-34, L3-35 |
| **dashboard-ap-matrix** | Phase 8.3-8.4: AP Payments + Aging | L3-36, L3-38, L3-39 |
| **dashboard-ap-supplier** | Phase 8.5-8.7: Supplier Ledger + Awaiting OR + Exceptions | L3-37 |

### Wave 3: Defect Fix (after Wave 2 reports)
**Single agent: defect-fixer**
- Collect all defects from Wave 1 + Wave 2
- Fix CRITICAL/HIGH
- Re-verify

---

## Requirements Regression Checklist

### Credential & Role Checks
- [ ] Is `mae@bebang.ph` used (NOT test.finance) for ALL PO Mae approvals? (EMAIL MATCH enforced at `bei_purchase_order.py:325`)
- [ ] Is `butch@bebang.ph` used (NOT test.finance) for ALL PO Butch approvals? (EMAIL MATCH enforced at `bei_purchase_order.py:364`)
- [ ] Is `sam@bebang.ph` used for ALL PO CEO approvals? (EMAIL MATCH enforced)
- [ ] Does `test.finance@bebang.ph` have the `Accounts Manager` role for RFP L2/L3/L4?
- [ ] Are BEI Settings approver emails confirmed: cpo=mae, cfo=butch, ceo=sam?

### Workflow Coverage
- [ ] Is every form submission done on the ACTUAL /new page in a REAL browser (not API-only)?
- [ ] Does every L3 scenario verify Frappe-side state (not just UI state)?
- [ ] Is Chain A tested with PO ≤P500K (Mae-only, NO Butch)?
- [ ] Is Chain B tested with PO >P500K (Mae + Butch dual approval)?
- [ ] Is Chain C tested with PO from NEW vendor (Mae + Butch + CEO triple approval)?
- [ ] Is Chain C RFP tested with amount >P1M (Reviewer + Budget + CFO + CEO 4-level)?
- [ ] Does `sam@bebang.ph` perform the CEO approval at Level 4 on the >P1M RFP?
- [ ] Is PO rejection tested with `mae@bebang.ph` (Mae rejects)?
- [ ] Is RFP rejection tested (Budget level rejects)?
- [ ] Is partial GR tested (received < ordered)?
- [ ] Is invoice variance tested (3-way match fails, then variance approved)?
- [ ] Is OR upload tested end-to-end?

### Frontend Button Visibility
- [ ] Does the Mae "Approve" button ONLY appear when logged in as mae@bebang.ph?
- [ ] Does the Butch "Approve" button ONLY appear when logged in as butch@bebang.ph?
- [ ] Does the CEO "Approve" button ONLY appear when logged in as sam@bebang.ph?
- [ ] Do RFP approval buttons appear for test.finance (Accounts Manager role)?
- [ ] Are approval buttons HIDDEN when logged in as a user without the right email/role?

### Script Integrity (Browser-Only Enforcement)
- [ ] Do the test scripts (`l3_s152_chain_a.mjs`, `chain_bc.mjs`, `edge_cases.mjs`, `dashboards.mjs`) contain ZERO `fCall()` imports or invocations?
- [ ] Do the test scripts contain ZERO `fetch(...POST)` calls for procurement endpoints?
- [ ] Do the helper browser functions (`browserCreatePO`, `browserApprovePO`, etc.) use ONLY Playwright page actions?
- [ ] When a browser button was not found, was it logged as FAIL (not silently replaced with API)?
- [ ] If any test script was modified during execution, was the modification committed to the branch?
- [ ] Were any API mutations added to test scripts during execution? (Must be NO)

### Dashboard & Data Validation
- [ ] Are ALL 20 procurement pages visited and verified?
- [ ] Are ALL 5 AP Command Center tabs verified with data accuracy?
- [ ] Is CSV export tested for ALL rows (not just current page)?
- [ ] Is Supplier Ledger verified to show 100+ suppliers?
- [ ] Is Aging matrix verified as multi-supplier grid?
- [ ] Is L3 evidence committed to branch before closeout?

---

## Autonomous Execution Contract

```yaml
completion_condition:
  - All 40 L3 scenarios PASS with 100% confidence (no soft passes, no skips)
  - Every PASS backed by 4-part evidence (before state, action, after state, screenshot)
  - All 3 chains completed end-to-end (A: ≤500K, B: >500K, C: >1M+CEO)
  - CEO approval tested on BOTH PO (new vendor) and RFP (>1M)
  - PO rejection and RFP rejection both tested
  - Partial GR and invoice variance both tested
  - All 20 procurement pages verified
  - All 5 AP Command Center tabs verified
  - UI/UX audit complete with defect register
  - ZERO unfixed CRITICAL or HIGH **in-scope** defects remaining
  - ALL collateral defects (any severity) logged in DEFECTS.md and DEFECT_REGISTER.csv
  - Every defect fix re-verified with re-test of affected code paths
  - L3 evidence committed to branch
  - Plan status updated to COMPLETED
  - SPRINT_REGISTRY.md updated
stop_only_for:
  - Missing test data that cannot be created via /frappe-bulk-edits
  - Production site down or unreachable
  - mae@bebang.ph or butch@bebang.ph login fails AND password reset via /frappe-bulk-edits also fails
  - test.finance@bebang.ph missing Accounts Manager role AND cannot be added
  - BEI Settings approver emails misconfigured
  - Business-policy decision about approval thresholds
continue_without_pause_through:
  - Test data setup
  - All 3 E2E workflow chains
  - Dashboard validation
  - Defect cataloging and fixing
  - Evidence capture and closeout
blocker_policy:
  programmatic: fix the code, re-deploy, re-test — NEVER skip
  test_failure: diagnose root cause, fix (code or test), re-run — loop until PASS or 3x circuit breaker
  environment: debug, retry 3x, then escalate as CRITICAL defect
  business: pause and ask
  ambiguous_result: treat as FAIL, investigate until 100% confident
signoff_authority: single-owner (Sam)
canonical_closeout_artifacts:
  - output/l3/s152/form_submissions.json
  - output/l3/s152/api_mutations.json
  - output/l3/s152/state_verification.json
  - output/l3/s152/defects/DEFECT_REGISTER.csv (in-scope AND collateral defects)
  - output/l3/s152/DEFECTS.md (human-readable defect descriptions)
  - docs/plans/2026-03-31-sprint-152-procurement-e2e-acceptance.md
  - docs/plans/SPRINT_REGISTRY.md
```

---

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

## Zero-Skip / Zero-Ambiguity Testing Policy (MANDATORY)

**NO SKIPS. NO SOFT PASSES. NO "PROBABLY WORKS".**

### Rule 1: Failed = Fix, Not Skip
If a test fails, the agent MUST:
1. Diagnose the root cause (code bug? test setup? wrong selector? wrong user?)
2. Fix the underlying issue (backend code, frontend code, test data, or test script)
3. Re-run the exact same test
4. Only mark PASS after the fix is verified

**NEVER mark a failed test as "skipped", "known issue", "out of scope", or "works manually".**

### Rule 2: 100% Confidence or FAIL
A test is PASS only when ALL of the following are true:
- The exact expected outcome occurred (not "something similar")
- The state was verified via API (not just visual check)
- The data matches exactly (amounts, statuses, dates, linked documents)
- No console errors, no 500 responses, no timeouts masked as success

If confidence is below 100% → the test is **FAILED**. Investigate, fix, re-run.

### Rule 3: No Partial Credit
- "Page loaded but I couldn't verify the data" = FAIL
- "Button clicked but I didn't check the status change" = FAIL
- "API returned 200 but I didn't verify the response body" = FAIL
- "It worked for Chain A so it probably works for Chain C" = FAIL — test each chain independently

### Rule 4: Fix-and-Repeat Loop
```
TEST → FAIL → DIAGNOSE → FIX → RE-TEST → FAIL → DIAGNOSE → FIX → RE-TEST → PASS
```
The loop continues until PASS. After 3 consecutive failures on the same test:
- Log the 3 attempts with exact error messages
- Escalate as a CRITICAL defect in the defect register
- Continue to next test (do NOT block the entire sprint)
- Return to this test after other tests complete (fresh context may help)

### Rule 5: Evidence Must Be Airtight
Every PASS must have:
- **Before state:** What was the status/data before the action?
- **Action taken:** Exact form values, exact button clicked, exact user logged in
- **After state:** API-verified status, field values, linked documents
- **Screenshot:** Visual proof of the final state

If any of these 4 are missing → the test result is **INVALID**, not PASS.

### Rule 6: Defects Found = Fix In-Sprint
When a test reveals a code defect:
1. Log in `output/l3/s152/defects/DEFECT_REGISTER.csv`
2. CRITICAL/HIGH: Fix immediately on the sprint branch, re-deploy, re-test
3. MEDIUM: Fix before closeout
4. LOW: Fix before closeout if feasible, otherwise document with exact reproduction steps
5. **The sprint cannot close with unfixed CRITICAL or HIGH defects**

### Rule 7: Re-Test After Every Fix
After fixing a defect, re-run ALL tests that touch the same code path — not just the one that failed. A fix that breaks something else is worse than the original bug.

### Rule 8: Report ALL Defects — Including Out-of-Scope (MANDATORY)

Testing exists to find bugs. **ALL bugs found during a test run must be reported — even if they are outside the sprint scope.**

**When any form submit, workflow action, or state verification reveals ANY error:**
1. **Report it as a defect** — always. A bug is a bug. Period.
2. **Never call a scenario PASS and hide the error** because it's "pre-existing" or "not our sprint"
3. **Classify every defect:**
   - **IN-SCOPE**: Directly related to S152 test scenarios
   - **COLLATERAL**: Discovered during testing but outside S152 scope (e.g., a broken form field that existed before, a missing page, a wrong calculation in an unrelated module)
4. **Both types get logged to** `output/l3/S152/defects/DEFECT_REGISTER.csv` **and** `output/l3/S152/DEFECTS.md`
5. **Both types appear in the final summary** — listed separately
6. **Severity rating applies to both** — a CRITICAL collateral defect is still CRITICAL

**DEFECT-PASS vs PASS vs FAIL:**
- **PASS**: Scenario fully succeeded, all assertions green, no errors observed
- **FAIL**: The test scenario itself failed (in-scope)
- **DEFECT-PASS**: The scenario's primary assertion passed, but a collateral bug was discovered during execution. The scenario goal is met but something else is broken.

**What counts as a reportable defect:**
- A form field that throws an error → REPORT
- A page that shows wrong data → REPORT
- A button that doesn't work on a page you navigated through → REPORT
- A console error on any visited page → REPORT
- A miscalculation in a KPI card → REPORT
- A missing column in a table → REPORT
- A broken link to a detail page → REPORT
- An approval that produces a wrong status → REPORT
- A 500 error from any API call observed in network tab → REPORT

**What the agent MUST NOT do:**
- Hide an error because "it's pre-existing"
- Dismiss a failure as "works as designed" without verification
- Say "out of scope" to avoid logging a defect
- Decide which bugs matter — report ALL, let Sam prioritize

**DEFECTS.md format:**
```markdown
## DEFECT: [short description]
- **Severity:** CRITICAL / HIGH / MEDIUM / LOW
- **Type:** IN-SCOPE / COLLATERAL
- **Scenario:** S152-A08 (invoice creation)
- **Error:** [exact error message or observed behavior]
- **Expected:** [what should have happened]
- **Impact:** [who is affected, what workflow is broken]
- **First Seen:** [timestamp PHT]
```

**Why this rule exists:** S107 (2026-03-24): Agent found that PR creation returns MandatoryError but called the test "PASS" because the sprint's specific fix worked and the missing fields were "pre-existing." The PR form had NEVER worked end-to-end. A test that reveals a bug outside the sprint scope is MORE valuable than one that only validates the happy path within scope.

### Rule 9: ABSOLUTE Browser-Only Enforcement (NO EXCEPTIONS, NO CIRCUMSTANCES)
**Every create, submit, approve, reject, and upload action MUST happen via Playwright browser click.** This is non-negotiable.

- If a button is not found → that is a **FAIL**, not a reason to call the API
- If a selector doesn't work → **fix the selector**, not bypass with `fCall()`
- If a form doesn't submit → **debug the form**, not create via API
- If login fails → **fix the login**, not switch to API token
- If a dropdown doesn't open → **fix the interaction**, not skip the field
- **`fCall()`, `fPost()`, `fetch(...POST)` are FORBIDDEN in test scripts** for any mutation
- **`fDoc()`, `fList()`, `fGet()` (GET only) are ALLOWED** — but only for state verification AFTER a browser action
- The test scripts have been audited: **zero `fCall` imports in any test file**. Any agent that re-adds `fCall` or any POST-based API mutation to a test script is violating this plan.

**If a test script fails because the browser interaction doesn't work:**
1. The agent MUST fix the test script (better selectors, better waits, better flow)
2. The agent MUST NOT replace the browser action with an API call
3. If the browser action fails because the UI is genuinely broken → log as a DEFECT, fix the UI code, re-test
4. After 3 failed attempts at the same browser interaction → escalate as CRITICAL defect, move to next test, come back later
5. Under NO circumstances does "the button wasn't found" justify an API mutation

**This rule exists because:** The previous version of these scripts had 28 API fallback calls that silently replaced browser actions when selectors weren't found. The agent declared "all tests pass" when half the actions never touched the browser. Sam had to ask "did you cut any corners?" to discover the truth. That will never happen again.

### Rule 9: Fix the Script, Not the Rules
When a test script fails during execution:
1. The executing agent MUST fix the `.mjs` script file (selectors, waits, flow logic)
2. The fix MUST be committed to the sprint branch
3. The fixed script MUST be re-run to prove the fix works
4. The agent MUST NOT:
   - Delete the failing test
   - Comment out the failing assertion
   - Change FAIL to PASS without fixing the root cause
   - Add an API fallback to replace the browser action
   - Skip the scenario and move on permanently
   - Modify the scenario definition to match the broken behavior

---

## Test Scripts (Playwright .mjs)

| Script | Scenarios | Run Command |
|--------|-----------|-------------|
| `scripts/testing/l3_s152_helpers.mjs` | Shared: login, Frappe API, evidence, PNG generator | (imported by other scripts) |
| `scripts/testing/l3_s152_chain_a.mjs` | S152-A01 to A13 (PR→PO→GR→INV→RFP 3-level→OR) | `node scripts/testing/l3_s152_chain_a.mjs` |
| `scripts/testing/l3_s152_chain_bc.mjs` | S152-B01 to B04, C01 to C09 (dual + CEO) | `node scripts/testing/l3_s152_chain_bc.mjs` |
| `scripts/testing/l3_s152_edge_cases.mjs` | S152-R01 to R05 (reject, partial, variance) | `node scripts/testing/l3_s152_edge_cases.mjs` |
| `scripts/testing/l3_s152_dashboards.mjs` | S152-D01 to D07 (AP CC + procurement pages) | `node scripts/testing/l3_s152_dashboards.mjs` |
| `scripts/testing/l3_s152_run_all.mjs` | Master runner — all scripts in sequence | `node scripts/testing/l3_s152_run_all.mjs` |

**Scenario definitions:** `docs/testing/scenarios/modules/s152-procurement-e2e.md`
**Scenario index:** `docs/testing/scenarios/index.yaml` (key: `procurement-e2e`, command: `flow-procure-pay`)

### Run Commands

```bash
# Full run (all 4 scripts in sequence)
node scripts/testing/l3_s152_run_all.mjs

# Individual chains
node scripts/testing/l3_s152_run_all.mjs chain-a     # ≤500K Mae-only
node scripts/testing/l3_s152_run_all.mjs chain-bc     # >500K dual + >1M CEO
node scripts/testing/l3_s152_run_all.mjs edge         # Rejections + variance
node scripts/testing/l3_s152_run_all.mjs dashboards   # AP CC + procurement pages
```

### Evidence Output

All evidence written to `output/l3/S152/`:
- `chain_a_results.json`, `chain_bc_results.json`, `edge_cases_results.json`, `dashboards_results.json`
- `*_form_submissions.json`, `*_api_mutations.json`, `*_state_verification.json`
- `screenshots/*.png`
- `aggregate_results.json` (combined results from master runner)

---

## Key File Paths

| What | Path |
|------|------|
| Procurement API (132 endpoints) | `hrms/api/procurement.py` |
| PR DocType | `hrms/hr/doctype/bei_purchase_requisition/bei_purchase_requisition.json` |
| PO DocType | `hrms/hr/doctype/bei_purchase_order/bei_purchase_order.json` |
| GR DocType | `hrms/hr/doctype/bei_goods_receipt/bei_goods_receipt.json` |
| Invoice DocType | `hrms/hr/doctype/bei_invoice/bei_invoice.json` |
| Payment Request DocType | `hrms/hr/doctype/bei_payment_request/bei_payment_request.json` |
| Frontend — PR new form | `bei-tasks/app/dashboard/procurement/purchase-requisitions/new/page.tsx` |
| Frontend — PO new form | `bei-tasks/app/dashboard/procurement/purchase-orders/new/page.tsx` |
| Frontend — GR new form | `bei-tasks/app/dashboard/procurement/goods-receipts/new/page.tsx` |
| Frontend — Invoice new form | `bei-tasks/app/dashboard/procurement/invoices/new/page.tsx` |
| Frontend — Payment new form | `bei-tasks/app/dashboard/procurement/payments/new/page.tsx` |
| Frontend — Supplier new form | `bei-tasks/app/dashboard/procurement/suppliers/new/page.tsx` |
| Frontend — PO detail + approval | `bei-tasks/app/dashboard/procurement/purchase-orders/[id]/page.tsx` |
| Frontend — Payment detail + 4-level | `bei-tasks/app/dashboard/procurement/payments/[id]/page.tsx` |
| Frontend — AP Command Center | `bei-tasks/app/dashboard/accounting/ap-command-center/page.tsx` |
| Frontend — Procurement hooks | `bei-tasks/hooks/use-procurement.ts` |
| Frontend — RBAC | `bei-tasks/lib/roles.ts` |
| Frontend — Routes | `bei-tasks/lib/constants.ts` |
| Test accounts | `memory/testing-accounts.md` |
| E2E patterns | `memory/e2e-testing.md` |
