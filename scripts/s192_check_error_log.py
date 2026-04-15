#!/usr/bin/env python3
"""Read recent Frappe error logs from the backend (last 10 min)."""
import base64, time, boto3

SCRIPT = r'''
import os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()

logs = frappe.db.sql("""SELECT name, error, creation, method FROM `tabError Log`
    WHERE creation >= (NOW() - INTERVAL 15 MINUTE)
    ORDER BY creation DESC LIMIT 8""", as_dict=True)
for l in logs:
    print("---", l.creation, l.method or "(no-method)", "---")
    print((l.error or "")[-1500:])
    print()
frappe.destroy()
'''
enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/s192_err.py",
    "docker cp /tmp/s192_err.py $BACKEND:/tmp/s192_err.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s192_err.py",
]
ssm = boto3.client("ssm", region_name="ap-southeast-1")
r = ssm.send_command(
    InstanceIds=["i-026b7477d27bd46d6"],
    DocumentName="AWS-RunShellScript",
    Parameters={"commands": cmds, "executionTimeout": ["120"]},
)
cid = r["Command"]["CommandId"]
print("CommandId:", cid)
for _ in range(50):
    time.sleep(3)
    inv = ssm.get_command_invocation(CommandId=cid, InstanceId="i-026b7477d27bd46d6")
    if inv["Status"] in ("Success", "Failed", "TimedOut"):
        print("STATUS:", inv["Status"])
        print(inv["StandardOutputContent"][:8000])
        if inv["StandardErrorContent"]:
            print("STDERR:", inv["StandardErrorContent"][-800:])
        break
