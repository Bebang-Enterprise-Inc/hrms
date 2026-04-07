# S166 R2-Fix — Role Access Probe Results

**Run:** 2026-04-07T22:56:41+08:00

## Route Probed
`https://my.bebang.ph/dashboard/hr/overtime/apply`

## Per-Role Access Matrix

| Role | Email | Login OK | Final URL | Access Restricted | Form Present | Sidebar "My OT" | Screenshot |
|------|-------|----------|-----------|-------------------|--------------|-----------------|------------|
| test.crew1 | test.crew1@bebang.ph | ✅ | https://my.bebang.ph/dashboard/hr/overtime/apply | YES (blocked) | no | yes | probe_crew_apply_page.png |
| test.hr | test.hr@bebang.ph | ✅ | https://my.bebang.ph/dashboard/hr/overtime/apply | no | YES | yes | probe_hr_apply_page.png |
| test.supervisor | test.supervisor@bebang.ph | ✅ | https://my.bebang.ph/dashboard/hr/overtime/apply | no | YES | yes | probe_supervisor_apply_page.png |
| test.area | test.area@bebang.ph | ✅ | https://my.bebang.ph/dashboard/hr/overtime/apply | no | YES | yes | probe_area_apply_page.png |

## Defect #19 Scope Analysis

**SEVERITY: PARTIAL**

Accessible: test.hr, test.supervisor, test.area
Blocked: test.crew1

## RBAC Code Reference

File: `bei-tasks/app/dashboard/hr/overtime/apply/page.tsx`

Current RoleGuard allows: EMPLOYEE, STORE_STAFF, STORE_SUPERVISOR, AREA_SUPERVISOR, HR_USER, HR_MANAGER, HQ_FINANCE, SYSTEM_MANAGER, ADMINISTRATOR

**Missing role:** No explicit CREW or STORE_STAFF cross-mapping for test.crew1's Frappe role.
**To fix:** Verify test.crew1's Frappe role in hq.bebang.ph User doctype, confirm it maps to ROLES.STORE_STAFF or ROLES.EMPLOYEE in MODULES map.

