# Procurement Module - Consolidated Plan

**Status:** BUGFIX IN PROGRESS (7 bugs from Feb 7 audit)
**Module URL:** https://my.bebang.ph/dashboard/procurement
**Last Updated:** 2026-02-07
**Bugfix Spec:** `specs/procurement-bugfix/`

---

## Plan History

| Date | Milestone |
|------|-----------|
| 2026-01-11 | Procurement authority memo issued (Mae/Butch/CEO signing rules) |
| 2026-01-11 | Mae's procurement runbook created |
| 2026-01-11 | Cayla's 1-week training plan created |
| 2026-02-03 | Module architecture designed, DocTypes and API specified |
| 2026-02-03 | Full execution plan written (5 waves, 30+ tasks) |
| 2026-02-04 | Phase 1 complete: 6 DocTypes, 20+ API endpoints, 20 frontend pages, 92% E2E pass |
| 2026-02-04 | Internal audit findings received (Angela Godino, 12 critical gaps) |
| 2026-02-05 | Phase 2 complete: All 8 audit control sections (30 tasks) implemented and deployed |
| 2026-02-07 | Full audit: 63 backend endpoints tested, 13 frontend pages verified, 7 bugs identified |
| 2026-02-07 | Bugfix spec created: `specs/procurement-bugfix/` (research, requirements, design, tasks) |

---

## 1. Business Context

### What It Replaces
Two fragmented AppSheet apps (Procurement Compliance + RFP) with a unified module on my.bebang.ph.

### Key Metrics (From Legacy System)
| Metric | Value |
|--------|-------|
| Total Suppliers | 80 |
| Total PO Value | PHP 153.3M |
| Total Invoiced | PHP 95.5M |
| Outstanding | ~PHP 57.7M |
| Active POs | 422 |

---

## 2. Business Rules

### 2.1 PO Approval Thresholds
- **Below PHP 500,000:** Mae Karazi approves
- **PHP 500,000 and above:** Mae AND Butch Formoso (CFO) - both required
- **Anti-splitting rule:** Related purchases for same supplier/requirement treated as one commitment

### 2.2 Non-Recurring Purchases
CEO written approval required first (regardless of amount) for:
- New suppliers or service providers
- New products/ingredients/SKUs
- Outsourced production
- Equipment/capex
- Non-routine repairs/maintenance
- Subscriptions, retainers, contracts
- Purchases requiring deposit/downpayment

### 2.3 Payment Modes
- Bank Transfer: Requires bank_name, account_number
- Check: Requires payee name
- GCash/Maya: **NOT ALLOWED**

### 2.4 Supplier Requirements
- TIN: Required for tax compliance
- BIR 2307: Required before payment processing
- SEC Certificate: Required for corporations
- Bank details: CFO must approve all supplier bank accounts

### 2.5 Three-Way Match (Mandatory)
Payment requires all three to match:
1. **Signed PO** (what BEI approved to buy)
2. **DR / Receiving Confirmation** (what BEI actually received)
3. **Supplier Invoice** (what BEI is being billed)

Partial deliveries: pay only for quantity received; remaining PO balance stays open.

### 2.6 Four-Level Payment Approval
1. **Review:** Requestor's supervisor
2. **Budget:** Department head
3. **CFO:** Butch Formoso
4. **CEO:** For amounts >PHP 1M or special cases

### 2.7 Contracts
Any contract/agreement/addendum must be signed by **CFO AND CEO** (per Memo 0925-001).

### 2.8 Valid vs Invalid Commitments
**Valid:** Internal request + formal PO with required signatures + supplier invoice referencing PO + receiving confirmation.
**Invalid:** Verbal approvals, chat approvals, emails from unauthorized staff, POs signed by non-signatories.

---

## 3. Team Roles

| Role | Responsibility |
|------|----------------|
| **Mae** (Procurement Approver) | Final purchase decisions, price verification, PO approval |
| **Cayla** (Procurement Admin) | Request preparation, invoice/DR collection, RFP organization |
| **Butch** (CFO) | PO approval >PHP 500K, payment approval, bank detail verification |
| **Aldrin** (Finance) | RFP review, budget approval, payment processing |
| **Ian** (Warehouse) | Goods receipt approval |
| **Sam** (CEO) | Non-recurring purchase approval, final payment approval >PHP 1M |

---

## 4. Architecture

### Backend (Frappe - BEI-ERP repo)
```
hrms/
├── api/
│   └── procurement.py          # All procurement APIs (63 endpoints)
└── hr/
    └── doctype/
        ├── bei_supplier/
        ├── bei_purchase_requisition/
        ├── bei_pr_item/
        ├── bei_purchase_order/
        ├── bei_po_item/
        ├── bei_goods_receipt/
        ├── bei_gr_item/
        ├── bei_invoice/
        └── bei_payment_request/
```

### Frontend (bei-tasks repo)
```
app/dashboard/procurement/
├── page.tsx                    # Executive Dashboard
├── suppliers/
│   ├── page.tsx               # Supplier list
│   ├── [id]/page.tsx          # Supplier detail
│   ├── [id]/edit/page.tsx     # Supplier edit
│   └── new/page.tsx           # Add supplier
├── requisitions/
│   ├── page.tsx               # PR list
│   ├── [id]/page.tsx          # PR detail
│   └── new/page.tsx           # Create PR
├── orders/
│   ├── page.tsx               # PO list
│   ├── [id]/page.tsx          # PO detail
│   └── new/page.tsx           # Create PO
├── receipts/
│   ├── page.tsx               # GR list
│   ├── [id]/page.tsx          # GR detail
│   └── new/page.tsx           # Create GR
├── invoices/
│   ├── page.tsx               # Invoice list
│   └── [id]/page.tsx          # Invoice detail
├── payments/
│   ├── page.tsx               # RFP list
│   ├── [id]/page.tsx          # RFP detail
│   └── new/page.tsx           # Create RFP
└── reports/
    └── page.tsx               # Analytics
```

### Module Flow
```
PR (Request) → PO (Order) → GR (Receive) → Invoice (Bill) → RFP (Pay)
                  ↓                                            ↓
           Dual Approval                               4-Level Approval
           (>500K: Mae+Butch)                    (Review→Budget→CFO→CEO)
```

---

## 5. DocTypes

### 5.1 BEI Supplier
| Field | Type | Notes |
|-------|------|-------|
| supplier_code | Data | Unique, required |
| supplier_name | Data | Required |
| frappe_supplier | Link → Supplier | Links to Frappe native |
| status | Select | Active / Inactive / Pending Verification / Blacklisted |
| contact_person, contact_number, email, address | Data/Text | Contact info |
| tin | Data | Required for >PHP 250K annual |
| sec_registration | Data | For corporations |
| bir_2307, sec_certificate, business_permit | Attach | Compliance docs |
| bank_name, bank_account_name, bank_account_number | Data | Payment info |
| payment_terms | Link → Payment Terms | Default terms |
| total_po_count, total_po_value, total_outstanding | Currency/Int | Read-only metrics |

### 5.2 BEI Purchase Order
| Field | Type | Notes |
|-------|------|-------|
| po_no | Data | Auto-generated: PO-YYYY-##### |
| pr_reference | Link → BEI Purchase Requisition | Optional source |
| supplier | Link → BEI Supplier | Required |
| transaction_date, delivery_date | Date | PO and expected delivery dates |
| items | Table → BEI PO Item | Line items |
| subtotal, discount_amount, delivery_fee, vat_amount, grand_total | Currency | Totals |
| status | Select | Draft → Pending → Approved → Received |
| requires_dual_approval | Check | Auto-set when >PHP 500K |
| cpo_approved_by, cfo_approved_by | Link → User | Approval tracking |
| frappe_po | Link → Purchase Order | Frappe native link |

### 5.3 BEI Goods Receipt
| Field | Type | Notes |
|-------|------|-------|
| gr_no | Data | Auto-generated: GR-YYYY-##### |
| purchase_order | Link → BEI Purchase Order | Required |
| receipt_date | Date | When goods arrived |
| items | Table → BEI GR Item | Received items with quantity and unit_cost |
| status | Select | Draft → Pending Approval → Approved → Invoiced |

### 5.4 BEI Invoice
| Field | Type | Notes |
|-------|------|-------|
| invoice_no | Data | Auto-generated: INV-YYYY-##### |
| purchase_order, goods_receipt | Links | Source references |
| supplier | Link → BEI Supplier | |
| grand_total | Currency | Invoice amount |
| status | Select | Draft → Matched → Approved |

### 5.5 BEI Payment Request (RFP)
| Field | Type | Notes |
|-------|------|-------|
| rfp_id | Data | Auto-generated: PAY-YYYY-##### |
| invoice_reference, gr_reference, po_reference | Links | Source chain |
| supplier | Link → BEI Supplier | |
| payee_name | Data | Required |
| payment_mode | Select | Bank Transfer / Check |
| payment_amount | Currency | Net payable |
| vat_sales, vat_amount, ewt_amount, other_deductions, net_amount | Currency | Tax breakdown |
| status | Select | Draft → Pending Review → Budget → CFO → CEO → Approved → Paid |
| review/budget/cfo/ceo approval fields | Link + Select + Datetime | 4-level workflow |
| payment_reference, deposit_slip | Data/Attach | Payment proof |

---

## 6. API Endpoints (63 functions)

**File:** `hrms/api/procurement.py`
**Audit:** 2026-02-07 - 63/63 endpoints reachable (30 PASS, 33 EXISTS, 0 FAIL)

### Supplier (5)
| Endpoint | Description |
|----------|-------------|
| `get_suppliers` | Paginated list with search/filter |
| `get_supplier` | Single supplier detail |
| `create_supplier` | Create with duplicate detection (phone, email, bank, TIN) |
| `update_supplier` | Update supplier details |
| `get_supplier_metrics` | PO count, total value, outstanding |

### Purchase Requisition (7)
| Endpoint | Description |
|----------|-------------|
| `get_purchase_requisitions` | Paginated PR list |
| `get_purchase_requisition` | Single PR with items |
| `create_purchase_requisition` | Create PR with items |
| `submit_pr_for_approval` | Submit PR for approval |
| `approve_pr` | Approve PR |
| `reject_pr` | Reject PR with reason |
| `convert_pr_to_po` | Convert approved PR to PO |

### Purchase Order (9)
| Endpoint | Description |
|----------|-------------|
| `get_purchase_orders` | Paginated PO list |
| `get_purchase_order` | Single PO with items and approvals |
| `create_purchase_order` | Create PO (price variance check, TIN validation) |
| `submit_po_for_approval` | Submit PO for approval workflow |
| `approve_po_mae` | Mae approves (first approval) |
| `approve_po_butch` | Butch approves (second, for >PHP 500K) |
| `reject_po` | Reject PO with reason |
| `send_po_to_supplier` | Generate PDF and email supplier |
| `get_pending_po_approvals` | List POs awaiting approval |

### Goods Receipt (7)
| Endpoint | Description |
|----------|-------------|
| `get_goods_receipts` | Paginated GR list |
| `get_goods_receipt` | Single GR with items |
| `create_goods_receipt` | Create GR from PO (validates approval status) |
| `load_gr_from_po` | Pre-fill GR items from PO |
| `submit_goods_receipt` | Submit GR for inspection |
| `complete_gr_inspection` | Mark GR inspection passed/failed |
| `get_pending_gr_for_po` | Items pending receipt for a PO |

### Invoice (7)
| Endpoint | Description |
|----------|-------------|
| `get_invoices` | Paginated invoice list |
| `get_invoice` | Single invoice with match details |
| `create_invoice` | Create invoice (validates 3-way match, date sequence) |
| `submit_invoice_for_verification` | Submit for match verification |
| `verify_invoice_match` | Run PO-GR-Invoice match check |
| `approve_invoice_variance` | Approve variance with notes |
| `reject_invoice_variance` | Reject variance with reason |

### Payment Request (10)
| Endpoint | Description |
|----------|-------------|
| `get_payment_requests` | Paginated payment list |
| `get_payment_request` | Single RFP with approval history |
| `create_payment_request` | Create RFP (validates GR exists, partial delivery limit) |
| `submit_payment_for_approval` | Submit RFP for review workflow |
| `approve_payment_review` | Level 1: Supervisor review |
| `approve_payment_budget` | Level 2: Budget approval |
| `approve_payment_cfo` | Level 3: CFO approval |
| `approve_payment_ceo` | Level 4: CEO approval |
| `reject_payment_request` | Reject at any level with reason |
| `mark_payment_complete` | Mark paid with reference/proof |
| `get_pending_payment_approvals` | List RFPs awaiting approval |

### Dashboard & Reports (8)
| Endpoint | Description |
|----------|-------------|
| `get_dashboard_kpis` | All dashboard metrics |
| `get_outstanding_by_supplier` | Outstanding by supplier |
| `get_aging_analysis` | AP aging buckets |
| `get_monthly_po_trend` | Monthly PO value trend |
| `get_payment_schedule` | Upcoming payment schedule |
| `get_supplier_performance` | Supplier delivery/quality metrics |
| `get_ap_aging_report` | Detailed AP aging with custom buckets |
| `get_supplier_aging` | Aging for specific supplier |

### Audit Controls (7)
| Endpoint | Description |
|----------|-------------|
| `get_open_po_aging` | Open PO aging report |
| `check_price_variance` | Historical price check (5% threshold) |
| `get_price_history` | Price history for item/supplier |
| `get_single_source_suppliers` | Concentration risk report |
| `get_supplier_duplicates` | Duplicate contact detection |
| `get_supplier_data_quality` | Missing docs/TIN report |
| `get_received_value_for_po` | Received vs ordered value |

### Billing (2)
| Endpoint | Description |
|----------|-------------|
| `send_billing_statement` | Send billing statement |
| `get_billing_list` | List billing records with filters |

---

## 7. RBAC

| Role | Capabilities |
|------|-------------|
| Procurement User | Create PR, view POs, create GR |
| Procurement Manager (Mae) | Approve PR, create/approve PO (<PHP 500K) |
| CFO (Butch) | Approve PO (>PHP 500K), approve RFP |
| CEO (Sam) | Non-recurring approval, final RFP approval |
| Finance User | Create/view payment requests |
| Finance Manager (Aldrin) | Review RFP, budget approval |
| Warehouse User (Ian) | Create/approve GR |

---

## 8. Audit Controls (From Internal Audit - Jan 30, 2026)

**Auditor:** Angela Godino (Internal Audit)
**Scope:** AppSheet procurement data, Sept 26, 2025 - Jan 19, 2026

### 8.1 Findings and System Controls Implemented

| # | Finding | Risk | System Control |
|---|---------|------|----------------|
| 1 | PO paid without Goods Receipt | HIGH | Block RFP/Invoice creation without approved GR |
| 2 | Invoice dated before PO | HIGH | Date sequence validation (Invoice >= PO >= GR) |
| 3 | >PHP 500K without CFO approval | HIGH | Block GR/Invoice/Payment when dual approval incomplete |
| 4 | Full payment for partial delivery | HIGH | Payment capped at received value |
| 5 | Duplicate supplier contacts | MEDIUM | Hard block on duplicate phone/bank/TIN; warning on email |
| 6 | Single-source concentration | MEDIUM | Auto-flag items >80% from one supplier |
| 7 | Price manipulation | MEDIUM | 5% variance alert from 90-day average |
| 8 | Suppliers not in master list | MEDIUM | TIN required for >PHP 250K annual; data quality report |

### 8.2 High-Risk Suppliers Flagged

**Not in Master List (require onboarding):**
| Supplier | Total Paid | Action |
|----------|-----------|--------|
| Max's Bakeshop, Inc. | PHP 10,016,622 | Verify TIN/BIR 2303 |
| M Tealicious Milktea Supplies | PHP 678,720 | Validate and add |
| Marivic's Ube | PHP 530,400 | Validate and add |
| YANA Chemodities Inc. | PHP 126,000 | Validate and add |
| PV'S TISSUE TRADING | PHP 89,500 | Validate and add |
| Schalen Sales Corporation | PHP 54,500 | Validate and add |
| RESTAURANT DEPO | PHP 19,800 | Validate and add |

**Single-Source Concentration Risk:**
| Supplier | Total PO | Items | Risk |
|----------|----------|-------|------|
| RIGHT GOODS SOUTH OPERATIONS INC. | PHP 23,649,930 | 1 | Single item, massive spend |
| MIDDLEBY PHILIPPINES CORPORATION | PHP 12,115,871 | 8 | Equipment dependency |
| 1 To 1 Marketing, Inc. | PHP 10,191,048 | 3 | High concentration |
| CLE ACE CORPORATION | PHP 9,298,104 | 4 | High concentration |
| Griffift Foods Philippines Inc. | PHP 8,523,182 | 7 | Ingredient dependency |

**Duplicate Contact Info (Fraud Risk):**
| Supplier 1 | Supplier 2 | Shared | Risk |
|------------|------------|--------|------|
| LABELMEN ENTERPRISES | MGRACE Creative | Phone 09454131740 | Same phone, different names |
| Handyware Philippines | RHODIUM PREMIER TECHNOLOGY | Phone 09954866110 | Same phone, different names |
| Vanj's Homemade Native Delicacies | Vangie Homemade Food Trading | Phone 09677627901 | Supplier rename |

---

## 9. E2E Test Results (Final)

**Date:** 2026-02-04
**Pass Rate:** 92% (24/26 tests)

| Phase | Tests | Pass | Fail | Notes |
|-------|-------|------|------|-------|
| Frontend Fix | 1 | 1 | 0 | QueryClientProvider added |
| Backend Fix | 1 | 1 | 0 | SQL columns corrected |
| Frappe Master Data | 5 | 5 | 0 | Accounts, Warehouse, Price List |
| Supplier CRUD | 1 | 1 | 0 | UI-CREATED-001 via UI |
| PO Dual Approval | 4 | 4 | 0 | PHP 672K - Mae + Butch approved |
| Goods Receipt | 1 | 1 | 0 | GR-2026-00041, GR-2026-00044 |
| Invoice 3-Way Match | 2 | 1 | 1 | Variance acknowledged |
| Payment 4-Level | 5 | 5 | 0 | Full workflow complete |
| Dashboard KPIs | 6 | 5 | 1 | Minor chart issue |
| **TOTAL** | **26** | **24** | **2** | **92% Pass Rate** |

### Test Records Created
| DocType | Record | Notes |
|---------|--------|-------|
| BEI Supplier | UI-CREATED-001 | Created via UI |
| BEI Purchase Order | PO-2026-00040 | PHP 672K dual approval |
| Frappe Purchase Order | PUR-ORD-2026-00001 | Auto-created on approval |
| BEI Goods Receipt | GR-2026-00041, GR-2026-00044 | Linked to PO |
| BEI Invoice | INV-2026-00042 | 3-way match verified |
| BEI Payment Request | PAY-2026-00043 | 4-level approval complete |

---

## 10. Deployment

### Production Deployments
| Component | Platform | Commits | Status |
|-----------|----------|---------|--------|
| Frontend (20 pages) | Vercel | `4240dc9`, `192f94c`, `1941be6` | Deployed |
| Backend API (20+ endpoints) | AWS Docker | `21122c79`, `33ff73a3e` | Deployed |
| Audit Controls (Phase 2) | AWS Docker | Workflows #235, #236, #237 | Deployed |

### Bugs Fixed During Implementation
| Bug | Root Cause | Fix |
|-----|------------|-----|
| QueryClientProvider missing | Layout.tsx missing wrapper | Added provider |
| SQL column names wrong | `net_amount` vs `payment_amount` | Fixed queries |
| supplier_performance 500 | Wrong column names | Fixed to correct fields |
| GR rate not saved | API field mismatch | Map `rate` → `unit_cost` |
| PO form blocked | ItemSelector combobox broken | Replaced with Input |
| Supplier edit missing | No edit page existed | Created full edit page |

---

## 11. Quick Commands

### Test API
```bash
FRAPPE_KEY=$(doppler secrets get FRAPPE_API_KEY --project bei-erp --config dev --plain)
FRAPPE_SECRET=$(doppler secrets get FRAPPE_API_SECRET --project bei-erp --config dev --plain)

# Suppliers
curl -s "https://hq.bebang.ph/api/method/hrms.api.procurement.get_suppliers?page=1&page_size=5" \
  -H "Authorization: token ${FRAPPE_KEY}:${FRAPPE_SECRET}"

# Dashboard KPIs
curl -s "https://hq.bebang.ph/api/method/hrms.api.procurement.get_dashboard_kpis" \
  -H "Authorization: token ${FRAPPE_KEY}:${FRAPPE_SECRET}"
```

### E2E Test
```
/test flow procurement
```

---

## 12. File Locations

| Purpose | Location |
|---------|----------|
| Backend API | `hrms/api/procurement.py` |
| DocTypes | `hrms/hr/doctype/bei_supplier/`, `bei_purchase_order/`, etc. |
| Frontend repo | `F:\Dropbox\Projects\bei-tasks` |
| Frontend hooks | `bei-tasks/hooks/use-procurement.ts` |
| Deploy workflow | `.github/workflows/build-and-deploy.yml` |
| Internal audit PDF | `F:\Downloads\Procurement Observation Review.pptx.pdf` |
| Governance memo | `docs/plans/Completed/MEMO_PROCUREMENT_AUTHORITY_AND_VENDOR_CONTROLS_2026-01-11.md` |
| Mae's runbook | `docs/plans/Completed/PROCUREMENT_MAE_RUNBOOK_2026-01-11.md` |
| Training plan | `docs/plans/Completed/PROCUREMENT_TRAINING_PLAN.md` |

---

## 13. Feb 7 Comprehensive Audit & Bug Fixes

### 13.1 Audit Scope
| Area | Coverage | Result |
|------|----------|--------|
| Backend API | 63/63 endpoints tested | 100% reachable |
| Frontend Pages | 13/13 pages audited | All load correctly |
| Business Rules | 8/8 rules verified | All implemented |
| Audit Controls | 8/8 controls tested | All deployed |
| **Bugs Found** | **7** | **3 critical, 2 medium, 2 low** |

### 13.2 Bug Tracker

| # | Bug | Severity | Status | Fix |
|---|-----|----------|--------|-----|
| BUG-1 | Invoice PO link -> `/purchase-orders/undefined` | CRITICAL | OPEN | Add `purchase_order` to `get_invoices()` SELECT |
| BUG-2 | Payment supplier links -> `/suppliers/null` | CRITICAL | OPEN | Add `supplier` to `get_payment_requests()` response |
| BUG-3 | `get_received_value_for_po` returns 500 | CRITICAL | OPEN | Fix table/field names in SQL query |
| BUG-4 | Supplier list shows "PHP NaN" | MEDIUM | OPEN | Align field name (`total_po_value` → `total_amount`) |
| BUG-5 | Sidebar badges show "0" (ambiguous) | MEDIUM | OPEN | Add "pending" label to badge counts |
| BUG-6 | Goods Receipt Log missing "Coming Soon" | LOW | OPEN | Add `comingSoon` flag to report entry |
| BUG-7 | PO Detail shows "0 line items" | LOW | OPEN | Add items subquery to `get_purchase_order()` |

### 13.3 Fix Plan

**Bugfix spec:** `specs/procurement-bugfix/` (research.md, requirements.md, design.md, tasks.md)

**Execution order:**
1. Fix 5 backend bugs in `procurement.py` (TASK-1)
2. Code review backend (TASK-2)
3. Deploy backend via PR (TASK-3)
4. Fix 2 frontend bugs in `bei-tasks` (TASK-4)
5. Code review frontend (TASK-5)
6. Deploy frontend via PR (TASK-6)
7. E2E verification all 7 bugs fixed (TASK-7)
8. Update this plan (TASK-8)

### 13.4 Full Audit Report
`scratchpad/PROCUREMENT_AUDIT_REPORT_2026-02-07.md`

---

## 14. Data Migration (Pending)

| Data Set | Source | Records | Status |
|----------|--------|---------|--------|
| Suppliers | Google Sheets | 80 | Pending |
| Historical POs | Google Sheets | 422 | Pending |
| Historical GRs | Google Sheets | 695 | Pending |
| Payment history | Google Sheets | TBD | Pending |

**Source Sheets:**
- Procurement: `1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q`
- RFP: `14fdBT-pQoCpQuvoFcENiMiMY3cpa2YZ80-j2UTMI484`

---

## 15. Evidence & Reports

| File | Purpose |
|------|---------|
| `scratchpad/PROCUREMENT_AUDIT_REPORT_2026-02-07.md` | Full audit report (63 endpoints, 13 pages, 7 bugs) |
| `scratchpad/procurement_audit_01_dashboard.png` | Dashboard screenshot |
| `scratchpad/procurement_audit_02_suppliers.png` | Suppliers list (shows NaN bug) |
| `specs/procurement-bugfix/` | Complete bugfix spec (research, requirements, design, tasks) |
