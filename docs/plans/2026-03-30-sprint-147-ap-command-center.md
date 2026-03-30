# Sprint S147 — AP Command Center (Finance Team Workspace)

```yaml
sprint: S147
branch: s147-ap-command-center
status: GO
plan_file: docs/plans/2026-03-30-sprint-147-ap-command-center.md
depends_on: S145
registry_row: "| S147 | Sprint 147 | s147-ap-command-center | — | GO — AP Command Center |"
completed_date:
execution_summary:
```

---

## Why This Exists

The accounting team manages P62M in AP using a Google Sheet because my.bebang.ph has no finance-friendly payables workspace. The existing procurement module serves the procurement team (ordering, receiving, approvals). The existing accounting module has shells for SOA, pending payments, and OR tracking but they're not designed for daily AP management.

**This sprint builds a workspace that's better than their spreadsheet** — not a copy of it.

**Backend status:** 132 API endpoints exist in `hrms/api/procurement.py`. 3 new endpoints needed for this sprint (inline in Phase 1). This is primarily a frontend build with minor backend additions.

---

## Design Rationale (For Cold-Start Agents)

### The complete chain (all connected, no silos)

```
RFP Request -> PR -> PO -> GR -> Invoice -> Payment Request -> Payment -> OR
|               |    |    |      |          |                |         |
|               |    |    |      |          |                |         +- OR Follow-Up
|               |    |    |      |          |                +- Bank Transfer / Check
|               |    |    |      |          +- 4-Level Approval (Reviewer->Budget->CFO->CEO)
|               |    |    |      +- 3-Way Match (PO<->GR<->Invoice)
|               |    |    +- Quality Inspection
|               |    +- Mae/Butch/CEO Approval
|               +- Department Approval
+- RFP Type determines GL account + EWT rate + approval routing
```

### What the accounting team needs (from their spreadsheet analysis)

| Need | Their Sheet | AP Command Center |
|------|-------------|-------------------|
| See all unpaid invoices | Flat list filtered by status | Filterable table with aging badges |
| Track payment status | FIN STATUS column (manual) | Real-time from BEI Payment Request |
| Aging analysis | Formula-driven aging columns | Interactive donut chart + drill-down |
| Mode of payment | MOP column | Tracked on Payment Request |
| Outstanding per supplier | AP AGING tab pivot | Supplier drill-down with history |
| Mark as paid | Edit cell manually | Click button -> status changes -> OR tracking starts |
| Bird's eye totals | SUBTOTAL formulas in row 1 | KPI cards (auto-refresh) |

### Architecture: One route, tab-based views

Route: `/dashboard/accounting/ap-command-center`

Tabs: Overview | Invoices | Payments | Aging | Supplier Ledger

**Cross-tab state management:** URL search params pattern.
- Tab switch: `?tab=invoices`
- Aging filter: `?tab=invoices&aging=31-60`
- Supplier filter: `?tab=supplier-ledger&supplier=SUP-0001`
- Read params via `useSearchParams()`, update via `router.push()`

### RBAC

| Role | roles.ts Constant | Access |
|------|-------------------|--------|
| Accounts Manager (finance team) | `HQ_FINANCE` | Full access — view, approve payments, mark paid, upload OR |
| Procurement Manager (Mae) | `PROCUREMENT_MANAGER` | View invoices + payments, approve Level 1 |
| CFO (Butch) | `HQ_FINANCE` | View + approve Level 3 (CFO) |
| CEO (Sam) | `SYSTEM_MANAGER` | View + approve Level 4 (CEO) |
| HQ User | `HQ_USER` | View only |

Module guard: Add `MODULES.AP_COMMAND_CENTER` to `lib/roles.ts`.

---

## Agent Boot Sequence (FIRST ACTION)

```bash
# 1. Branch setup
git fetch origin production
git checkout -b s147-ap-command-center origin/production
git branch --show-current  # MUST return s147-ap-command-center

# 2. Read this plan fully
# 3. Read Requirements Regression Checklist
# 4. Begin Phase 1
```

**HARD BLOCKER:** If `git branch --show-current` does not return `s147-ap-command-center`, STOP. Do not write code on any other branch.

---

## Phase 1: Backend Prerequisites + Route Shell (8 units)

### 1.1: Create 3 new backend endpoints — 3 units [BUILD]

In `hrms/api/procurement.py`, create:

**a) `update_invoice_payment_status(invoice_name, payment_status, notes=None)`**
- Updates `payment_status` on BEI Invoice (Unpaid / Partially Paid / Paid)
- Writes audit trail to `verification_notes` with timestamp and user
- Must call `set_backend_observability_context(module="finance", action="update_invoice_payment_status", mutation_type="update")`
- Permission check: only `Accounts Manager` or `System Manager` roles

**b) `get_supplier_transaction_timeline(supplier, limit=50)`**
- Returns unified chronological list: POs + GRs + Invoices + Payments + ORs for one supplier
- Each row: `{date, doc_type, doc_name, description, amount, status}`
- Client-side stitching of 5 queries is too slow for 50+ transactions — backend does the merge
- Must call `set_backend_observability_context(module="finance", action="get_supplier_transaction_timeline")`

**c) `bulk_update_invoice_acctg_status(invoice_names, acctg_status)`**
- Sets `verification_notes` to include the accounting status (e.g., "Transferred to Finance - 2026-03-30 by sam@bebang.ph")
- We use `verification_notes` rather than adding a new DocType field — simpler, no migration needed
- Must call `set_backend_observability_context(module="finance", action="bulk_update_invoice_acctg_status", mutation_type="update")`

### 1.2: Create AP Command Center route shell — 2 units [BUILD]

Create: `bei-tasks/app/dashboard/accounting/ap-command-center/page.tsx`

Tab layout with 5 tabs using Shadcn Tabs component. URL search params for tab state:
```tsx
const searchParams = useSearchParams()
const activeTab = searchParams.get('tab') || 'overview'
```

Add to sidebar navigation under "Finance & Accounting" section.

### 1.3: Create hooks for AP Command Center — 2 units [BUILD]

Add to `bei-tasks/hooks/use-procurement.ts`:
- `useAPDashboardKPIs()` — wraps `get_dashboard_kpis` (refetchInterval: 60000)
- `useAPAging()` — wraps `get_aging_analysis`
- `useAPOutstandingBySupplier()` — wraps `get_outstanding_by_supplier`
- `useAPInvoices(filters)` — wraps `get_invoices` with `aging_bucket` filter param
- `useUpdateInvoicePaymentStatus()` — mutation hook for new endpoint
- `useSupplierTimeline(supplier)` — wraps new `get_supplier_transaction_timeline`
- `useBulkUpdateAcctgStatus()` — mutation hook for new endpoint

Reuse any existing hooks that already cover these. Check before creating duplicates.

### 1.4: RBAC setup — 1 unit [EXTEND]

In `bei-tasks/lib/roles.ts`:
- Add `AP_COMMAND_CENTER` to `MODULES` map
- Map allowed roles: `HQ_FINANCE`, `PROCUREMENT_MANAGER`, `SYSTEM_MANAGER`, `HQ_USER`
- Define permission levels: `canApprovePayment`, `canEditInvoiceStatus`, `canUploadOR`

---

## Phase 2: Overview Tab (10 units)

### 2.1: KPI Cards Row — 3 units [BUILD]

6 KPI cards, auto-refresh every 60 seconds:

| Card | Source | Color |
|------|--------|-------|
| Total Outstanding | `SUM(balance_due) WHERE payment_status != 'Paid'` | Red if > P50M |
| Overdue Amount | Same + `due_date < TODAY()` | Red always |
| Not Yet Due | Outstanding - Overdue | Green |
| Avg Payment Days | From Payment Requests (paid last 90 days) | Amber if > 30 |
| Pending Approvals | Payment Requests in approval queue | Badge count |
| Awaiting OR | Payments paid but no OR received | Badge count |

### 2.2: AP Aging Donut Chart — 2 units [EXTEND]

Interactive donut chart (already on procurement dashboard — adapt):
- Buckets: Current, 1-30, 31-60, 61-90, 91-120, 120+
- Click a bucket -> `router.push(?tab=invoices&aging=31-60)`
- Total in center

### 2.3: Upcoming Payments Table — 2 units [BUILD]

Next 10 invoices by due date:
- Supplier, Invoice No, Amount, Due Date, Days Until Due, Status
- Click row -> opens invoice detail slide-out

### 2.4: Outstanding by Supplier Bar Chart — 2 units [EXTEND]

Top 10 suppliers by outstanding balance (adapt from procurement dashboard).
Click bar -> `router.push(?tab=supplier-ledger&supplier=SUP-XXXX)`

### 2.5: Quick Actions — 1 unit [BUILD]

Buttons: Record Payment | Upload OR | View Approval Queue | Generate SOA (navigates to existing `/dashboard/accounting/soa/`)

---

## Phase 3: Invoices Tab (12 units)

This is the core — replaces the accounting team's spreadsheet.

### 3.1: Invoice Table with Aging Badges — 4 units [BUILD]

Table columns:
| Column | What | Interactive? |
|--------|------|-------------|
| Supplier | Name + link | Click -> Supplier Ledger tab |
| Invoice No | Supplier invoice number | |
| Invoice Date | Date on invoice | |
| Due Date | Payment due date | |
| Amount | Grand total | PHP format |
| Balance Due | Outstanding | Red if overdue |
| Aging | Days overdue badge (green/amber/red) | Auto-calculated |
| Payment Status | Unpaid / Partially Paid / Paid | **Inline dropdown** |
| Match Status | 3-way match result | Badge |
| PO | Linked PO number | Click -> PO detail |
| Actions | Pay / View / History | Buttons |

Filters: Status, Supplier, Aging bucket (from URL param), Date range, Search
Sort: By due date (default), amount, supplier, aging

**HARD BLOCKER:** The inline status dropdown must call `useUpdateInvoicePaymentStatus()` hook -> `update_invoice_payment_status()` API. Status changes must be audited. Do NOT save directly to the DocType.

### 3.2: Inline Payment Recording — 3 units [BUILD]

Click "Pay" on an invoice -> slide-out panel:
- Payment amount (pre-filled with balance_due)
- Payment mode: Bank Transfer / Check
- Payment date
- Transaction reference / check number
- Upload payment proof (via existing file upload)
- Submit -> Creates BEI Payment Request + marks invoice as Paid

### 3.3: 3-Way Match Indicator — 2 units [EXTEND]

Each invoice row shows match status:
- Matched (PO = GR = Invoice within tolerance)
- Variance Detected (show amount)
- Not Matched (missing GR or PO)
- Click -> expands to show PO amount, GR amount, Invoice amount side-by-side

### 3.4: Bulk Actions — 2 units [BUILD]

Select multiple invoices -> Bulk actions:
- Export to CSV (client-side)
- Bulk mark as "Transferred to Finance" (calls `useBulkUpdateAcctgStatus()`)
- Generate payment batch

### 3.5: Invoice Detail Slide-Out — 1 unit [EXTEND]

Click invoice row -> slide-out showing:
- Full invoice details
- Linked PO (with PO details)
- Linked GR (with GR details)
- Payment history
- OR status
- Timeline (created -> matched -> paid -> OR received)

---

## Phase 4: Payments Tab (12 units)

### 4.1: Payment Request Table — 4 units [BUILD]

Table columns:
| Column | What |
|--------|------|
| Payment No | PAY-YYYY-XXXXX |
| Supplier | Name |
| Invoice | Linked invoice number |
| Amount | Payment amount |
| RFP Type | Category (Vendor Invoice, PCF, etc.) |
| Payment Mode | Bank Transfer / Check |
| Approval Status | 4-level progress indicator |
| OR Status | Awaiting / Received / Overdue |
| Actions | Approve / Reject / Mark Paid / Upload OR |

### 4.2: 4-Level Approval Progress Bar — 3 units [BUILD]

Visual progress indicator per payment:
```
[Reviewer] -> [Budget] -> [CFO] -> [CEO]
```
- Green = approved, Yellow = pending (current level), Grey = not yet, Red = rejected
- Click a level -> shows approver name, date, comment
- If current user can approve this level (RBAC-gated) -> "Approve" button appears
- Use `HQ_FINANCE` for CFO gate, `SYSTEM_MANAGER` for CEO gate

### 4.3: Payment Processing Actions — 3 units [BUILD]

When payment is approved:
- "Process Payment" button -> enters bank reference + payment proof
- "Mark Complete" -> calls `mark_payment_complete()` -> triggers OR tracking
- Status changes to "Paid - Awaiting OR"

### 4.4: OR Tracking Panel — 2 units [EXTEND]

For each paid payment:
- OR Status badge (Awaiting / Received / Overdue)
- Upload OR button -> calls existing `upload_official_receipt()`
- Follow-up counter + last follow-up date
- "Send Reminder" button -> calls existing `send_or_follow_up()`

---

## Phase 5: Aging Tab + Supplier Ledger (15 units)

### 5.1: Interactive Aging Matrix — 4 units [BUILD]

Pivot table: Suppliers (rows) x Aging Buckets (columns)

| Supplier | Not Yet Due | 0-30 | 31-60 | 61-90 | 91-120 | 120+ | Total |
|----------|------------|------|-------|-------|--------|------|-------|
| 1 To 1 Marketing | P0 | P414K | P311K | P0 | P0 | P0 | P725K |

- Click any cell -> `router.push(?tab=invoices&aging=31-60&supplier=SUP-XXXX)`
- Column totals at bottom
- Color-coded: green (current) -> red (120+)
- Uses `get_ap_aging_report()` endpoint

### 5.2: Export & Print — 2 units [BUILD]

- Export aging matrix to CSV (client-side)
- Print-friendly layout via `@media print` CSS

**Note:** Aging trend chart (6-month historical) DESCOPED to S148. Requires `get_aging_trend()` endpoint + historical data collection that doesn't exist yet.

### 5.3: Supplier Selector + Summary — 3 units [BUILD]

Search/select a supplier -> shows:
- Supplier profile card (name, TIN, bank, contact)
- KPI row: Total POs, Total Invoiced, Total Paid, Outstanding, Avg Payment Days

### 5.4: Full Transaction History — 4 units [BUILD]

Uses `useSupplierTimeline(supplier)` hook -> `get_supplier_transaction_timeline()`:

```
2026-03-25  PO-2026571  Purchase Order     P188,160    Approved
2026-03-26  GR-2026-498 Goods Receipt      P188,160    Accepted
2026-03-27  INV-2026-501 Invoice           P188,160    3-Way Matched
2026-03-28  PAY-2026-301 Payment Request   P188,160    Pending CFO
```

Each row links to the full document.

### 5.5: Supplier Aging + Compliance — 2 units [BUILD]

Per-supplier aging buckets + compliance info:
- Payment terms (Net 30, etc.)
- Compliance docs (BIR, SEC, BP) with expiry flags
- EWT config

---

## Phase 6: Navigation + RBAC + Polish (5 units)

### 6.1: Sidebar Navigation — 1 unit [EXTEND]

Add "AP Command Center" to the Finance & Accounting sidebar section.
Link existing Form 2307 page from Quick Actions or nav (page already exists at `/dashboard/accounting/form-2307/`).

### 6.2: RBAC Enforcement — 2 units [EXTEND]

- HQ_FINANCE: full access (view + approve + pay + upload OR)
- PROCUREMENT_MANAGER: view invoices + payments, approve Level 1
- HQ_FINANCE (CFO): view + approve Level 3
- SYSTEM_MANAGER (CEO): view + approve Level 4
- HQ_USER: view only

Approval buttons must be conditionally rendered based on role.

### 6.3: Empty States + Error Handling — 1 unit [BUILD]

Every tab needs:
- Empty state when no data (with helpful message)
- Error boundary for API failures (retry button)
- Loading skeletons for async content

### 6.4: Closeout — 1 unit

- Update plan YAML status to COMPLETED
- Update SPRINT_REGISTRY.md with PR numbers and final status
- `git add -f docs/plans/ output/l3/S147/`
- Output L3 Handoff Prompt

---

## Phase Budget

| Phase | Units | Description |
|-------|-------|-------------|
| Phase 1: Backend + Route Shell | 8 | 3 new endpoints, route, hooks, RBAC setup |
| Phase 2: Overview Tab | 10 | KPIs, aging chart, upcoming, supplier chart |
| Phase 3: Invoices Tab | 12 | Table, inline pay, 3-way match, bulk actions |
| Phase 4: Payments Tab | 12 | Table, 4-level approval, processing, OR tracking |
| Phase 5: Aging + Supplier Ledger | 15 | Matrix, export, selector, timeline, compliance |
| Phase 6: Navigation + Polish | 5 | Sidebar, RBAC, empty states, closeout |
| **TOTAL** | **62** | |

---

## Key File Paths

| What | Path |
|------|------|
| **New AP Command Center page** | `bei-tasks/app/dashboard/accounting/ap-command-center/page.tsx` |
| **Procurement hooks** | `bei-tasks/hooks/use-procurement.ts` |
| **Procurement API** | `BEI-ERP/hrms/api/procurement.py` (132 endpoints + 3 new) |
| **RBAC config** | `bei-tasks/lib/roles.ts` |
| **BEI Invoice DocType** | `BEI-ERP/hrms/hr/doctype/bei_invoice/bei_invoice.json` |
| **BEI Payment Request DocType** | `BEI-ERP/hrms/hr/doctype/bei_payment_request/bei_payment_request.json` |
| **Existing invoice list page** | `bei-tasks/app/dashboard/procurement/invoices/page.tsx` |
| **Existing payment page** | `bei-tasks/app/dashboard/procurement/payments/page.tsx` |
| **Existing accounting pages** | `bei-tasks/app/dashboard/accounting/` |
| **Existing Form 2307 page** | `bei-tasks/app/dashboard/accounting/form-2307/page.tsx` |
| **Existing SOA page** | `bei-tasks/app/dashboard/accounting/soa/page.tsx` |

---

## Endpoints to Wire

### Existing (confirmed in procurement.py)

| Frontend Feature | Backend Endpoint | Status |
|-----------------|-----------------|--------|
| KPI cards | `get_dashboard_kpis()` | EXISTS |
| Aging analysis | `get_aging_analysis()` | EXISTS |
| Outstanding by supplier | `get_outstanding_by_supplier()` | EXISTS |
| Invoice list | `get_invoices()` | EXISTS |
| Payment request list | `get_payment_requests()` | EXISTS |
| Pending approvals | `get_pending_payment_approvals()` | EXISTS |
| Approve payment (4 levels) | `approve_payment_review/budget/cfo/ceo()` | EXISTS |
| Mark payment complete | `mark_payment_complete()` | EXISTS |
| OR tracking | `get_awaiting_or_list()` | EXISTS |
| Supplier aging | `get_supplier_aging()` | EXISTS |
| Advance tracking | `get_outstanding_advances()` | EXISTS |
| Payment disbursement | `get_payment_disbursement_report()` | EXISTS |
| 3-way match | `verify_invoice_match()` | EXISTS |
| AP aging report | `get_ap_aging_report()` | EXISTS |
| Create payment request | `create_payment_request()` | EXISTS |
| Upload OR | `upload_official_receipt()` | EXISTS |
| Send OR Reminder | `send_or_follow_up()` | EXISTS |

### New (built in Phase 1)

| Frontend Feature | Backend Endpoint | Status |
|-----------------|-----------------|--------|
| Inline status change | `update_invoice_payment_status()` | **BUILD in Phase 1.1** |
| Supplier timeline | `get_supplier_transaction_timeline()` | **BUILD in Phase 1.1** |
| Bulk transfer to finance | `bulk_update_invoice_acctg_status()` | **BUILD in Phase 1.1** |

---

## L3 Workflow Scenarios

| # | User | Action | Expected Outcome | Failure Means |
|---|------|--------|-------------------|---------------|
| 1 | sam@bebang.ph | Open AP Command Center -> Overview tab | 6 KPI cards with real data, aging chart, upcoming payments | Overview not wired |
| 2 | sam@bebang.ph | Click "31-60 days" aging bucket on Overview | Invoices tab filters to 31-60 day overdue invoices (URL: ?tab=invoices&aging=31-60) | Cross-tab filter broken |
| 3 | sam@bebang.ph | Change invoice status to "Paid" via inline dropdown | Status updates, audit trail written to verification_notes | Inline status update broken |
| 4 | sam@bebang.ph | Click "Pay" on an unpaid invoice, fill form, submit | Payment Request created, 4-level progress bar shows status | Inline payment broken |
| 5 | sam@bebang.ph | Open Supplier Ledger -> select "1 To 1 Marketing" | Full timeline: POs -> GRs -> Invoices -> Payments | Supplier ledger broken |
| 6 | sam@bebang.ph | Aging tab -> export aging matrix to CSV | CSV downloads with supplier x bucket data | Export broken |
| 7 | sam@bebang.ph | Select 3 invoices -> "Transferred to Finance" bulk action | All 3 get verification_notes updated, toast confirmation | Bulk action broken |
| 8 | sam@bebang.ph | Open Payments tab -> click "Upload OR" on a paid payment | OR upload dialog, OR number + date + amount fields | OR tracking broken |

### L3 Evidence File Contract

Evidence files required before closeout:
- `output/l3/S147/form_submissions.json` — payment recording, status changes, OR upload
- `output/l3/S147/api_mutations.json` — all API calls with request/response
- `output/l3/S147/state_verification.json` — before/after state for each mutation

**L3 must run in a FRESH session (not the builder session).** Builder outputs L3 Handoff Prompt at end of execution.

---

## Requirements Regression Checklist

- [ ] Does the Overview tab show 6 KPI cards with real data from 714 invoices?
- [ ] Does the Invoices tab replace the accounting team's spreadsheet functionality?
- [ ] Can the finance team change payment status with one click (inline dropdown)?
- [ ] Does the inline status dropdown call `update_invoice_payment_status()` with audit trail?
- [ ] Does the 4-level approval progress bar show real approval status?
- [ ] Does clicking an aging bucket cross-filter to the Invoices tab via URL params?
- [ ] Does the Supplier Ledger show the full chain (PO->GR->Invoice->Payment->OR)?
- [ ] Is RFP type visible on payment requests?
- [ ] Do all 3 new `@frappe.whitelist()` endpoints call `set_backend_observability_context()`?
- [ ] Are approval buttons RBAC-gated (only visible to authorized roles via roles.ts constants)?
- [ ] Does "Transferred to Finance" use verification_notes (not a new DocType field)?
- [ ] Is the aging trend chart (6-month historical) DESCOPED to S148?

---

## Autonomous Execution Contract

```yaml
completion_condition:
  - AP Command Center page loads with 5 working tabs
  - Overview shows real KPIs from 714 invoices
  - Invoices tab shows all unpaid invoices with aging badges
  - Payments tab shows payment requests with approval progress
  - Aging tab shows interactive supplier x bucket matrix
  - Supplier Ledger shows full PO->GR->Invoice->Payment chain
  - 3 new backend endpoints created with Sentry instrumentation
  - PRs created for BOTH bei-tasks AND hrms repos
  - Plan YAML status updated to COMPLETED
  - SPRINT_REGISTRY.md updated with PR numbers
  - L3 evidence files committed (git add -f output/l3/S147/)
stop_only_for:
  - Missing credentials or access
  - RBAC config prevents page access (investigate first)
  - BEI Invoice data missing (714 invoices from S145 — verified present)
  - Destructive action requiring approval
continue_without_pause_through:
  - build -> PR creation -> closeout
blocker_policy:
  programmatic: fix and continue
  missing_api: check procurement.py, wire existing endpoint or build if listed in Phase 1
  business_data: pause and ask
signoff_authority: single-owner (Sam)
```

---

## Sentry Observability

3 new `@frappe.whitelist()` endpoints (Phase 1.1) MUST include `set_backend_observability_context()`:

| Endpoint | module | action |
|----------|--------|--------|
| `update_invoice_payment_status()` | finance | update_invoice_payment_status |
| `get_supplier_transaction_timeline()` | finance | get_supplier_transaction_timeline |
| `bulk_update_invoice_acctg_status()` | finance | bulk_update_invoice_acctg_status |

Frontend API routes auto-instrumented by `@sentry/nextjs`.

---

## Execution Workflow

### Repos and PRs

| Repo | Changes | PR Target |
|------|---------|-----------|
| `hrms` (BEI-ERP) | 3 new endpoints in `hrms/api/procurement.py` | `production` branch |
| `bei-tasks` | AP Command Center page, hooks, RBAC, nav | `main` branch |

### PR-Handoff (MANDATORY)

After all code is complete:
1. Create PR in `hrms` repo targeting `production`
2. Create PR in `bei-tasks` repo targeting `main`
3. Output PR numbers in a clear table
4. State "PRs ready for your review and merge"
5. **STOP** — do not deploy, do not poll, do not merge

Sam handles merge and deployment for both repos.

---

## Execution Authority

This sprint is intended for autonomous end-to-end execution up to PR creation.
Do not stop for progress-only updates.
Only pause for items listed in `stop_only_for`.
Terminal state for agent execution is `PR_CREATED`.

---

## Descoped to S148

- Aging trend chart (6-month historical stacked bar) — requires new `get_aging_trend()` endpoint + historical data collection
- PDF aging report generation (server-side)
- Form 2307 integration into AP Command Center (page exists, just needs deeper linking)

---

## Audit History

### Audit v1 (2026-03-30) — 7 domains + code verifier + adversarial fact-checker

Original verdict: NO-GO (10 blockers). All 10 verified by adversarial fact-check.

**Blockers resolved inline:**
- [x] B-01: PR-Handoff replaces direct deploy (Execution Workflow section)
- [x] B-02: 60 units acknowledged — single-session execution acceptable per user decision
- [x] B-03: `update_invoice_payment_status()` added to Phase 1.1
- [x] B-04: "Transferred to Finance" uses verification_notes (no schema change)
- [x] B-05: Aging trend descoped to S148
- [x] B-06: Branch boot sequence added (Agent Boot Sequence section)
- [x] B-07: L3 evidence contract added (L3 section)
- [x] B-08: S145 completed and status updated
- [x] B-09: CFO/CEO role mapping defined (HQ_FINANCE/SYSTEM_MANAGER)
- [x] B-10: Cross-tab state pattern defined (URL search params)

**Stale findings removed:** DM-2 savepoint (already implemented), Form 2307 page (already exists), SOA page (already exists).

Full audit artifacts: `output/plan-audit/s147-ap-command-center/`
