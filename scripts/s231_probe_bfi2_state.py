#!/usr/bin/env python3
"""S231: probe production for any partial BFI2 / BEBANG FT INC. state
that might have been left by a prior failed creation attempt.
"""

from __future__ import annotations

import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from s231_ssm_helper import PAYLOAD_PREAMBLE, decode_output, run_in_container

OUT = REPO_ROOT / "output" / "s231" / "verification" / "bfi2_state_probe.json"

PROBE = (
	PAYLOAD_PREAMBLE
	+ """
result = {}

# 1. Company
result["company_BEBANG_FT_INC"] = bool(frappe.db.exists("Company", "BEBANG FT INC."))

# 2. All accounts with - BFI2 suffix
accounts = frappe.db.sql(
    '''SELECT name, is_group, account_number, parent_account, root_type, account_type, disabled
       FROM `tabAccount` WHERE name LIKE '%- BFI2'
       ORDER BY name''',
    as_dict=True,
)
result["bfi2_accounts_count"] = len(accounts)
result["bfi2_accounts"] = accounts[:200]

# 3. Specifically the offender from the create error
target = "6020602 - ACCOUNTING FEES - BFI2"
result["target_account_exists"] = bool(frappe.db.exists("Account", target))
if result["target_account_exists"]:
    result["target_account"] = frappe.db.get_value(
        "Account", target,
        ["name", "is_group", "account_number", "parent_account", "root_type", "disabled"],
        as_dict=True,
    )

# 4. Cost Centers with - BFI2
cc = frappe.db.sql(
    '''SELECT name, is_group, parent_cost_center, disabled
       FROM `tabCost Center` WHERE name LIKE '%- BFI2' ORDER BY name''',
    as_dict=True,
)
result["bfi2_cost_centers_count"] = len(cc)
result["bfi2_cost_centers"] = cc

# 5. Warehouses with - BFI2
wh = frappe.db.sql(
    '''SELECT name, company, is_group, disabled FROM `tabWarehouse`
       WHERE name LIKE '%- BFI2' ORDER BY name''',
    as_dict=True,
)
result["bfi2_warehouses_count"] = len(wh)
result["bfi2_warehouses"] = wh

# 6. Customers / Suppliers with - BFI2
result["bfi2_customer_count"] = frappe.db.count("Customer", {"name": ["like", "%- BFI2"]})
result["bfi2_supplier_count"] = frappe.db.count("Supplier", {"name": ["like", "%- BFI2"]})

_s231_emit(result)
frappe.destroy()
"""
)


def main() -> int:
	OUT.parent.mkdir(parents=True, exist_ok=True)
	stdout = run_in_container(PROBE, timeout=180)
	data = decode_output(stdout)
	OUT.write_text(json.dumps(data, indent=2, default=str))
	print(f"Wrote {OUT}")
	print(f"Company BEBANG FT INC.: {data['company_BEBANG_FT_INC']}")
	print(f"Accounts with -BFI2: {data['bfi2_accounts_count']}")
	print(f"Cost Centers with -BFI2: {data['bfi2_cost_centers_count']}")
	print(f"Warehouses with -BFI2: {data['bfi2_warehouses_count']}")
	print(f"Customers with -BFI2: {data['bfi2_customer_count']}")
	print(f"Suppliers with -BFI2: {data['bfi2_supplier_count']}")
	if data.get("target_account_exists"):
		print(f"\n6020602 - ACCOUNTING FEES - BFI2 state:")
		print(f"  {data['target_account']}")
	# Show first 30 accounts to understand the structure
	print(f"\nFirst 30 BFI2 accounts:")
	for a in data["bfi2_accounts"][:30]:
		print(f"  {a['name']}  is_group={a['is_group']} parent={a['parent_account']}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
