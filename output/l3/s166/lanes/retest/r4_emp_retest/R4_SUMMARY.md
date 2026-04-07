# R4 EMP-RETEST Summary

**Generated:** 4/7/2026, 22:51:55 PHT
**EMP-RETEST:** HR-EMP-00046 (bio_id=9001894)
**Branch:** ARANETA GATEWAY
**Cleanup status:** cleanup_partial

## Totals

| Status | Count |
|--------|-------|
| PASS | 4 |
| DEFECT-PASS | 2 |
| SKIP | 18 |
| FAIL | 9 |
| **Total** | **33** |

## S170 Phase 2 Check (compensation-setup/[employee])

See evidence/COMP_PAGE_PROBE-retest.json for Phase 2 page render result.

## S170 Phase 4 Check (clearance module)

See evidence/EMP-TERMINATE-002-retest.json for Phase 4 clearance module detection.

## Defect #16 (SSA activation)

See evidence/EMP-SALARY-CHANGE-002-retest.json for SSA verification result.

## Per-Scenario Verdicts

| Scenario | Status | Note |
|----------|--------|------|
| EMP-CREATE-RETEST | PASS | Created HR-EMP-00046 bio_id=9001894 |
| EMP-SALARY-SETUP-001 | FAIL | No BCC returned. API resp: {"ok":false,"status":417,"json":{"exception":"frappe.exceptions.ValidationError: Failed to get method for command hrms.api.payroll.update_compensation with module 'hrms.api.payroll' has no attribute ' |
| EMP-SALARY-SETUP-002 | FAIL | locator.click: Timeout 30000ms exceeded.
Call log:
[2m  - waiting for getByRole('button', { name: /edit/i }).first()[22m
[2m    - locator resolved to <button disabled data-slot="button" class="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive bg-primary text-pri…>…</button>[22m
[2m  - attempting click action[22m
[2m    2 × waiting for element to be visible, enabled and stable[22m
[2m      - element is not enabled[22m
[2m    - retrying click action[22m
[2m    - waiting 20ms[22m
[2m    2 × waiting for element to be visible, enabled and stable[22m
[2m      - element is not enabled[22m
[2m    - retrying click action[22m
[2m      - waiting 100ms[22m
[2m    57 × waiting for element to be visible, enabled and stable[22m
[2m       - element is not enabled[22m
[2m     - retrying click action[22m
[2m       - waiting 500ms[22m
 |
| EMP-SALARY-SETUP-003 | DEFECT-PASS | Statutory deductions are auto-computed from base salary — no separate BCC. Compensation page shows statutory preview. Architectural note recorded. |
| EMP-SALARY-SETUP-004 | SKIP | Formula-based components not addressable via update_compensation API — same architectural note as A4 SALARY-SETUP-004. Compensation UI shows computed values (daily rate, gross, deductions) but formula components have no input field. |
| EMP-SALARY-CHANGE-001 | FAIL | No BCC returned: "{\"exception\":\"frappe.exceptions.ValidationError: Failed to get method for command hrms.api.payroll.update_compensation with module 'hrms.api.payro |
| EMP-SALARY-CHANGE-002 | SKIP | No BCC from CHANGE-001 to approve |
| EMP-SALARY-CHANGE-003 | FAIL | No BCC: "{\"exception\":\"frappe.exceptions.ValidationError: Failed to get method for command hrms.api.payroll.update_compensation with module 'hrms.api.payro |
| EMP-SALARY-CHANGE-004 | FAIL | No BCC: "{\"exception\":\"frappe.exceptions.ValidationError: Failed to get method for command hrms.api.payroll.update_compensation with module 'hrms.api.payro |
| EMP-SALARY-CHANGE-005 | FAIL | No BCC to reject: "{\"exception\":\"frappe.exceptions.ValidationError: Failed to get method for command hrms.api.payroll.update_compensation with module 'hrms.api.payro |
| EMP-SALARY-CHANGE-006 | PASS | negative rejected=true, zero=rejected, string rejected=true |
| EMP-SALARY-PAYROLL-001 | SKIP | DEFER_PAYROLL_RUN_NOT_TRIGGERED: no payroll run covers EMP-RETEST period. Consistent with Lane A A4. Salary Structure Assignment may exist but no salary slip generated. |
| EMP-SALARY-PAYROLL-002 | SKIP | DEFER_PAYROLL_RUN_NOT_TRIGGERED: no payroll run covers EMP-RETEST period. Consistent with Lane A A4. Salary Structure Assignment may exist but no salary slip generated. |
| EMP-REGULARIZE-001 | PASS | employment_type=Regular confirmed via API (HR-EMP-00046) |
| EMP-REGULARIZE-002 | PASS | employment_type=Regular, compliance page loads, 13th month check available |
| EMP-TERMINATE-001 | FAIL | locator.click: Timeout 30000ms exceeded.
Call log:
[2m  - waiting for locator('[role="dialog"]').first().getByRole('button', { name: /create/submit/start/i }).first()[22m
[2m    - locator resolved to <button disabled type="submit" data-slot="button" class="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive bg-pr…>Create Separation</button>[22m
[2m  - attempting click action[22m
[2m    2 × waiting for element to be visible, enabled and stable[22m
[2m      - element is not enabled[22m
[2m    - retrying click action[22m
[2m    - waiting 20ms[22m
[2m    2 × waiting for element to be visible, enabled and stable[22m
[2m      - element is not enabled[22m
[2m    - retrying click action[22m
[2m      - waiting 100ms[22m
[2m    57 × waiting for element to be visible, enabled and stable[22m
[2m       - element is not enabled[22m
[2m     - retrying click action[22m
[2m       - waiting 500ms[22m
 |
| EMP-TERMINATE-002 | FAIL | Clearance init failed. API: "{\"exc_type\":\"DoesNotExistError\",\"_server_messages\":\"[\\\"{\\\\\\\"message\\\\\\\": \\\\\\\"Employee Separation HR-EMP-SEP-HR-EMP-00046 not found\\\\\\\", \\\\\\\"title\\\\\\\": \\\\\\\"Message |
| EMP-TERMINATE-003 | SKIP | No clearance_name in empState — depends on TERMINATE-002 |
| EMP-TERMINATE-004 | SKIP | DEFER_DOCUMENSO_INTEGRATION: Documenso integration deferred per S170 Phase 4 scope. No documenso trigger in clearance API as of deployment. |
| EMP-TERMINATE-005 | SKIP | No clearance_name — depends on TERMINATE-002 |
| EMP-TERMINATE-006 | DEFECT-PASS | EMP-RETEST status=Active in Employee API |
| EMP-FINALPAY-001 | SKIP | DEFER_FINAL_PAY: Final pay feature not discoverable in payroll dashboard |
| EMP-FINALPAY-002 | SKIP | DEFER_FINAL_PAY: Final pay feature not discoverable in payroll dashboard |
| EMP-FINALPAY-003 | SKIP | DEFER_FINAL_PAY: Final pay feature not discoverable in payroll dashboard |
| EMP-USERDISABLE-001 | SKIP | No user_id on EMP-RETEST employee record (fresh test employee may not have a user account) |
| EMP-USERDISABLE-002 | SKIP | No user_id on EMP-RETEST employee record (fresh test employee may not have a user account) |
| EMP-ADMSREMOVE-001 | SKIP | No ADMS DELETE_USERINFO command queued for EMP-RETEST. ADMS removal may be triggered only if Bio ID was enrolled. EMP-RETEST had bio_id cleared during cleanup. |
| EMP-ADMSREMOVE-002 | SKIP | No ADMS DELETE_USERINFO command queued for EMP-RETEST. ADMS removal may be triggered only if Bio ID was enrolled. EMP-RETEST had bio_id cleared during cleanup. |
| EMP-EXITINTERVIEW-001 | FAIL | Exit interview route not found: h1="" |
| EMP-EXITINTERVIEW-002 | SKIP | DEPENDS_ON_EXITINTERVIEW-001 |
| EMP-EXITINTERVIEW-003 | SKIP | DEPENDS_ON_EXITINTERVIEW-001 |
| EMP-REHIRE-001 | SKIP | DEFER_REHIRE: No rehire UI element found. Rehire pathway not implemented or requires different entry point. EMP-RETEST is Left — no rehire attempted to avoid polluting bio_id sequence. |
| EMP-REHIRE-002 | SKIP | DEFER_REHIRE: No rehire UI element found. Rehire pathway not implemented or requires different entry point. EMP-RETEST is Left — no rehire attempted to avoid polluting bio_id sequence. |

## Defects Found

_(none beyond previously tracked)_

## Cleanup

- EMP-RETEST: cleanup_partial
- BCCs created: 0
- Clearance: none
- Separation: none
- ORPHANS.csv written: see F:/Dropbox/Projects/BEI-ERP/output/l3/s166/lanes/retest/r4_emp_retest/ORPHANS.csv

## Ready for R4 Audit

Evidence directory: `F:/Dropbox/Projects/BEI-ERP/output/l3/s166/lanes/retest/r4_emp_retest/evidence`
Screenshots: `F:/Dropbox/Projects/BEI-ERP/output/l3/s166/lanes/retest/r4_emp_retest/screenshots`