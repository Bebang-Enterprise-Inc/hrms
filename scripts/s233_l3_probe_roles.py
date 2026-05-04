#!/usr/bin/env python3
"""S233 L3 — probe existing Frappe Roles relevant to S233 RBAC."""
from __future__ import annotations
import json, pathlib, sys
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from s231_ssm_helper import run_in_container

PREAMBLE = """\
import os, sys, json, traceback
for d in ("/home/frappe/logs", "/home/frappe/frappe-bench/logs", "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"):
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")
def _emit(p):
    print("---S233-ROLES-START---")
    print(json.dumps(p, indent=2, default=str))
    print("---S233-ROLES-END---")
"""

PROBE = PREAMBLE + """
result = {"target_roles": {}}
TARGETS = ["BD Manager", "Business Development", "Accounts Manager", "HQ User", "System Manager", "Administrator", "Crew", "Store Crew", "Area Supervisor"]
for r in TARGETS:
    result["target_roles"][r] = bool(frappe.db.exists("Role", r))
# Sample existing BD-ish roles
all_roles = frappe.db.sql("SELECT name, disabled FROM `tabRole` WHERE name LIKE %s OR name LIKE %s OR name LIKE %s ORDER BY name", ("%BD%", "%Business%", "%Crew%"), as_dict=True)
result["existing_bd_or_crew_roles"] = all_roles
_emit(result)
frappe.destroy()
"""


def main() -> int:
    stdout = run_in_container(PROBE, timeout=60)
    if "---S233-ROLES-START---" not in stdout:
        print("ERR:\n" + stdout[-1500:])
        return 1
    s = stdout.split("---S233-ROLES-START---", 1)[1].split("---S233-ROLES-END---", 1)[0].strip()
    print(s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
