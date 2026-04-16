"""S201 Phase 7: backfill Employee.company based on branch + non-store rules.

For every Active Employee, computes the target Company (same logic as the
Employee.validate hook) and UPDATEs tabEmployee.company via direct SQL
(bypasses validate to avoid hook re-firing and to keep the patch fast).

Safety:
  - DRY-RUN by default. Writes a line-by-line change list to
    output/s201/diagnostics/backfill_report_<timestamp>.json and exits.
  - To apply: S201_APPLY=1 env var.
  - Idempotent: rerunning after apply is a no-op (everyone already at target).
  - Emits per-Company before/after counts for audit.

Run directly:
    bench --site hq.bebang.ph execute \\
      hrms.patches.v16_0.s201_backfill_employee_company.execute
"""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime

import frappe

from hrms.utils.company_lookup import (
	UnknownBranch,
	get_non_store_parent,
	resolve_branch_to_company,
)
from hrms.utils.non_store_billing import is_non_store_billing


REPORT_DIR_REL = os.path.join("output", "s201", "diagnostics")


def _apply_mode() -> bool:
	return os.environ.get("S201_APPLY", "").strip() == "1"


def _compute_target_company(emp: dict) -> tuple[str | None, str]:
	"""Return (target_company, reason). None target means 'no change'."""
	branch = emp.get("branch") or ""
	dept = emp.get("department") or ""
	desig = emp.get("designation") or ""
	bio_id = emp.get("new_attendance_device_id") or emp.get("attendance_device_id") or ""

	if is_non_store_billing(
		bio_id=bio_id, department=dept, designation=desig, branch=branch
	):
		return get_non_store_parent(), "non_store_rule"

	if not branch:
		return None, "no_branch"

	try:
		target = resolve_branch_to_company(branch, department=dept)
		return target, "branch_resolved"
	except UnknownBranch:
		return None, "unresolvable_branch"


def _write_report(payload: dict) -> str:
	site_path = frappe.get_site_path()
	stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
	filename = f"backfill_report_{stamp}.json"
	out_path = os.path.join(site_path, "private", "files", filename)
	try:
		os.makedirs(os.path.dirname(out_path), exist_ok=True)
		with open(out_path, "w", encoding="utf-8") as f:
			json.dump(payload, f, indent=2, default=str)
	except Exception as exc:
		frappe.logger().warning(f"[S201] report write failed: {exc}")
	return out_path


def execute() -> None:
	apply_mode = _apply_mode()

	employees = frappe.get_all(
		"Employee",
		filters={"status": "Active"},
		fields=[
			"name",
			"employee_name",
			"company",
			"branch",
			"department",
			"designation",
			"attendance_device_id",
			"new_attendance_device_id",
		],
	)

	pre_counts = Counter(e.get("company") or "<blank>" for e in employees)
	changes: list[dict] = []
	no_change: list[dict] = []
	unresolvable: list[dict] = []

	for emp in employees:
		current = emp.get("company") or ""
		target, reason = _compute_target_company(emp)

		if target is None:
			# Can't decide — leave alone, log.
			unresolvable.append({
				"employee": emp["name"],
				"employee_name": emp["employee_name"],
				"branch": emp.get("branch"),
				"department": emp.get("department"),
				"designation": emp.get("designation"),
				"current_company": current,
				"reason": reason,
			})
			continue

		if target == current:
			no_change.append({
				"employee": emp["name"],
				"current_company": current,
				"reason": reason,
			})
			continue

		changes.append({
			"employee": emp["name"],
			"employee_name": emp["employee_name"],
			"branch": emp.get("branch"),
			"department": emp.get("department"),
			"designation": emp.get("designation"),
			"old_company": current,
			"new_company": target,
			"reason": reason,
		})

	post_counts = Counter(
		pre_counts.get(c, 0) for c in pre_counts  # placeholder; replaced below
	)
	# Recompute post-counts by walking the change list
	post = dict(pre_counts)
	for ch in changes:
		post[ch["old_company"] or "<blank>"] = max(0, post.get(ch["old_company"] or "<blank>", 0) - 1)
		post[ch["new_company"]] = post.get(ch["new_company"], 0) + 1
	post_counts = Counter(post)

	summary = {
		"dry_run": not apply_mode,
		"totals": {
			"active_employees": len(employees),
			"changes": len(changes),
			"no_change": len(no_change),
			"unresolvable": len(unresolvable),
		},
		"pre_counts": dict(pre_counts),
		"post_counts": dict(post_counts),
		"changes": changes,
		"unresolvable": unresolvable,
	}

	if not apply_mode:
		report_path = _write_report(summary)
		frappe.logger().info(
			f"[S201] DRY-RUN. {len(changes)} changes planned; "
			f"{len(unresolvable)} unresolvable. Report: {report_path}"
		)
		return

	# Apply changes via direct SQL to avoid re-firing the Employee.validate
	# hook we just shipped (it would compute the same target anyway, but
	# direct SQL is faster and keeps the patch deterministic).
	applied = 0
	errors = []
	for ch in changes:
		try:
			frappe.db.sql(
				"UPDATE `tabEmployee` SET company=%s WHERE name=%s",
				(ch["new_company"], ch["employee"]),
			)
			applied += 1
		except Exception as exc:
			errors.append({"employee": ch["employee"], "error": str(exc)})

	frappe.db.commit()

	summary["totals"]["applied"] = applied
	summary["totals"]["errors"] = len(errors)
	summary["errors"] = errors
	report_path = _write_report(summary)
	frappe.logger().info(
		f"[S201] APPLIED. {applied} company reassignments. "
		f"{len(errors)} errors. Report: {report_path}"
	)
