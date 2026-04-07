# S166 R2-Fix Summary

**Run completed:** 2026-04-07T22:57:16+08:00
**Route tested:** `/dashboard/hr/overtime/apply`

## Step 1 — Role Access Matrix

| Role | Can Access /apply | Notes |
|------|-------------------|-------|
| test.crew1 | NO (restricted=true, hasForm=false) |  |
| test.hr | YES |  |
| test.supervisor | YES |  |
| test.area | YES |  |

## Step 2 — OT Scenario Verdicts

| Scenario | Verdict | Notes |
|----------|---------|-------|
| EMP-OVERTIME-001 | FAIL | Submit error: Failed to load resource: the server responded with a status of 417 (); {"exception":"frappe.exceptions.ValidationError: No attendance record found on 2026-04-06. Overtime can only be filed for days you actually worked.","exc_type":"ValidationError","_exc_source":"hrms (app)","exc":"[\"Traceback (most recent call last):\\n  File \\\"apps/frappe/frappe/app.py\\\", line 120, in application\\n    response = frappe.api.handle(request)\\n               ^^^^^^^^^^^^^^^^^^^^^^^^^^\\n  File \\\"apps/frappe/frappe/api/__init__.py\\\", line 52, in handle\\n    data = endpoint(**arguments)\\n           ^^^^^^^^^^^^^^^^^^^^^\\n  File \\\"apps/frappe/frappe/api/v1.py\\\", line 40, in handle_rpc_call\\n    return frappe.handler.handle()\\n           ^^^^^^^^^^^^^^^^^^^^^^^\\n  File \\\"apps/frappe/frappe/handler.py\\\", line 53, in handle\\n    data = execute_cmd(cmd)\\n           ^^^^^^^^^^^^^^^^\\n  File \\\"apps/frappe/frappe/handler.py\\\", line 86, in execute_cmd\\n    return frappe.call(method, **frappe.form_dict)\\n           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\\n  File \\\"apps/frappe/frappe/__init__.py\\\", line 1764, in call\\n    return fn(*args, **newargs)\\n           ^^^^^^^^^^^^^^^^^^^^\\n  File \\\"apps/frappe/frappe/utils/typing_validations.py\\\", line 32, in wrapper\\n    return func(*args, **kwargs)\\n           ^^^^^^^^^^^^^^^^^^^^^\\n  File \\\"apps/hrms/hrms/api/overtime_request.py\\\", line 94, in create_overtime_request\\n    frappe.throw(\\n  File \\\"apps/frappe/frappe/__init__.py\\\", line 619, in throw\\n    msgprint(\\n  File \\\"apps/frappe/frappe/__init__.py\\\", line 584, in msgprint\\n    _raise_exception()\\n  File \\\"apps/frappe/frappe/__init__.py\\\", line 535, in _raise_exception\\n    raise exc\\nfrappe.exceptions.ValidationError: No attendance record found on 2026-04-06. Overtime can only be filed for days you actually worked.\\n\"]","_server_messages":"[\"{\\\"message\\\": \\\"No attendance record found on 2026-04-06. Overtime can only be filed for days you actually worked.\\\", \\\"title\\\": \\\"Message\\\", \\\"indicator\\\": \\\"red\\\", \\\"raise_exception\\\": 1, \\\"__frappe_exc_id\\\": \\\"92dc7a729569148c3742635c801546f957bb5358f283ad3d3417d73c\\\"}\"]"} |
| EMP-OVERTIME-002 | FAIL | SKIP_DEPENDS: OT-001 did not produce a docname |
| EMP-OVERTIME-003 | FAIL | Second OT not created (name not captured) — cannot test rejection |

## Defect #19 Scope

**PARTIAL** — 3 role(s) accessible, 1 blocked.

## OTs Created During Run

None created.

## Cleanup

No cleanup required (no OTs created).

## Evidence Files

- `F:\Dropbox\Projects\BEI-ERP\output\l3\s166\lanes\retest\r2_fix\PROBE_RESULTS.md`
- `F:\Dropbox\Projects\BEI-ERP\output\l3\s166\lanes\retest\r2_fix\evidence\EMP-OVERTIME-001-retest2.json`
- `F:\Dropbox\Projects\BEI-ERP\output\l3\s166\lanes\retest\r2_fix\evidence\EMP-OVERTIME-002-retest2.json`
- `F:\Dropbox\Projects\BEI-ERP\output\l3\s166\lanes\retest\r2_fix\evidence\EMP-OVERTIME-003-retest2.json`
- Screenshots in `F:\Dropbox\Projects\BEI-ERP\output\l3\s166\lanes\retest\r2_fix\screenshots`
