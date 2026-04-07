"""S170 — Backfill Leave Ledger Entries for already-approved leaves missing them.

Background: prior to the S170 fix in `hrms/api/leave_dashboard.py:bulk_action`,
leaves submitted via the leave-command-center API were silently failing the
ledger entry creation step. Several leaves are now at docstatus=1, status=Approved
with no corresponding `Leave Ledger Entry` row. This script finds them and
runs `create_leave_ledger_entry` for each.

Run via: bench --site hq.bebang.ph execute scripts.s170_backfill_leave_ledger.run

Output: output/s170/backfilled_leaves.csv with one row per leave.
"""
from __future__ import annotations

import csv
import os
import frappe


def run() -> None:
    out_dir = os.path.join("output", "s170")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "backfilled_leaves.csv")

    # Filter: status='Approved' for backfill (Rejected leaves don't need ledger entries)
    broken = frappe.db.sql(
        """
        SELECT la.name, la.employee, la.leave_type, la.from_date, la.to_date,
               la.total_leave_days, la.modified_by
        FROM `tabLeave Application` la
        WHERE la.docstatus = 1
          AND la.status = 'Approved'
          AND la.name NOT IN (
              SELECT DISTINCT transaction_name
              FROM `tabLeave Ledger Entry`
              WHERE transaction_type = 'Leave Application'
          )
        ORDER BY la.from_date DESC
        """,
        as_dict=True,
    )

    print(f"S170 backfill: found {len(broken)} approved leaves missing ledger entries")

    rows = []
    for row in broken:
        try:
            doc = frappe.get_doc("Leave Application", row["name"])
            doc.create_leave_ledger_entry()
            frappe.db.commit()
            rows.append({**row, "result": "OK"})
            print(f"  [OK] {row['name']} ({row['employee']}, {row['leave_type']}, {row['from_date']})")
        except Exception as exc:
            frappe.db.rollback()
            rows.append({**row, "result": f"FAIL: {exc}"})
            print(f"  [FAIL] {row['name']}: {exc}")

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    ok_count = sum(1 for r in rows if r["result"] == "OK")
    print(f"\nS170 backfill complete: {ok_count}/{len(rows)} succeeded")
    print(f"Report: {out_path}")
