#!/usr/bin/env python3
"""Check TIH's allow_account_creation_against_child_company setting + TIH Chart of Accounts."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from s175_ssm_runner import run_on_frappe

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "output" / "s175" / "diagnostics"

PAYLOAD = r'''
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

out = {}
# TIH company config
tih = frappe.db.sql("""
    SELECT name, allow_account_creation_against_child_company, is_group
    FROM `tabCompany` WHERE name='Triple I Holdings'
""", as_dict=True)
out["tih_config"] = tih

# TIH's existing Account names matching template
template_names = [
    "SALES","STORE SALES","IN-STORE SALES","ONLINE SALES","BEI WEBSITE","FOOD PANDA","GRAB",
    "BKI SALES","DELIVERIES","LOGISTICS","DELIVERY INCOME","LOGISTICS INCOME",
    "FEES","ROYALTY FEES","MANAGEMENT FEES","FRANCHISE FEES","MARKETING FEES","E-COMMERCE FEES",
    "DISCOUNTS AND PROMO","SALES DISCOUNT DUE TO FREE HALOHALO","SALES DISCOUNT OF SENIOR CITIZENS",
    "SALES DISCOUNTS OF PWDS","SALES DISCOUNTS OF STAFFS AND EMPLOYEES",
    "SALES DISCOUNTS FROM VAT OF PWD","SALES DISCOUNTS FROM VAT OF SENIOR CITIZENS",
    "SALES REFUNDS TO CUSTOMER","SALES DISCOUNTS - EMPLOYEE DISC",
]
out["tih_matching_template"] = {}
for tn in template_names:
    row = frappe.db.sql(
        "SELECT name, account_number, is_group, root_type FROM `tabAccount` WHERE company='Triple I Holdings' AND account_name=%s",
        tn, as_dict=True,
    )
    if row:
        out["tih_matching_template"][tn] = row

# Total TIH 4xxxxxx accounts
out["tih_4xxxxxx_count"] = frappe.db.sql("SELECT COUNT(*) FROM `tabAccount` WHERE company='Triple I Holdings' AND account_number LIKE '4%%'")[0][0]

print("DIAG_START")
print(json.dumps(out, default=str))
print("DIAG_END")
frappe.destroy()
'''
payload_path = OUT / "_tih_config.py"
payload_path.write_text(PAYLOAD, encoding="utf-8")
stdout, stderr, status = run_on_frappe(payload_path, tag="diag_tih_config")
if status != "Success":
    print(stderr); sys.exit(1)
raw = stdout.split("DIAG_START", 1)[1].split("DIAG_END", 1)[0].strip()
data = json.loads(raw)
(OUT / "tih_config.json").write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
print(json.dumps(data, indent=2, default=str))
