"""S204: Get the full latest S203 Submit SI error trace."""
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

errs = frappe.db.sql("""SELECT name,method,creation,error FROM `tabError Log` WHERE method LIKE '%S203%Submit%' OR method LIKE '%S203 Submit%' ORDER BY creation DESC LIMIT 3""", as_dict=True)
for e in errs[:2]:
    print(f"=== [{e['creation']}] {e['method']} ===")
    print(e['error'])
    print("---")

frappe.destroy()
'''
enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/s204_lse.py",
    "docker cp /tmp/s204_lse.py $BACKEND:/tmp/s204_lse.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s204_lse.py",
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
        print(inv["StandardOutputContent"][:8000])
        sys.exit(0)
