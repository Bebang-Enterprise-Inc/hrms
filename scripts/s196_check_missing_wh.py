"""Quick check: does Vista Mall Taguig / The Grid / etc. actually exist in production?"""
import os, sys, time, boto3
os.environ.setdefault("AWS_REGION", "ap-southeast-1")
ssm = boto3.client("ssm", region_name=os.environ["AWS_REGION"],
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"])

script = """
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
import json
patterns = ["Vista Mall Taguig", "The Grid", "Rockwell", "Tricern", "TASTECARTEL",
            "Megaworld Paseo", "Paseo Center", "TEST-STORE-MAKATI"]
for p in patterns:
    rows = frappe.db.sql(
        "SELECT name, company, is_group, disabled FROM `tabWarehouse` WHERE name LIKE %s",
        f"%{p}%",
        as_dict=True,
    )
    print(f"Pattern {p!r}: {len(rows)} matches")
    for r in rows[:5]:
        print(f"  {r}")
frappe.destroy()
"""

import base64
enc = base64.b64encode(script.encode()).decode()
commands = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/chk.py",
    "docker cp /tmp/chk.py $BACKEND:/tmp/chk.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/chk.py",
]
resp = ssm.send_command(InstanceIds=["i-026b7477d27bd46d6"],
    DocumentName="AWS-RunShellScript",
    Parameters={"commands": commands, "executionTimeout": ["300"]})
cid = resp["Command"]["CommandId"]
for i in range(60):
    time.sleep(5)
    inv = ssm.get_command_invocation(CommandId=cid, InstanceId="i-026b7477d27bd46d6")
    if inv["Status"] not in ("Pending","InProgress","Delayed"):
        print(inv.get("StandardOutputContent", ""))
        if inv.get("StandardErrorContent"): print("ERR:", inv["StandardErrorContent"])
        sys.exit(0 if inv["Status"]=="Success" else 1)
