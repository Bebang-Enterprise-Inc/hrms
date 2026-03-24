---
canonical_sprint_id: S107
display: Sprint 107
status: COMPLETED
branch: s107-pr-form-frontend-fix
lane: single
created_date: 2026-03-24
completed_date: 2026-03-24
deployed_at: 2026-03-24
backend_pr: "#336 (hrms)"
frontend_pr: "#234 (bei-tasks)"
l3_result: "6/6 PASS"
execution_summary: "Backend PR #336 fixes get_department_list (returns {value,label} with company filter), get_uom_list ({value,label}), and adds pr_number to create_purchase_requisition response. Frontend PR #234 replaces hardcoded arrays with API-fetched data, adds item_code onBlur price auto-fill, fixes qty NaN. Build fix commit 0e08bbd (z.number vs z.coerce.number TS mismatch). L3 6/6 PASS including Luwi's bug verified fixed."
depends_on: S104
---

# S107 — Purchase Requisition Form Frontend Fix

**Goal:** Fix the New Purchase Requisition form at my.bebang.ph so departments, UOMs, and prices come from the database — not hardcoded arrays. Luwi reported "Could not find Department: Commissary" because the frontend sends `"Commissary"` but Frappe needs `"Commissary - BEI"`.

**Origin:** Luwi Azusano bug report (2026-03-24 4:25 PM). S104 L3 browser test confirmed: rate field shows P0.00 (no contracted price auto-fill), department dropdown sends wrong value.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists
The PR creation form (`bei-tasks/app/dashboard/procurement/purchase-requisitions/new/page.tsx`) has three hardcoded arrays that cause production failures:

1. **Departments** (line 94–105): Hardcoded `["Operations", "Commissary", ...]`. Frappe's `Department` table stores records as `"Commissary - BEI"` (with company abbreviation). The Link field validation rejects `"Commissary"` → users can't create PRs.

2. **UOMs** (line 108–123): Hardcoded `["Piece", "Box", "Pack", ...]`. Missing real UOMs like JAR, BARREL, GAL, BUNDLE, KG that exist in Frappe. Users can't select the right unit.

3. **No price auto-fill**: S104 added `get_contracted_price()` and updated `get_item_last_price()` to return `contracted_price`, but the form has no `onBlur` handler on the item_code field. The `estimated_rate` always starts at 0.

### Why this architecture
- **Fetch from API, not hardcode** — the backend already has `get_department_list()` and `get_uom_list()` endpoints (added in S099). They just need proxy routes in bei-tasks and hooks in the form.
- **Fix `get_department_list()` backend** — currently returns `department_name` (display name) but the Link field needs `name` (record ID like `"Commissary - BEI"`). Also returns 473 duplicates (one per company branch). Must return unique `name` values filtered to BEI company.
- **bei-tasks is a separate repo** — changes deploy to Vercel automatically on push to `main`. No Docker build needed.

### Key trade-offs
- **Return `name` vs `department_name`**: Return `name` (record ID) because that's what the Link field validates against. Show `department_name` as the display label in the dropdown.
- **Filter by company**: Only return departments for `Bebang Enterprise Inc.` — not all 473 across all companies.
- **Auto-fill price vs leave blank**: Auto-fill `estimated_rate` from `contracted_price` when available. If no contracted price, leave blank (don't auto-fill from PO history — that's the S104 design decision).

### Known limitations
- The PR form uses shadcn Select component with hardcoded options. Changing to API-fetched requires `useEffect` + loading state.
- The qty input issue Luwi reported needs investigation — may be a form validation or number input rendering issue.
- bei-tasks uses its own API proxy (`app/api/procurement/[...slug]/route.ts`) — direct Frappe API calls from the browser are blocked by CORS.

---

## Scope

### Phase A: Backend Fix — `get_department_list()` (3 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| A1 | FIX | `hrms/api/procurement.py` | Fix `get_department_list()`: (1) Return `name` (Link ID like `"Commissary - BEI"`) AND `department_name` (display label). (2) Filter by `company = "Bebang Enterprise Inc."`. (3) Deduplicate. Response shape: `[{value: "Commissary - BEI", label: "Commissary"}, ...]`. **HARD BLOCKER:** Must return `name` as `value` — the Link field validates against `name`, not `department_name`. | 2 |
| A2 | FIX | `hrms/api/procurement.py` | Fix `get_uom_list()`: Currently returns flat strings `["Nos", "Box"]`. Change to return `[{value: "Nos", label: "Nos"}, ...]` (same `{value, label}` shape as departments for consistency). This is a format change, not just verification. | 1 |
| A3 | FIX | `hrms/api/procurement.py` | Cleanup: add `pr_number: pr.pr_no or pr.name` to `create_purchase_requisition()` response. **Note:** The bei-tasks proxy at `route.ts:568` already patches this with `payload.pr_number ?? payload.name`, so the toast works. This is a backend-correctness fix, not a user-facing bug. | 1 |

### Phase B: Proxy Routes in bei-tasks (3 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| B1 | BUILD | `bei-tasks/.../route.ts` | Add 4 routes to ROUTE_MAP: `GET /lookup/departments` → `get_department_list`, `GET /lookup/uoms` → `get_uom_list`, `GET /lookup/item-price` → `get_item_last_price`, `GET /lookup/contracted-price` → `get_contracted_price`. | 2 |
| B2 | BUILD | `bei-tasks/hooks/use-procurement.ts` | Add hooks: `useDepartments()`, `useUOMs()`, `useItemPrice(itemCode)`. Each calls the new lookup proxy routes with TanStack Query caching. | 1 |

### Phase C: PR Form Fix — Wire API Data (8 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| C1 | FIX | `bei-tasks/.../new/page.tsx` | Replace hardcoded `departments` array with `useDepartments()` hook. Show loading spinner while fetching. Dropdown displays `label` (e.g., "Commissary") but sends `value` (e.g., "Commissary - BEI") in the form data. **HARD BLOCKER:** The value sent to Frappe MUST be the `name` field, not the display name. | 3 |
| C2 | FIX | `bei-tasks/.../new/page.tsx` | Replace hardcoded `uomOptions` array with `useUOMs()` hook. Same pattern — loading state, display label, send value. | 1 |
| C3 | BUILD | `bei-tasks/.../new/page.tsx` | Add `onBlur` handler on `item_code` input: when user tabs out, call `useItemPrice(itemCode)` → if `contracted_price` exists, auto-fill `estimated_rate` field. Show reference label below: "(contracted: P188.16)" or "(last PO: P80.24)" if no contracted price. | 3 |
| C4 | FIX | `bei-tasks/.../new/page.tsx` | Investigate and fix the qty input issue Luwi reported. Check if it's a form validation, number input type, or rendering bug. | 1 |

### Phase D: Verification + Closeout (4 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| D1 | VERIFY | Production | Browser test: open PR form → department dropdown loads from API → select "Commissary" → shows "Commissary" but sends "Commissary - BEI" → PR creates successfully. | 1 |
| D2 | VERIFY | Production | Browser test: enter item_code RM001 → tab → estimated_rate auto-fills with 188.16 (contracted price). | 1 |
| D3 | VERIFY | Production | Browser test: enter quantity → field accepts input → total calculates correctly. | 1 |
| D4 | BUILD | Closeout | Update plan status, sprint registry (`git add -f docs/plans/`), commit evidence. | 1 |

**Total: 19 work units across 4 phases.**

> Audit amendment (2026-03-24): +1 unit (A3 — pr_number response fix). A2 description corrected from "already correct" to "format change required".

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| luwi@bebang.ph | Open New PR form → click Department dropdown | Dropdown shows departments fetched from API (not hardcoded). "Commissary" appears as an option. | B2/C1 department fetch broken |
| luwi@bebang.ph | Select "Commissary" department → fill item SAGO, qty 1, UOM Kg, price 84 → click Create PR | PR created successfully. No "Could not find Department" error. | C1 sends display name instead of record ID |
| sam@bebang.ph | Open New PR form → enter item_code RM001 → press Tab | estimated_rate auto-fills with contracted price (P188.16). Reference label shows "(contracted: P188.16)". | C3 onBlur handler not wired |
| sam@bebang.ph | Open New PR form → enter item_code for item with no contracted price → press Tab | estimated_rate stays blank. No error. | C3 fallback broken |
| sam@bebang.ph | Open New PR form → click UOM dropdown | Shows UOMs fetched from API including JAR, BARREL, GAL, BUNDLE. Not just the old hardcoded 14. | B2/C2 UOM fetch broken |
| sam@bebang.ph | Open New PR form → enter qty field | Quantity accepts numeric input. | C4 qty regression |

Evidence files required before closeout:
```
output/l3/S107/form_submissions.json
output/l3/S107/api_mutations.json
output/l3/S107/state_verification.json
```

---

## Requirements Regression Checklist

- [ ] Does the department dropdown send the Frappe `name` (e.g., "Commissary - BEI"), NOT the display name (e.g., "Commissary")?
- [ ] Does the department dropdown show the human-readable `department_name` as the label?
- [ ] Are departments filtered to BEI company only (not 473 across all companies)?
- [ ] Does the UOM dropdown fetch from API instead of hardcoded array?
- [ ] Does item_code onBlur call get_item_last_price and read the contracted_price field?
- [ ] Does estimated_rate auto-fill from contracted_price (not last_po_price)?
- [ ] If no contracted price exists, does estimated_rate stay blank (not auto-fill from PO history)?
- [ ] Does the qty input field accept numeric input (Luwi's regression)?
- [ ] Are proxy routes added to ROUTE_MAP for all 4 lookup endpoints?
- [ ] Does the form show loading state while departments/UOMs are being fetched?
- [ ] Does create_purchase_requisition return pr_number in the response (not just name)?
- [ ] Does the success toast show the PR number (not "undefined")?
- [ ] Does get_uom_list return {value, label} objects (not flat strings)?
- [ ] Does every new/modified @frappe.whitelist() endpoint call set_backend_observability_context()?

---

## Autonomous Execution Contract

- completion_condition:
  - All phases A-D complete
  - All L3 scenarios pass with browser evidence
  - Plan YAML status updated to COMPLETED
  - SPRINT_REGISTRY.md updated
- stop_only_for:
  - Missing credentials/access to bei-tasks repo
  - Business-policy decision on department/UOM selection
- continue_without_pause_through:
  - code -> test -> PR creation (hrms + bei-tasks) -> deploy -> L3 -> closeout
- blocker_policy:
  - programmatic -> fix and continue
  - business-data/policy -> pause
- signoff_authority: single-owner (Sam)

---

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branches:**
   - hrms: `git fetch origin production && git checkout -b s107-pr-form-frontend-fix origin/production`
   - bei-tasks: `cd ../bei-tasks && git fetch origin main && git checkout -b s107-pr-form-frontend-fix origin/main`
3. Read `bei-tasks/app/dashboard/procurement/purchase-requisitions/new/page.tsx` — the PR form.
4. Read `bei-tasks/app/api/procurement/[...slug]/route.ts` — the ROUTE_MAP proxy.
5. Read `bei-tasks/hooks/use-procurement.ts` — existing hooks.
6. Read `hrms/api/procurement.py` — find `get_department_list()` and `get_uom_list()`.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

## Execution Workflow
- Test Python changes: `/local-frappe`
- Deploy backend: create hrms PR → governor handles merge + deploy
- Deploy frontend: push bei-tasks branch → Vercel auto-deploys on merge to main
- E2E testing: Node.js Playwright (Python Playwright is broken on this machine — use `npx playwright` or `node test.cjs`)
