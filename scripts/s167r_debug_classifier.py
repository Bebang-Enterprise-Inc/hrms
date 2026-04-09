#!/usr/bin/env python3
import os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

from hrms.api.expense_classifier import classify_expense, _get_runtime_health, MODEL_PATH
import os as os2

print("=== Classifier runtime health ===")
h = _get_runtime_health()
for k, v in h.items(): print(f"  {k}: {v}")

print(f"\n=== MODEL_PATH exists? ===")
print(f"  {MODEL_PATH} -> exists={os2.path.exists(MODEL_PATH)}")

print("\n=== classify_expense full return ===")
for desc, vendor, amt in [
    ("Snacks for team meeting", "Jollibee", 350),
    ("Office printer paper", "National Book Store", 480),
    ("Mercury Drug supplies", "Mercury Drug", 250),
    ("Lalamove delivery rider fee", "Lalamove", 180),
]:
    r = classify_expense(description=desc, vendor=vendor, amount=amt)
    print(f"  {vendor}: {r}")

frappe.destroy()
