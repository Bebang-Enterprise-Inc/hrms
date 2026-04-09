#!/usr/bin/env python3
import os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")
row = frappe.db.get_value("BEI Petty Cash Fund", "PCF-HR and Admin",
    ["name","fund_amount","threshold_percentage","is_enabled","custodian"], as_dict=True)
print(row)
if not row["is_enabled"]:
    frappe.db.set_value("BEI Petty Cash Fund", "PCF-HR and Admin", "is_enabled", 1, update_modified=False)
    frappe.db.commit()
    print("RE-ENABLED")
frappe.destroy()
