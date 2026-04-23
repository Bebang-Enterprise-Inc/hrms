#!/usr/bin/env python3
"""Probe state of FESTIVAL MALL failing order."""
import base64, json, pathlib, sys, time
AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"

SCRIPT = '''
import json, frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()

# Pull last 8 orders to find FESTIVAL MALL variant (likely BEI-ORD-2026-00408..443)
rows = frappe.db.sql("""
    SELECT * FROM `tabBEI Store Order`
    WHERE name LIKE 'BEI-ORD-2026-004%'
    ORDER BY creation DESC LIMIT 30
""", as_dict=True)
keep = ("name","store","status","approval_stage","owner","creation","modified","docstatus")
rows = [{k: r.get(k) for k in keep if k in r} | {"approval_related": {k: v for k, v in r.items() if "approv" in k.lower()}} for r in rows]
for r in rows:
    print(json.dumps(r, default=str))
frappe.destroy()
'''


def main():
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(SCRIPT.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s218_p.py",
        "docker cp /tmp/s218_p.py $BACKEND:/tmp/s218_p.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s218_p.py",
    ]
    r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": ["60"]})
    cid = r["Command"]["CommandId"]
    deadline = time.time() + 90
    while time.time() < deadline:
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut", "Cancelled"):
            print(inv.get("StandardOutputContent", ""))
            if inv.get("StandardErrorContent"): sys.stderr.write(inv.get("StandardErrorContent", ""))
            return 0 if inv["Status"] == "Success" else 1
    return 2


sys.exit(main())
