#!/usr/bin/env python3
"""S231 Phase A-1: read-only probe of the Ayala Fairview Terraces Company
+ any other Companies whose name or abbr matches BFI2 / FT INC.

Captures every default_* / round_off_* / asset_* / stock_* / depreciation_*
field plus a `missing_refs` map per row. Writes
`output/s231/verification/ayala_fairview_probe.json`.

Run:
    python scripts/s231_probe_ayala_fairview.py
"""

from __future__ import annotations

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

OUT = REPO_ROOT / "output" / "s231" / "verification" / "ayala_fairview_probe.json"

PROBE_SCRIPT = (
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

field_list = ", ".join(f"`{f}`" for f in [
    "name", "abbr", "store_ownership_type", "parent_company",
    "first_provision_done", "entity_category",
] + DEFAULT_FIELDS)

candidates = frappe.db.sql(
    f'''
    SELECT {field_list}
    FROM `tabCompany`
    WHERE name LIKE '%Ayala Fairview%'
       OR name LIKE '%FT INC%'
       OR name LIKE '%FAIRVIEW TERRACES%'
       OR abbr = 'BFI2'
       OR name = 'BEBANG FT INC.'
    ''',
    as_dict=True,
)

# For each candidate, classify which referenced Accounts/CostCenters exist.
results = []
for c in candidates:
    missing = {}
    for f in DEFAULT_FIELDS:
        v = c.get(f)
        if v:
            target_dt = "Cost Center" if "cost_center" in f else "Account"
            if not frappe.db.exists(target_dt, v):
                missing[f] = v
    c["missing_refs"] = missing
    c["missing_count"] = len(missing)
    results.append(c)

# Also report whether parent_company `BEBANG FT INC.` exists
fti_check = {
    "BEBANG FT INC._exists": bool(frappe.db.exists("Company", "BEBANG FT INC.")),
    "Bebang FT Inc._exists": bool(frappe.db.exists("Company", "Bebang FT Inc.")),
    "Bebang FTE Inc._exists": bool(frappe.db.exists("Company", "Bebang FTE Inc.")),
}

_s231_emit({"candidates": results, "candidate_count": len(results), "fti_check": fti_check})

frappe.destroy()
"""
)


def main() -> int:
	OUT.parent.mkdir(parents=True, exist_ok=True)
	stdout = run_in_container(PROBE_SCRIPT, timeout=120)
	data = decode_output(stdout)
	OUT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
	print(f"Wrote {OUT}")
	print(f"Candidates: {data['candidate_count']}")
	for c in data["candidates"]:
		print(f"  {c['name']} (abbr={c['abbr']}) — missing_count={c['missing_count']}")
	print(f"BEBANG FT INC. exists: {data['fti_check']['BEBANG FT INC._exists']}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
