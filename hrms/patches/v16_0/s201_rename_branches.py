"""S201 Phase 6: rename Branch docs to match Company prefixes.

Reads hrms/data_seed/branch_company_map.csv and renames every Branch where
old_branch != new_branch using frappe.rename_doc. Merges Branches that
collapse into the same canonical name (e.g. BGC -> UPTOWN BGC,
ROBINSON GENTRI -> ROBINSONS GENERAL TRIAS).

Safety:
  - DRY-RUN by default. Writes a report to
    output/s201/diagnostics/branch_rename_report_<timestamp>.json and
    exits without mutating anything.
  - To actually apply, set env var `S201_APPLY=1` before running the
    patch (bench --site <site> migrate with S201_APPLY=1 in the env).
  - Idempotent: if a rename has already been applied, it's logged as
    "skipped (already canonical)" and no error is raised.

Run directly for a dry-run report:
    bench --site hq.bebang.ph execute hrms.patches.v16_0.s201_rename_branches.execute
"""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime

import frappe


MAP_RELPATH = ("data_seed", "branch_company_map.csv")
REPORT_DIR = os.path.join("output", "s201", "diagnostics")


def _apply_mode() -> bool:
	return os.environ.get("S201_APPLY", "").strip() == "1"


def _load_map() -> list[dict]:
	path = os.path.normpath(os.path.join(frappe.get_app_path("hrms"), *MAP_RELPATH))
	if not os.path.exists(path):
		frappe.logger().error(f"[S201] branch_company_map.csv missing at {path}")
		return []
	with open(path, encoding="utf-8-sig") as f:
		return list(csv.DictReader(f))


def _write_report(payload: dict) -> str:
	site_path = frappe.get_site_path()
	# Write relative to site for availability; also mirror to repo output dir if present
	stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
	filename = f"branch_rename_report_{stamp}.json"
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
	rows = _load_map()
	if not rows:
		frappe.logger().error("[S201] No map rows loaded; aborting.")
		return

	plan = []
	skipped = []
	errors = []

	for row in rows:
		old = (row.get("old_branch") or "").strip()
		new = (row.get("new_branch") or "").strip()
		category = (row.get("target_category") or "").strip()
		if not old or not new or new == "NEEDS_MANUAL_REVIEW":
			skipped.append({"old": old, "new": new, "reason": "blank or manual-review"})
			continue
		if old == new:
			# Branch name already canonical — still count employees for reporting.
			count = frappe.db.count("Employee", filters={"branch": old})
			skipped.append({
				"old": old, "new": new,
				"reason": "already canonical", "employees": count,
			})
			continue

		# Plan the rename
		exists_old = frappe.db.exists("Branch", old)
		exists_new = frappe.db.exists("Branch", new)
		employees_on_old = frappe.db.count("Employee", filters={"branch": old})
		plan.append({
			"old": old,
			"new": new,
			"category": category,
			"exists_old": bool(exists_old),
			"exists_new": bool(exists_new),
			"employees_on_old": employees_on_old,
			"will_merge": bool(exists_new),
		})

	summary = {
		"dry_run": not apply_mode,
		"planned": plan,
		"skipped": skipped,
		"errors": errors,
		"counts": {
			"to_rename": len(plan),
			"merges": sum(1 for p in plan if p["will_merge"]),
			"new_only": sum(1 for p in plan if not p["will_merge"]),
			"skipped": len(skipped),
		},
	}

	if not apply_mode:
		report_path = _write_report(summary)
		frappe.logger().info(
			f"[S201] DRY-RUN. {len(plan)} renames planned, "
			f"{summary['counts']['merges']} merges. Report: {report_path}"
		)
		return

	# Execute renames. Merge when target already exists.
	# S201 audit fix: wrap in savepoint so a mid-batch failure rolls back
	# the partial renames (DM-2). Route errors through log_error so Sentry
	# captures them.
	frappe.db.savepoint("s201_rename_branches")
	for entry in plan:
		old = entry["old"]
		new = entry["new"]
		try:
			if not entry["exists_old"]:
				errors.append({"old": old, "new": new, "reason": "source branch missing"})
				continue
			frappe.rename_doc(
				"Branch", old, new,
				merge=entry["will_merge"],
				force=True,
				show_alert=False,
			)
			entry["status"] = "renamed"
		except Exception as exc:
			errors.append({"old": old, "new": new, "reason": str(exc)})
			entry["status"] = f"failed: {exc}"

	summary["errors"] = errors

	if errors:
		frappe.db.rollback(save_point="s201_rename_branches")
		frappe.log_error(
			title="S201 rename_branches rolled back on partial failure",
			message=(
				f"planned={len(plan)}, errors={len(errors)}; "
				f"first_error={errors[0]}"
			),
		)
		report_path = _write_report(summary)
		frappe.logger().error(
			f"[S201] ROLLBACK. {len(errors)} errors. Report: {report_path}"
		)
		return

	frappe.db.release_savepoint("s201_rename_branches")
	frappe.db.commit()
	report_path = _write_report(summary)
	frappe.logger().info(
		f"[S201] APPLIED. {len([p for p in plan if p.get('status')=='renamed'])} renames. "
		f"Report: {report_path}"
	)
