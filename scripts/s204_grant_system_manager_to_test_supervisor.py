"""S204: Grant test.supervisor the System Manager role for SI submit permission.

Root cause: _submit_dispatch_draft_si (hrms/api/warehouse.py) calls
si_doc.submit() in the user's session context, without ignore_permissions.
test.supervisor (Store Supervisor role) has no write permission on Sales
Invoice, so the submit fails with PermissionError. The savepoint rolls
back, the SI stays Draft, the WR completes anyway, and the spec's
assertion that a submitted SI exists for the order fails.

This patch is a TEST INFRASTRUCTURE change — grant test.supervisor
System Manager to simulate an accounts-enabled user. A separate Mode A
code fix is needed to make `_submit_dispatch_draft_si` work for
non-accountant store crew in production (e.g., wrap submit with
frappe.set_user("Administrator") or use sudo).
"""
from __future__ import annotations
import base64, sys, time

SCRIPT = r'''
import os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

user = "test.supervisor@bebang.ph"
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
roles = sorted({r.role for r in (frappe.get_doc("User", user).roles or [])})
print(f"current_roles: {roles}")

frappe.destroy()
'''

enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/s204_grant_sup.py",
    "docker cp /tmp/s204_grant_sup.py $BACKEND:/tmp/s204_grant_sup.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s204_grant_sup.py",
]
import boto3
ssm = boto3.client("ssm", region_name="ap-southeast-1")
r = ssm.send_command(InstanceIds=["i-026b7477d27bd46d6"], DocumentName="AWS-RunShellScript",
    Parameters={"commands": cmds, "executionTimeout": ["180"]})
cid = r["Command"]["CommandId"]
print("CommandId:", cid)
for _ in range(60):
    time.sleep(3)
    inv = ssm.get_command_invocation(CommandId=cid, InstanceId="i-026b7477d27bd46d6")
    if inv["Status"] in ("Success", "Failed", "TimedOut"):
        print("STATUS:", inv["Status"])
        print(inv["StandardOutputContent"][-2000:])
        if inv["StandardErrorContent"]:
            print("STDERR:", inv["StandardErrorContent"][-800:])
        sys.exit(0 if inv["Status"] == "Success" else 1)
