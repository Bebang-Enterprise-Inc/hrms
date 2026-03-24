# Sprint 107 — HR Self-Service Navigation Fix

```yaml
canonical_sprint_id: S107
status: GO
created: 2026-03-24
branch: s107-hr-self-service-nav-fix
lane: single
depends_on: null
completed_date: null
execution_summary: null
```

## Summary

Fix the HR Self-Service sidebar navigation so admin users (CEO, System Manager, HR Manager) can easily reach the self-service pages (Leave, Attendance, Payslip) without landing on the HR Command Center.

**Current bug:** Clicking "HR Self-Service" in the sidebar navigates to `/dashboard/hr` which renders the HR Command Center for admin roles. The employee self-service leave page exists at `/dashboard/hr/leave` but admins miss it because the section header takes them to the admin dashboard.

**Root cause:** `/dashboard/hr/page.tsx` already has role-aware rendering (`isHRAdmin ? <AdminHome /> : <SelfServiceHome />`), but for users with both admin AND employee roles (CEO, System Manager), the admin view takes priority and there's no visible path back to self-service.

## Design Rationale (For Cold-Start Agents)

### Why this exists

Sam (CEO, System Manager) reported that clicking "HR Self-Service" in the sidebar lands on the HR Command Center. He expected to see his own leave balance and file VL/SL. The self-service pages exist but are buried under sub-items that admins don't notice because the section header takes them to the wrong destination.

### Why this architecture

- **Option A (chosen): Add self-service quick-links to AdminHome** — Keep the current role-based routing but add a "My Self-Service" card at the top of the HR Command Center with direct links to Leave, Attendance, Payslip. This way admins who ARE employees can access both views from one page.
- **Option B (rejected): Remove `href` from HR Self-Service section header** — Would make the section header non-clickable. But this breaks expected behavior for regular employees who click the header to reach the self-service landing.
- **Option C (rejected): Role-based redirect** — Redirect admins to `/dashboard/hr/leave` when they click HR Self-Service. But admins need the Command Center too, and a redirect would hide it.

### Source references

- Sidebar nav config: `bei-tasks/components/layout/nav-main.tsx` line 247-252 (HR Self-Service has `href: ROUTES.HR`)
- Role check: `bei-tasks/app/dashboard/hr/page.tsx` lines 363-377 (isHRAdmin conditional)
- Self-service home: `bei-tasks/app/dashboard/hr/page.tsx` lines 91-124 (SelfServiceHome component)
- Admin home: `bei-tasks/app/dashboard/hr/page.tsx` lines 152-361 (AdminHome component)

## Duplication Audit

| Feature | Existing Code | Classification |
|---------|--------------|----------------|
| Self-service landing | `SelfServiceHome` in `page.tsx` lines 91-124 — exists but hidden from admins | [EXTEND] — add self-service links to admin view |
| Leave page | `/dashboard/hr/leave` — fully functional | [SKIP] |
| Admin dashboard | `AdminHome` in `page.tsx` — complete | [EXTEND] — add "My Leave" quick-link card |

## Phase 1 — Add Self-Service Quick Links to Admin View (~6 units)

### P1-1: Add "My Self-Service" card to AdminHome [EXTEND]

**What:** Add a compact card section at the TOP of `AdminHome` (before the stats grid) that gives admin users quick access to their own self-service pages:

```tsx
{/* My Self-Service — for admin users who are also employees */}
<Card className="border-dashed">
  <CardContent className="pt-4 pb-4">
    <div className="flex items-center justify-between">
      <div>
        <p className="text-sm font-medium text-muted-foreground">My Self-Service</p>
        <p className="text-xs text-muted-foreground">Access your personal HR services</p>
      </div>
      <div className="flex gap-2">
        <Button variant="outline" size="sm" asChild>
          <Link href={ROUTES.HR_LEAVE}>My Leave</Link>
        </Button>
        <Button variant="outline" size="sm" asChild>
          <Link href={ROUTES.HR_ATTENDANCE}>My Attendance</Link>
        </Button>
        <Button variant="outline" size="sm" asChild>
          <Link href={ROUTES.HR_PAYSLIP}>My Payslip</Link>
        </Button>
      </div>
    </div>
  </CardContent>
</Card>
```

**HARD BLOCKER:** Do NOT remove or change the role-based rendering logic. AdminHome must still render for admin roles. We are ADDING self-service links to it, not replacing it.

**Files:** `bei-tasks/app/dashboard/hr/page.tsx`

### P1-2: Verify sidebar "Leave" link works for all roles [SKIP — already works]

The sidebar already has "Leave" as a sub-item under "HR Self-Service" at `/dashboard/hr/leave`. No change needed — just verify during L3.

## Phase 2 — Closeout (~2 units)

### P2-1: Update plan and registry

1. Update this plan YAML: status -> COMPLETED
2. Update SPRINT_REGISTRY.md: S107 row -> COMPLETED
3. `git add -f docs/plans/` and push

## Shell Prevention — Failure Pattern

| Pattern | Risk | Mitigation |
|---------|------|------------|
| Admin clicks "HR Self-Service" → sees Command Center, can't find Leave | HIGH — current state | Add "My Self-Service" card with direct links |
| Self-service links broken for non-admin employees | LOW | RoleGuard already handles this; L3 tests both roles |
| "My Leave" link points to wrong route | LOW | Use ROUTES.HR_LEAVE constant |

## Build Integrity Gates

| Gate | Status |
|------|--------|
| gate_route_contract_defined | PASS — `/dashboard/hr/leave` exists |
| gate_action_wiring_complete | PASS — LeaveRequestDialog wired to POST /api/hr/leave |
| gate_dependency_map_complete | PASS — useLeave hook handles all API calls |
| gate_navigation_placement_defined | **FIX NEEDED** — admin users need visible path to self-service |
| gate_empty_error_states_defined | PASS — leave page handles loading/error states |
| gate_mutation_outcomes_defined | PASS — toast success/error on leave submission |
| gate_mobile_layout_defined | CHECK — verify "My Self-Service" card renders on mobile |

## L3 Workflow Scenarios

| # | User | Action | Expected Outcome | Failure Means |
|---|------|--------|-------------------|---------------|
| 1 | sam@bebang.ph (System Manager) | Navigate to /dashboard/hr | HR Command Center renders WITH "My Self-Service" card at top showing Leave/Attendance/Payslip links | Card not added or hidden |
| 2 | sam@bebang.ph | Click "My Leave" button in the self-service card | Navigates to /dashboard/hr/leave, shows leave balances and request button | Link broken or route guard blocks |
| 3 | test.crew1@bebang.ph (Crew) | Navigate to /dashboard/hr | SelfServiceHome renders (7-card layout) NOT the Command Center | Role check broken |
| 4 | test.crew1@bebang.ph | Click sidebar "Leave" under HR Self-Service | Navigates to /dashboard/hr/leave, shows leave balances | Sidebar link broken |

## Requirements Regression Checklist

- [ ] Does `/dashboard/hr` still show AdminHome for HR admin roles?
- [ ] Does `/dashboard/hr` still show SelfServiceHome for non-admin roles?
- [ ] Is the "My Self-Service" card visible at the TOP of AdminHome?
- [ ] Do the card links use ROUTES constants (not hardcoded paths)?
- [ ] Does the card render correctly on mobile (375px)?
- [ ] Is NO existing functionality removed or broken?

## Autonomous Execution Contract

- completion_condition:
  - "My Self-Service" card renders on /dashboard/hr for admin roles
  - All 4 L3 scenarios pass
  - plan YAML and SPRINT_REGISTRY.md updated to COMPLETED
- stop_only_for:
  - bei-tasks build failure
  - role check logic unclear
- signoff_authority: single-owner (Sam)

## Sentry Observability

No new `@frappe.whitelist()` endpoints or API routes modified. No Sentry instrumentation needed.

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch:** `cd ../bei-tasks && git fetch origin main && git checkout -b s107-hr-self-service-nav-fix origin/main`. NEVER write code on main.
3. Read `bei-tasks/app/dashboard/hr/page.tsx` fully.
4. Implement Phase 1.
5. Create PR targeting `main`.
6. Write L3 handoff prompt.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

## Execution Workflow

- Test frontend: `cd ../bei-tasks && npm run dev` (Vercel auto-deploys on push to main)
- Deploy: Vercel auto-deploy on PR merge to main
- No backend changes needed
