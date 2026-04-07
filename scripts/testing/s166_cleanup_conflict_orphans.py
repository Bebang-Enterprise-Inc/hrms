#!/usr/bin/env python3
"""
S166 CONFLICT-001 orphan cleanup.

Soft-deletes HR-EMP-00044 and HR-EMP-00045 (scratch test employees created
by the CONFLICT-001 fix-iter1 runner that failed to self-cleanup).

Runs inside the Frappe backend container via SSM.
"""
import os, sys

# Step 0: Create log directories before importing frappe
for d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(d, exist_ok=True)

import frappe

frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

TARGETS = ["HR-EMP-00044", "HR-EMP-00045"]

print("=== S166 CONFLICT-001 orphan cleanup ===")

for name in TARGETS:
    # Verify exists
    exists = frappe.db.sql(
        "SELECT name, status, relieving_date, attendance_device_id, employee_name "
        "FROM `tabEmployee` WHERE name = %s",
        name, as_dict=True
    )
    if not exists:
        print(f"  {name}: NOT FOUND, skipping")
        continue

    cur = exists[0]
    print(f"  {name}: before status={cur['status']} relieving={cur['relieving_date']} bio={cur['attendance_device_id']} emp_name={cur['employee_name'][:60]}")

    # Direct SQL update bypassing ORM validations
    frappe.db.sql(
        """
        UPDATE `tabEmployee`
        SET status = 'Left',
            relieving_date = '2026-04-07',
            attendance_device_id = NULL
        WHERE name = %s
        """,
        name,
    )
    frappe.db.commit()

    # Verify
    after = frappe.db.sql(
        "SELECT status, relieving_date, attendance_device_id FROM `tabEmployee` WHERE name = %s",
        name, as_dict=True
    )[0]
    print(f"  {name}: after  status={after['status']} relieving={after['relieving_date']} bio={after['attendance_device_id']}")

# Final orphan sweep
remaining = frappe.db.sql(
    """
    SELECT name, status, attendance_device_id, employee_name
    FROM `tabEmployee`
    WHERE employee_name LIKE '%%(L3 2026-04-07%%CONFLICT-001%%'
      AND status = 'Active'
    """,
    as_dict=True,
)
print(f"\nRemaining Active CONFLICT-001 orphans: {len(remaining)}")
for r in remaining:
    print(f"  POLLUTION: {r['name']} | {r['status']} | bio={r['attendance_device_id']} | {r['employee_name'][:60]}")

# Broader L3 sweep (best-effort)
broad = frappe.db.sql(
    """
    SELECT name, status, attendance_device_id, employee_name
    FROM `tabEmployee`
    WHERE employee_name LIKE '%%(L3 2026-04-07%%'
      AND status = 'Active'
    """,
    as_dict=True,
)
print(f"\nAll Active L3 2026-04-07 employees: {len(broad)}")
for r in broad:
    print(f"  {r['name']} | bio={r['attendance_device_id']} | {r['employee_name'][:60]}")

frappe.destroy()
print("\nCLEANUP-DONE")
