#!/usr/bin/env python3
"""Dry-run-first estimated OUT backfill for single-punch days."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, time, timedelta
from pathlib import Path
import sys

try:
  import frappe
  from frappe.utils import get_datetime, getdate
except ModuleNotFoundError:  # pragma: no cover - CLI help still works without bench-loaded frappe
  frappe = None

  def _missing_frappe(*_args, **_kwargs):
    raise ModuleNotFoundError("frappe is required to run this script. Activate the site environment first.")

  get_datetime = _missing_frappe
  getdate = _missing_frappe

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from scripts.missing_punch_report import (
  DEFAULT_SITES_PATH,
  REPO_ROOT,
  build_missing_punch_rows,
  connect,
)


def build_output_dir(base_dir: str | None):
  root = Path(base_dir) if base_dir else REPO_ROOT / "output" / "support" / "estimated-out"
  return root / datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def fetch_shift_type_windows(shift_names: list[str]):
  if not shift_names:
    return {}
  rows = frappe.get_all(
    "Shift Type",
    filters={"name": ["in", shift_names]},
    fields=["name", "start_time", "end_time"],
    limit=len(shift_names),
  )
  return {row["name"]: row for row in rows}


def estimate_out_timestamp(row: dict, shift_windows: dict[str, dict]):
  work_date = getdate(row["work_date"])
  shift_name = str(row.get("shift_type") or "")
  shift_meta = shift_windows.get(shift_name)

  if shift_meta and shift_meta.get("end_time"):
    start_value = str(shift_meta.get("start_time") or "")
    end_value = str(shift_meta.get("end_time") or "")
    estimate = datetime.combine(work_date, time.fromisoformat(end_value))
    if start_value and end_value and end_value <= start_value:
      estimate += timedelta(days=1)
    return estimate

  if "COMMISSARY" in shift_name.upper():
    if "NIGHT" in shift_name.upper():
      return datetime.combine(work_date + timedelta(days=1), time(hour=2, minute=0))
    return datetime.combine(work_date, time(hour=14, minute=0))
  return datetime.combine(work_date, time(hour=22, minute=0))


def insert_estimated_out(row: dict, estimated_out: datetime):
  doc = frappe.get_doc(
    {
      "doctype": "Employee Checkin",
      "employee": row["employee"],
      "time": estimated_out,
      "log_type": "OUT",
      "device_id": "ESTIMATED",
      "skip_auto_attendance": 0,
    }
  )
  doc.flags.ignore_permissions = True
  doc.insert(ignore_permissions=True)
  return doc.name


def write_artifacts(rows: list[dict], output_dir: Path):
  output_dir.mkdir(parents=True, exist_ok=True)
  csv_path = output_dir / "estimated_out_candidates.csv"
  summary_path = output_dir / "estimated_out_summary.json"
  fieldnames = [
    "store",
    "work_date",
    "employee",
    "employee_name",
    "shift_type",
    "estimated_out",
    "mode",
    "inserted_checkin",
    "issue_codes",
    "first_in",
  ]
  with csv_path.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
      writer.writerow({key: row.get(key) for key in fieldnames})

  summary = {
    "generated_at": datetime.now().isoformat(timespec="seconds"),
    "candidate_count": len(rows),
    "inserted_count": sum(1 for row in rows if row.get("inserted_checkin")),
    "csv_path": str(csv_path),
  }
  summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
  return csv_path, summary_path, summary


def main():
  parser = argparse.ArgumentParser(description="Backfill estimated OUT checkins for single-punch days.")
  parser.add_argument("--site", default="hq.bebang.ph")
  parser.add_argument("--sites-path", default=str(DEFAULT_SITES_PATH))
  parser.add_argument("--start-date", required=True)
  parser.add_argument("--end-date", required=True)
  parser.add_argument("--store")
  parser.add_argument("--output-dir")
  parser.add_argument("--apply", action="store_true", help="Insert the estimated OUT checkins.")
  args = parser.parse_args()

  connect(args.site, args.sites_path)
  try:
    missing_rows = build_missing_punch_rows(args.start_date, args.end_date, args.store)
    candidates = [
      row
      for row in missing_rows
      if "MISSING_OUT" in str(row.get("issue_codes") or "") or "SINGLE_PUNCH" in str(row.get("issue_codes") or "")
    ]
    shift_windows = fetch_shift_type_windows(sorted({str(row.get("shift_type") or "") for row in candidates if row.get("shift_type")}))

    report_rows = []
    for row in candidates:
      estimated_out = estimate_out_timestamp(row, shift_windows)
      report_row = {
        **row,
        "estimated_out": estimated_out.isoformat(sep=" ", timespec="seconds"),
        "mode": "apply" if args.apply else "dry_run",
        "inserted_checkin": None,
      }
      if args.apply:
        report_row["inserted_checkin"] = insert_estimated_out(row, estimated_out)
      report_rows.append(report_row)

    if args.apply:
      frappe.db.commit()

    output_dir = build_output_dir(args.output_dir)
    csv_path, summary_path, summary = write_artifacts(report_rows, output_dir)
    print(json.dumps({"csv_path": str(csv_path), "summary_path": str(summary_path), **summary}, indent=2))
  finally:
    frappe.destroy()


if __name__ == "__main__":
  main()
