#!/usr/bin/env python3
"""Clear naked COAs on HR batch items + find a valid expense Account to use."""
import os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

HR_BATCH = "BEI-PCF-2026-00004"

# Clear naked/short COAs on expenses AND on batch items
exps = frappe.db.sql("""
    SELECT name, internal_suggested_coa FROM `tabBEI Expense Request` WHERE pcf_batch=%s
""", (HR_BATCH,), as_dict=True)
print("Before:", exps)
frappe.db.sql("""UPDATE `tabBEI Expense Request` SET internal_suggested_coa=NULL WHERE pcf_batch=%s""", (HR_BATCH,))
# Inspect BEI PCF Batch Item columns
cols = [c[0] for c in frappe.db.sql("DESCRIBE `tabBEI PCF Batch Item`")]
print("Batch Item cols:", cols)

frappe.db.commit()

# Find a valid expense Account for Bebang Enterprise Inc.
accts = frappe.db.sql("""
    SELECT name, account_name, account_type, is_group
    FROM `tabAccount`
    WHERE company='Bebang Enterprise Inc.' AND is_group=0
      AND (account_type IN ('Expense Account','') OR root_type='Expense')
      AND account_name LIKE '%%Office%%'
    LIMIT 10
""", as_dict=True)
print("\nCandidate Office expense accounts:")
for a in accts:
    print(" ", a)

# Also get any general expense account
any_exp = frappe.db.sql("""
    SELECT name FROM `tabAccount`
    WHERE company='Bebang Enterprise Inc.' AND is_group=0 AND root_type='Expense'
    ORDER BY name LIMIT 5
""", as_dict=True)
print("\nAny expense accounts:")
for a in any_exp: print(" ", a["name"])

frappe.destroy()
