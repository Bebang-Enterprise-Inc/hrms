#!/usr/bin/env python3
"""S233 L3 — probe whether the test Company + 4 records actually exist in DB."""
from __future__ import annotations
import json, pathlib, sys
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from s231_ssm_helper import run_in_container

PROBE = """\
import os, json
for d in ("/home/frappe/logs", "/home/frappe/frappe-bench/logs", "/home/frappe/frappe-bench/hq.bebang.ph/logs", "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"):
    try: os.makedirs(d, exist_ok=True)
    except: pass
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

result = {}
for dt, name in [
    ("Company", "L3 Test Store 233 - BEBANG FT INC."),
    ("Warehouse", "L3 Test Store 233 - BEBANG FT INC."),
    ("Customer", "L3 Test Store 233 - BEBANG FT INC."),
    ("Customer", "L3 Test Store 233 (Internal)"),
]:
    exists = bool(frappe.db.exists(dt, name))
    result[f"{dt}::{name}"] = exists

# Also dump the Company doc fields if it exists
if frappe.db.exists("Company", "L3 Test Store 233 - BEBANG FT INC."):
    doc = frappe.db.get_value("Company", "L3 Test Store 233 - BEBANG FT INC.",
        ["abbr", "parent_company", "store_ownership_type", "entity_category", "operational_status", "tax_id", "first_provision_done"], as_dict=True)
    result["company_doc"] = doc

# Check S037 CSV row
import csv
from hrms.utils.bei_config import STORE_ENTITY_MAPPING_RELPATH
s037 = os.path.normpath(os.path.join(frappe.get_app_path("hrms"), *STORE_ENTITY_MAPPING_RELPATH))
with open(s037, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.reader(f))
result["s037_test_row_present"] = any(r and r[0].strip() == "L3 Test Store 233" for r in rows[1:])

print("---PROBE-START---")
print(json.dumps(result, indent=2, default=str))
print("---PROBE-END---")
frappe.destroy()
"""


def main() -> int:
    stdout = run_in_container(PROBE, timeout=60)
    if "---PROBE-START---" not in stdout:
        print("ERR:\n" + stdout[-1500:])
        return 1
    s = stdout.split("---PROBE-START---", 1)[1].split("---PROBE-END---", 1)[0].strip()
    print(s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
