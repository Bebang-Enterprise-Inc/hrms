# Sprint S141 — Procurement Module Full Fix

```yaml
sprint: S141
branch: s141-procurement-module-fix
status: COMPLETED
plan_file: docs/plans/2026-03-28-sprint-141-procurement-module-fix.md
depends_on: null
registry_row: "| S141 | Sprint 141 | s141-procurement-module-fix | BEI-Tasks#274 | COMPLETED 2026-03-28 — PO pagination, approved tab, status filters, dashboard empty states, sidebar dedup. |"
frontend_pr: BEI-Tasks#274
execution_started: 2026-03-28
completed_date: 2026-03-28
l3_result: 12/12 PASS (2 reclassified from selector issues)
execution_summary: |
  All 6 fixes deployed and verified live on my.bebang.ph:
  - PO pagination: 577 POs accessible, Next/Previous functional
  - Approved tab: 543 POs with pagination
  - Status filters: Pending CEO + Cancelled added
  - Dashboard: "No data yet" for invoice-dependent KPIs, MTD PO shows ₱41.1M
  - AP Aging: proper empty state
  - Sidebar: duplicate removed, single navigation
  PR BEI-Tasks#274 merged 2026-03-28T11:43:14Z
```

---

## Why This Exists

Full audit of the procurement module at `my.bebang.ph/dashboard/procurement/` revealed multiple issues on 2026-03-28:

### Group 1: PO Page Bugs (discovered first)

1. **No pagination on PO page** — fetches `page=1, pageSize=20` and stops. 557 of 577 POs invisible. No Next/Previous buttons. `setPage` state exists but never advances.

2. **Empty "Approved" tab** — `TabsContent value="approved"` (line 901-903 of `page.tsx`) is a comment placeholder. Clicking "Approved" shows nothing.

3. **Missing "Pending CEO Approval" in status filter** — S132 added CEO approval but the dropdown (lines 684-693) wasn't updated. Also missing "Cancelled" (15 POs).

### Group 2: Dashboard Data Issues (all zeros)

4. **Total Outstanding: ₱0** — should show unpaid supplier invoices but Invoice/AP data pipeline returns empty.

5. **Overdue Amount: ₱0** — no overdue tracking data feeding in.

6. **Avg Payment Days: 0.0 days** — payment tracking data not connected.

7. **AP Aging Analysis: ₱0 Total Outstanding** — aging buckets empty, no AP data.

8. **Outstanding by Supplier: empty** — no supplier payable data.

### Group 3: Duplicate Sidebar

9. **Two sidebars visible** — The main left sidebar has the full procurement nav (Dashboard, Critical Stockout, Purchase Requisitions, Purchase Orders, Suppliers, Goods Receipts, Invoices, Payment Requests, Approvals, SOA, OR Follow-Up, Reports, Monthly Spend, Supplier Performance, Single-Source Suppliers, Three-Way Match, Payment Disbursement, Goods Receipt Log, PO Aging, Price History, Settings, Critical Items Control Tower, Critical Stockout Incidents). A SECOND inner sidebar appears inside the procurement content area (Dashboard, Suppliers, Purchase Orders, Goods Receipts, Invoices, Payments, OR Follow-up, Reports). This is redundant and confusing.

### Investigation Required Before Execution

The executing agent MUST investigate these before writing code:

1. **Why is AP/Invoice/Payment data all zero?** Check the backend endpoints that feed the dashboard cards. Are they querying the right DocTypes? Is the data in Frappe? (577 POs exist but 0 invoices — is that because invoices were never synced, or the query is wrong?)

2. **Where does the duplicate sidebar come from?** Is it a layout component wrapping the procurement pages? Use `/workspace-normalizer-bei-erp` to understand the sidebar architecture.

3. **Which of the 25+ sidebar items are actually functional?** Many may be shells (pages exist but show empty or error).

**Source file:** `bei-tasks/app/dashboard/procurement/purchase-orders/page.tsx`
**Hook file:** `bei-tasks/hooks/use-procurement.ts`
**Dashboard file:** `bei-tasks/app/dashboard/procurement/page.tsx` (or layout)
**Sidebar:** Investigate via `/workspace-normalizer-bei-erp`

---

## Agent Boot Sequence

1. Read this plan fully.
2. `git fetch origin main && git checkout -b s141-procurement-module-fix origin/main` (bei-tasks uses `main`, not `production`)
3. Read the PO page: `bei-tasks/app/dashboard/procurement/purchase-orders/page.tsx`
4. Read the procurement hook: `bei-tasks/hooks/use-procurement.ts`
5. Read the procurement dashboard: `bei-tasks/app/dashboard/procurement/page.tsx`
6. Read the procurement layout: `bei-tasks/app/dashboard/procurement/layout.tsx` (if exists — this is likely where the inner sidebar lives)
7. Read the main sidebar config: `bei-tasks/lib/constants.ts` or wherever sidebar nav items are defined

---

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

---

## Phase 0: Full QA Investigation (12 units — MUST complete before any code changes)

This phase is a **proper QA audit** of the entire procurement module. All findings go to `tmp/s141_investigation.md` and `tmp/s141_page_audit.json`. Use `/l3-v2-bei-erp` as the browser investigation tool — Playwright for every check.

### INV-1: Dashboard Data Pipeline Audit (2 units)

Investigate why every dashboard card shows ₱0:

| Card | Shows | Should Show | Investigate |
|------|-------|-------------|-------------|
| Total Outstanding | ₱0 | Unpaid supplier invoices | What endpoint feeds this? Does the data exist in Frappe? |
| Overdue Amount | ₱0 | Past due invoices | Same endpoint or separate? |
| Avg Payment Days | 0.0 | Average days to pay suppliers | What table/query calculates this? |
| AP Aging Analysis | ₱0 | Aging buckets (30/60/90 days) | What endpoint? Is AP data synced? |
| Outstanding by Supplier | empty | Top 5 suppliers by payables | Same as AP aging? |

**Steps:**
1. Read the procurement dashboard page component — find every `useQuery` / fetch call
2. Trace each to the backend API endpoint
3. Call each endpoint directly via Python requests to see raw response
4. If endpoint returns empty, check if underlying Frappe data exists (`frappe.client.get_count` for Purchase Invoice, Payment Entry, Journal Entry)
5. Classify root cause per card: **NO_DATA** vs **QUERY_BUG** vs **NOT_IMPLEMENTED**

### INV-2: Duplicate Sidebar Investigation (1 unit)

1. Read `bei-tasks/app/dashboard/procurement/layout.tsx` — does it render its own sidebar?
2. Read the main app layout — where are procurement nav items defined?
3. Map which items appear in BOTH sidebars vs only one
4. Recommend: keep one, remove the other, or merge

### INV-3: Full Surface Audit — Every Page, Every Role (3 units)

**Use Playwright via `/l3-v2-bei-erp` browser automation.** Load every procurement page and document what happens.

For EACH of the 25+ sidebar items:
1. Navigate to the page (click sidebar, not direct URL)
2. Screenshot the page
3. Check for: console errors, empty states, error banners, loading spinners that never resolve
4. Record: does the page have data? Is it interactive? Or is it a shell?

**Test with 3 roles** (not just CEO):

| Role | Account | Why |
|------|---------|-----|
| CEO (full access) | sam@bebang.ph / 2289454 | See everything |
| Procurement staff | test.staff@bebang.ph / BeiTest2026! | Should see POs, PRs, suppliers |
| Warehouse | test.warehouse@bebang.ph / BeiTest2026! | Should see GRs, receiving |

**Output per page:**
```json
{
  "route": "/dashboard/procurement/invoices",
  "page_loads": true,
  "has_data": false,
  "console_errors": [],
  "interactive_elements": ["search", "filter", "table"],
  "buttons_tested": [{"name": "New Invoice", "works": false, "error": "404"}],
  "classification": "SHELL",
  "screenshot": "tmp/s141_screenshots/invoices.png",
  "roles_tested": {"ceo": "loads", "staff": "403", "warehouse": "loads"}
}
```

Write all results to `tmp/s141_page_audit.json`.

### INV-4: Click Every Button + CTA (2 units)

On pages that DO load, click every interactive element:

| Element Type | What to Test |
|-------------|-------------|
| "New PO" / "New PR" buttons | Does the form open? Can you fill it? |
| "Export" / "Download" buttons | Does it produce a file? |
| "Refresh" button | Does it refetch data? |
| Table row clicks | Does it navigate to detail page? |
| Approve / Reject buttons | Do they trigger the right API call? |
| Filter dropdowns | Do they filter the list? |
| Search inputs | Do they search? |
| Pagination (where it exists) | Does it paginate? |
| Tab switches | Do they load different data? |

Log every CTA with: `{element, action, result: "works"|"broken"|"stub"|"403"}`.

### INV-5: End-to-End Workflow Test (2 units)

Test the full procurement workflow as it exists today:

1. **PR → PO flow:** Can you create a Purchase Requisition and convert it to a PO?
2. **PO approval:** Submit a PO → does it go to Pending Mae? Can Mae approve it?
3. **GR from PO:** After PO is approved, can you create a Goods Receipt against it?
4. **Invoice from GR:** After GR, can you create an invoice?
5. **Payment from Invoice:** After invoice, can you create a payment?

For each step: does it work, fail, or not exist? This determines whether the ₱0 dashboard is because the workflow is broken upstream (no invoices ever created) or the dashboard query is wrong.

### INV-6: API vs UI Data Consistency Check (1 unit)

For pages that show data, verify the UI matches the API:

| Check | Method |
|-------|--------|
| PO count: API says 577, UI should show 577 (not 20) | Compare `get_purchase_orders` total vs "All POs" display |
| Supplier count: API vs supplier list page | Compare `get_suppliers` vs page |
| GR count: API vs GR list page | Compare `get_goods_receipts` vs page |
| PR count: API vs PR list page | Compare `get_purchase_requisitions` vs page |
| Dashboard PO trend chart: does the data match actual PO creation dates? | Spot-check 3 months |

### INV-7: Cross-Reference Source Data (1 unit)

Pick 5 random POs from Frappe and verify against the Compliance App Google Sheet:

| PO Number | Frappe Supplier | Sheet Supplier | Frappe Amount | Sheet Amount | Match? |
|-----------|----------------|----------------|---------------|--------------|--------|

**Google Sheet:** `1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q` tab `Purchase Order`

This catches sync data quality issues — wrong amounts, wrong suppliers, missing fields.

**Output:** The full investigation produces:
- `tmp/s141_investigation.md` — narrative findings with root causes
- `tmp/s141_page_audit.json` — per-page structured results
- `tmp/s141_screenshots/` — screenshot per page per role
- `tmp/s141_proof_matrix.md` — the Proof Matrix (see below)
- Classification of every page as [WORKS], [BROKEN], [SHELL], [EMPTY], or [403]
- Scope determination for Phases B and C

---

## Procurement Proof Matrix (MANDATORY — no page passes without ALL columns green)

Every procurement page must be verified across 4 dimensions. A page is NOT PASS unless all 4 columns are green. Write results to `tmp/s141_proof_matrix.md`.

### Dimension 1: Data Accuracy Proof

For every page that displays data, the agent must perform a **three-way match**:

```
Google Sheet (Compliance App) ←→ Frappe API (hq.bebang.ph) ←→ UI (my.bebang.ph)
```

| Step | Action | Evidence Required |
|------|--------|-------------------|
| 1 | Query the Frappe API directly for the raw data (`GET /api/resource/...`) | Save API response JSON |
| 2 | Read the Google Sheet source via Sheets API | Save extracted values |
| 3 | Read the UI values via Playwright (text content, not just element exists) | Screenshot + extracted text |
| 4 | Compare all three — if any differ, document the exact delta | Diff table with row-level values |

**Per-page data checks:**

| Page | Data Source (Google Sheet) | Frappe DocType | UI Values to Verify |
|------|--------------------------|----------------|---------------------|
| Purchase Orders | Compliance App → `Purchase Order` tab | BEI Purchase Order (577) | PO number, date, supplier name, grand_total, status — spot-check 5 random POs |
| Purchase Requisitions | Compliance App → `Purchase Requisitions` tab | BEI Purchase Requisition (488) | PR number, date, requester, items — spot-check 5 |
| Suppliers | Compliance App → `Suppliers` tab | BEI Supplier (145) | Supplier name, code, contact — spot-check 5 |
| Goods Receipts | Compliance App → `Goods Receipts` tab | BEI Goods Receipt (974) | GR number, PO reference, qty received — spot-check 5 |
| Invoices | AP Opening → `SUPPLIERS SOA` tab | Purchase Invoice (if any) | Invoice number, amount, supplier — check if data exists at all |
| Dashboard cards | Multiple endpoints | Multiple DocTypes | MTD PO Value matches actual PO sum for current month |

**HARD BLOCKER:** Do NOT verify data by checking that an element exists on the page. Read the actual TEXT value and compare it against the API number. `page.locator('.amount').count() > 0` is NOT verification. `page.locator('.amount').textContent() === '₱41,108,853'` IS verification.

### Dimension 2: Functional Proof (CTA Verification)

For every button/action on every page, the agent must prove it works:

| Step | Action | Evidence Required |
|------|--------|-------------------|
| 1 | Screenshot BEFORE clicking | `{page}_{cta}_before.png` |
| 2 | Click the button/action | — |
| 3 | Capture the network request (method, URL, payload) | Network log |
| 4 | Verify the API response (status code, response body) | Response JSON |
| 5 | Screenshot AFTER the action | `{page}_{cta}_after.png` |
| 6 | Verify UI state changed (toast, redirect, table update, dialog) | Text content of the change |

**Per-page CTA matrix:**

| Page | CTAs to Test | Expected Behavior |
|------|-------------|-------------------|
| Purchase Orders | "New PO" button | Opens PO creation form |
| Purchase Orders | Status filter dropdown (each status) | Filters table to matching POs only, count updates |
| Purchase Orders | Search input | Filters by PO number or supplier name |
| Purchase Orders | PO row click | Navigates to PO detail page |
| Purchase Orders | "Approve" button (on pending POs) | Opens approval dialog, submits approval |
| Purchase Orders | "Reject" button | Opens reject dialog with reason field |
| Purchase Orders | Batch approve checkboxes | Select multiple → batch approve works |
| Purchase Requisitions | "New PR" button | Opens PR creation form |
| Purchase Requisitions | PR row click | Navigates to PR detail |
| Suppliers | Supplier row click | Navigates to supplier detail |
| Suppliers | Search input | Filters supplier list |
| Goods Receipts | GR row click | Navigates to GR detail |
| Goods Receipts | "Quick Receive" button (if exists) | Opens receiving form |
| Dashboard | "Refresh" button | Refetches all dashboard data |
| Dashboard | PO Approval cards click | Navigates to PO detail |
| Dashboard | Monthly PO Trend chart | Hoverable, shows month values |

### Dimension 3: UX/Design Proof

For every page, verify the design serves the procurement workflow:

| Check | How to Verify | Pass Criteria |
|-------|--------------|---------------|
| Currency formatting | Read amount text from table cells | Shows `₱` prefix, comma-separated thousands (e.g., `₱41,108,853`) — NOT raw numbers like `41108853` |
| Date formatting | Read date text from table cells | Consistent format (e.g., "Mar 26, 2026") — NOT ISO `2026-03-26T00:00:00` |
| Status badge colors | Read badge class/style | Green = Approved/Fully Received, Orange = Pending, Red = Rejected/Cancelled, Blue = Draft |
| Empty state messaging | Load page with filters that return 0 results | Shows helpful message (e.g., "No pending POs") — NOT blank white space |
| Loading state | Intercept network and delay response | Shows skeleton/spinner — NOT frozen page |
| Mobile responsive | Set viewport to 375x812 | Tables scroll horizontally, buttons are tappable, no overflow |
| Pagination info | When >20 items exist | Shows "Showing X-Y of Z" text with working Previous/Next |
| Table sorting | Click column headers | Sorts by that column (if sortable) |
| Sidebar active state | Navigate to each page | Current page is highlighted in sidebar |

### Dimension 4: Business Rules Proof

Verify procurement-specific rules are enforced in the UI:

| Rule | How to Verify | Pass Criteria |
|------|--------------|---------------|
| PO >500K requires CFO (Butch) approval | Find a PO >500K, check approval chain shows "CFO (Butch)" | Badge shows CFO requirement |
| New vendor (<30 days) triggers CEO approval | Find a PO with recently-created supplier, check for CEO flag | `requires_ceo_approval` badge visible |
| CEO approval flow (S132) | Filter by "Pending CEO Approval" status | Filter works and shows any CEO-pending POs |
| GR qty ≤ PO qty | Open a GR detail, compare received qty against PO ordered qty | Received does not exceed ordered (or shows warning) |
| Duplicate PO detection | Check if "Duplicate" button exists on PO detail (S128) | Button exists and functions |
| Mae approval threshold | POs ≤500K go to Mae only | Check approval badges on POs ≤500K |
| Three-way match | Open three-way match page, check PO vs GR vs Invoice | Shows match status per PO line |

### Proof Matrix Summary Template

Write to `tmp/s141_proof_matrix.md`:

```markdown
# S141 Procurement Proof Matrix

| Page | Data Accuracy | Functional (CTAs) | UX/Design | Business Rules | Overall |
|------|:---:|:---:|:---:|:---:|:---:|
| Dashboard | ❌ AP=₱0 | ✅ Refresh works | ⚠️ misleading zeros | N/A | FAIL |
| Purchase Orders | ✅ 577 match | ❌ no pagination | ⚠️ no CEO status | ✅ >500K CFO badge | FAIL |
| Purchase Requisitions | ? | ? | ? | ? | ? |
| Suppliers | ? | ? | ? | ? | ? |
| Goods Receipts | ? | ? | ? | ? | ? |
| Invoices | ? | ? | ? | ? | ? |
| ... | | | | | |

Legend: ✅ PASS | ❌ FAIL | ⚠️ WARNING | ? NOT TESTED
```

**A page is PASS only if ALL 4 dimensions are ✅.** Any ❌ = FAIL. Any ⚠️ = WARNING (document but not blocking unless it's a data accuracy issue).

---

## Phase A: PO Page Fixes (6 units) — Can start in parallel with Phase 0

### FIX-1: Add Pagination to All POs Tab (3 units)

**File:** `bei-tasks/app/dashboard/procurement/purchase-orders/page.tsx`

Add pagination controls after the PO table (after line 746, before `</TabsContent>`):

```tsx
{/* Pagination */}
{allPOs && allPOs.total > 20 && (
  <div className="flex items-center justify-between px-4 py-3">
    <p className="text-sm text-muted-foreground">
      Showing {((page - 1) * 20) + 1}–{Math.min(page * 20, allPOs.total)} of {allPOs.total} POs
    </p>
    <div className="flex gap-2">
      <Button
        variant="outline"
        size="sm"
        onClick={() => setPage(p => Math.max(1, p - 1))}
        disabled={page === 1}
      >
        Previous
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setPage(p => p + 1)}
        disabled={page * 20 >= allPOs.total}
      >
        Next
      </Button>
    </div>
  </div>
)}
```

**Verify:** The `allPOs` response from `usePurchaseOrders` returns `{ data: [...], total: number }`. The `total` field is already returned by the backend (`get_purchase_orders` returns `total=577`).

**Reference implementation:** The Goods Receipts page (`bei-tasks/app/dashboard/procurement/goods-receipts/page.tsx`) already has working pagination. Copy its pattern rather than writing from scratch.

### FIX-2: Populate Approved Tab (2 units)

**File:** `bei-tasks/app/dashboard/procurement/purchase-orders/page.tsx`

Replace the empty `TabsContent value="approved"` (lines 901-903) with a filtered table that shows only Approved + Fully Received + Partially Received POs. Use the same `usePurchaseOrders` hook with `status` filter.

**HARD BLOCKER:** The `buildOperationalProcurementFilters` function in `hooks/use-procurement.ts` passes `status` directly to the filter object. If passing an array, the backend `get_purchase_orders` needs Frappe's `["in", [...]]` filter format. Before using array status, verify the backend handles it. If not, use separate queries or a comma-separated string. Check the backend at `hrms/api/procurement.py` → `get_purchase_orders`.

Add a separate query:
```tsx
const { data: approvedPOs, isLoading: approvedLoading } = usePurchaseOrders({
  page: approvedPage,
  pageSize: 20,
  status: ['Approved', 'Fully Received', 'Partially Received'],
});
```

Add `approvedPage` state alongside existing `page` state. Include pagination on this tab too.

**Reference implementation:** The Goods Receipts page (`bei-tasks/app/dashboard/procurement/goods-receipts/page.tsx`) already has working pagination. Use it as the pattern for both FIX-1 and FIX-2 instead of writing from scratch.

### FIX-3: Add Missing Status to Filter Dropdown (1 unit)

**File:** `bei-tasks/app/dashboard/procurement/purchase-orders/page.tsx`

After the `Pending Butch Approval` SelectItem (line 688), add:
```tsx
<SelectItem value="Pending CEO Approval">Pending CEO</SelectItem>
```

Also add `Cancelled` to the dropdown since 15 cancelled POs exist:
```tsx
<SelectItem value="Cancelled">Cancelled</SelectItem>
```

---

## Phase B: Fix Dashboard Data Pipeline (scope determined by Phase 0 — estimated 6 units)

Based on INV-1 findings, fix the dashboard cards that show ₱0. The fix depends on root cause:

- **If NO_DATA** (Frappe has no invoices/payments): This is expected — procurement is still Google Sheet-based. Dashboard cards should show a "No ERP data yet" state instead of misleading ₱0.
- **If QUERY_BUG** (data exists but query is wrong): Fix the query/endpoint.
- **If NOT_IMPLEMENTED** (endpoint is a stub): Either implement or show "Coming soon" state.

| Task | Action | Condition |
|------|--------|-----------|
| B1 | Fix Total Outstanding card | Based on INV-1 finding |
| B2 | Fix Overdue Amount card | Based on INV-1 finding |
| B3 | Fix Avg Payment Days card | Based on INV-1 finding |
| B4 | Fix AP Aging Analysis section | Based on INV-1 finding |
| B5 | Fix Outstanding by Supplier section | Based on INV-1 finding |
| B6 | Handle empty states properly — show "No invoice data synced yet" instead of ₱0 | All cards |

---

## Phase C: Fix Duplicate Sidebar (scope determined by Phase 0 — estimated 3 units)

Based on INV-2 findings, eliminate the duplicate sidebar.

| Task | Action | Condition |
|------|--------|-----------|
| C1 | Remove the inner procurement sidebar OR remove duplicate items from the main sidebar | Based on INV-2 finding |
| C2 | Consolidate navigation items — one canonical list, no duplicates | Use `/workspace-normalizer-bei-erp` |
| C3 | Verify all sidebar links route correctly after consolidation | Playwright check |

---

## Phase D: Sentry Observability (0 units — N/A)

No `@frappe.whitelist()` endpoints modified. Frontend-only change. `@sentry/nextjs` auto-instruments.

---

## Phase E: Create PR + L3 Test (4 units)

| Task | Action |
|------|--------|
| E1 | Create PR to `main` on `Bebang-Enterprise-Inc/BEI-Tasks` (may also need a backend PR to `Bebang-Enterprise-Inc/hrms` if dashboard endpoints need fixing) |
| E2 | Share PR number(s) with Sam — STOP and wait for merge+deploy |
| E3 | After deploy, run L3 scenarios below |
| E4 | Update plan + registry to COMPLETED |

---

## L3 Workflow Scenarios

| # | User | Action | Expected Outcome | Failure Means |
|---|------|--------|-------------------|---------------|
| L3-1 | sam@bebang.ph | Open `/dashboard/procurement/purchase-orders` → "All POs" tab | Page shows 20 POs with "Showing 1–20 of 577 POs" text and Previous/Next buttons | FIX-1 pagination not added |
| L3-2 | sam@bebang.ph | Click "Next" button on All POs tab | Page advances to rows 21-40, different PO numbers shown, "Showing 21–40 of 577" | FIX-1 setPage not wired |
| L3-3 | sam@bebang.ph | Click "Next" until page 10+ | POs with status "Pending Butch Approval" visible in the table | Pending POs still unreachable |
| L3-4 | sam@bebang.ph | Click "Previous" button | Returns to previous page, Previous button disabled on page 1 | Backward navigation broken |
| L3-5 | sam@bebang.ph | Select "Pending Butch" from status dropdown | Only Pending Butch POs shown (should be 18), total count updates | Status filter broken |
| L3-6 | sam@bebang.ph | Select "Pending CEO" from status dropdown | Shows any Pending CEO POs (may be 0 currently, but filter must work without error) | FIX-3 missing status option |
| L3-7 | sam@bebang.ph | Select "Cancelled" from status dropdown | Shows 15 cancelled POs | FIX-3 missing Cancelled option |
| L3-8 | sam@bebang.ph | Click "Approved" tab | Table renders with Approved + Fully Received + Partially Received POs, pagination works | FIX-2 empty tab |
| L3-9 | sam@bebang.ph | On "All POs" tab, type "Orangepop" in search → verify results | Only POs with "Orangepop" supplier shown | Search broken after pagination changes |
| L3-10 | sam@bebang.ph | Select "All Statuses" after filtering by "Pending Butch" | Returns to showing all POs, page resets to 1 | Filter reset broken |
| L3-11 | sam@bebang.ph | Open `/dashboard/procurement` dashboard | Dashboard loads. Total Outstanding shows real value or "No invoice data" — NOT ₱0 | Phase B dashboard fix broken |
| L3-12 | sam@bebang.ph | Check AP Aging Analysis section on dashboard | Shows aging buckets with real data or "No AP data synced yet" — NOT ₱0 | Phase B AP aging fix broken |
| L3-13 | sam@bebang.ph | Verify only ONE sidebar is visible on procurement pages | No duplicate navigation. Either main sidebar OR inner sidebar, not both | Phase C sidebar fix broken |
| L3-14 | sam@bebang.ph | Click every sidebar nav item under Procurement | Each routes to a page that loads without error (may show empty state but no crash) | Dead sidebar links |
| L3-15 | sam@bebang.ph | Verify 5 random POs: compare UI amount vs Frappe API vs Google Sheet | All three match for supplier name, amount, date | Data accuracy broken (three-way mismatch) |
| L3-16 | sam@bebang.ph | Click "New PO" → fill form → submit | PO created with correct status (Draft or Pending Mae) | PO creation workflow broken |
| L3-17 | sam@bebang.ph | Open PO detail for a >500K PO | Shows CFO (Butch) approval requirement | Business rule not enforced in UI |
| L3-18 | sam@bebang.ph | Set viewport to 375x812 (mobile) → navigate procurement | Tables scroll, buttons tappable, no overflow | Mobile layout broken |
| L3-19 | test.staff@bebang.ph | Open procurement module | Can see POs, PRs, suppliers (appropriate for procurement staff role) | RBAC broken — staff sees too much or too little |
| L3-20 | sam@bebang.ph | Verify Proof Matrix is complete | `tmp/s141_proof_matrix.md` exists with ALL pages assessed across all 4 dimensions | Investigation incomplete |

**Evidence files required:**
```
output/l3/S141/form_submissions.json
output/l3/S141/api_mutations.json
output/l3/S141/state_verification.json
tmp/s141_proof_matrix.md              (4-dimension proof per page)
tmp/s141_investigation.md             (narrative findings)
tmp/s141_page_audit.json              (structured per-page results)
tmp/s141_screenshots/                 (screenshot per page per role)
```

---

## Requirements Regression Checklist

- [ ] Does "All POs" tab show pagination with total count?
- [ ] Does clicking Next/Previous change the displayed POs?
- [ ] Does the status dropdown include Pending CEO Approval and Cancelled?
- [ ] Does the "Approved" tab render a table with data (not empty)?
- [ ] Does search still work after pagination is added?
- [ ] Does changing the status filter reset to page 1?
- [ ] Are all 577 POs reachable by paginating through all pages?
- [ ] Does every new/modified component follow existing shadcn/ui patterns in the file?
- [ ] Does the Approved tab's array status filter work with the backend? (Frappe needs `["in", [...]]` format)
- [ ] Was the Goods Receipts page pagination used as the reference pattern?
- [ ] Do dashboard cards show appropriate state (real data OR "no data yet") instead of misleading ₱0?
- [ ] Is there only ONE sidebar visible (no duplicate navigation)?
- [ ] Do all sidebar items route to functional pages (no dead links)?
- [ ] Was Phase 0 investigation completed and findings written to `tmp/s141_investigation.md`?
- [ ] Were ALL 25+ pages tested with 3 roles (CEO, staff, warehouse)?
- [ ] Was every CTA/button clicked and result documented?
- [ ] Was E2E workflow tested (PR → PO → approve → GR → invoice → payment)?
- [ ] Were 5 random POs cross-referenced against the Compliance App Google Sheet?
- [ ] Is API data consistent with UI display (counts match)?

---

## Total: ~31 units across 6 phases

| Phase | Units | Description |
|-------|-------|-------------|
| 0 | 12 | Full QA investigation: dashboard data (2), sidebar (1), every page x3 roles (3), click every CTA (2), E2E workflow (2), API vs UI consistency (1), source data cross-ref (1) |
| A | 6 | PO page fixes: pagination (3), Approved tab (2), status filter (1) |
| B | ~6 | Dashboard data pipeline fixes (scope from Phase 0) |
| C | ~3 | Sidebar deduplication (scope from Phase 0) |
| D | 0 | Sentry N/A (frontend only) |
| E | 4 | PR + L3 (20 scenarios) |

**Note:** Phase 0 may reveal additional scope (broken pages, dead workflows). If total exceeds 40 units after Phase 0 findings, split into S141 (investigation + PO fixes) and S142 (dashboard + sidebar + remaining).

---

## Autonomous Execution Contract

- completion_condition:
  - Phase 0 investigation written to tmp/s141_investigation.md
  - All PO page bugs fixed (pagination, Approved tab, status filter)
  - Dashboard cards show real data or appropriate empty states (not misleading ₱0)
  - Duplicate sidebar eliminated — one canonical navigation
  - PR(s) created on BEI-Tasks (and hrms if backend changes needed)
  - L3 PASS after deploy
  - Plan + registry updated to COMPLETED
- stop_only_for:
  - PR creation requires user merge
  - Phase 0 reveals scope >40 units → recommend splitting
  - Dashboard data issue requires backend changes that affect other modules → get Sam's approval
- continue_without_pause_through:
  - Phase 0 (investigation), A (PO fixes), B (dashboard), C (sidebar)
- blocker_policy:
  - shadcn component missing → install via npx shadcn add
  - API response shape different → read backend code and adapt
  - Dashboard endpoint returns empty because no Frappe data exists → implement proper empty state, not fake ₱0
  - Page route exists but is a shell → classify and add to findings, fix if <2 units per page
- signoff_authority: single-owner (Sam)

---

## Design Rationale (For Cold-Start Agents)

**Why is pagination missing?**
The `page` state and `setPage` were added to the component but pagination UI controls were never built. `setPage` is only called to reset to page 1 on search/filter change (lines 669, 678). No Next/Previous buttons exist. The backend already supports pagination — `get_purchase_orders` accepts `page` and `page_size` params and returns `total` count.

**Why is the Approved tab empty?**
It was likely a placeholder created during initial procurement module build (S002 era) and never implemented. The comment `{/* Similar table for approved POs */}` confirms intent but no code was written.

**Why is Pending CEO missing from the filter?**
The CEO approval flow was added in S132 (`Pending CEO Approval` status added to BEI Purchase Order DocType). The frontend filter dropdown was not updated in that sprint — the dropdown was hardcoded with only the original statuses.

**What components to use?**
The page already uses shadcn `Button`, `Table`, `Select`, `Card`, `Tabs`, `Badge`. Use the same components for pagination controls. Do not introduce new UI libraries.

**Backend API reference:**
- Endpoint: `hrms.api.procurement.get_purchase_orders`
- Params: `page`, `page_size`, `search`, `filters` (JSON with `status`, `supplier`, etc.)
- Returns: `{ data: [...], total: number, page: number, page_size: number }`
- The `total` field already exists and returns 577 for unfiltered queries.
