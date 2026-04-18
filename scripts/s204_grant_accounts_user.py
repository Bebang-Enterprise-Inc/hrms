"""S204: Grant Accounts User role to test.supervisor.

BEI Custom DocPerm on Sales Invoice restricts write/submit to:
- Accounts Manager (full)
- Accounts User (write + submit; no cancel)
System Manager is NOT granted SI write perm by these custom perms.

For S204 browser-only L3 testing, test.supervisor (who triggers accept-
delivery) needs to be able to submit the Draft SI as a side-effect.
Granting Accounts User gives them the minimum needed perm.

Also grants to test.scm — they may trigger SI submit via their dispatch
path in some workflows (e.g., S198 hooks).
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

role = "Accounts User"
for user in ["test.supervisor@bebang.ph", "test.scm@bebang.ph"]:
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
    print(f"  current_roles: {roles}")

# Verify perm
frappe.set_user("test.supervisor@bebang.ph")
has_submit = frappe.has_permission("Sales Invoice", "submit")
print(f"\ntest.supervisor now has Sales Invoice submit perm: {has_submit}")

frappe.destroy()
'''

enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/s204_ga.py",
    "docker cp /tmp/s204_ga.py $BACKEND:/tmp/s204_ga.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s204_ga.py",
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
    if inv["Status"] in ("Success","Failed","TimedOut"):
        print("STATUS:", inv["Status"])
        print(inv["StandardOutputContent"][-2000:])
        sys.exit(0)
