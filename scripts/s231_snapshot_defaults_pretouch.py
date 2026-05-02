#!/usr/bin/env python3
"""S231 Phase B-2: snapshot all 49 store Companies' default_* state +
first_provision_done sentinel BEFORE any Phase B mutation.

Snapshot is the rollback ground truth — if Phase B-3 produces unexpected
results, revert each company's fields to its snapshot value.

Output: output/s231/state/PRETOUCH_BACKUP.json
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

OUT = REPO_ROOT / "output" / "s231" / "state" / "PRETOUCH_BACKUP.json"

SNAPSHOT_SCRIPT = (
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
    "first_provision_done",
]

field_select = ", ".join([f"`{f}`" for f in DEFAULT_FIELDS])
companies = frappe.db.sql(
    f'''
    SELECT name, abbr, entity_category, store_ownership_type,
           parent_company, {field_select}
    FROM `tabCompany`
    ORDER BY name
    ''',
    as_dict=True,
)

_s231_emit({
    "captured_at": frappe.utils.now(),
    "company_count": len(companies),
    "companies": companies,
})

frappe.destroy()
"""
)


def main() -> int:
	OUT.parent.mkdir(parents=True, exist_ok=True)
	stdout = run_in_container(SNAPSHOT_SCRIPT, timeout=120)
	data = decode_output(stdout)
	OUT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
	print(f"Wrote {OUT}: {data['company_count']} Companies snapshotted")
	return 0


if __name__ == "__main__":
	sys.exit(main())
