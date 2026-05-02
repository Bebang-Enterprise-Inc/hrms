#!/usr/bin/env python3
"""S231 Phase B-1 / B-4: read-only audit of broken default_* refs across
ALL store-category Companies in production.

For every Company with `entity_category='Store'`, scans the 21 default_* /
round_off_* / depreciation_* / capital_* / asset_* / stock_* / expenses_*
fields. For each field with a value, checks if the target Account / Cost
Center actually exists.

Modes:
    --dry-run        — write inventory CSV, no mutation (default)
    --verify-after   — write inventory_AFTER.csv (post-sweep verification)

Outputs:
    output/s231/verification/broken_defaults_inventory.csv         (default)
    output/s231/verification/broken_defaults_inventory_AFTER.csv   (--verify-after)
    output/s231/verification/sweep_report.json                     (always)
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from s231_ssm_helper import (  # noqa: E402
	PAYLOAD_PREAMBLE,
	decode_output,
	run_in_container,
)

AUDIT_SCRIPT = (
	PAYLOAD_PREAMBLE
	+ """
DEFAULT_FIELDS = [
    "default_inventory_account", "default_payable_account", "default_receivable_account",
    "default_payroll_payable_account", "default_employee_advance_account",
    "default_expense_account", "default_income_account",
    "round_off_account", "round_off_cost_center",
    "default_cash_account", "exchange_gain_loss_account",
    "accumulated_depreciation_account", "depreciation_expense_account",
    "expenses_included_in_asset_valuation", "disposal_account",
    "depreciation_cost_center", "capital_work_in_progress_account",
    "asset_received_but_not_billed", "stock_adjustment_account",
    "stock_received_but_not_billed", "expenses_included_in_valuation",
]

field_select = ", ".join([f"`{f}`" for f in DEFAULT_FIELDS])
companies = frappe.db.sql(
    f'''
    SELECT name, abbr, store_ownership_type, parent_company,
           first_provision_done, entity_category, {field_select}
    FROM `tabCompany`
    WHERE entity_category = 'Store' OR entity_category IS NULL OR entity_category = ''
    ORDER BY name
    ''',
    as_dict=True,
)

rows = []
broken_companies = set()
broken_with_payroll = []

for c in companies:
    abbr = c.get("abbr") or ""
    cname = c.get("name")
    has_active_salary_struct = bool(frappe.db.exists(
        "Salary Structure Assignment",
        {"company": cname, "docstatus": 1},
    ))
    for f in DEFAULT_FIELDS:
        v = c.get(f)
        if not v:
            rows.append({
                "company_name": cname, "abbr": abbr,
                "store_ownership_type": c.get("store_ownership_type") or "",
                "parent_company": c.get("parent_company") or "",
                "first_provision_done": c.get("first_provision_done") or 0,
                "field_name": f, "current_value": "",
                "target_doctype": "Cost Center" if "cost_center" in f else "Account",
                "ref_exists": "",
                "action_recommended": "no_action",
            })
            continue
        target_dt = "Cost Center" if "cost_center" in f else "Account"
        ref_exists = bool(frappe.db.exists(target_dt, v))
        if ref_exists:
            # Check if disabled
            try:
                disabled = bool(frappe.db.get_value(target_dt, v, "disabled"))
            except Exception:
                disabled = False
            action = "enable_account" if disabled else "no_action"
        else:
            broken_companies.add(cname)
            if has_active_salary_struct:
                broken_with_payroll.append(cname)
            # Cross-contamination: orphan abbr != company abbr
            orphan_abbr = v.rsplit(" - ", 1)[-1] if " - " in v else ""
            if orphan_abbr and orphan_abbr != abbr:
                action = "null_field_cross_company"
            else:
                action = "null_field_same_company"
        rows.append({
            "company_name": cname, "abbr": abbr,
            "store_ownership_type": c.get("store_ownership_type") or "",
            "parent_company": c.get("parent_company") or "",
            "first_provision_done": c.get("first_provision_done") or 0,
            "field_name": f, "current_value": v,
            "target_doctype": target_dt,
            "ref_exists": ref_exists,
            "action_recommended": action,
        })

actionable = [r for r in rows if r["action_recommended"] not in ("no_action",)]

summary = {
    "scanned_companies": len(companies),
    "broken_companies_count": len(broken_companies),
    "broken_companies_with_active_payroll": list(set(broken_with_payroll)),
    "broken_companies_with_active_payroll_count": len(set(broken_with_payroll)),
    "actionable_field_count": len(actionable),
    "broken_companies": sorted(broken_companies),
}

_s231_emit({"rows": rows, "summary": summary})

frappe.destroy()
"""
)


def main() -> int:
	parser = argparse.ArgumentParser()
	parser.add_argument("--verify-after", action="store_true",
	                    help="Write inventory_AFTER.csv instead of inventory.csv")
	args = parser.parse_args()

	out_dir = REPO_ROOT / "output" / "s231" / "verification"
	out_dir.mkdir(parents=True, exist_ok=True)
	csv_name = "broken_defaults_inventory_AFTER.csv" if args.verify_after else "broken_defaults_inventory.csv"
	out_csv = out_dir / csv_name
	report_json = out_dir / "sweep_report.json"

	stdout = run_in_container(AUDIT_SCRIPT, timeout=300)
	data = decode_output(stdout)
	rows = data["rows"]
	summary = data["summary"]

	# Write CSV — every field state, including no_action rows, for audit.
	with out_csv.open("w", newline="", encoding="utf-8") as f:
		w = csv.DictWriter(f, fieldnames=list(rows[0].keys())) if rows else None
		if w:
			w.writeheader()
			w.writerows(rows)
	print(f"Wrote {out_csv} ({len(rows)} rows, {summary['actionable_field_count']} actionable)")

	# Write / merge sweep_report.json
	if args.verify_after:
		# Read existing then update broken_companies_after
		try:
			report = json.loads(report_json.read_text())
		except FileNotFoundError:
			report = {}
		report["broken_companies_after"] = summary["broken_companies_count"]
		report["scanned_companies_after"] = summary["scanned_companies"]
		report["samples_after"] = summary["broken_companies"][:10]
	else:
		report = {
			"scanned_companies": summary["scanned_companies"],
			"broken_companies_before": summary["broken_companies_count"],
			"broken_companies_after": None,
			"broken_companies_with_active_payroll_count": summary["broken_companies_with_active_payroll_count"],
			"broken_companies_with_active_payroll": summary["broken_companies_with_active_payroll"],
			"fields_cleared": 0,
			"accounts_created": 0,
			"manual_review_required": 0,
			"samples_before": summary["broken_companies"][:10],
		}

	report_json.write_text(json.dumps(report, indent=2, default=str))
	print(f"Wrote {report_json}")
	print(f"Broken companies: {summary['broken_companies_count']}/{summary['scanned_companies']}")
	print(f"With active payroll: {summary['broken_companies_with_active_payroll_count']}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
