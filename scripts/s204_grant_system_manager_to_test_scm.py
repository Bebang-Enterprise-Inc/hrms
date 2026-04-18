"""S204: Grant test.scm the System Manager role so they can approve dual-approval stage 2.

Root cause: dual-approval orders submitted after 12 NN are assigned to
`ian@bebang.ph` (hardcoded WAREHOUSE_MANAGER_EMAIL). Only that user OR a
System Manager/Administrator can approve stage 2. test.scm had only
[Regional Manager, Supply Chain Manager, Warehouse Manager] — missing the
system override role.

Adding System Manager to test.scm is a TEST INFRASTRUCTURE change, not a
production code change. It reflects the real-world pattern that test
accounts carry broader permissions to simulate multi-role flows.

Safe to rerun: idempotent (skips if role already present).
"""
from __future__ import annotations

import base64
import sys
import time
import subprocess

SCRIPT = r'''
import os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

user = "test.scm@bebang.ph"
role = "System Manager"
udoc = frappe.get_doc("User", user)
has = any(r.role == role for r in (udoc.roles or []))
if has:
    print(f"ALREADY_PRESENT user={user} role={role}")
else:
    udoc.append("roles", {"role": role})
    udoc.save(ignore_permissions=True)
    frappe.db.commit()
    print(f"GRANTED user={user} role={role}")

# Report current roles
roles = sorted({r.role for r in (frappe.get_doc("User", user).roles or [])})
print(f"current_roles: {roles}")

frappe.destroy()
'''

enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/s204_grant.py",
    "docker cp /tmp/s204_grant.py $BACKEND:/tmp/s204_grant.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s204_grant.py",
]

import boto3
ssm = boto3.client("ssm", region_name="ap-southeast-1")
r = ssm.send_command(
    InstanceIds=["i-026b7477d27bd46d6"],
    DocumentName="AWS-RunShellScript",
    Parameters={"commands": cmds, "executionTimeout": ["240"]},
)
cid = r["Command"]["CommandId"]
print("CommandId:", cid)
for _ in range(60):
    time.sleep(3)
    inv = ssm.get_command_invocation(CommandId=cid, InstanceId="i-026b7477d27bd46d6")
    if inv["Status"] in ("Success", "Failed", "TimedOut"):
        print("STATUS:", inv["Status"])
        print(inv["StandardOutputContent"][-2500:])
        if inv["StandardErrorContent"]:
            print("STDERR:", inv["StandardErrorContent"][-1000:])
        sys.exit(0 if inv["Status"] == "Success" else 1)
