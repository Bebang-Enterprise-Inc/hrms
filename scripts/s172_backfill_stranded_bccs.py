"""
S172 Phase 2 Task 2.3 — Backfill SSAs for BCCs that reached Approved without
creating an SSA (caused by Defect #16 silent activation failure).

Context:
  Prior to S172, `process_compensation_approval` had a bare `except Exception:`
  that swallowed activation failures, and `_activate_compensation_change` had
  an `if latest_ssa:` guard that silently skipped SSA creation for employees
  with no prior SSA. Net effect: BCCs for new hires reached status=Approved
  but no Salary Structure Assignment was ever created.

How to find stranded rows:
  SELECT bcc.name, bcc.employee, bcc.new_value, bcc.effective_date
  FROM `tabBEI Compensation Change` bcc
  LEFT JOIN `tabSalary Structure Assignment` ssa
    ON ssa.employee = bcc.employee
    AND ssa.docstatus = 1
    AND ssa.from_date = bcc.effective_date
  WHERE bcc.status = 'Approved'
    AND bcc.change_type = 'Salary'
    AND ssa.name IS NULL;

Run via SSM following the /frappe-bulk-edits pattern:
  1. Encode this file to base64
  2. docker exec into the frappe-prod-1 container
  3. Decode + run via `bench --site hq.bebang.ph execute /tmp/s172_backfill.py`

Or via bench directly in a dev environment:
  bench --site <site> execute scripts.s172_backfill_stranded_bccs.main
"""

import csv
import sys

import frappe

from hrms.api.payroll_compensation import _activate_compensation_change


OUTPUT_CSV = "/tmp/s172_backfill_results.csv"


def find_stranded_bccs():
	"""Return BCCs where status=Approved but no matching SSA exists."""
	return frappe.db.sql(
		"""
		SELECT bcc.name, bcc.employee, bcc.change_type, bcc.employee_field_name,
		       bcc.new_value, bcc.effective_date
		FROM `tabBEI Compensation Change` bcc
		LEFT JOIN `tabSalary Structure Assignment` ssa
		  ON ssa.employee = bcc.employee
		 AND ssa.docstatus = 1
		 AND ssa.from_date = bcc.effective_date
		WHERE bcc.status = 'Approved'
		  AND bcc.change_type = 'Salary'
		  AND ssa.name IS NULL
		ORDER BY bcc.approval_date ASC
		""",
		as_dict=True,
	)


def main():
	stranded = find_stranded_bccs()
	print(f"[S172] Found {len(stranded)} stranded BCC rows")

	results = []
	fixed = 0
	failed = 0

	for row in stranded:
		bcc_name = row["name"]
		employee = row["employee"]
		try:
			doc = frappe.get_doc("BEI Compensation Change", bcc_name)
			frappe.db.savepoint(f"s172_backfill_{bcc_name}")
			_activate_compensation_change(doc)
			frappe.db.release_savepoint(f"s172_backfill_{bcc_name}")
			frappe.db.commit()
			results.append({
				"bcc": bcc_name,
				"employee": employee,
				"new_value": row["new_value"],
				"status": "FIXED",
				"error": "",
			})
			fixed += 1
			print(f"  [OK]  {bcc_name} / {employee} / base={row['new_value']}")
		except Exception as e:  # noqa: BLE001 - backfill tool needs the context
			frappe.db.rollback_to_savepoint(f"s172_backfill_{bcc_name}")
			results.append({
				"bcc": bcc_name,
				"employee": employee,
				"new_value": row["new_value"],
				"status": "FAILED",
				"error": str(e)[:300],
			})
			failed += 1
			print(f"  [ERR] {bcc_name} / {employee}: {e}")

	# Write audit trail
	with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
		writer = csv.DictWriter(f, fieldnames=["bcc", "employee", "new_value", "status", "error"])
		writer.writeheader()
		writer.writerows(results)

	print(f"\n[S172] Backfill complete: fixed={fixed} failed={failed} total={len(stranded)}")
	print(f"[S172] Audit CSV: {OUTPUT_CSV}")
	return {"fixed": fixed, "failed": failed, "total": len(stranded), "csv": OUTPUT_CSV}


if __name__ == "__main__":
	sys.exit(0 if main()["failed"] == 0 else 1)
