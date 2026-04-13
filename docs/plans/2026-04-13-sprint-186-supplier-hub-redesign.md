# S186 — Supplier Hub Redesign

- canonical_sprint_id: `S186`
- status: PR_CREATED
- completed_date: 2026-04-13
- execution_summary: Backend PR hrms#553 (get_supplier_grid + get_supplier_overview). Frontend branch pushed (s186-supplier-hub-frontend). Frontend PR pending backend deploy.
- created: 2026-04-13
- owner: Sam
- branch_backend: `s186-supplier-hub-backend` (hrms)
- branch_frontend: `s186-supplier-hub-frontend` (bei-tasks)
- depends_on: None (builds on existing BEI Supplier DocType + procurement API)
- estimated_units: ~80 (backend ~30, frontend ~45, proxy+closeout ~5)
- registry_lock: `| S186 | Sprint 186 | s186-supplier-hub-backend (hrms) + s186-supplier-hub-frontend (bei-tasks) | — | PLANNED 2026-04-13 |`

## Mission

Replace the basic supplier list + tabbed detail pages with a **Supplier Hub** — a dense, single-page supplier overview (bird's eye) and a single-page supplier detail (everything visible, no tabs). Modeled after the Employee Master Dashboard (S160) and Compensation Setup (S158) patterns.

The goal is: **one glance at the list tells you fleet-level supplier health; one click into a supplier tells you everything about that relationship without switching tabs.**

## Why Now

Procurement is live (S152 E2E accepted, S153 defects remediated). Sam needs to see supplier performance at a glance — who we spend the most with, who has pending POs, who is missing compliance docs, who delivers late. The current supplier pages are functional but require too many clicks and hide critical information behind tabs.

## Design Rationale (For Cold-Start Agents)

**Why this exists:** The current supplier list page (`bei-tasks/app/dashboard/procurement/suppliers/page.tsx`) is a basic table with 4 stat cards computed client-side, no frozen columns, no fullscreen, no URL-backed filters. The detail page (`bei-tasks/app/dashboard/procurement/suppliers/[id]/page.tsx`) uses a 5-tab layout (Details, Documents, Items, Orders, Invoices) that hides information behind clicks. Sam (CEO) wants everything visible at a glance — same as the Employee Master Dashboard (S160) and Compensation Setup (S158) he already uses daily.

**Why this architecture (two new endpoints, page rewrites):**
- The existing `get_suppliers` endpoint (line 277 of `hrms/api/procurement.py`) returns basic supplier fields but no PO/GR/Invoice aggregates and no fleet-level summary metrics. A new `get_supplier_grid` endpoint is needed to return all data the grid page needs in one call with server-side summary.
- The existing `get_supplier` (line 339), `get_supplier_purchase_orders` (line 470), `get_supplier_invoices` (line 501), and `get_supplier_items` (line 531) are separate endpoints requiring 4 round-trips. A new `get_supplier_overview` endpoint consolidates all into one call.
- The frontend pages are rewritten (not patched) because the layout pattern is fundamentally different — frozen-column matrix vs basic table, vertical stacking vs tabs.

**Key trade-off decisions:**
1. **New endpoints vs extending existing:** New endpoints chosen because `get_suppliers` (line 277) is used by other pages (supplier combobox, supplier approval queue). Changing its response shape would break existing consumers.
2. **Page rewrite vs patch:** Rewrite chosen because the tab-based detail page structure cannot be incrementally converted to vertical stacking — the entire component tree is different.
3. **Supplier Scorecard as placeholder:** Deferred to future sprint because KPI weights need Sam's input. Only raw metrics shown now.

**Known limitations:**
- BEI Supplier DocType (~37 data fields, 51 total entries including layout breaks, in `bei_supplier.json`) does NOT have a `category` field (FOOD/NON-FOOD/SERVICE). The `get_supplier_grid` endpoint omits category filter — it is not in the request parameters.
- **Stored metrics vs live aggregates:** The DocType has stored read-only fields (`total_po_count`, `total_po_value`, `total_outstanding`, `avg_delivery_days`, `on_time_rate`). These are stale snapshots. **S186 endpoints compute ALL metrics live via SQL JOINs. The stored DocType metrics fields are NOT used by S186.**
- The `contact_number` field in the DocType is named `contact_number`, not `phone`. The frontend must map accordingly.
- Compliance doc field names in DocType differ from display: `bir_2307` (Attach), `sec_certificate` (Attach), `business_permit` (Attach), with expiry dates `bir_expiry_date`, `sec_expiry_date`, `permit_expiry_date`.

## Scope Summary

### In-Scope
- **Supplier Grid page** — Employee-Master-style dense scrollable matrix with frozen columns, clickable KPI metric cards, rich filters, fullscreen mode, density toggle, URL-backed filters
- **Supplier Overview page** — Compensation-Setup-style vertical card stacking (NO tabs), all data visible: identity, contact, business info, compliance docs, spending summary, items purchased, recent POs, pending POs/GRs, invoice history
- **Backend API** — New `get_supplier_grid` endpoint (server-side metrics, filters, pagination) and `get_supplier_overview` endpoint (single-call everything for one supplier)
- **Future-ready** — Placeholder section for Supplier Scorecard (KPI-based rating)

### Out-of-Scope
- Supplier Scorecard KPI engine (future sprint — placeholder section only)
- Supplier onboarding workflow changes
- Purchase Order or Invoice page redesigns
- Edit/create supplier forms (existing forms remain as-is)
- Mobile-specific layouts (responsive is enough)

## Non-Negotiable Rules

1. **No tabs on the detail page.** Everything is visible in vertical card stacking. Collapsible sections are OK (like Employee Detail Dialog).
2. **Server-side metrics.** KPI cards must show fleet-level totals from the API, not client-side computation from the current page slice.
3. **Frozen columns.** Supplier name/code sticky left, actions sticky right — matches Employee Master pattern.
4. **URL-backed filters.** Every filter state is in the URL so links are shareable and browser back works.
5. **Reuse existing hooks/components.** Extend `hooks/use-procurement.ts`, reuse `HrPageHeader`, shadcn components.
6. **Sentry DM-7.** All new `@frappe.whitelist()` endpoints get `set_backend_observability_context()`.

## Existing Assets (Duplication Audit)

| Asset | Location | Classification | Notes |
|-------|----------|----------------|-------|
| BEI Supplier DocType | `hrms/hr/doctype/bei_supplier/bei_supplier.json` | REFERENCE | ~37 data fields, read schema for field names |
| `get_suppliers()` | `hrms/api/procurement.py:277` | REFERENCE | Do NOT modify — used by combobox/approval pages |
| `get_supplier()` | `hrms/api/procurement.py:339` | REFERENCE | Single supplier fetch — overview replaces need for multiple calls |
| `get_supplier_purchase_orders()` | `hrms/api/procurement.py:470` | REFERENCE | Keep — used by other pages |
| `get_supplier_invoices()` | `hrms/api/procurement.py:501` | REFERENCE | Keep — used by other pages |
| `get_supplier_items()` | `hrms/api/procurement.py:531` | REFERENCE | Keep — used by other pages |
| `get_supplier_metrics()` | `hrms/api/procurement.py:820` | REFERENCE | Basic metrics — overview supersedes for detail page |
| Supplier list page | `bei-tasks/app/dashboard/procurement/suppliers/page.tsx` | REPLACE | Full rewrite |
| Supplier detail page | `bei-tasks/app/dashboard/procurement/suppliers/[id]/page.tsx` | REPLACE | Full rewrite |
| Supplier edit page | `bei-tasks/app/dashboard/procurement/suppliers/[id]/edit/page.tsx` | SKIP | Keep as-is |
| New supplier page | `bei-tasks/app/dashboard/procurement/suppliers/new/page.tsx` | SKIP | Keep as-is |
| Supplier approvals | `bei-tasks/app/dashboard/procurement/suppliers/approvals/page.tsx` | SKIP | Keep as-is |
| Procurement hooks | `bei-tasks/hooks/use-procurement.ts` | EXTEND | Add `supplierGridOptions` + `supplierOverviewOptions` |
| API proxy | `bei-tasks/app/api/procurement/[...slug]/route.ts` | EXTEND | Add 2 new route mappings |
| Employee Master page | `bei-tasks/app/dashboard/hr/employee-master/page.tsx` | REFERENCE | Pattern source for grid |
| Compensation Setup | `bei-tasks/app/dashboard/hr/payroll/compensation-setup/page.tsx` | REFERENCE | Pattern source for detail |
| HrPageHeader | `bei-tasks/components/hr/hr-page-header.tsx` | REUSE | Generic enough for procurement |

## Architecture Context

```
┌─────────────────────────────────────────────────────────────────┐
│  my.bebang.ph (bei-tasks)                                       │
│                                                                 │
│  /dashboard/procurement/suppliers          ← Supplier Grid      │
│  /dashboard/procurement/suppliers/[id]     ← Supplier Overview  │
│                                                                 │
│  hooks/use-procurement.ts                  ← React Query hooks  │
│  app/api/procurement/[...slug]/route.ts    ← Proxy to Frappe    │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  Frappe Backend (hrms)                                          │
│                                                                 │
│  hrms/api/procurement.py (~7500 lines, 128 endpoints)           │
│    ├── get_supplier_grid()      ← NEW: paginated grid + metrics │
│    └── get_supplier_overview()  ← NEW: full supplier detail     │
│                                                                 │
│  Key tables:                                                    │
│    tabBEI Supplier         (~37 data fields, autoname=supplier_code) │
│    tabBEI Purchase Order   (autoname=PO-{YYYY}-{#####})         │
│    `tabBEI PO Item`        (child table — NOT "Purchase Order Item") │
│    tabBEI Invoice                                               │
│    tabBEI Goods Receipt                                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch (BACKEND):** `cd F:/Dropbox/Projects/BEI-ERP && git fetch origin production && git checkout -b s186-supplier-hub-backend origin/production`. NEVER write code on production.
3. **Create sprint branch (FRONTEND):** `cd F:/Dropbox/Projects/bei-tasks && git fetch origin main && git checkout -b s186-supplier-hub-frontend origin/main`. NEVER write code on main.
4. Read `docs/plans/SPRINT_REGISTRY.md` for cross-sprint context.
5. Read `hrms/api/procurement.py` lines 277-340 (existing `get_suppliers`) and lines 820-853 (existing `get_supplier_metrics`) to understand current patterns.
6. Read `hrms/hr/doctype/bei_supplier/bei_supplier.json` for field names.
7. Read `bei-tasks/hooks/use-procurement.ts` lines 1-50 (types + API_BASE) and lines 272-310 (existing supplier hooks).
8. Read `bei-tasks/app/api/procurement/[...slug]/route.ts` lines 105-255 (ROUTE_MAP) to understand proxy routing pattern.
9. Read `bei-tasks/app/dashboard/hr/employee-master/page.tsx` for grid pattern reference.
10. Confirm all Phase 0 dependencies are met before starting.

## Execution Authority

This sprint is intended for autonomous end-to-end execution across two lanes (backend then frontend).
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

---

## Delivery Phases

### Phase 0 — Backend: `get_supplier_grid` endpoint (~12 units)

Add a new whitelisted endpoint at the end of `hrms/api/procurement.py`.

**MUST_MODIFY:** `hrms/api/procurement.py`
**MUST_CONTAIN after:** `def get_supplier_grid` AND `set_backend_observability_context`

**Request parameters:**
- `search` (str, optional) — fuzzy match on supplier_name, supplier_code, contact_person, email
- `status` (str, optional) — Active / Inactive / Blacklisted / Pending Verification
- `compliance` (str, optional) — exception filter: missing_bir, missing_sec, missing_permit, expiring_soon
- `sort_by` (str, optional) — **HARD BLOCKER: Must be validated against allowlist before SQL interpolation (SQL injection risk).** Allowed values: `supplier_name`, `supplier_code`, `status`, `total_po_value`, `total_po_count`, `total_outstanding`, `on_time_rate`
- `sort_order` (str, optional) — asc / desc. **HARD BLOCKER: Validate against `{"ASC", "DESC"}` allowlist.**
- `page` (int, default 1)
- `page_size` (int, default 50)

**Sort param sanitization (MANDATORY):**
```python
ALLOWED_SORT_COLUMNS = {"supplier_name", "supplier_code", "status", "total_po_value", "total_po_count", "total_outstanding", "on_time_rate"}
ALLOWED_SORT_DIRECTIONS = {"ASC", "DESC"}
sort_col = sort_by if sort_by in ALLOWED_SORT_COLUMNS else "supplier_name"
sort_dir = sort_order.upper() if sort_order and sort_order.upper() in ALLOWED_SORT_DIRECTIONS else "ASC"
```

**Response shape:**
```python
{
  "data": [
    {
      "name": "SUP-001",
      "supplier_code": "SUP-001",
      "supplier_name": "...",
      "status": "Active",
      "contact_person": "...",
      "email": "...",
      "contact_number": "...",
      "tin": "...",
      "payment_terms": "...",
      "total_po_count": 42,
      "total_po_value": 1_250_000,
      "total_outstanding": 150_000,
      "pending_po_count": 3,
      "pending_gr_count": 2,
      "last_order_date": "2026-04-01",
      "on_time_rate": 87.5,
      "avg_delivery_days": 3.2,
      "bir_2307": true,          # boolean: has attachment
      "bir_expiry_date": "2026-12-31",
      "sec_certificate": true,
      "sec_expiry_date": "2027-06-30",
      "business_permit": false,
      "permit_expiry_date": null,
      "items_count": 15
    }
  ],
  "total": 81,
  "page": 1,
  "page_size": 50,
  "total_pages": 2,
  "summary": {
    "total_suppliers": 81,
    "active": 72,
    "inactive": 5,
    "blacklisted": 2,
    "pending_verification": 2,
    "missing_bir": 12,
    "missing_sec": 8,
    "missing_permit": 25,
    "expiring_soon": 4,
    "total_outstanding": 2_450_000,
    "total_pending_pos": 18,
    "total_pending_grs": 7
  },
  "filters": {
    "statuses": ["Active", "Inactive", "Blacklisted", "Pending Verification"]
  }
}
```

**Implementation notes:**
- Follow `_require_roles()` pattern at line 98 for role checking. Allowed: `{"Procurement User", "Procurement Manager", "Warehouse User", "System Manager"}`. **HARD BLOCKER: Must include `Warehouse User` — they have PROCUREMENT module access per `lib/roles.ts:635-642`.**
- **Metrics source of truth:** Compute ALL metrics live via SQL JOINs. Do NOT read stored DocType fields (`total_po_count`, `total_po_value`, `total_outstanding`) — they are stale snapshots.
- **Pending PO status values** (same as Phase 1): `status IN ('Draft', 'Pending Mae Approval', 'Pending Butch Approval', 'Pending CEO Approval')`
- Use `frappe.db.sql()` for supplier data with LEFT JOIN on `tabBEI Purchase Order` for PO aggregates.
- Summary computed across ALL suppliers (not just current page) — run a separate count query.
- Boolean compliance fields: `bool(supplier.bir_2307)` — Attach fields are truthy when populated.
- `set_backend_observability_context(module="procurement", action="get_supplier_grid")` as first line.
- **HARD BLOCKER:** The `contact_number` field in DocType is `contact_number`, NOT `phone`. Use the correct field name.

**Verification:**
- [ ] Returns correct total/active/inactive counts matching `frappe.db.count('BEI Supplier', {'status': 'Active'})`
- [ ] Search filters by name, code, email, contact person
- [ ] Status filter works
- [ ] Compliance exception filter works (missing_bir returns suppliers where bir_2307 is null/empty)
- [ ] Pagination works (page, page_size, total_pages)
- [ ] Sort by total_po_value and total_outstanding works
- [ ] Sentry context is set

### Phase 1 — Backend: `get_supplier_overview` endpoint (~12 units)

Add `hrms.api.procurement.get_supplier_overview` below `get_supplier_grid` in `hrms/api/procurement.py`.

**MUST_MODIFY:** `hrms/api/procurement.py`
**MUST_CONTAIN after:** `def get_supplier_overview` AND `set_backend_observability_context`

**Request:** `supplier` (str) — supplier name (doctype primary key)

**Response shape:**
```python
{
  "supplier": {
    # All BEI Supplier fields (use frappe.get_doc)
    "name", "supplier_code", "supplier_name", "status",
    "contact_person", "email", "contact_number", "address",
    "tin", "sec_registration", "vat_status",
    "payment_terms", "payment_terms_days",
    "bank_name", "bank_account_name", "bank_account_number",
    "ewt_applicable", "ewt_exempt", "default_ewt_rate", "atc_code",
    "bir_2307", "bir_expiry_date",
    "sec_certificate", "sec_expiry_date",
    "business_permit", "permit_expiry_date",
    "allow_missing_supplier_invoice", "is_new_supplier"
  },
  "metrics": {
    "total_po_count": 42,
    "total_po_value": 1_250_000,
    "total_outstanding": 150_000,
    "pending_po_count": 3,
    "pending_gr_count": 2,
    "pending_invoice_count": 1,
    "last_order_date": "2026-04-01",
    "first_order_date": "2025-06-15",
    "on_time_rate": 87.5,
    "avg_delivery_days": 3.2,
    "items_count": 15,
    "ytd_spend": 850_000,
    "last_month_spend": 120_000,
    "avg_monthly_spend": 104_166
  },
  "items": [...],         # aggregated from `tabBEI PO Item` (child table)
  "recent_pos": [...],    # last 20, sorted by po_date desc
  "pending_pos": [...],   # status NOT IN (Approved, Closed, Rejected)
  "pending_grs": [...],   # linked to supplier's POs, not completed
  "recent_invoices": [...], # last 20, sorted by invoice_date desc
  "monthly_spend": [...]  # last 12 months from PO data
}
```

**Implementation notes:**
- Supplier fetch: `frappe.get_doc("BEI Supplier", supplier)` — convert to dict, cast Attach fields to bool.
- **HARD BLOCKER: Child table is `tabBEI PO Item`, NOT `tabBEI Purchase Order Item`.** Verified in `bei_purchase_order.json` → `"options": "BEI PO Item"`.
- **HARD BLOCKER: Item price field is `unit_cost`, NOT `rate`.** Verified in `bei_po_item.json`.
- Items aggregated via SQL: `SELECT poi.item_code, poi.item_name, poi.uom, COUNT(DISTINCT poi.parent) as po_count, SUM(poi.qty) as total_qty, AVG(poi.unit_cost) as avg_unit_cost, SUM(poi.amount) as total_amount, MAX(po.po_date) as last_purchase_date FROM \`tabBEI PO Item\` poi JOIN \`tabBEI Purchase Order\` po ON poi.parent=po.name WHERE po.supplier=%(supplier)s GROUP BY poi.item_code ORDER BY total_amount DESC`
- Monthly spend: `SELECT DATE_FORMAT(po_date, '%%Y-%%m') as month, SUM(grand_total) as amount FROM \`tabBEI Purchase Order\` WHERE supplier=%(supplier)s AND po_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH) AND status NOT IN ('Rejected','Draft') GROUP BY month ORDER BY month`
- YTD spend: `SUM(grand_total) WHERE po_date >= CONCAT(YEAR(CURDATE()), '-01-01') AND status NOT IN ('Rejected','Draft')`
- **HARD BLOCKER: Pending PO status values are FULL strings:** `status IN ('Draft', 'Pending Mae Approval', 'Pending Butch Approval', 'Pending CEO Approval')`. NOT truncated forms like `'Pending Mae'`.
- `_require_roles()` allowed: `{"Procurement User", "Procurement Manager", "Warehouse User", "System Manager"}`
- `set_backend_observability_context(module="procurement", action="get_supplier_overview")`
- **HARD BLOCKER:** Field name is `sec_registration` NOT `sec_registration_no`. Check the DocType JSON.
- Use `frappe.get_doc("BEI Supplier", supplier).as_dict()` to return ALL supplier fields (do not hardcode the field list — the response shape above is illustrative).

**Verification:**
- [ ] Returns all supplier fields from DocType
- [ ] Metrics match manual SQL queries
- [ ] Items list correctly aggregated with avg/last rate
- [ ] recent_pos returns last 20 sorted by date desc
- [ ] pending_pos/pending_grs correctly filtered
- [ ] monthly_spend returns 12 months of data
- [ ] ytd_spend is correct for current year
- [ ] Works for supplier with 0 POs (empty arrays, zero metrics)

### Phase 2 — Frontend: Supplier Grid Page (~15 units)

Rewrite `bei-tasks/app/dashboard/procurement/suppliers/page.tsx` using the Employee Master pattern.

**MUST_MODIFY:** `bei-tasks/app/dashboard/procurement/suppliers/page.tsx`
**MUST_MODIFY:** `bei-tasks/hooks/use-procurement.ts` (add `supplierGridOptions`)
**MUST_CONTAIN after (page.tsx):** `MetricCard` AND `isFullscreen` AND `useSearchParams` AND `sticky left-0`

**Layout (top to bottom):**

1. **Header** — HrPageHeader with "Supplier Hub" title, `backHref={ROUTES.PROCUREMENT}`, "Add Supplier" button
2. **Metric Cards Row** — `grid gap-3 md:grid-cols-3 xl:grid-cols-7`
   - Total Suppliers (default)
   - Active (default)
   - Missing BIR 2307 (alert tone if >0, clickable → compliance filter)
   - Missing SEC Cert (alert tone if >0, clickable → compliance filter)
   - Missing Permit (alert tone if >0, clickable → compliance filter)
   - Expiring Soon (alert tone if >0, clickable → compliance filter)
   - Pending POs (clickable)
3. **Filter Card** — search, status, sort_by, page_size, density toggle, fullscreen toggle
4. **Scrollable Matrix** — frozen columns:
   - **Frozen left (sticky left-0 z-40):** Supplier Name + Code
   - **Scrollable center:** Status, Contact (email+phone), Documents (BIR/SEC/Permit badges), Payment Terms, Total POs, Total Spend, Outstanding, Pending POs, Pending GRs, Last Order, On-Time %, Items
   - **Frozen right (sticky right-0 z-20):** Actions dropdown (View, Edit, View POs, View Invoices)
5. **Pagination** — page controls with page_size selector (50, 100, 200)

**Key patterns to copy from Employee Master (`bei-tasks/app/dashboard/hr/employee-master/page.tsx`):**
- `MetricCard` component with `tone`, `active`, `onClick` props (lines 56-92)
- URL-backed filters via `useSearchParams` + `updateParams` helper (lines 195-208)
- Fullscreen mode: `fixed inset-0 z-50 bg-background` toggle (lines 155-163)
- Density toggle: compact h-12, comfortable h-16 row height
- Escape key handler for fullscreen exit
- Skeleton loading states for rows
- Empty state with `Building2` icon + "Add your first supplier" CTA

**React Query hook addition to `hooks/use-procurement.ts`:**

**MUST_MODIFY:** Add `queryOptions` to the existing import line:
```typescript
// BEFORE: import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
// AFTER:
import { useQuery, useMutation, useQueryClient, queryOptions } from '@tanstack/react-query';
```

```typescript
export interface SupplierGridParams {
  search?: string;
  status?: string;
  compliance?: string;
  sort_by?: string;
  sort_order?: string;
  page?: number;
  page_size?: number;
}

export const supplierGridOptions = (params: SupplierGridParams) =>
  queryOptions({
    queryKey: ['procurement', 'supplier-grid', params],
    queryFn: async () => {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([k, v]) => {
        if (v != null && v !== '') searchParams.set(k, String(v));
      });
      return fetchAPI<SupplierGridResponse>(`/suppliers/grid?${searchParams}`);
    },
  });
```

**RBAC:** Wrap in `<RoleGuard roles={[ROLES.PROCUREMENT_USER, ROLES.PROCUREMENT_MANAGER, ROLES.HQ_USER, ROLES.WAREHOUSE_USER, ROLES.SYSTEM_MANAGER, ROLES.ADMINISTRATOR]}>` per `lib/roles.ts:635-642`. **HARD BLOCKER: Must include `ROLES.WAREHOUSE_USER` — omitting it is a permission regression.**

**Verification:**
- [ ] 7 metric cards show server-side totals
- [ ] Clicking "Missing BIR" card sets `compliance=missing_bir` in URL
- [ ] Search works across supplier name, code, email, contact person
- [ ] Status filter works
- [ ] Frozen columns: supplier name stays visible during horizontal scroll
- [ ] Fullscreen mode works, Escape exits
- [ ] URL updates on every filter change
- [ ] Pagination with page_size options works
- [ ] Row click navigates to `/dashboard/procurement/suppliers/[id]`
- [ ] Loading skeleton shows during fetch
- [ ] Empty state shows when no suppliers match

### Phase 3 — Frontend: Supplier Overview Page (~15 units)

Rewrite `bei-tasks/app/dashboard/procurement/suppliers/[id]/page.tsx` using vertical stacking — **NO TABS**.

**MUST_MODIFY:** `bei-tasks/app/dashboard/procurement/suppliers/[id]/page.tsx`
**MUST_MODIFY:** `bei-tasks/hooks/use-procurement.ts` (add `supplierOverviewOptions`)
**MUST_CONTAIN after (page.tsx):** `Collapsible` AND `CollapsibleContent` AND NOT `TabsTrigger`

**Layout (top to bottom, all visible on scroll):**

1. **Header** — Back to `/dashboard/procurement/suppliers` + Supplier Name + Status Badge + Code + Edit/Blacklist buttons
2. **KPI Cards Row** — `grid gap-4 md:grid-cols-3 lg:grid-cols-6`: Total Spend, YTD Spend, Outstanding, Total POs, On-Time Rate %, Items Count
3. **Monthly Spend Trend** — Bar chart showing last 12 months using recharts `BarChart` (confirmed installed at `^2.15.4` in `bei-tasks/package.json`). When `monthly_spend` is empty or has <2 data points, show a placeholder ("No spend data yet" with muted chart icon) instead of an empty recharts instance.
4. **Section: Contact & Business Info** — `<Collapsible defaultOpen>`, 2-column grid
5. **Section: Compliance Documents** — `<Collapsible defaultOpen>`, document cards with status/expiry. Upload/Replace buttons MUST be present but `disabled` with tooltip "Use Frappe to upload documents" — do NOT leave them as unwired click targets (shell risk).
6. **Section: Items Purchased** — `<Collapsible defaultOpen>`, table sorted by total_amount desc
7. **Section: Pending Activity** — `<Collapsible defaultOpen>`, **alert border (`border-amber-300 bg-amber-50/80`) if any pending items**. Sub-tables: Pending POs, Pending GRs, Unpaid Invoices
8. **Section: Purchase Order History** — `<Collapsible>` (default closed), last 20 POs + "View all" link
9. **Section: Invoice History** — `<Collapsible>` (default closed), last 20 invoices + "View all" link
10. **Section: Supplier Scorecard** — `<Collapsible defaultOpen>`, placeholder with "Coming Soon" + raw metrics (On-Time Rate, Avg Delivery Days, Document Compliance %)

**Collapsible pattern (from `bei-tasks/app/dashboard/hr/employee-master/employee-detail-dialog.tsx`):**
```tsx
<Collapsible defaultOpen>
  <CollapsibleTrigger className="flex w-full items-center justify-between py-3 px-4 font-medium text-sm hover:bg-muted/50 rounded-lg">
    <span>Section Title</span>
    <ChevronDown className="h-4 w-4 transition-transform" />
  </CollapsibleTrigger>
  <CollapsibleContent className="px-4 pb-4">
    {/* content */}
  </CollapsibleContent>
</Collapsible>
```

**React Query hook:**
```typescript
export const supplierOverviewOptions = (supplier: string) =>
  queryOptions({
    queryKey: ['procurement', 'supplier-overview', supplier],
    queryFn: async () => fetchAPI<SupplierOverviewResponse>(`/suppliers/${supplier}/overview`),
    enabled: !!supplier,
    staleTime: 30_000,
  });
```

**Verification:**
- [ ] ALL data visible on one page — NO `<TabsTrigger>` or `<TabsContent>` in the file
- [ ] KPI cards show correct totals from API
- [ ] Contact info uses `contact_number` (NOT `phone`)
- [ ] Compliance docs show correct status with expiry warnings (amber <30 days, red expired)
- [ ] Items table aggregated from PO data, sorted by spend
- [ ] Pending Activity section has alert border when items exist
- [ ] PO and Invoice history tables render with links to detail pages
- [ ] Scorecard placeholder present with "Coming Soon"
- [ ] Back button navigates to supplier grid
- [ ] Works for supplier with 0 POs (graceful empty states)

### Phase 4 — API Proxy + Verification + Closeout (~5 units)

**MUST_MODIFY:** `bei-tasks/app/api/procurement/[...slug]/route.ts`
**MUST_CONTAIN after:** `get_supplier_grid` AND `get_supplier_overview`

**4a. API Proxy Routes** — Add to `ROUTE_MAP` in `bei-tasks/app/api/procurement/[...slug]/route.ts`. **HARD BLOCKER: Use the existing string-key format, NOT object literal format.** The route `/suppliers/grid` MUST appear as a direct key BEFORE the existing `/suppliers/:name` pattern to avoid the `:name` catch-all matching `grid` as a supplier name.

```typescript
// ADD these as string keys in ROUTE_MAP (matching existing format):
'GET /suppliers/grid': 'hrms.api.procurement.get_supplier_grid',
'GET /suppliers/:name/overview': 'hrms.api.procurement.get_supplier_overview',

// IMPORTANT: /suppliers/grid must come BEFORE /suppliers/:name in insertion order
// The proxy checks direct matches first (line 261), so /suppliers/grid as a direct key is safe
```

**4b. Create PRs (SEQUENTIAL — backend first, frontend second):**

**Step 4b-1: Backend PR (create FIRST):**
```bash
# Check divergence before PR
cd F:/Dropbox/Projects/BEI-ERP
git fetch origin production
GH_TOKEN="" gh api "repos/Bebang-Enterprise-Inc/hrms/compare/production...s186-supplier-hub-backend" --jq '.behind_by'
# If >0 behind: git rebase origin/production, verify no conflict markers, force-push
GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms --base production --head s186-supplier-hub-backend --title "feat(S186): Supplier Hub backend — get_supplier_grid + get_supplier_overview" --body "..."
```
Update `SPRINT_REGISTRY.md` with backend PR number. **STOP HERE.** Do NOT create frontend PR until Sam merges backend PR and Frappe deploy completes (skip_build=false required for new endpoints).

**Step 4b-2: Frontend PR (create AFTER backend is deployed):**
```bash
# Check divergence before PR
cd F:/Dropbox/Projects/bei-tasks
git fetch origin main
GH_TOKEN="" gh api "repos/Bebang-Enterprise-Inc/BEI-Tasks/compare/main...s186-supplier-hub-frontend" --jq '.behind_by'
# If >0 behind: git rebase origin/main, verify no conflict markers, force-push
GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/BEI-Tasks --base main --head s186-supplier-hub-frontend --title "feat(S186): Supplier Hub frontend — grid + overview redesign" --body "..."
```
Update `SPRINT_REGISTRY.md` with frontend PR number.

**4c. Closeout:**
- Update plan YAML: status `PLANNED` → `PR_CREATED`, add `completed_date`, `execution_summary`.
- Update `SPRINT_REGISTRY.md` row with PR numbers and status.
- Commit all artifacts:
```bash
git add -f docs/plans/2026-04-13-sprint-186-supplier-hub-redesign.md docs/plans/SPRINT_REGISTRY.md
git add -f output/s186/phase_0_checklist.md output/s186/phase_1_checklist.md output/s186/phase_2_checklist.md output/s186/phase_3_checklist.md output/s186/phase_4_checklist.md
git commit -m "chore(S186): plan closeout + phase checklists" && git push
```

**Rollback procedure (if frontend deploy breaks supplier pages):**
```bash
# Revert the frontend PR merge commit on bei-tasks main
git revert <frontend-PR-merge-commit>
git push origin main
# Vercel auto-redeploys within ~2 minutes, restoring old supplier pages
```

**Verification:**
- [ ] API proxy routes GET requests correctly to Frappe
- [ ] Plan YAML metadata updated to PR_CREATED
- [ ] SPRINT_REGISTRY.md updated with PR numbers

---

## Shell Prevention (S026)

### Failure Patterns to Prevent
1. **Dead metric cards** — cards render but show 0/NaN because API returns wrong shape
2. **Frozen columns without data** — sticky columns render but table has no scrollable content
3. **Compliance filter does nothing** — clicking "Missing BIR" card doesn't update URL or filter
4. **Empty detail page** — overview page renders sections but all show "—" because API failed

### Build Integrity Gates
| Gate | Description | Pass Criteria |
|------|-------------|---------------|
| `gate_route_contract_defined` | Both pages have routes in constants.ts | `PROCUREMENT_SUPPLIERS` already exists at `lib/constants.ts:289` |
| `gate_action_wiring_complete` | Every button/link leads to a real action | Row click → detail, Edit → edit page, View POs → PO list with filter |
| `gate_dependency_map_complete` | Frontend depends on backend endpoints existing | Backend PRs merged before frontend can be tested |
| `gate_navigation_placement_defined` | Pages are reachable from procurement sidebar | Already wired — `/dashboard/procurement/suppliers` exists in navigation |
| `gate_empty_error_states_defined` | Empty states for: no suppliers, no POs, no items, API error | Each section has empty text + icon |
| `gate_mutation_outcomes_defined` | No mutations in this sprint (read-only redesign) | N/A — skip |
| `gate_mobile_layout_defined` | Responsive breakpoints defined (md, lg, xl) | Grid columns collapse: xl:7 → md:3 → 1 |
| `gate_seed_dependency_defined` | Supplier data must exist in Frappe | BEI Supplier DocType has ~80 active records |
| `gate_backend_deployed_before_frontend` | Backend PR must be merged + deployed before frontend PR is created | Agent STOPs at Step 4b-1 until Sam confirms backend deploy |

### Vertical Slice First
Implement Phase 0 (`get_supplier_grid`) fully and test with curl before starting any frontend work. This proves the backend contract.

---

## Requirements Regression Checklist

- [ ] Does the Supplier Overview page have ZERO tabs? (Non-Negotiable Rule #1)
- [ ] Are KPI metrics computed server-side, not from the client page slice? (Non-Negotiable Rule #2)
- [ ] Does the grid have supplier name frozen left and actions frozen right? (Non-Negotiable Rule #3)
- [ ] Are all filter states in the URL via `useSearchParams`? (Non-Negotiable Rule #4)
- [ ] Is `hooks/use-procurement.ts` extended (not a new file)? (Non-Negotiable Rule #5)
- [ ] Does every new `@frappe.whitelist()` call `set_backend_observability_context()`? (Non-Negotiable Rule #6 / DM-7)
- [ ] Is `contact_number` used (NOT `phone`) per DocType schema? (Design Rationale)
- [ ] Is `sec_registration` used (NOT `sec_registration_no`) per DocType schema? (Design Rationale)
- [ ] Are compliance doc fields `bir_2307`, `sec_certificate`, `business_permit` (NOT `mayors_permit`)? (DocType JSON)
- [ ] Are expiry fields `bir_expiry_date`, `sec_expiry_date`, `permit_expiry_date`? (DocType JSON)
- [ ] Is RoleGuard using `PROCUREMENT_USER, PROCUREMENT_MANAGER, HQ_USER` per `lib/roles.ts:635`?
- [ ] Are existing endpoints (`get_suppliers` at line 277, `get_supplier` at line 339) left unmodified?
- [ ] Does the API proxy use `GH_TOKEN=""` prefix for all `gh` commands?
- [ ] Is the child table name `` `tabBEI PO Item` `` (NOT `tabBEI Purchase Order Item`)? (Audit CRIT-1)
- [ ] Are PO pending status strings FULL: `'Pending Mae Approval'` (NOT `'Pending Mae'`)? (Audit CRIT-2)
- [ ] Is the item price field `unit_cost` (NOT `rate`)? (Audit WARN-4)
- [ ] Are `sort_by`/`sort_order` validated against an allowlist before SQL interpolation? (Audit WARN-5)
- [ ] Does `WAREHOUSE_USER` appear in BOTH frontend RoleGuard AND backend `_require_roles()`? (Audit C-2/C-3)
- [ ] Is the proxy route key format `'GET /suppliers/grid': 'method'` (NOT object literal)? (Audit C-3)
- [ ] Are metrics computed live via JOINs (NOT read from stored DocType fields)? (Audit CRIT-5)
- [ ] Is `queryOptions` imported in `use-procurement.ts`? (Audit C-1)

---

## Zero-Skip Enforcement

Every task MUST be implemented, no exceptions. If a task cannot be completed, the agent STOPS and asks the user.

### Forbidden Agent Behaviors
- Skipping a task silently
- Marking partial work as "done"
- Replacing a task with a simpler version without user approval
- Saying "deferred to next sprint"
- Combining tasks and dropping features in the merge
- Implementing happy path only, skipping empty/error states

### Phase Completion Checklist Format
After each phase, the agent writes to `output/s186/phase_N_checklist.md`:
```
| Task | Status | Evidence | Skipped? | If skipped, why? |
```

### Machine-Verifiable Phase Gates (S154)

After completing Phase 0+1 (backend), run:
```bash
cd F:/Dropbox/Projects/BEI-ERP
git diff --name-only origin/production...HEAD | grep "procurement.py"
grep -c "def get_supplier_grid" hrms/api/procurement.py
grep -c "def get_supplier_overview" hrms/api/procurement.py
grep -c "set_backend_observability_context" hrms/api/procurement.py | tail -1
```
Expected: `procurement.py` in diff, both function counts = 1, observability count increased by 2.

After completing Phase 2+3 (frontend), run:
```bash
cd F:/Dropbox/Projects/bei-tasks
git diff --name-only origin/main...HEAD
grep -c "supplierGridOptions" hooks/use-procurement.ts
grep -c "supplierOverviewOptions" hooks/use-procurement.ts
grep -c "isFullscreen" app/dashboard/procurement/suppliers/page.tsx
grep -c "Collapsible" "app/dashboard/procurement/suppliers/[id]/page.tsx"
grep -c "TabsTrigger" "app/dashboard/procurement/suppliers/[id]/page.tsx"
```
Expected: Both hook options = 1, isFullscreen >= 1, Collapsible >= 5, TabsTrigger = 0.

---

## L3 Workflow Scenarios

> **Note:** L3 scenarios execute against production AFTER deploy. For S186 (read-only redesign), scenarios are navigation + data verification, not mutations.

| # | User | Action | Expected Outcome | Failure Means |
|---|------|--------|-------------------|---------------|
| L3-1 | test.procurement@bebang.ph | Open `/dashboard/procurement/suppliers`. Record metric card values. Cross-check "Active" count against `frappe.db.count('BEI Supplier', {'status': 'Active'})` — save both values to `state_verification.json` | Grid page loads, metric cards show totals matching Frappe data (Active count verified via SQL) | Backend `get_supplier_grid` broken or proxy misconfigured |
| L3-2 | test.procurement@bebang.ph | Click "Missing BIR" metric card | URL changes to `?compliance=missing_bir`, table filters to show only suppliers without BIR 2307 | Compliance exception filter not wired |
| L3-3 | test.procurement@bebang.ph | Type "sago" in search box | Table filters to show suppliers matching "sago" in name/code/email/contact | Search not implemented or debounce broken |
| L3-4 | test.procurement@bebang.ph | Click a supplier row | Navigates to `/dashboard/procurement/suppliers/[id]` showing overview page with KPI cards, contact info, items table, pending activity | Router or overview API broken |
| L3-5 | test.procurement@bebang.ph | On overview page, scroll down | All sections visible (Contact, Compliance, Items, Pending Activity, PO History, Invoice History, Scorecard placeholder) without clicking any tabs | Tabs still present — design violation |
| L3-6 | test.procurement@bebang.ph | On grid page, click Fullscreen button then press Escape | Grid expands to full viewport, then returns to normal layout | Fullscreen toggle broken |
| L3-7 | test.procurement@bebang.ph | On grid page, scroll horizontally | Supplier name column stays fixed on the left, actions column stays fixed on the right | Frozen columns not implemented |
| L3-8 | test.procurement@bebang.ph | Open an existing supplier with 0 POs (find one via grid sorted by total_po_count ASC, or use a known inactive supplier). Do NOT create a test supplier — avoid polluting production data | Overview shows "No items purchased yet", "No purchase orders yet", "No spend data yet" chart placeholder, metrics show 0/— | Empty states broken — distinguish "API returns empty correctly" vs "page crashes on empty response" |

**L3 evidence files required before closeout:**
```
output/l3/s186/form_submissions.json    # navigation evidence (URLs visited)
output/l3/s186/state_verification.json  # metric values verified
```

---

## Phase Budget Contract

| Phase | Units | Files Modified |
|-------|-------|----------------|
| Phase 0 — Backend: get_supplier_grid | 12 | `hrms/api/procurement.py` |
| Phase 1 — Backend: get_supplier_overview | 12 | `hrms/api/procurement.py` |
| Phase 2 — Frontend: Supplier Grid | 15 | `suppliers/page.tsx`, `use-procurement.ts` |
| Phase 3 — Frontend: Supplier Overview | 15 | `suppliers/[id]/page.tsx`, `use-procurement.ts` |
| Phase 4 — Proxy + PRs + Closeout | 5 | `[...slug]/route.ts`, registry, plan |
| **Total** | **~59** | |

- hard_limit: 15 per phase
- All phases within budget.

---

## Ground-Truth Lock

- **evidence_sources:**
  - `hrms/hr/doctype/bei_supplier/bei_supplier.json` → DocType field names (~37 data fields, 51 total entries)
  - `hrms/api/procurement.py` → existing endpoint signatures and line numbers
  - `bei-tasks/hooks/use-procurement.ts` → existing hook names and API_BASE pattern
  - `bei-tasks/app/api/procurement/[...slug]/route.ts` → ROUTE_MAP structure
  - `bei-tasks/lib/roles.ts:635-642` → PROCUREMENT module RBAC
  - `bei-tasks/lib/constants.ts:286-306` → PROCUREMENT route constants
- **authoritative_sections:** Delivery Phases (0-4) and Requirements Regression Checklist are authoritative for execution. This section is traceability only.

---

## Anti-Rewind / Concurrent-Run Protection

- **ownership_matrix:**
  - Backend lane owns: `hrms/api/procurement.py` (append-only — new functions at end of file)
  - Frontend lane owns: `bei-tasks/app/dashboard/procurement/suppliers/page.tsx`, `bei-tasks/app/dashboard/procurement/suppliers/[id]/page.tsx`, `bei-tasks/hooks/use-procurement.ts` (extend), `bei-tasks/app/api/procurement/[...slug]/route.ts` (extend ROUTE_MAP)
- **protected_surfaces:** All other procurement pages (`purchase-orders/`, `invoices/`, `goods-receipts/`, `payments/`, `approvals/`, `suppliers/new/`, `suppliers/[id]/edit/`, `suppliers/approvals/`) — DO NOT MODIFY.
- **remote_truth_baseline:** Latest `production` HEAD (hrms) and `main` HEAD (bei-tasks) at time of branch creation.

---

## Autonomous Execution Contract

- **completion_condition:**
  - Both `get_supplier_grid` and `get_supplier_overview` endpoints exist and return correct data
  - Supplier Grid page renders with metric cards, frozen columns, fullscreen, URL-backed filters
  - Supplier Overview page renders with NO tabs, all sections visible via vertical stacking
  - Backend PR created and shared with Sam (Step 4b-1)
  - Frontend PR created AFTER backend is deployed (Step 4b-2)
  - Plan YAML updated to PR_CREATED
  - SPRINT_REGISTRY.md updated with PR numbers
  - Phase checklist files written to `output/s186/`
- **stop_only_for:**
  - Missing credentials/access to Frappe or bei-tasks repo
  - BEI Supplier DocType schema has >50% deviation from documented ~37 data fields
  - `hrms/api/procurement.py` has merge conflicts from concurrent work
  - Business-policy question about supplier data visibility
  - Backend PR not yet merged by Sam (STOP before creating frontend PR)
- **continue_without_pause_through:** code → test → PR creation → closeout
- **blocker_policy:**
  - programmatic → fix and continue
  - field name mismatch → check DocType JSON, fix, continue
  - repeated technical failure x3 → stop and present options
  - business-data/policy → pause
- **signoff_authority:** single-owner (Sam)
- **canonical_closeout_artifacts:**
  - `docs/plans/2026-04-13-sprint-186-supplier-hub-redesign.md` (status updated)
  - `docs/plans/SPRINT_REGISTRY.md` (row updated)
  - `output/s186/phase_N_checklist.md` (per-phase)
  - `output/l3/s186/` (L3 evidence — deferred to post-deploy session)

---

## Execution Workflow

- Test Python changes: `/local-frappe`
- Deploy changes: PR-handoff (agent creates PR, Sam merges + deploys)
- E2E testing: `/e2e-test` or `/test-full-cycle` (post-deploy, separate session recommended)

---

## Verification Checklist (Final)

- [ ] Supplier Grid page shows 7 metric cards with server-side totals
- [ ] Clickable metric cards filter the grid (exception filter pattern)
- [ ] Grid has frozen supplier name column (left) and actions column (right)
- [ ] Fullscreen mode works with Escape to exit
- [ ] URL-backed filters are shareable
- [ ] Supplier Overview page has NO tabs — all sections visible on scroll
- [ ] KPI cards show lifetime spend, YTD spend, outstanding, total POs, on-time rate, items count
- [ ] Compliance section shows document status with expiry warnings
- [ ] Items Purchased table is correctly aggregated from PO data
- [ ] Pending Activity section highlights when pending items exist
- [ ] Scorecard placeholder is present with "Coming Soon"
- [ ] Both new API endpoints have Sentry DM-7 observability context
- [ ] RoleGuard wraps both pages with correct procurement roles
- [ ] Empty states work (supplier with 0 POs)
- [ ] Loading skeletons show during data fetch
- [ ] Phase gate verification scripts pass
- [ ] Plan YAML and SPRINT_REGISTRY.md updated

## Branch Lifecycle

| Branch | Repo | Merge Target | Cleanup |
|--------|------|--------------|---------|
| `s186-supplier-hub-backend` | hrms | production | Delete after PR merge |
| `s186-supplier-hub-frontend` | bei-tasks | main | Delete after PR merge |

Both branches created from latest default branch. PRs created separately. Backend deployed first (Frappe rebuild requires `skip_build=false`), then frontend (Vercel auto-deploys on merge to main).
