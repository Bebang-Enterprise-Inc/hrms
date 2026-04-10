#!/usr/bin/env python3
"""Repoint the 3 orphans to the actual parent account names (not the short alias)."""
import json, os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

BEI = "Bebang Enterprise Inc."
r = {"fixes": []}

# The orphans point to "X - BEI" but the actual accounts are "X - Bebang Enterprise Inc."
repoints = [
    ("ADVANCES TO SSS - BEI", "NON-TRADE RECEIVABLES - BEI", "NON-TRADE RECEIVABLES - Bebang Enterprise Inc."),
    ("GR/IR CLEARING - BEI", "INVENTORY - BEI", "INVENTORY - Bebang Enterprise Inc."),
    ("PROPERTY, PLANT AND EQUIPMENT - BEI", "NON-CURRENT ASSETS - BEI", "NON-CURRENT ASSETS - Bebang Enterprise Inc."),
]

for orphan, old_parent, new_parent in repoints:
    exists = bool(frappe.db.exists("Account", new_parent))
    if exists:
        frappe.db.set_value("Account", orphan, "parent_account", new_parent)
        r["fixes"].append({"orphan": orphan, "old": old_parent, "new": new_parent, "status": "FIXED"})
    else:
        r["fixes"].append({"orphan": orphan, "new": new_parent, "status": "TARGET_MISSING"})

frappe.db.commit()

# Verify
remaining = frappe.db.sql("""
    SELECT a.name, a.parent_account FROM `tabAccount` a
    LEFT JOIN `tabAccount` p ON a.parent_account = p.name
    WHERE a.company = %s AND a.parent_account IS NOT NULL AND a.parent_account != '' AND p.name IS NULL
""", BEI, as_dict=True)
r["remaining_orphans"] = len(remaining)
r["all_pass"] = len(remaining) == 0

print("R_BEGIN")
print(json.dumps(r, default=str, indent=2))
print("R_END")
