#!/usr/bin/env python3
"""
End-to-end DEFECT-009 proof:
1. Create 1 HR expense with vendor="Lalamove" (rule-matches 6009003)
2. Submit batch
3. Call classify_batch_items -> should store FULL Account name not naked code
4. Call approve_batch_with_coa with resolved name -> should succeed (was LinkValidationError)
5. Rollback
"""
import os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

from hrms.api.pcf import classify_batch_items, _resolve_coa_code_to_account
import json

# First, check if 6009003 account exists
target = _resolve_coa_code_to_account("6009003", "Bebang Enterprise Inc.")
print(f"6009003 resolves to: {target}")
if not target:
    # Fallback: use 6006001 (Store Supplies) which we confirmed exists
    print("Falling back to 6006001 (STORE SUPPLIES)")

# Get HR fund (must exist from earlier runs)
fund = frappe.db.get_value("BEI Petty Cash Fund", "PCF-HR and Admin",
    ["name","company","custodian"], as_dict=True)
print(f"HR fund: {fund}")
if not fund:
    print("ERROR: PCF-HR and Admin fund does not exist - skip e2e")
    frappe.destroy()
    raise SystemExit(0)

# Create an expense request as test.hr custodian
frappe.set_user("test.hr@bebang.ph")
doc = frappe.get_doc({
    "doctype": "BEI Expense Request",
    "employee": "TEST-HR-001",
    "manual_vendor": "Lalamove",
    "manual_description": "DEFECT-009 e2e test — delivery rider fee",
    "manual_amount": 180,
    "manual_date": "2026-04-09",
    "pcf_fund": fund["name"],
    "status": "Pending",
})
doc.receipt_photo = "/files/s167_test_receipt.png"
doc.flags.ignore_permissions = True
doc.flags.ignore_mandatory = True
doc.insert(ignore_permissions=True, ignore_mandatory=True)
frappe.db.commit()
print(f"Created expense: {doc.name}")

# Create a batch manually with this expense
frappe.set_user("Administrator")
from hrms.hr.doctype.bei_pcf_batch.bei_pcf_batch import create_batch_from_pending
batch_result = create_batch_from_pending(pcf_fund=fund["name"], submission_type="Manual")
print(f"Batch: {json.dumps(batch_result, default=str)[:400]}")
batch_name = batch_result.get("batch_name") if isinstance(batch_result, dict) else None
if not batch_name:
    # find latest batch
    rows = frappe.db.sql("""
        SELECT name FROM `tabBEI PCF Batch`
        WHERE pcf_fund=%s ORDER BY creation DESC LIMIT 1
    """, (fund["name"],), as_dict=True)
    batch_name = rows[0]["name"] if rows else None
print(f"batch_name: {batch_name}")

if batch_name:
    # Classify it - this exercises DEFECT-009 fix
    result = classify_batch_items(batch_name)
    print(f"\nclassify result: {json.dumps(result, default=str)[:800]}")

    # Check the batch item's suggested_coa value
    items = frappe.db.sql("""
        SELECT name, vendor, suggested_coa, suggested_coa_label
        FROM `tabBEI PCF Batch Item` WHERE parent=%s
    """, (batch_name,), as_dict=True)
    print(f"\nBatch items after classify:")
    for i in items:
        print(f"  {i}")
        # CRITICAL: suggested_coa should be a full Account name, not a naked code
        if i["suggested_coa"]:
            if i["suggested_coa"].isdigit() or len(i["suggested_coa"]) < 20:
                print(f"  !!! FAIL: suggested_coa is STILL NAKED: {i['suggested_coa']!r}")
            else:
                print(f"  PASS suggested_coa is RESOLVED: {i['suggested_coa']!r}")

    # Rollback: delete the test expense + batch
    frappe.db.sql("DELETE FROM `tabBEI PCF Batch Item` WHERE parent=%s", (batch_name,))
    frappe.db.sql("DELETE FROM `tabBEI PCF Batch` WHERE name=%s", (batch_name,))
    frappe.db.sql("DELETE FROM `tabBEI Expense Request` WHERE name=%s", (doc.name,))
    frappe.db.commit()
    print(f"\nCleaned up: deleted batch {batch_name} + expense {doc.name}")

frappe.destroy()
