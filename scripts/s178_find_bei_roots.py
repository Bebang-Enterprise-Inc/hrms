#!/usr/bin/env python3
"""Find BEI's actual root-level account groups."""
import json, os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

BEI = "Bebang Enterprise Inc."

# Get ALL BEI accounts with no parent (roots)
roots = frappe.db.sql("""
    SELECT name, account_name, account_number, root_type, is_group, parent_account
    FROM `tabAccount`
    WHERE company = %s
      AND (parent_account IS NULL OR parent_account = '')
    ORDER BY root_type, name
    LIMIT 30
""", BEI, as_dict=True)

# Get BEI Asset group accounts (any level)
asset_groups = frappe.db.sql("""
    SELECT name, account_name, account_number, parent_account, is_group
    FROM `tabAccount`
    WHERE company = %s AND root_type = 'Asset' AND is_group = 1
    ORDER BY account_number, name
    LIMIT 30
""", BEI, as_dict=True)

# Get the 3 orphans' current state
orphans = {}
for acct in ["ADVANCES TO SSS - BEI", "GR/IR CLEARING - BEI", "PROPERTY, PLANT AND EQUIPMENT - BEI"]:
    orphans[acct] = frappe.db.get_value("Account", acct,
        ["name", "parent_account", "root_type", "account_number"], as_dict=True)

print("R_BEGIN")
print(json.dumps({"roots": roots, "asset_groups": asset_groups, "orphans": orphans}, default=str, indent=2))
print("R_END")
