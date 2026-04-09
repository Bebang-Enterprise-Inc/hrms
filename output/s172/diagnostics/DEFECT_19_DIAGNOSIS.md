# Defect #19 Diagnosis — `/dashboard/hr/overtime/apply` test.crew1 Access Restricted

## Source trace

| File | Line | Finding |
|---|---|---|
| `bei-tasks/app/dashboard/hr/overtime/apply/page.tsx` | 237-254 | Wraps `ApplyOvertimeForm` in `<RoleGuard roles={[EMPLOYEE, STORE_STAFF, STORE_SUPERVISOR, AREA_SUPERVISOR, HR_USER, HR_MANAGER, HQ_FINANCE, SYSTEM_MANAGER, ADMINISTRATOR]}>` |
| `bei-tasks/components/layout/role-guard.tsx` | 88-131 | `RoleGuard` calls `hasRole(userRoles, requiredRoles)` — fails-closed when user has zero matching roles |
| `bei-tasks/lib/roles.ts` | 986-988 | `hasRole` = `userRoles.some((role) => requiredRoles.includes(role))` — pure string includes |
| `bei-tasks/lib/roles.ts` | 16-59 | `ROLES` enum does NOT contain any "Crew" or "BEI Crew" entry |

## Root cause

`test.crew1@bebang.ph`'s actual Frappe role set is not in the RoleGuard allowlist. Two possible root causes:

1. **test.crew1 has a Frappe role like "BEI Crew" or "Crew"** — not in the `ROLES` enum, so `hasRole` returns false.
2. **test.crew1 has only `"Employee"` role** — but the RoleGuard already includes `ROLES.EMPLOYEE = "Employee"`, so this case should already pass.

Without production query access from this session, the most likely cause is #1: the user has a role string that doesn't match any of the 9 allowed strings.

## Fix rationale

`/dashboard/hr/overtime/apply` is a self-service OT filing page — by design, every employee who can log into my.bebang.ph should be able to file OT for themselves. There is no business reason to restrict this page by role; the dashboard layout already requires authentication, and the backend `overtime_request.py` validates the employee identity server-side.

The correct fix is to remove the RoleGuard wrapper entirely. The page is gated by auth middleware (dashboard layout), and the OT apply form operates on `frappe.session.user`'s own employee record — there is no way for an unauthorized user to file OT on behalf of someone else.

## Alternatives considered

| Option | Why rejected |
|---|---|
| Add "Crew" to `ROLES` enum + add to RoleGuard allowlist | Would fix test.crew1 but leaves ANY other unenumerated role (e.g., "BEI Driver", "Commissary Staff") broken. Not structurally correct for a self-service page. |
| Build dynamic role list from Employee doctype | Over-engineered for a self-service page. |
| Keep RoleGuard but pass no `roles` prop | When `requiredRoles` is empty, `RoleGuard` returns `hasAccess = true` (line 112) — equivalent to removing the wrapper but less explicit. |

## Fix applied

Removed the `<RoleGuard>` wrapper from `ApplyOvertimePage` export. The page is now accessible to any authenticated my.bebang.ph user, and the backend validates the actual Employee → User binding on submit.
