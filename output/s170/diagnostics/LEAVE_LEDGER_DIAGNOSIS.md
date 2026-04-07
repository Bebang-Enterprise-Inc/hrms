# S170 Phase 1 — Leave Ledger Diagnosis

## Reproduction
- HR-LAP-2026-00118: docstatus=1, status=Approved, total_leave_days=1.0, modified_by=test.supervisor@bebang.ph
- `Leave Ledger Entry` filter `transaction_name=HR-LAP-2026-00118` returns `data=[]`
- Same for HR-LAP-2026-00117

## Root cause: Hypothesis H2 (refined) — `bulk_action` API never sets status before submit

**File:** `hrms/api/leave_dashboard.py:317-353`

**Buggy code path** (line 337-340):
```python
if status == "Approved":
    if doc.docstatus == 0:
        doc.flags.ignore_permissions = True
        doc.submit()           # ← submitted with status STILL "Open"
```

**Why this breaks the ledger:**

1. Frontend calls `bulk_action(leave_ids, status="Approved")` from `leave-command-center` UI (verified in `bei-tasks/hooks/use-leave-dashboard.ts:163`).
2. The leave doc is at `docstatus=0, status="Open"` when fetched.
3. `bulk_action` calls `doc.submit()` WITHOUT first setting `doc.status = "Approved"`.
4. `LeaveApplication.on_submit` (line 101-114) runs and immediately checks:
   ```python
   if self.status in ["Open", "Cancelled"]:
       frappe.throw(_("Only Leave Applications with status 'Approved' and 'Rejected' can be submitted"))
   ```
5. The throw is **caught silently** by `bulk_action`'s `except Exception as exc` (line 350-351) and added to `failed` results.
6. The leave **stays at docstatus=0, status=Open** in this path.

**How leaves still end up at docstatus=1, status=Approved with no ledger:**

There's a separate code path (Frappe Desk standard form, or programmatic patch via `db_set`) that sets status=Approved + bumps docstatus=1 directly, bypassing `on_submit` entirely. This is how Lane D's HR-LAP-2026-00118 reached its current state. Either path is broken — the bulk_action API path NEVER successfully creates a ledger entry, and any direct mutation path bypasses the ledger entirely.

The `else` branch at line 342 (`doc.db_set("status", "Approved")` for already-submitted docs) is an additional silent gap: it changes status without invoking `create_leave_ledger_entry`.

## Fix (Task 1.2)

Modify `bulk_action` to:
1. Set `doc.status = status` BEFORE calling `submit()` so `on_submit`'s guard passes and `create_leave_ledger_entry` runs.
2. For the already-submitted edge case, call `doc.create_leave_ledger_entry()` directly after `db_set`.
3. Reload the doc after `db_set` so subsequent property reads are fresh.
4. Add `set_backend_observability_context` for Sentry traceability.

The fix is in `bulk_action` (the BEI-owned API), NOT in upstream `LeaveApplication.on_submit` — keeps fork delta minimal.

## Backfill (Task 1.3)

Existing broken leaves: query `tabLeave Application WHERE docstatus=1 AND status='Approved' AND name NOT IN (SELECT DISTINCT transaction_name FROM tabLeave Ledger Entry)`. For each, `frappe.get_doc(...).create_leave_ledger_entry()`.
