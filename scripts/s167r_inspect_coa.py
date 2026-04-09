#!/usr/bin/env python3
import os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# Search for accounts containing the GL code 6010100
for code in ["6010100", "6006001", "6006003"]:
    rows = frappe.db.sql("""
        SELECT name, account_number FROM `tabAccount`
        WHERE company='Bebang Enterprise Inc.' AND (name LIKE %s OR account_number=%s)
        LIMIT 5
    """, (f"%{code}%", code), as_dict=True)
    print(f"\nCode {code}:")
    for r in rows: print(f"  {r}")

# Check schema
cols = [c[0] for c in frappe.db.sql("DESCRIBE `tabAccount`")]
print(f"\ntabAccount columns: {cols}")

frappe.destroy()
