
## 0.1_HR
- **time:** 2026-04-07T05:19:56.686Z
- **error:** no matching dept found for /^HR and Admin$|^HR and Admin - BEI$/i
- **hypothesis:** 

## 0.1_SupplyChain
- **time:** 2026-04-07T05:19:57.266Z
- **error:** no matching dept found for /^Supply Chain - BEI$|^Supply Chain$/i
- **hypothesis:** 

## DEFECT-004 — PCF-TEST-STORE-BGC fund references non-existent warehouse

- **Scenario:** Phase 0.2 (staff, supv), Phase 1 entire phase
- **Severity:** MEDIUM — blocks store PCF L3 testing in this sprint
- **Root cause:** Fund `PCF-TEST-STORE-BGC - BEI` has `store = "TEST-STORE-BGC - BEI"` but no `Warehouse` DocType with that name exists. The PCF resolver's `_get_store_for_employee` → `_resolve_store_name` returns None because `frappe.db.exists("Warehouse", ...)` is false for all tried suffixes.
- **Impact:** test.staff and test.supervisor (both on branch=TEST-STORE-BGC) cannot resolve any PCF fund, blocking Phase 1 store expense lifecycle (6 scenarios).
- **Fix:** Create the missing warehouse `TEST-STORE-BGC - BEI` under company `Bebang Enterprise Inc.` (sam currently lacks DocType Warehouse create permission via REST — requires either (a) role permission adjustment, (b) SSM direct insert, or (c) pointing the PCF fund at an existing warehouse).
- **S167 action:** Phase 1 (store lifecycle) marked BLOCKED in L3 report. Phases 2–5 continue with dept accounts.

## DEFECT-005 — update_pcf_settings silently ignores is_enabled

- **Scenario:** Phase 0 post-create fund enablement
- **Severity:** MEDIUM — blocks any programmatic enable/disable via the API
- **Root cause:** `POST /api/pcf {action:"update_pcf_settings", pcf_fund:"PCF-X", is_enabled:1}` returns success but the fund's `is_enabled` stays 0. Either the action handler doesn't map `is_enabled` to the DocType field, or the validated params filter strips it.
- **Impact:** new dept funds created via `create_pcf_fund` start with `is_enabled=0` and there is no UI/API path to enable them short of direct DocType mutation.
- **Workaround used in S167:** `PUT /api/frappe/api/resource/BEI Petty Cash Fund/{name}` with `{is_enabled:1}` — works (admin-only).
- **Fix recommendation:** Audit `update_pcf_settings` handler in `hrms/api/pcf.py` to ensure `is_enabled` is accepted + set on the doc.

## 2.2_submit
- **time:** 2026-04-08T11:50:02.681Z
- **error:** locator.waitFor: Timeout 15000ms exceeded.
Call log:
[2m  - waiting for getByRole('button', { name: /^submit batch$/i }).first() to be visible[22m

- **hypothesis:** 

## DEFECT-026
- **severity:** HIGH
- **title:** PCF Review Queue links break — `/review/{fund_name}` passed into `[batch]` route
- **time:** 2026-04-09
- **where:** `bei-tasks/app/dashboard/accounting/pcf/review/page.tsx:83` links to `/review/${encodeURIComponent(fund.name)}`, but `review/[batch]/page.tsx` treats `[batch]` as a batch_name and calls `get_batch_details?batch_name={fund_name}` → empty page.
- **impact:** Accountant cannot reach per-batch review UI via the queue. Workaround: direct-URL `/review/BEI-PCF-XXXX-YYYYY`.
- **fix (proposed):** Add intermediate fund-level batch list page `/review/fund/[fund_name]`, or change review/page.tsx to link to `/review/latest?fund=...` resolving to most-recent pending batch.
- **status:** OPEN

## DEFECT-027
- **severity:** MED
- **title:** Sidebar role filter leaks: non-owner users see PCF links for other departments
- **time:** 2026-04-09
- **where:** bei-tasks sidebar nav
- **evidence:** test.staff (crew) sees `/dashboard/hr-admin/pcf` anchors. test.hr sees `/dashboard/store-ops/pcf` anchors. test.finance sees both HR and store-ops PCF links without an accounting path in the visible PCF anchors list (though accountant review queue IS accessible).
- **impact:** Users can navigate to PCF pages outside their dept, then get role-gated page-level. RBAC still enforced at page level but sidebar should hide the links.
- **status:** OPEN

## DEFECT-028
- **severity:** LOW
- **title:** Legacy `/dashboard/expense/pcf` redirect lands on `/dashboard/accounting/pcf` for all users
- **time:** 2026-04-09
- **where:** bei-tasks middleware / redirect rule
- **evidence:** test.hr redirects to `/dashboard/accounting/pcf` and `/dashboard/accounting/pcf/add` — not their own dept path `/dashboard/hr-admin/pcf`. An HR custodian lands on the accountant page instead of their own dashboard.
- **expected:** redirect should resolve to the user's dept-specific PCF path based on role.
- **impact:** minor UX — user has to navigate back to correct path. Page still works via role gate.
- **status:** OPEN
