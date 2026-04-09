#!/usr/bin/env python3
"""Re-align test employees to match dept funds for Phase 0.2 / Phase 1 REDO."""
import os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

MAPPING = {
    "TEST-HR-001":         "HR and Admin - BEI",
    "TEST-COMMISSARY-001": "Commissary - BEI",
    "TEST-WAREHOUSE-001":  "Supply Chain - BEI",
}
for emp, dept in MAPPING.items():
    cur = frappe.db.get_value("Employee", emp, "department")
    frappe.db.set_value("Employee", emp, "department", dept, update_modified=False)
    print(f"  {emp}: {cur} -> {dept}")
frappe.db.commit()
frappe.destroy()
