#!/usr/bin/env python3
"""S231 Phase A-3 / A-5: fix dead default_* refs on a single Company.

Implements the v1 Phase A-3 logic: for the named Company, null any
default_* / round_off_* / depreciation_* / capital_* / asset_* / stock_* /
expenses_* field whose target Account or Cost Center does not exist.
This is the SAME field-clearing the new S231-C2 validate hook does
proactively, but applied retroactively to companies that already
have rotted defaults BEFORE the hook deploys.

Each cleared field is captured to the closeout TOUCH_PRESERVATION_LEDGER.

Used by Phase A-5 to unblock Ayala Fairview Terraces immediately. Run
again post-Phase-B-sweep to confirm clean state.

Usage:
    python scripts/s231_fix_company_defaults.py "AYALA FAIRVIEW TERRACES - BEBANG FT INC."
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


def build_fix_payload(company_name: str) -> str:
	# `company_name` may include single-quotes etc.; embed as repr for safety.
	return PAYLOAD_PREAMBLE + f"""
company_name = {company_name!r}

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

if not frappe.db.exists("Company", company_name):
    _s231_emit({{"error": f"Company {{company_name!r}} does not exist"}})
    frappe.destroy()
    raise SystemExit(0)

cleared = []
for f in DEFAULT_FIELDS:
    v = frappe.db.get_value("Company", company_name, f)
    if v:
        target_dt = "Cost Center" if "cost_center" in f else "Account"
        if not frappe.db.exists(target_dt, v):
            frappe.db.set_value("Company", company_name, f, None, update_modified=False)
            cleared.append({{"field": f, "old_value": v}})

frappe.db.commit()

# Re-read every field for after-state evidence
after = {{f: frappe.db.get_value("Company", company_name, f) for f in DEFAULT_FIELDS}}

_s231_emit({{
    "company_name": company_name,
    "fields_cleared": len(cleared),
    "cleared": cleared,
    "after": after,
    "timestamp": frappe.utils.now(),
}})

frappe.destroy()
"""


def main() -> int:
	if len(sys.argv) != 2:
		print(f"Usage: {sys.argv[0]} <Company Docname>", file=sys.stderr)
		return 2
	company_name = sys.argv[1]
	out_dir = REPO_ROOT / "output" / "s231" / "verification"
	out_dir.mkdir(parents=True, exist_ok=True)
	# Sanitize for filename: replace path-unsafe chars with underscore.
	safe = (
		company_name.replace("/", "_")
		.replace("\\", "_")
		.replace(":", "_")
		.replace(" ", "_")
		.replace(".", "")
	)
	out = out_dir / f"company_defaults_fix_{safe}.json"

	stdout = run_in_container(build_fix_payload(company_name), timeout=120)
	data = decode_output(stdout)
	out.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
	print(f"Wrote {out}")
	if "error" in data:
		print(f"ERROR: {data['error']}", file=sys.stderr)
		return 3
	print(f"Cleared {data['fields_cleared']} fields on {data['company_name']}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
