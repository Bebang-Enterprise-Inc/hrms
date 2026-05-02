#!/usr/bin/env python3
"""S231 Phase A-4: trigger S181 templates on BEBANG FT INC. via retry_provision.

The Company shell exists. Now run BEI's S181 helpers (warehouse, cost
center, sales template, balance sheet template, default accounts, BKI
customer). The C-1 atomicity wrapper handles the ERPNext chart-of-
accounts error by catching it and continuing to the S181 helpers.

Wraps the call in our own try/except so the orchestrator can see the
detailed result even if internal steps fail.
"""
from __future__ import annotations
import json, pathlib, sys
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from s231_ssm_helper import PAYLOAD_PREAMBLE, decode_output, run_in_container

PROBE = (
	PAYLOAD_PREAMBLE
	+ """
result = {}

# Set the chart-of-accounts ignore flag for this session so ERPNext's
# create_default_accounts (which auto_provision_company Step 0 calls)
# becomes a no-op. The S181 templates that BEI runs as Steps 1-9 do
# their own account creation and don't need ERPNext's chart import.
frappe.local.flags.ignore_chart_of_accounts = True

result["before"] = {
    "exists": bool(frappe.db.exists("Company", "BEBANG FT INC.")),
    "first_provision_done": frappe.db.get_value("Company", "BEBANG FT INC.", "first_provision_done"),
    "bfi2_accounts_count": frappe.db.count("Account", {"company": "BEBANG FT INC."}),
    "bfi2_warehouses_count": frappe.db.count("Warehouse", {"company": "BEBANG FT INC."}),
    "bfi2_cost_centers_count": frappe.db.count("Cost Center", {"company": "BEBANG FT INC."}),
}

import traceback
try:
    from hrms.overrides.company import retry_provision_company
    out = retry_provision_company(company_name="BEBANG FT INC.")
    result["retry_result"] = out
    result["retry_succeeded"] = True
except Exception as e:
    result["retry_succeeded"] = False
    result["retry_error"] = str(e)[:1000]
    result["retry_traceback"] = traceback.format_exc()[:5000]
    try:
        frappe.db.rollback()
    except Exception:
        pass

frappe.db.commit()

result["after"] = {
    "exists": bool(frappe.db.exists("Company", "BEBANG FT INC.")),
    "first_provision_done": frappe.db.get_value("Company", "BEBANG FT INC.", "first_provision_done"),
    "bfi2_accounts_count": frappe.db.count("Account", {"company": "BEBANG FT INC."}),
    "bfi2_warehouses_count": frappe.db.count("Warehouse", {"company": "BEBANG FT INC."}),
    "bfi2_cost_centers_count": frappe.db.count("Cost Center", {"company": "BEBANG FT INC."}),
}

# List sample accounts created
result["sample_bfi2_accounts"] = frappe.db.sql(
    "SELECT name, is_group, root_type FROM `tabAccount` WHERE company = 'BEBANG FT INC.' ORDER BY name LIMIT 30",
    as_dict=True,
)

# Check the required ones from the plan
required = [f"{n} - BFI2" for n in ["Stock In Hand", "Payroll Payable", "Employee Advances",
    "Cash on Hand", "Debtors", "Creditors", "Cost of Goods Sold", "Round Off"]]
result["required_accounts"] = required
result["required_accounts_present"] = [a for a in required if frappe.db.exists("Account", a)]
result["required_accounts_missing"] = [a for a in required if not frappe.db.exists("Account", a)]

_s231_emit(result)
frappe.destroy()
"""
)


def main() -> int:
	stdout = run_in_container(PROBE, timeout=300)
	data = decode_output(stdout)
	out = pathlib.Path("output/s231/verification/bfi2_retry_provision_log.json")
	out.parent.mkdir(parents=True, exist_ok=True)
	out.write_text(json.dumps(data, indent=2, default=str))
	print(f"Wrote {out}")
	print(f"\nBefore: {data.get('before')}")
	print(f"After:  {data.get('after')}")
	print(f"Retry succeeded: {data.get('retry_succeeded')}")
	if not data.get("retry_succeeded"):
		print(f"Error: {data.get('retry_error', '')[:200]}")
	print(f"\nRequired accounts present: {len(data.get('required_accounts_present', []))} / {len(data.get('required_accounts', []))}")
	print(f"Missing: {data.get('required_accounts_missing', [])[:10]}")
	if data.get("sample_bfi2_accounts"):
		print(f"\nSample accounts:")
		for a in data["sample_bfi2_accounts"][:10]:
			print(f"  {a['name']}  is_group={a['is_group']} root={a['root_type']}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
