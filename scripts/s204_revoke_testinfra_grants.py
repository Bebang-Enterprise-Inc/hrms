"""S204 Phase A: revoke the four test-infra role grants.

Earlier sessions granted `System Manager` + `Accounts User` to
`test.scm@bebang.ph` and `test.supervisor@bebang.ph` as workarounds for
product defects that have since been fixed at root cause by:

- hrms#621 (admin-wraps _submit_dispatch_draft_si + _create_warehouse_receiving_for_se)
- hrms#625 (log_error positional-arg clamp)
- hrms#630 (data-driven buyer customer resolver)
- bei-tasks#418 (Warehouse Manager + SCM in MODULES.ORDER_APPROVALS)

This script removes those four grants so the re-verification proves the
L3 chain works with production-shaped permissions, not inflated test
accounts.

Safe to rerun: idempotent (skips roles already absent, keeps other roles
intact).
"""
from __future__ import annotations
import base64
import sys
import time

SCRIPT = r'''
import os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

TARGETS = [
    ("test.scm@bebang.ph",        ["System Manager", "Accounts User"]),
    ("test.supervisor@bebang.ph", ["System Manager", "Accounts User"]),
]

for user, roles_to_remove in TARGETS:
    udoc = frappe.get_doc("User", user)
    before = sorted({r.role for r in (udoc.roles or [])})
    kept = [r for r in (udoc.roles or []) if r.role not in roles_to_remove]
    if len(kept) == len(udoc.roles or []):
        print(f"NO_OP user={user} none of {roles_to_remove} present")
        print(f"  current_roles: {before}")
        print()
        continue
    udoc.set("roles", kept)
    udoc.save(ignore_permissions=True)
    frappe.db.commit()
    after = sorted({r.role for r in (frappe.get_doc("User", user).roles or [])})
    removed = sorted(set(before) - set(after))
    print(f"REVOKED user={user} removed={removed}")
    print(f"  before={before}")
    print(f"  after ={after}")
    print()

# Verify post-revoke permissions
for user in ["test.supervisor@bebang.ph", "test.scm@bebang.ph"]:
    frappe.set_user(user)
    si_submit = frappe.has_permission("Sales Invoice", "submit")
    so_write = frappe.has_permission("BEI Store Order", "write")
    frappe.set_user("Administrator")
    print(f"perm-check {user}: SI.submit={si_submit}  BEIStoreOrder.write={so_write}")

frappe.destroy()
'''

enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/s204_revoke.py",
    "docker cp /tmp/s204_revoke.py $BACKEND:/tmp/s204_revoke.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s204_revoke.py",
]

import boto3
ssm = boto3.client("ssm", region_name="ap-southeast-1")
r = ssm.send_command(
    InstanceIds=["i-026b7477d27bd46d6"],
    DocumentName="AWS-RunShellScript",
    Parameters={"commands": cmds, "executionTimeout": ["180"]},
)
cid = r["Command"]["CommandId"]
print("CommandId:", cid)
for _ in range(60):
    time.sleep(3)
    inv = ssm.get_command_invocation(CommandId=cid, InstanceId="i-026b7477d27bd46d6")
    if inv["Status"] in ("Success", "Failed", "TimedOut"):
        print("STATUS:", inv["Status"])
        print(inv["StandardOutputContent"][-3000:])
        if inv["StandardErrorContent"]:
            print("STDERR:", inv["StandardErrorContent"][-1000:])
        sys.exit(0 if inv["Status"] == "Success" else 1)
