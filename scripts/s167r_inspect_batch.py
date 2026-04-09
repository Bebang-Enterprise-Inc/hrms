#!/usr/bin/env python3
import os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

HR_BATCH = "BEI-PCF-2026-00004"
print("=== BEI Expense Request rows linked to batch ===")
for r in frappe.db.sql("SELECT name, employee_name, manual_vendor, manual_amount, internal_suggested_coa FROM `tabBEI Expense Request` WHERE pcf_batch=%s", (HR_BATCH,), as_dict=True):
    print(" ", r)
print("\n=== BEI PCF Batch Item rows ===")
for r in frappe.db.sql("SELECT name, idx, expense_request, vendor, amount, suggested_coa, final_coa, approved_amount FROM `tabBEI PCF Batch Item` WHERE parent=%s ORDER BY idx", (HR_BATCH,), as_dict=True):
    print(" ", r)
frappe.destroy()
