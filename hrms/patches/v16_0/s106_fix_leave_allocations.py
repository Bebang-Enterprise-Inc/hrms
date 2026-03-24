"""
S106: Fix 1,555+ broken Leave Allocations created via direct SQL INSERT.

Problem:
  - total_leaves_allocated = 0 (validate() was never called)
  - No Leave Ledger Entries exist (on_submit() was never called)
  - get_leave_balance_on() returns 0 for all employees

Fix:
  1. set_total_leaves_allocated() via ORM to compute total correctly
  2. create_leave_ledger_entry() to create ledger records for balance calculation
  3. db_update() instead of save() to avoid naming_series MandatoryError

Run via: bench --site hq.bebang.ph execute hrms.patches.v16_0.s106_fix_leave_allocations.execute
"""

import frappe
from frappe.utils import flt


BATCH_SIZE = 50


def execute():
    """Main entry point for bench execute."""

    # ── Before snapshot ──────────────────────────────────────────────
    # B-1 AUDIT FIX: query by MISSING ledger entries, not just total=0
    # This catches records we already patched (total=15) but still have no ledger.
    broken = frappe.db.sql("""
        SELECT la.name, la.employee, la.employee_name, la.leave_type,
               la.new_leaves_allocated, la.total_leaves_allocated
        FROM `tabLeave Allocation` la
        WHERE la.docstatus = 1
          AND la.new_leaves_allocated > 0
          AND la.name NOT IN (
              SELECT DISTINCT transaction_name
              FROM `tabLeave Ledger Entry`
              WHERE transaction_type = 'Leave Allocation'
          )
    """, as_dict=True)

    total_before = len(broken)
    ledger_before = frappe.db.count("Leave Ledger Entry", {
        "transaction_type": "Leave Allocation",
    })

    print(f"Before: {total_before} allocations missing ledger entries, {ledger_before} existing ledger entries")

    if total_before == 0:
        print("Nothing to fix. All allocations have ledger entries.")
        return

    # Group by leave type for summary
    by_type = {}
    for row in broken:
        lt = row.get("leave_type", "Unknown")
        by_type.setdefault(lt, 0)
        by_type[lt] += 1
    for lt, count in sorted(by_type.items()):
        print(f"  {lt}: {count}")

    # ── Fix loop ─────────────────────────────────────────────────────
    fixed = 0
    skipped = 0
    errors = []

    for i, row in enumerate(broken):
        try:
            doc = frappe.get_doc("Leave Allocation", row.name)

            # Step 1: Recompute total_leaves_allocated via ORM
            doc.set_total_leaves_allocated()

            # Step 2: Save field update (NOT doc.save() — naming_series is NULL)
            doc.db_update()

            # Step 3: B-2 AUDIT FIX — idempotency guard before creating ledger
            existing_ledger = frappe.get_all("Leave Ledger Entry", filters={
                "transaction_type": "Leave Allocation",
                "transaction_name": doc.name,
            }, limit=1)

            if not existing_ledger:
                doc.create_leave_ledger_entry()
                fixed += 1
            else:
                skipped += 1
                print(f"  SKIP {doc.name}: ledger already exists (race condition guard)")

        except Exception as e:
            errors.append({"name": row.name, "employee": row.employee, "error": str(e)})
            print(f"  ERROR {row.name} ({row.employee}): {e}")

        # Batch commit
        if (i + 1) % BATCH_SIZE == 0:
            frappe.db.commit()
            print(f"  Committed batch {(i + 1) // BATCH_SIZE} ({i + 1}/{total_before})")

    # Final commit
    frappe.db.commit()

    # ── After snapshot ───────────────────────────────────────────────
    remaining = frappe.db.sql("""
        SELECT COUNT(*) as cnt
        FROM `tabLeave Allocation` la
        WHERE la.docstatus = 1
          AND la.new_leaves_allocated > 0
          AND la.name NOT IN (
              SELECT DISTINCT transaction_name
              FROM `tabLeave Ledger Entry`
              WHERE transaction_type = 'Leave Allocation'
          )
    """)[0][0]

    ledger_after = frappe.db.count("Leave Ledger Entry", {
        "transaction_type": "Leave Allocation",
    })

    zero_total_remaining = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabLeave Allocation`
        WHERE docstatus = 1 AND new_leaves_allocated > 0 AND total_leaves_allocated = 0
    """)[0][0]

    print(f"\n{'='*60}")
    print(f"RESULTS:")
    print(f"  Fixed: {fixed}")
    print(f"  Skipped (already had ledger): {skipped}")
    print(f"  Errors: {len(errors)}")
    print(f"  Remaining without ledger: {remaining}")
    print(f"  Remaining with total=0: {zero_total_remaining}")
    print(f"  Ledger entries: {ledger_before} -> {ledger_after}")
    print(f"{'='*60}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors[:20]:
            print(f"  {e['name']} ({e['employee']}): {e['error']}")

    # Spot-check balances
    print("\nSpot-check balances:")
    from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on
    for emp, lt in [("9000924", "Vacation Leave"), ("9000358", "Sick Leave"), ("9000003", "Emergency Leave")]:
        try:
            bal = get_leave_balance_on(emp, "2026-03-27", lt)
            print(f"  {emp} {lt}: {bal}")
        except Exception as e:
            print(f"  {emp} {lt}: ERROR - {e}")
