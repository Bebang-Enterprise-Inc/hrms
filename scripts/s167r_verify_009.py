#!/usr/bin/env python3
"""DEFECT-009 verification: check that classify_batch_items now stores
full Account names (not naked GL codes) on tabBEI PCF Batch Item.suggested_coa."""
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# Helper directly imported
from hrms.api.pcf import _resolve_coa_code_to_account

# Test the helper directly with known codes
print("=== _resolve_coa_code_to_account direct test ===")
for code in ["6010100", "6006001", "6006003", "6010003", "6004005"]:
    name = _resolve_coa_code_to_account(code, "Bebang Enterprise Inc.")
    print(f"  {code} -> {name}")

# Also classify a sample expense end-to-end
from hrms.api.expense_classifier import classify_expense
print("\n=== classify_expense + resolve sample ===")
samples = [
    ("Snacks for team meeting", "Jollibee", 350),
    ("Office printer paper", "National Book Store", 480),
    ("Mercury Drug supplies", "Mercury Drug", 250),
]
for desc, vendor, amt in samples:
    c = classify_expense(description=desc, vendor=vendor, amount=amt)
    code = c.get("coa")
    resolved = _resolve_coa_code_to_account(code, "Bebang Enterprise Inc.")
    print(f"  {vendor:30s} -> code:{code} -> {resolved}")

frappe.destroy()
