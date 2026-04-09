#!/usr/bin/env python3
"""S167 REDO Phase 2 reset — wipe HR fund pending expenses + any HR batches in last 12h."""
import os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

FUND = "PCF-HR and Admin"

# Find HR batches in the last 12h
batches = frappe.db.sql("""
    SELECT name FROM `tabBEI PCF Batch`
    WHERE pcf_fund=%s AND creation > DATE_SUB(NOW(), INTERVAL 12 HOUR)
""", (FUND,), as_dict=True)
print(f"HR batches to delete: {[b['name'] for b in batches]}")

# Find HR expenses
exps = frappe.db.sql("""
    SELECT name, status, pcf_batch FROM `tabBEI Expense Request`
    WHERE pcf_fund=%s AND creation > DATE_SUB(NOW(), INTERVAL 12 HOUR)
""", (FUND,), as_dict=True)
print(f"HR expenses to delete: {[(e['name'], e['status']) for e in exps]}")

# Clear internal_suggested_coa + pcf_batch on expenses so delete works
for e in exps:
    try:
        frappe.db.set_value("BEI Expense Request", e["name"], {"internal_suggested_coa": None, "pcf_batch": None}, update_modified=False)
    except Exception as ex:
        print(f"  clear fail {e['name']}: {ex}")

# Delete batch items + batches
for b in batches:
    frappe.db.sql("DELETE FROM `tabBEI PCF Batch Item` WHERE parent=%s", (b["name"],))
    try:
        d = frappe.get_doc("BEI PCF Batch", b["name"])
        if d.docstatus == 1:
            d.cancel()
        frappe.delete_doc("BEI PCF Batch", b["name"], force=True, ignore_permissions=True)
        print(f"  deleted batch {b['name']}")
    except Exception as ex:
        print(f"  batch delete fail {b['name']}: {ex}")

# Delete expenses
for e in exps:
    try:
        d = frappe.get_doc("BEI Expense Request", e["name"])
        if d.docstatus == 1:
            d.cancel()
        frappe.delete_doc("BEI Expense Request", e["name"], force=True, ignore_permissions=True)
        print(f"  deleted expense {e['name']}")
    except Exception as ex:
        print(f"  expense delete fail {e['name']}: {ex}")

frappe.db.commit()

# Verify
remaining = frappe.db.sql("""
    SELECT COUNT(*) FROM `tabBEI Expense Request`
    WHERE pcf_fund=%s AND creation > DATE_SUB(NOW(), INTERVAL 12 HOUR)
""", (FUND,))[0][0]
print(f"REMAINING HR expenses (last 12h): {remaining}")
frappe.destroy()
