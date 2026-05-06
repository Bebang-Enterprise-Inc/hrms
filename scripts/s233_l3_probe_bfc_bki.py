#!/usr/bin/env python3
"""S233 L3 — probe BFC and BKI entity_category + is_group state."""
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
for name in ["BEBANG FRANCHISE CORP.", "BEBANG KITCHEN INC."]:
    if frappe.db.exists("Company", name):
        result[name] = frappe.db.get_value("Company", name, ["is_group", "entity_category", "abbr"], as_dict=True)
    else:
        result[name] = "NOT_FOUND"

# Also list all Companies with is_group=1
groups = frappe.db.sql("SELECT name, entity_category, abbr FROM `tabCompany` WHERE is_group=1 ORDER BY name", as_dict=True)
result["all_is_group_companies"] = groups

print("---PROBE-START---")
print(json.dumps(result, indent=2, default=str))
print("---PROBE-END---")
frappe.destroy()
"""


def main() -> int:
    stdout = run_in_container(PROBE, timeout=60)
    if "---PROBE-START---" not in stdout: print("ERR:\\n" + stdout[-1500:]); return 1
    s = stdout.split("---PROBE-START---", 1)[1].split("---PROBE-END---", 1)[0].strip()
    print(s); return 0


if __name__ == "__main__":
    sys.exit(main())
