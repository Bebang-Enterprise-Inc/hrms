#!/usr/bin/env python3
"""Query recent BEI Store Orders by test.area — quick check if any submitted in last hour."""
import base64, json, time, boto3

INSTANCE_ID = "i-026b7477d27bd46d6"
REGION = "ap-southeast-1"

SCRIPT = r'''
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# Orders by test.area in last 2 hours
two_hours = frappe.utils.add_to_date(None, hours=-2)
rows = frappe.db.sql("""
    SELECT name, owner, store, company, status, docstatus, creation
    FROM `tabBEI Store Order`
    WHERE owner='test.area@bebang.ph' AND creation >= %s
    ORDER BY creation DESC LIMIT 20
""", (two_hours,), as_dict=True)

# And any MRs/SIs linked
for r in rows:
    r['creation'] = str(r['creation'])
    try:
        r['linked_mr'] = frappe.db.get_value("Material Request",
            {"custom_store_order": r['name']}, "name")
    except Exception:
        r['linked_mr'] = None
    try:
        r['linked_si'] = frappe.db.get_value("Sales Invoice",
            {"custom_bei_store_order": r['name']}, "name")
    except Exception:
        r['linked_si'] = None

print("RESULT:" + json.dumps(rows, default=str))
frappe.destroy()
'''

ssm = boto3.client("ssm", region_name=REGION)
enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/s192_check.py",
    "docker cp /tmp/s192_check.py $BACKEND:/tmp/s192_check.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s192_check.py",
]
r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
    Parameters={"commands": cmds, "executionTimeout": ["120"]})
cid = r["Command"]["CommandId"]
for _ in range(50):
    time.sleep(3)
    inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
    if inv["Status"] in ("Success","Failed","TimedOut"):
        break
print("status:", inv["Status"])
i = inv["StandardOutputContent"].find("RESULT:")
if i >= 0:
    print(json.dumps(json.loads(inv["StandardOutputContent"][i+7:].split("\n")[0]), indent=2, default=str))
else:
    print("STDERR:", inv["StandardErrorContent"][-1500:])
    print("STDOUT:", inv["StandardOutputContent"][-1500:])
