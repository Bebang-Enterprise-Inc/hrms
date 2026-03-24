---
canonical_sprint_id: S108
display: Sprint 108
status: COMPLETED
branch: s108-pr-form-luwi-fix
lane: single
created_date: 2026-03-24
completed_date: 2026-03-24
deployed_at: 2026-03-24
backend_pr: "#341 (hrms)"
frontend_pr: "#236 (bei-tasks)"
l3_result: "3/3 PASS"
execution_summary: "Backend auto-sets request_date, requested_by, date_required(+7d), maps justification→purpose, item_code fallback. Frontend sends purpose instead of justification, card renamed. Sentry added. L3: PR-2026-02968 and PR-2026-02969 created by luwi@bebang.ph. Price auto-fill verified (RM001→195)."
depends_on: S107
---

# S108 — PR Form Fix: Make Purchase Requisitions Work for Luwi

**Goal:** Fix the remaining MandatoryError blockers so Luwi and Cayla can create Purchase Requisitions from my.bebang.ph tomorrow. The training guide (Section 3) says they should be able to create PRs — right now it fails with `MandatoryError: date_required, purpose`.

**Origin:** S107 L3 testing (2026-03-24) — PR creation returns MandatoryError because frontend doesn't send `date_required`, `purpose`, `request_date`, or `requested_by`. These are mandatory on BEI Purchase Requisition DocType.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists
S107 fixed the department/UOM dropdowns and price auto-fill, but L3 revealed the form has NEVER successfully created a PR. The backend requires `date_required`, `purpose`, `request_date`, `requested_by` — the frontend sends none of these.

### Why backend auto-set
The training guide (v2.0, March 2026) does NOT ask users to enter `date_required` or `request_date`. These should be auto-set:
- `request_date` = today
- `requested_by` = current user
- `date_required` = 7 days from now (default lead time)
- `purpose` = mapped from `justification` field (frontend label)

### Why minimal frontend changes
Luwi needs this working TOMORROW. Adding a DatePicker component risks TypeScript errors and Vercel build failures (S107 lesson: `z.coerce.number` broke the build). The safest path is: backend auto-sets defaults, frontend maps field names.

---

## Scope

### Phase A: Backend Fix (3 units)

| Task | Type | Description |
|------|------|-------------|
| A1 | FIX | In `create_purchase_requisition()`: auto-set `request_date`, `requested_by`, `date_required` if not provided. Map `justification` → `purpose`. |
| A2 | FIX | Add Sentry instrumentation to `create_purchase_requisition()` (DM-7). |
| A3 | VERIFY | Local test via `/local-frappe` — confirm PR creates without MandatoryError. |

### Phase B: Frontend Fix (3 units)

| Task | Type | Description |
|------|------|-------------|
| B1 | FIX | In onSubmit: map `justification` → `purpose` in the payload sent to backend. |
| B2 | FIX | Rename "Justification" card title to "Purpose" to match training guide language. |
| B3 | VERIFY | Run `npx tsc --noEmit` — zero TS errors before committing. **HARD BLOCKER.** |

### Phase C: Deploy + L3 Verify (6 units)

| Task | Type | Description |
|------|------|-------------|
| C1 | BUILD | Commit + push hrms branch. Create PR. |
| C2 | BUILD | Commit + push bei-tasks branch. Create PR. |
| C3 | BUILD | Merge PRs (governor or manual). Wait for deploy. |
| C4 | VERIFY | L3: Login as luwi@bebang.ph, fill PR form (dept=Commissary, item=Sago, qty=5, UOM=Kg, rate=84, purpose="Weekly supplies"), click Create PR. Must succeed. |
| C5 | VERIFY | L3: Verify PR appears in PR list. Verify pr_number in success toast. |
| C6 | BUILD | Closeout: update plan status, sprint registry, push evidence. |

**Total: 12 units.**

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| luwi@bebang.ph | Open New PR → select Commissary dept → add item Sago, qty=5, UOM=Kg, rate=84, purpose="Weekly supplies" → click Create PR | PR created, success toast with pr_number, redirect to PR detail | A1 auto-set not working |
| luwi@bebang.ph | Open New PR → enter item_code RM001 → Tab | Rate auto-fills with contracted price | S107 regression |
| sam@bebang.ph | Call create_purchase_requisition API with minimal data (dept + 1 item) | PR created, no MandatoryError | A1 defaults broken |

---

## Requirements Regression Checklist

- [ ] Does create_purchase_requisition auto-set request_date if not provided?
- [ ] Does create_purchase_requisition auto-set requested_by if not provided?
- [ ] Does create_purchase_requisition auto-set date_required (today+7) if not provided?
- [ ] Does create_purchase_requisition map justification → purpose?
- [ ] Does the frontend send `purpose` (not `justification`) in the payload?
- [ ] Does the PR form still send department as Link ID (S107)?
- [ ] Does item_code onBlur still auto-fill price (S107)?
- [ ] Does `npx tsc --noEmit` pass with zero errors?
- [ ] Does create_purchase_requisition have Sentry instrumentation?

---

## Autonomous Execution Contract

- **completion_condition:**
  - PR creation works end-to-end on live my.bebang.ph
  - L3 evidence files exist in output/l3/S108/
  - Plan YAML status = COMPLETED, pushed to production
  - SPRINT_REGISTRY.md updated

- **stop_only_for:**
  - Missing credentials/access
  - Governor down AND manual merge unauthorized

- **continue_without_pause_through:**
  - code → test → PR → deploy → L3 → closeout

- **blocker_policy:**
  - programmatic → fix and continue
  - TS type error → fix before pushing
  - business-data → pause

- **signoff_authority:** single-owner (Sam)

---

## Agent Boot Sequence

1. Read this plan fully.
2. Create sprint branch: `git checkout -b s108-pr-form-luwi-fix origin/production`
3. Read `hrms/api/procurement.py` line 588-601 (create_purchase_requisition)
4. Read `bei-tasks/app/dashboard/procurement/purchase-requisitions/new/page.tsx` line 171-191 (onSubmit)

## Execution Workflow
- Test Python changes: `/local-frappe`
- Deploy backend: create hrms PR → governor or manual merge
- Deploy frontend: push bei-tasks → Vercel auto-deploys on merge to main
- E2E testing: Node.js Playwright

## Execution Authority
This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
