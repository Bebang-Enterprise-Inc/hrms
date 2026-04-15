#!/usr/bin/env python3
"""Cancel/delete S192 L3 test orders created this run."""
import base64, json, time, boto3

ORDERS = [
    "BEI-ORD-2026-00248",  # S4 Ayala Evo
    "BEI-ORD-2026-00249",  # S3 attempt 1
    "BEI-ORD-2026-00250",  # S3 attempt 2
    "BEI-ORD-2026-00251",  # S3 attempt 3
    "BEI-ORD-2026-00252",  # S2 SM Megamall
    "BEI-ORD-2026-00253",  # S3 attempt 4
]

SCRIPT = f'''
import os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

orders = {ORDERS!r}
result = {{"cancelled": [], "deleted": [], "skipped": [], "errors": []}}

for name in orders:
    try:
        if not frappe.db.exists("BEI Store Order", name):
            result["skipped"].append({{"name": name, "reason": "not found"}})
            continue
        doc = frappe.get_doc("BEI Store Order", name)
        if doc.docstatus == 2:
            result["skipped"].append({{"name": name, "reason": "already cancelled"}})
            continue
        if doc.docstatus == 1:
            doc.cancel()
            frappe.db.commit()
            result["cancelled"].append(name)
        else:
            # Draft - just delete
            frappe.delete_doc("BEI Store Order", name, force=1, ignore_permissions=True)
            frappe.db.commit()
            result["deleted"].append(name)
    except Exception as e:
        result["errors"].append({{"name": name, "error": str(e)[:300]}})

import json as _j
print(_j.dumps(result, indent=2))
frappe.destroy()
'''

enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/s192_cleanup.py",
    "docker cp /tmp/s192_cleanup.py $BACKEND:/tmp/s192_cleanup.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s192_cleanup.py",
]

ssm = boto3.client("ssm", region_name="ap-southeast-1")
r = ssm.send_command(InstanceIds=["i-026b7477d27bd46d6"], DocumentName="AWS-RunShellScript",
    Parameters={"commands": cmds, "executionTimeout": ["240"]})
cid = r["Command"]["CommandId"]
print("CommandId:", cid)
for _ in range(80):
    time.sleep(3)
    inv = ssm.get_command_invocation(CommandId=cid, InstanceId="i-026b7477d27bd46d6")
    if inv["Status"] in ("Success","Failed","TimedOut"):
        print("STATUS:", inv["Status"])
        print(inv["StandardOutputContent"][:5000])
        if inv["StandardErrorContent"]:
            print("STDERR:", inv["StandardErrorContent"][-1500:])
        break
