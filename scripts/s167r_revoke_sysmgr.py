#!/usr/bin/env python3
"""Revoke System Manager from test.hr and test.finance so RBAC tests are meaningful."""
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

TARGETS = ["test.hr@bebang.ph", "test.finance@bebang.ph"]

for email in TARGETS:
    if not frappe.db.exists("User", email):
        print(f"  {email}: user not found")
        continue
    user = frappe.get_doc("User", email)
    before = [r.role for r in user.roles]
    # Remove System Manager
    user.roles = [r for r in user.roles if r.role != "System Manager"]
    user.save(ignore_permissions=True)
    after = [r.role for r in user.roles]
    removed = set(before) - set(after)
    print(f"  {email}: removed {removed} | roles now: {sorted(after)}")

frappe.db.commit()
frappe.destroy()
