#!/usr/bin/env python3
# Copyright (c) 2026, Bebang Enterprise Inc.
# License: MIT
"""S233 v3 A15: repair the S037 register CSV after a post-savepoint append failed.

Called manually after Sentry alert raised by hrms/api/create_new_store.py
when DB-side 4-record creation succeeded but the subsequent CSV append
raised. Idempotent — checks for existing row before appending.

Usage (inside Frappe container):
    bench --site hq.bebang.ph execute scripts.canonical.repair_s037_for_company.repair \\
        --kwargs '{"company_name": "SM Tanza - BEBANG MEGA INC."}'

Or as standalone CLI:
    python scripts/canonical/repair_s037_for_company.py \\
        --company-name "SM Tanza - BEBANG MEGA INC."
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import sys
import tempfile
from typing import Optional


def repair(company_name: str) -> dict:
	"""Append the missing S037 row for an already-created Company. Idempotent.

	Reads Company doc, derives store_label/parent/ownership from the canonical
	docname pattern + DB row, checks if S037 already has the row, appends if not.

	Returns:
		{"status": "OK", "action": "appended" | "noop", "company_name": ..., ...}
		{"status": "ERROR", "reason": ...}
	"""
	import frappe  # late import (so CLI mode without frappe.init still parses args)

	# Load Company DB row
	co = frappe.db.get_value(
		"Company", company_name,
		["abbr", "parent_company", "store_ownership_type", "country"],
		as_dict=True,
	)
	if not co:
		return {"status": "ERROR", "reason": f"Company {company_name!r} not found"}

	parent = co["parent_company"]
	if not parent:
		return {"status": "ERROR", "reason": f"Company {company_name!r} has no parent_company set"}

	# Resolve store_label (everything before " - <parent>")
	suffix = f" - {parent}"
	if not company_name.endswith(suffix):
		return {
			"status": "ERROR",
			"reason": f"Company name {company_name!r} doesn't end with parent suffix {suffix!r}",
		}
	store_label = company_name[: -len(suffix)]

	# Resolve canonical CSV path via the v3-renamed constant
	from hrms.utils.bei_config import STORE_ENTITY_MAPPING_RELPATH
	s037_path = os.path.normpath(os.path.join(frappe.get_app_path("hrms"), *STORE_ENTITY_MAPPING_RELPATH))

	if not os.path.exists(s037_path):
		return {"status": "ERROR", "reason": f"S037 CSV not found at {s037_path}"}

	# Read existing rows + check if this store already there (idempotent)
	with open(s037_path, encoding="utf-8-sig", newline="") as f:
		rows = list(csv.reader(f))
	for r in rows[1:]:  # skip header
		if r and r[0].strip() == store_label:
			return {
				"status": "OK",
				"action": "noop",
				"reason": "row already present",
				"company_name": company_name,
				"store_label": store_label,
			}

	# Append the missing row using the canonical 6-column layout
	rows.append([
		store_label,
		parent,
		co["store_ownership_type"] or "",
		company_name,
		"BKI_TO_STORE_INTERCOMPANY",
		"active",
	])
	fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(s037_path), text=True)
	os.close(fd)
	with open(tmp_path, "w", encoding="utf-8", newline="") as f:
		csv.writer(f).writerows(rows)
	os.replace(tmp_path, s037_path)
	return {
		"status": "OK",
		"action": "appended",
		"company_name": company_name,
		"store_label": store_label,
		"csv_path": s037_path,
	}


if __name__ == "__main__":  # pragma: no cover — CLI only
	p = argparse.ArgumentParser(description="S233 v3 A15: repair S037 register CSV after a failed post-savepoint append")
	p.add_argument(
		"--company-name", required=True,
		help="Canonical company docname (e.g. 'SM Tanza - BEBANG MEGA INC.')",
	)
	args = p.parse_args()
	# Caller initializes Frappe (via bench execute or direct frappe.init+connect)
	out = repair(args.company_name)
	print(json.dumps(out, indent=2))
	sys.exit(0 if out["status"] == "OK" else 1)
