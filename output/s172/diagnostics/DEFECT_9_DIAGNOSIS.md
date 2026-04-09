# Defect #9 — test.hr proxy 403 on /api/resource/Employee

## Plan hypothesis (was wrong)
Plan said: "Add Employee doctype to the my.bebang.ph proxy permission allowlist for test.hr role. Find the proxy auth config in `../bei-tasks/app/api/frappe/[...path]/route.ts` or similar."

## Actual findings after inventory
1. `bei-tasks/app/api/frappe/[...path]/route.ts` (283 lines) is a **pure passthrough proxy**. It forwards cookies and body to Frappe, adds CSRF header for mutations, handles transient retries. **No allowlist. No role-based filtering. No doctype-level permission logic.**
2. `bei-tasks/middleware.ts` only checks for cookie presence (`bei_auth` or `sid`) for `/dashboard/*` routes. It explicitly excludes `api/*` from the matcher. **No per-doctype filtering.**
3. Grep for "Employee.*403", "EMPLOYEE_ALLOWLIST", "forbidden.*Employee", "test.hr" across `bei-tasks/app/api/`, `lib/`, `middleware.ts`: **zero matches.**

Therefore the 403 is coming from **Frappe itself**, not the proxy. The defect is a Frappe-side role permission gap, not a frontend allowlist.

## Root cause (Frappe side)
`/api/resource/Employee` is Frappe's built-in REST framework endpoint. It checks `has_permission("Employee", "read", user=session.user)`. If that returns false, Frappe emits 403. The standard ERPNext installation grants HR User and HR Manager read permission on Employee, but:
- A custom role may have been added/removed
- The production site may have had its DocPerm records tampered (manual admin edits, partial migration, stale fixture)
- test.hr's user record may be missing one of the expected roles

Note: `hrms/api/hr_reports.py:960 get_employee_permission_query_conditions` adds a row-level filter (`name NOT LIKE 'TEST-%'` OR `user_id = session.user`), but that's a WHERE clause injection that returns an empty list, NOT a 403. A 403 at the REST layer means the permission check failed before query construction.

## Fix applied
Added a Frappe patch `hrms/patches/s172_ensure_hr_employee_permissions.py` that idempotently ensures HR User and HR Manager roles have `read=1, write=1` on the Employee DocType in `tabDocPerm`. Runs on `bench migrate`. Safe: checks existence first, only inserts missing permissions, never downgrades.

Registered in `hrms/patches.txt` so it runs on the next deploy's `bench migrate` step.

## Verification post-deploy
After Sam deploys, the L3 retest scenario for this defect is:
```
login as test.hr@bebang.ph
GET /api/frappe/api/resource/Employee?limit_page_length=5
expect: 200 with a list of employees (possibly empty if permission_query_conditions filters them all, but NOT 403)
```
