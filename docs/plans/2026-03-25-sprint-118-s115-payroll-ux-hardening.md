# S118 — Payroll Processing & Remittances UX Hardening

```yaml
canonical_sprint_id: S118
sprint_title: "S115 UX Hardening: Processing Wizard + Remittances for 500+ Employees"
status: COMPLETED
execution_started: 2026-03-25
deployed_at: 2026-03-25
completed_date: 2026-03-25
l3_result: "6/6 PASS, 0 defects"
backend_pr: "#348 (hrms) — MERGED"
frontend_pr: "#244, #246, #247 (BEI-Tasks) — MERGED"
branch: s118-payroll-processing-ux
repos:
  - bei-tasks
  - hrms (backend blocker grouping)
created_date: 2026-03-25
completed_date: null
execution_summary: null
depends_on: S115
total_units: 18
signoff_owner: Sam Karazi (sam@bebang.ph)
```

---

## Design Rationale (For Cold-Start Agents)

### Why This Sprint Exists

S115 delivered a working payroll processing wizard and remittances page. L3 testing passed 6/6. But UX review (2026-03-25) against the reality of **516 active employees** revealed that the surfaces are functionally correct but operationally painful at BEI's scale.

Key findings from screenshots:
1. The Step 2 employee blocker table renders 516 identical rows ("No income tax slab assigned") in a flat list with no search, filter, grouping, or pagination. Ronald (HR Manager) cannot find a specific employee or understand the overall blocker picture.
2. Step 1 shows two conflicting date ranges simultaneously (picker vs text).
3. Remittances YTD shows ₱0.00 with a flat gray mini-chart — indistinguishable from "broken" vs "first-run empty".
4. Export CSV is disabled without any explanation — user clicks and nothing happens.
5. Mobile step indicators show only numbers, not labels.

### Why These Specific Fixes

Every fix maps to a real operator pain point at 500+ employee scale:
- Fix 1+2 (blocker table): Ronald's primary workflow — reviewing who's blocked and why. A wall of 516 identical rows is useless.
- Fix 3 (date consistency): Confusing dates cause wrong payroll period selection — a financial risk.
- Fix 4+5 (empty states + disabled buttons): Operators will report "it's broken" when it's actually correct first-run behavior. Support tickets avoided.
- Fix 6 (mobile labels): Store supervisors checking payroll status on phones can't navigate the wizard.

### Key Trade-offs

- **Group-then-detail vs flat list**: We group by issue type first (e.g., "516: No tax slab"), then allow expanding to see individual employees. This handles the common case (bulk issue) while preserving per-employee detail for mixed issues.
- **Backend grouping vs frontend grouping**: The backend `get_processing_blockers` already returns per-employee data. We'll add a `grouped_summary` field to the response so the frontend doesn't have to iterate 516 rows to count issue types. This keeps the frontend fast.

---

## Requirements Regression Checklist

| # | Assertion | Status |
|---|-----------|--------|
| D01 | Processing is separate from data entry (no compensation fields) | [ ] |
| D02 | S076 blockers shown as structured UI with owner/remediation | [ ] |
| D06 | No visible control without real action or explicit disabled reason | [ ] |
| D08 | Dense surfaces work on 14-inch laptop + mobile fallback | [ ] |
| UX-1 | Employee blocker table has search + filter + group-by-issue at 500+ scale | [ ] |
| UX-2 | Identical issues grouped into summary rows (not 516 repetitions) | [ ] |
| UX-3 | Step 1 date text matches date picker value exactly | [ ] |
| UX-4 | Remittances YTD shows info banner when all months are zero | [ ] |
| UX-5 | Disabled Export shows tooltip explaining why | [ ] |
| UX-6 | Mobile step indicators show abbreviated labels | [ ] |
| UX-7 | ~~REMOVED — column already says "Issue" in source~~ | N/A |

---

## Ground-Truth Lock

| Claim | Evidence Source |
|-------|----------------|
| 516 employees shown in blocker table | `output/l3/S115/api_mutations.json` — `get_processing_blockers` returns `total_employees: 516` |
| All 516 blocked with same issue | L3 response: `blocked_count: 516`, all with `no_tax_slab` |
| Date inconsistency visible | Screenshot `output/l3/S115/artifacts/01_processing.png` |
| Export disabled without tooltip | Screenshot `output/l3/S115/artifacts/06_export.png` |
| Mobile shows numbers only | Screenshot `output/l3/S115/artifacts/BONUS_processing_mobile.png` |

---

## Duplication Audit

| Feature | Exists? | Action |
|---------|---------|--------|
| Employee blocker table | `processing/page.tsx` Step 2 | **[EXTEND]** — add search, filter, grouping |
| Date range display | `processing/page.tsx` Step 1 | **[EXTEND]** — fix inconsistency |
| Remittances YTD card | `remittances/page.tsx` | **[EXTEND]** — add empty state banner |
| Export button | `remittances/page.tsx` | **[EXTEND]** — add disabled tooltip |
| Step indicator | `processing/page.tsx` | **[EXTEND]** — add mobile labels |
| Backend blocker grouping | `hrms/api/payroll.py:get_processing_blockers` | **[EXTEND]** — add `grouped_summary` |

---

## Files This Sprint Owns (Exclusive)

**Modifies:**
- `F:\Dropbox\Projects\bei-tasks\app\dashboard\hr\payroll\processing\page.tsx` — Step 1 date fix, Step 2 blocker table overhaul, step indicator mobile labels
- `F:\Dropbox\Projects\bei-tasks\app\dashboard\hr\payroll\remittances\page.tsx` — YTD empty state, export tooltip
- `F:\Dropbox\Projects\BEI-ERP\hrms\api\payroll.py` — extend `get_processing_blockers` with `grouped_summary`

**Does NOT touch:**
- `payroll/page.tsx` (S113 landing — S117 owns)
- `current-cutoff/page.tsx`, `review-output/page.tsx`, `history/page.tsx` (S113)
- `compensation-setup/page.tsx`, `sensitive-changes/page.tsx` (S114)
- `hr-payroll.ts` query layer — extend `ProcessingBlockers` interface with `grouped_summary` field
- `roles.ts`, `constants.ts`

---

## Phase Budget Contract

| Phase | Units | Description |
|-------|-------|-------------|
| Phase 1 | 8 | Backend blocker grouping + frontend table overhaul |
| Phase 2 | 6 | Empty states, disabled tooltips, date fix |
| Phase 3 | 4 | Mobile labels, column rename, L3 + closeout |
| **Total** | **18** | |

---

## Phase 1 — Blocker Table Overhaul (8 units)

### Backend (2 units)

- [ ] 1u — Extend `get_processing_blockers` to include `grouped_summary` in response:
  ```python
  "grouped_summary": [
      {"issue_type": "no_tax_slab", "message": "No income tax slab assigned", "severity": "critical", "count": 516},
      {"issue_type": "no_ssa", "message": "No Salary Structure Assignment", "severity": "critical", "count": 33},
      {"issue_type": "no_bank", "message": "No bank account number", "severity": "warning", "count": 54},
  ]
  ```
  **HARD BLOCKER:** Do NOT remove the per-employee `blocked_employees` array. The grouped summary is ADDITIONAL, not a replacement. Frontend needs both.
- [ ] 1u — Add Sentry context to the extended endpoint. `module="payroll"`, `action="get_processing_blockers"`.

### Frontend — Step 2 Table (6 units)

- [ ] 1u — Replace flat employee list with **issue-group-first** view:
  - Show summary cards per issue type: "516 employees: No income tax slab" / "33: No SSA" / "54: No bank (warning)"
  - Each card is expandable to show the employee list for that issue
  - **HARD BLOCKER:** Collapsed by default. 516-row expand must be paginated (show 20 at a time with "Load more").

- [ ] 1u — Add **search by name** to the employee table within each group:
  - `<Input placeholder="Search employee..." />` at the top of each expanded group
  - Filters the visible employee rows client-side
  - Must handle 500+ rows without lag (use `useMemo` for filtering)

- [ ] 1u — Add **filter by department/branch** dropdown above the table:
  - Extracted from the employee data already in the response
  - "All Departments" default, then each department with count

- [ ] 1u — Add **sort** by employee name (A-Z/Z-A) and department:
  - Column headers clickable for sort toggle

- [ ] 1u — **Update `ProcessingBlockers` interface** in `hr-payroll.ts`:
  - Add `grouped_summary: Array<{issue_type: string, message: string, severity: string, count: number}>` to the interface
  - This is REQUIRED for type-safe access to the new backend field

- [ ] 1u — Add **total counts bar** above the table:
  - "516 total | 483 blocked (critical) | 33 blocked (no SSA) | 54 missing bank (warning)"
  - Use color-coded badges: red for critical, yellow for warning, green for ready

**Phase 1 gate:** Blocker table renders grouped view with search, filter, sort at 500+ employee scale. `npm run build` passes.

---

## Phase 2 — Empty States & Disabled Feedback (6 units)

- [ ] 1u — **Step 1 date consistency fix**: Remove the "Processing payroll for: 2026-02-28 to 2026-03-30" text. The date picker already shows the selected range. Two conflicting dates is worse than one clear one.

- [ ] 1u — **Remittances YTD empty state**: When all 12 months have `total_amount === 0`, replace the mini-chart with:
  ```
  ℹ️ No payroll runs completed for 2026
  Process your first payroll to see remittance data here.
  ```
  Keep the ₱0.00 total visible (it's factually correct) but add the explanation.

- [ ] 1u — **Export button disabled tooltip**: When Export is disabled, wrap with `<Tooltip>`:
  ```
  "No data to export — process payroll for this period first"
  ```
  Use shadcn `<TooltipProvider>` + `<Tooltip>` + `<TooltipTrigger>` + `<TooltipContent>`.

- [ ] 1u — **Step 2 readiness summary banner**: Above the blocker cards, show a clear summary:
  - When blocked: "❌ 2 critical blockers must be resolved before payroll can proceed"
  - When ready: "✅ System ready — all checks passed. X employees can be processed."
  - Currently this exists but could be more prominent with the blocker count in the banner.

- [ ] 1u — **Remittances empty state per tab**: When switching to a tab with no data, show the current "No Remittance Data" alert but add: "This is expected if no payroll has been processed for this period yet." (already partially there but verify consistency across all 4 tabs)

- [ ] 1u — **BIR tab content**: Currently shows a generic "use Frappe HRMS tax report module" message. Add the YTD income tax total from `get_remittance_summary` (the `bir` key) so Finance can see the number without going to Frappe.

**Phase 2 gate:** All empty states have explanatory text. Disabled Export has tooltip. Date text matches picker. `npm run build` passes.

---

## Phase 3 — Mobile + Polish + L3 + Closeout (4 units)

- [ ] 1u — **Mobile step labels**: On `sm:hidden` breakpoint, show abbreviated labels instead of just numbers:
  ```
  1 → "Period"
  2 → "Check"
  3 → "Generate"
  4 → "Review"
  5 → "Submit"
  6 → "Bank"
  ```
  Replace `<span className="sm:hidden">{step.id}</span>` with the abbreviation.
  Remove `overflow-x-auto` on desktop (6 labels fit at 1366px).

- [ ] 1u — **L3 scenarios** (all 6 from S115 rerun + new UX assertions):

| # | User | Action | Expected Outcome | Failure Means |
|---|------|--------|-----------------|---------------|
| L3-01 | test.hr@bebang.ph | Navigate to `/processing`, click Next to Step 2 | Grouped blocker summary visible (e.g., "516: No income tax slab"), NOT flat employee rows | Grouping not working |
| L3-02 | test.hr@bebang.ph | Expand "No income tax slab" group, type "ABAD" in search | Only employees matching "ABAD" shown in the expanded list | Search not filtering |
| L3-03 | test.hr@bebang.ph | Click department filter, select "Operations - BEI" | Only Operations employees shown | Filter broken |
| L3-04 | test.hr@bebang.ph | Navigate to `/remittances`, check SSS tab with no data | YTD shows info banner "No payroll runs completed for 2026" | Empty state missing explanation |
| L3-05 | test.hr@bebang.ph | Hover over disabled Export button | Tooltip shows "No data to export — process payroll first" | Tooltip missing |
| L3-06 | test.hr@bebang.ph | View `/processing` on 375px mobile | Step labels show "Period", "Check", "Generate" etc. | Only numbers shown |

- [ ] 1u — Closeout: Sentry audit, requirements regression check, plan + registry update.
- [ ] 1u — PR creation, governor merge, evidence commit.

**Phase 3 gate:** All 6 L3 scenarios pass. Plan YAML → COMPLETED. Registry updated.

---

## Shell Prevention

| Pattern | Why Forbidden |
|---------|--------------|
| Tooltip that doesn't appear on hover | S026 — visible control must have real feedback |
| Search input that doesn't actually filter | Shell affordance — looks functional but isn't |
| Grouped view that doesn't expand | Interaction promise without delivery |
| "Load more" that doesn't load more | Pagination shell |

---

## Agent Boot Sequence

1. Read this plan fully.
2. `git fetch origin production && git checkout -b s118-payroll-processing-ux origin/production`
3. Read `docs/plans/SPRINT_REGISTRY.md` for cross-sprint context.
4. Read `hrms/api/payroll.py` — map `get_processing_blockers` response shape.
5. Read `../bei-tasks/app/dashboard/hr/payroll/processing/page.tsx` — understand current Step 2 table.
6. Read `../bei-tasks/app/dashboard/hr/payroll/remittances/page.tsx` — understand current empty states.
7. Read `../bei-tasks/components/ui/tooltip.tsx` — confirm shadcn Tooltip available.

---

## Autonomous Execution Contract

```yaml
completion_condition:
  - all L3 scenarios pass with real browser interactions
  - npm run build passes on bei-tasks
  - Sentry context on modified backend endpoint
  - output/l3/S118/form_submissions.json exists with real form data
  - output/l3/S118/api_mutations.json exists with captured API calls
  - output/l3/S118/state_verification.json exists
  - git add -f output/l3/S118/ && git push (release manager gate requires this)
  - plan YAML → COMPLETED, registry updated, pushed to production (git add -f docs/plans/)
stop_only_for:
  - missing credentials/access
  - genuine business-policy decision
  - direct conflict with in-flight S117 changes to shared files
continue_without_pause_through:
  - execute → pr_creation → governor → L3 → closeout
blocker_policy:
  - programmatic → fix and continue
  - S117 file conflict → rebase and continue
  - business-data/policy → pause
signoff_authority: single-owner (Sam Karazi)
governor_protocol: standard (per /execute-plan-bei-erp — REJECT→fix+push, NEEDS_FIX→apply+push, Merge Conflict→rebase+force-push, Deploy Failure→check logs+fix)
```

---

## Sentry Observability

Modified endpoint: `get_processing_blockers` — already has `set_backend_observability_context`. Verify it's still present after adding `grouped_summary`. No new endpoints.

---

## Execution Workflow

- Test Python changes: `/local-frappe`
- Deploy changes: `/deploy-frappe`
- Full workflow: `/agent-kickoff`
- E2E testing: `/l3-v2-bei-erp`

---

*Sprint S118 — Created 2026-03-25 — UX hardening for S115 Payroll Processing & Remittances*
