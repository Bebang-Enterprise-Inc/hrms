#!/usr/bin/env python3
"""S233 L3 — seed missing Frappe Role DocTypes (BD Manager, Business Development, Crew).

These roles are declared in bei-tasks/lib/roles.ts but were never migrated
to Frappe as Role DocTypes. Seed them so L3 can assign them to test users.
Idempotent — if a role already exists, no-op.

This is also recorded as collateral defect S233-COLLAT-1: ship a fixtures
migration so these roles exist in production by default (separate sprint).
"""
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
    print("---S233-SEEDROLES-START---")
    print(json.dumps(p, indent=2, default=str))
    print("---S233-SEEDROLES-END---")
"""

SEED = PREAMBLE + """
TARGETS = ["BD Manager", "Business Development", "Crew"]
result = {"actions": []}
try:
    for role in TARGETS:
        if frappe.db.exists("Role", role):
            result["actions"].append({"role": role, "action": "noop", "reason": "already exists"})
        else:
            r = frappe.new_doc("Role")
            r.role_name = role
            r.disabled = 0
            r.is_custom = 1
            r.flags.ignore_permissions = True
            r.insert()
            result["actions"].append({"role": role, "action": "created"})
    frappe.db.commit()
    result["status"] = "OK"
except Exception as e:
    result["error"] = str(e)
    result["traceback"] = traceback.format_exc()
    result["status"] = "ERROR"
_emit(result)
frappe.destroy()
"""


def main() -> int:
    stdout = run_in_container(SEED, timeout=60)
    if "---S233-SEEDROLES-START---" not in stdout:
        print("ERR:\n" + stdout[-1500:])
        return 1
    s = stdout.split("---S233-SEEDROLES-START---", 1)[1].split("---S233-SEEDROLES-END---", 1)[0].strip()
    print(s)
    return 0 if json.loads(s).get("status") == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
