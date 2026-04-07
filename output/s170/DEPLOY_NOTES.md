# S170 Deploy Notes

## Critical: full Docker rebuild required

S170 introduces 3 new Frappe DocTypes (`BEI Clearance Station`, `BEI Clearance Item`, `BEI Clearance`). These are NOT custom fields — they require a full image rebuild and `bench migrate` on container startup.

**Mandatory deploy flags for `/deploy-frappe`:**
- `skip_build=false`
- `no_cache=true`

Skipping the build (or reusing a cached layer) will deploy code that references DocTypes the database doesn't have, breaking the clearance pages and the employee separation flow.

## What ships in this sprint

### Backend (hrms repo, branch `s170-s166-defect-fixes`)

| Change | File | Notes |
|---|---|---|
| Leave Ledger pipeline fix | `hrms/api/leave_dashboard.py` | `bulk_action` now sets `doc.status` before `submit()` so `on_submit` runs and `create_leave_ledger_entry` fires. Adds Sentry context. |
| Leave Ledger backfill | `scripts/s170_backfill_leave_ledger.py` | Run AFTER deploy to fix existing approved leaves missing ledger entries. Command: `bench --site hq.bebang.ph execute scripts.s170_backfill_leave_ledger.run` |
| OT filing API | `hrms/api/overtime_request.py` | New `create_overtime_request` endpoint. Resolves employee server-side from `frappe.session.user`. |
| BEI Clearance doctypes | `hrms/hr/doctype/bei_clearance{,_station,_item}/` | 3 new doctypes (1 master, 1 child, 1 parent submittable). Auto-installed by `bench migrate`. |
| Stations fixture | `hrms/fixtures/bei_clearance_station.json` | 8 default stations. Loaded automatically because `hooks.py:fixtures` now includes `"BEI Clearance Station"`. |
| Clearance API | `hrms/api/clearance.py` | `create_clearance`, `update_clearance_item`, `submit_clearance`, `get_clearance_for_user`. All instrumented for Sentry. |
| `hooks.py` | `hrms/hooks.py` | Added `"BEI Clearance Station"` to `fixtures` list. |

### Frontend (bei-tasks repo, branch `s170-s166-defect-fixes`)

| Change | File |
|---|---|
| Compensation route Page wrapper | `app/dashboard/hr/payroll/compensation-setup/[employee]/page.tsx` |
| New CompensationDetailPanel | `components/hr/compensation-detail-panel.tsx` |
| OT apply page | `app/dashboard/hr/overtime/apply/page.tsx` |
| OT page entry button | `app/dashboard/hr/overtime/page.tsx` |
| HR clearance page | `app/dashboard/hr/clearance/page.tsx` |

## Post-deploy verification (smoke checklist for Sam)

1. **Leave Ledger fix**
   - As `test.crew1`, file a Casual Leave for tomorrow.
   - As `test.supervisor`, approve via the Leave Command Center.
   - Run `bench --site hq.bebang.ph console` and `frappe.get_all("Leave Ledger Entry", filters={"transaction_name": "<HR-LAP-...>"})` — must return 1+ rows.
2. **Run backfill once (post-deploy):**
   ```
   bench --site hq.bebang.ph execute scripts.s170_backfill_leave_ledger.run
   ```
   Then check `output/s170/backfilled_leaves.csv` for the report.
3. **Compensation route**
   - Navigate to `/dashboard/hr/payroll/compensation-setup/9000003` (any real Bio ID).
   - Page must render with sections: Compensation, Deductions, Payroll Info — NOT an empty shell.
4. **OT apply**
   - Navigate to `/dashboard/hr/overtime/apply` as `test.crew1`.
   - File OT for an attended date in the last 7 days.
   - Verify the new BEI Overtime Request appears in the admin OT page with `overtime_status=Pending Review`.
5. **Clearance**
   - Navigate to `/dashboard/hr/clearance` as `test.hr`.
   - Paste an active Employee Separation name and click Initialize.
   - Mark all 8 items as Returned/Waived/Missing.
   - Click Submit Clearance — verify the linked Employee transitions to `status=Left`.

## Sentry verification

After first traffic, check the **bei-hrms** Sentry project (org: `bebang-enterprise-inc`) for breadcrumbs with these `module` tags:

- `leave` action `bulk_action`
- `overtime` action `create_overtime_request`
- `clearance` actions `create_clearance`, `update_clearance_item`, `submit_clearance`, `get_clearance_for_user`

If any of these are missing after a known invocation, the Sentry monkey-patch is broken and DM-7 is at risk.

## Rollback plan

Both PRs target the default branch (`production` for hrms, `main` for bei-tasks). To rollback:

1. `git revert <merge-commit>` on the affected repo
2. Redeploy with `skip_build=false` (the new doctypes will remain in the DB but unreferenced — they don't break Frappe)
3. The backfilled leave ledger entries from `s170_backfill_leave_ledger.py` are NOT reverted by the code rollback. If you need them gone too, run a manual `DELETE FROM tabLeave Ledger Entry WHERE creation > '<deploy-timestamp>' AND transaction_name LIKE 'HR-LAP-%'` — but normally you'd want to keep the corrected ledger.

## Out of scope (deferred to follow-up)

- Documenso integration for clearance signoff
- ADMS biometric de-enrollment on clearance submit
- Auto-create clearance on Employee Separation approval
- Fixture seeding for any environment that needs custom station codes (current fixture is the BEI default 8 stations)
