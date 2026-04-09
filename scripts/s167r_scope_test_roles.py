#!/usr/bin/env python3
"""Trim test accounts to realistic role sets for meaningful RBAC testing."""
import os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# Target role sets - only roles each persona legitimately needs
TARGET_ROLES = {
    "test.hr@bebang.ph":        ["Employee", "HR User"],
    "test.finance@bebang.ph":   ["Employee", "Accounts User", "Accounts Manager"],
}
# NB: do NOT modify test.staff/supv/commi/warehouse - they already have correct roles per earlier audit

PRESERVE = {"Employee", "All", "Desk User", "Guest"}

for email, keep in TARGET_ROLES.items():
    if not frappe.db.exists("User", email):
        print(f"  {email}: user not found")
        continue
    user = frappe.get_doc("User", email)
    before = sorted([r.role for r in user.roles])
    keep_set = set(keep) | PRESERVE
    user.roles = [r for r in user.roles if r.role in keep_set]
    # Add any missing target roles
    existing = {r.role for r in user.roles}
    for role in keep:
        if role not in existing:
            if frappe.db.exists("Role", role):
                user.append("roles", {"role": role})
    user.save(ignore_permissions=True)
    after = sorted([r.role for r in user.roles])
    print(f"  {email}:")
    print(f"    before: {before}")
    print(f"    after:  {after}")

frappe.db.commit()
frappe.destroy()
