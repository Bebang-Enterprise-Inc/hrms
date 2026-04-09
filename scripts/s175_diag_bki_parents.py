#!/usr/bin/env python3
"""Diag — check BKI parent_account distribution and lft/rgt overlap with TIH."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from s175_ssm_runner import run_on_frappe

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "output" / "s175" / "diagnostics"
OUT.mkdir(parents=True, exist_ok=True)

PAYLOAD = r'''
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

out = {}
out["bki_parent_categories"] = {
    "NULL": frappe.db.sql("SELECT COUNT(*) FROM `tabAccount` WHERE company=%s AND parent_account IS NULL", "Bebang Kitchen Inc.")[0][0],
    "empty_string": frappe.db.sql("SELECT COUNT(*) FROM `tabAccount` WHERE company=%s AND parent_account=''", "Bebang Kitchen Inc.")[0][0],
    "non_null": frappe.db.sql("SELECT COUNT(*) FROM `tabAccount` WHERE company=%s AND parent_account IS NOT NULL AND parent_account != ''", "Bebang Kitchen Inc.")[0][0],
}
# What does BKI's income-type tree look like?
out["bki_income_accounts"] = frappe.db.sql("""
    SELECT name, account_name, is_group, parent_account, lft, rgt
    FROM `tabAccount` WHERE company=%s AND root_type='Income'
    ORDER BY lft LIMIT 20
""", "Bebang Kitchen Inc.", as_dict=True)

# Do BKI and TIH share lft/rgt ranges?
out["bki_lft_range"] = frappe.db.sql("SELECT MIN(lft), MAX(rgt), COUNT(*) FROM `tabAccount` WHERE company=%s", "Bebang Kitchen Inc.")[0]
out["tih_lft_range"] = frappe.db.sql("SELECT MIN(lft), MAX(rgt), COUNT(*) FROM `tabAccount` WHERE company=%s", "Triple I Holdings")[0]

# What's at lft 1-10?
out["global_lft_1_10"] = frappe.db.sql("""
    SELECT name, company, account_name, is_group, parent_account, lft, rgt
    FROM `tabAccount` WHERE lft BETWEEN 1 AND 10 ORDER BY lft
""", as_dict=True)

# What's at the very highest lft/rgt?
out["global_max"] = frappe.db.sql("""
    SELECT name, company, lft, rgt FROM `tabAccount` ORDER BY rgt DESC LIMIT 5
""", as_dict=True)

# Check if normalize UPDATE reaches anything (dry run count)
out["bki_would_normalize"] = frappe.db.sql("""
    SELECT COUNT(*) FROM `tabAccount` WHERE company=%s AND parent_account=''
""", "Bebang Kitchen Inc.")[0][0]

print("DIAG_START")
print(json.dumps(out, default=str))
print("DIAG_END")
frappe.destroy()
'''

payload_path = OUT / "_diag_bki_parents_payload.py"
payload_path.write_text(PAYLOAD, encoding="utf-8")
stdout, stderr, status = run_on_frappe(payload_path, tag="diag_bki_parents")
if status != "Success":
    print(stderr); sys.exit(1)
raw = stdout.split("DIAG_START", 1)[1].split("DIAG_END", 1)[0].strip()
data = json.loads(raw)
(OUT / "bki_parents.json").write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
print(json.dumps(data, indent=2, default=str)[:4000])
