#!/usr/bin/env python3
import os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

for u in ["test.staff@bebang.ph","test.supervisor@bebang.ph","test.hr@bebang.ph","test.warehouse@bebang.ph","test.commissary@bebang.ph","test.finance@bebang.ph"]:
    roles = [r.role for r in frappe.get_roles(u) if r and not str(r).startswith("All") and not str(r).startswith("Guest")] if False else frappe.get_roles(u)
    pcf_relevant = [r for r in roles if any(k in r for k in ["Store","Crew","Supervisor","HR","Warehouse","Commissary","Finance","Account","System Manager","Admin","Manager"])]
    print(f"\n{u}:")
    for r in pcf_relevant: print(f"  {r}")
frappe.destroy()
