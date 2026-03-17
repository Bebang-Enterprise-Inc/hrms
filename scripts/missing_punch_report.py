#!/usr/bin/env python3
"""Generate an auditable missing-punch report for a date range."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

try:
	import frappe
	from frappe.utils import add_days, get_datetime, getdate
except ModuleNotFoundError:  # pragma: no cover - CLI help still works without bench-loaded frappe
	frappe = None

	def _missing_frappe(*_args, **_kwargs):
		raise ModuleNotFoundError("frappe is required to run this script. Activate the site environment first.")

	add_days = _missing_frappe
	get_datetime = _missing_frappe
	getdate = _missing_frappe

REPO_ROOT = Path(__file__).resolve().parents[1]
BENCH_ROOT = REPO_ROOT.parent.parent
DEFAULT_SITES_PATH = BENCH_ROOT / "sites"


def iter_dates(start_date: str, end_date: str):
	current = str(getdate(start_date))
	finish = str(getdate(end_date))
	while current <= finish:
		yield current
		current = str(add_days(current, 1))


def connect(site: str, sites_path: str | None = None):
	resolved_sites_path = sites_path or str(DEFAULT_SITES_PATH)
	frappe.init(site=site, sites_path=resolved_sites_path)
	frappe.connect()


def fetch_shift_assignments(start_date: str, end_date: str, store: str | None = None):
	params = {"start_date": start_date, "end_date": end_date}
	store_clause = ""
	if store:
		store_clause = "AND e.branch = %(store)s"
		params["store"] = store

	return frappe.db.sql(
		f"""
		SELECT
			sa.name,
			sa.employee,
			e.employee_name,
			e.branch AS store,
			sa.shift_type,
			sa.start_date,
			sa.end_date
		FROM `tabShift Assignment` sa
		JOIN `tabEmployee` e ON e.name = sa.employee
		WHERE sa.docstatus = 1
			AND sa.status = 'Active'
			AND sa.start_date <= %(end_date)s
			AND (sa.end_date IS NULL OR sa.end_date = '' OR sa.end_date >= %(start_date)s)
			{store_clause}
		ORDER BY e.branch ASC, e.employee_name ASC, sa.start_date ASC
		""",
		params,
		as_dict=True,
	)


def expand_scheduled_days(assignments: list[dict], start_date: str, end_date: str):
	rows = []
	for assignment in assignments:
		row_start = str(max(getdate(assignment["start_date"]), getdate(start_date)))
		row_end = str(min(getdate(assignment.get("end_date") or assignment["start_date"]), getdate(end_date)))
		for work_date in iter_dates(row_start, row_end):
			rows.append(
				{
					"assignment_name": assignment["name"],
					"employee": assignment["employee"],
					"employee_name": assignment["employee_name"],
					"store": assignment.get("store") or "",
					"shift_type": assignment.get("shift_type") or "",
					"work_date": work_date,
				}
			)
	return rows


def fetch_checkins(employee_names: list[str], start_date: str, end_date: str):
	if not employee_names:
		return []
	placeholders = ", ".join(["%s"] * len(employee_names))
	params = [*employee_names, start_date, end_date]
	return frappe.db.sql(
		f"""
		SELECT employee, time, log_type, device_id
		FROM `tabEmployee Checkin`
		WHERE employee IN ({placeholders})
			AND DATE(time) BETWEEN %s AND %s
		ORDER BY employee ASC, time ASC
		""",
		params,
		as_dict=True,
	)


def fetch_attendance(employee_names: list[str], start_date: str, end_date: str):
	if not employee_names:
		return {}
	placeholders = ", ".join(["%s"] * len(employee_names))
	params = [*employee_names, start_date, end_date]
	rows = frappe.db.sql(
		f"""
		SELECT employee, attendance_date, status
		FROM `tabAttendance`
		WHERE employee IN ({placeholders})
			AND docstatus = 1
			AND attendance_date BETWEEN %s AND %s
		""",
		params,
		as_dict=True,
	)
	return {(row["employee"], str(row["attendance_date"])): row["status"] for row in rows}


def group_checkins(checkins: list[dict]):
	grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
	for checkin in checkins:
		grouped[(checkin["employee"], str(get_datetime(checkin["time"]).date()))].append(checkin)
	return grouped


def classify_issue(record: dict, day_checkins: list[dict], attendance_status: str | None):
	if not day_checkins:
		return {
			"issue_codes": ["NO_PUNCHES"],
			"first_in": None,
			"last_out": None,
			"punch_count": 0,
			"log_types": "",
			"gap_hours": None,
			"attendance_status": attendance_status or "",
			"device_ids": "",
		}

	issue_codes: list[str] = []
	log_types = {str(row.get("log_type") or "").upper() for row in day_checkins}
	if len(day_checkins) == 1:
		issue_codes.append("SINGLE_PUNCH")
	if "IN" in log_types and "OUT" not in log_types:
		issue_codes.append("MISSING_OUT")
	if "OUT" in log_types and "IN" not in log_types:
		issue_codes.append("MISSING_IN")
	if len(day_checkins) >= 2:
		first_time = get_datetime(day_checkins[0]["time"])
		last_time = get_datetime(day_checkins[-1]["time"])
		gap_hours = round((last_time - first_time).total_seconds() / 3600, 2)
		if gap_hours > 14:
			issue_codes.append("LONG_GAP")
	else:
		gap_hours = None

	first_in = next((row for row in day_checkins if str(row.get("log_type") or "").upper() == "IN"), None)
	last_out = next((row for row in reversed(day_checkins) if str(row.get("log_type") or "").upper() == "OUT"), None)

	return {
		"issue_codes": issue_codes or ["REVIEW"],
		"first_in": first_in["time"] if first_in else None,
		"last_out": last_out["time"] if last_out else None,
		"punch_count": len(day_checkins),
		"log_types": "|".join(sorted(code for code in log_types if code)),
		"gap_hours": gap_hours,
		"attendance_status": attendance_status or "",
		"device_ids": "|".join(
			sorted({str(row.get("device_id") or "").strip() for row in day_checkins if str(row.get("device_id") or "").strip()})
		),
	}


def build_missing_punch_rows(start_date: str, end_date: str, store: str | None = None):
	assignments = fetch_shift_assignments(start_date, end_date, store)
	scheduled_days = expand_scheduled_days(assignments, start_date, end_date)
	employee_names = sorted({row["employee"] for row in scheduled_days})
	checkins = fetch_checkins(employee_names, start_date, end_date)
	attendance = fetch_attendance(employee_names, start_date, end_date)
	grouped_checkins = group_checkins(checkins)

	rows = []
	for row in scheduled_days:
		day_checkins = grouped_checkins.get((row["employee"], row["work_date"]), [])
		attendance_status = attendance.get((row["employee"], row["work_date"]))
		issue = classify_issue(row, day_checkins, attendance_status)
		if not issue["issue_codes"]:
			continue
		rows.append({**row, **issue, "issue_codes": "|".join(issue["issue_codes"])})
	return rows


def write_report(rows: list[dict], output_dir: Path):
	output_dir.mkdir(parents=True, exist_ok=True)
	csv_path = output_dir / "missing_punch_report.csv"
	json_path = output_dir / "missing_punch_summary.json"

	fieldnames = [
		"store",
		"work_date",
		"employee",
		"employee_name",
		"shift_type",
		"attendance_status",
		"issue_codes",
		"punch_count",
		"log_types",
		"first_in",
		"last_out",
		"gap_hours",
		"device_ids",
		"assignment_name",
	]
	with csv_path.open("w", newline="", encoding="utf-8") as handle:
		writer = csv.DictWriter(handle, fieldnames=fieldnames)
		writer.writeheader()
		for row in rows:
			writer.writerow({key: row.get(key) for key in fieldnames})

	issue_counter = Counter()
	store_counter = Counter()
	for row in rows:
		store_counter[row.get("store") or "UNKNOWN"] += 1
		for issue_code in str(row.get("issue_codes") or "").split("|"):
			if issue_code:
				issue_counter[issue_code] += 1

	summary = {
		"generated_at": datetime.now().isoformat(timespec="seconds"),
		"row_count": len(rows),
		"issues_by_code": dict(issue_counter),
		"issues_by_store": dict(store_counter),
		"csv_path": str(csv_path),
	}
	json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
	return csv_path, json_path, summary


def build_output_dir(base_dir: str | None):
	root = Path(base_dir) if base_dir else REPO_ROOT / "output" / "support" / "missing-punch"
	return root / datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def main():
	parser = argparse.ArgumentParser(description="Generate a missing-punch report.")
	parser.add_argument("--site", default="hq.bebang.ph")
	parser.add_argument("--sites-path", default=str(DEFAULT_SITES_PATH))
	parser.add_argument("--start-date", required=True)
	parser.add_argument("--end-date", required=True)
	parser.add_argument("--store")
	parser.add_argument("--output-dir")
	args = parser.parse_args()

	connect(args.site, args.sites_path)
	try:
		rows = build_missing_punch_rows(args.start_date, args.end_date, args.store)
		output_dir = build_output_dir(args.output_dir)
		csv_path, json_path, summary = write_report(rows, output_dir)
		print(json.dumps({"csv_path": str(csv_path), "summary_path": str(json_path), **summary}, indent=2))
	finally:
		frappe.destroy()


if __name__ == "__main__":
	main()
