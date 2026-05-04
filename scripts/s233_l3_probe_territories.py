#!/usr/bin/env python3
"""S233 L3 — probe Territory + CustomerGroup state in production."""
from __future__ import annotations
import json, pathlib, sys
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from s231_ssm_helper import run_in_container

PROBE = """\
import os, json, traceback
for d in ("/home/frappe/logs", "/home/frappe/frappe-bench/logs", "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"):
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

result = {}
try:
    territories = frappe.db.sql("SELECT name FROM `tabTerritory` ORDER BY name", as_dict=True)
    result["territories_count"] = len(territories)
    result["territories"] = territories
    result["territory_philippines_exists"] = bool(frappe.db.exists("Territory", "Philippines"))

    cgroups = frappe.db.sql("SELECT name FROM `tabCustomer Group` WHERE name LIKE %s OR name LIKE %s ORDER BY name", ("%BKI%", "%Store%"), as_dict=True)
    result["bki_cgroups"] = cgroups
    result["bki_store_exists"] = bool(frappe.db.exists("Customer Group", "BKI Store"))

    # Sample existing Customer to see what territory + customer_group it uses
    sample = frappe.db.sql("SELECT name, customer_group, territory FROM `tabCustomer` LIMIT 5", as_dict=True)
    result["sample_customers"] = sample
except Exception as e:
    result["error"] = str(e)
    result["traceback"] = traceback.format_exc()

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
