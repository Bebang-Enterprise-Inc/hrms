#!/usr/bin/env python3
"""Clear suggested_coa/final_coa on HR batch items."""
import os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

HR_BATCH = "BEI-PCF-2026-00004"
frappe.db.sql("""
    UPDATE `tabBEI PCF Batch Item`
    SET suggested_coa=NULL, suggested_coa_label=NULL, coa_confidence=0, final_coa=NULL, approved_amount=0
    WHERE parent=%s
""", (HR_BATCH,))
frappe.db.commit()

# Verify
rows = frappe.db.sql("""
    SELECT name, suggested_coa, final_coa, approved_amount FROM `tabBEI PCF Batch Item` WHERE parent=%s
""", (HR_BATCH,), as_dict=True)
print("After clear:", rows)
frappe.destroy()
