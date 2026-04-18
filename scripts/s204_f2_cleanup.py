"""S204 F2 cleanup: remove the S204-F2-TEST-NULL-CO warehouse.

Run after F2 test completes (or out-of-band to wipe stale state).
Idempotent: no-op if the warehouse is already absent.
"""
from __future__ import annotations
import base64
import sys
import time

# Frappe auto-appends a company abbreviation when Warehouse.company is set
# at insert time (we seed with BEBANG ENTERPRISE INC. → suffix " - BEI"),
# even though we NULL the company field immediately after. The docname stays
# as the suffixed form, so cleanup must target that.
WH_NAME = "S204-F2-TEST-NULL-CO - BEI"

SCRIPT = rf'''
import os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

wh_name = "{WH_NAME}"
if not frappe.db.exists("Warehouse", wh_name):
    print(f"NO_OP: {{wh_name}} does not exist")
    frappe.destroy()
    raise SystemExit(0)

# Clean any linked Bin + SLE rows before delete
try:
    frappe.db.sql("DELETE FROM `tabBin` WHERE warehouse = %s", (wh_name,))
    frappe.db.sql("DELETE FROM `tabStock Ledger Entry` WHERE warehouse = %s", (wh_name,))
    frappe.db.commit()
except Exception as e:
    print(f"Bin/SLE cleanup WARN: {{type(e).__name__}}: {{e}}")

# Orders created against this test warehouse shouldn't exist (F2 asserts zero),
# but if they do (e.g., a prior pass leaked), let's report rather than delete.
leftover = frappe.db.sql(
    "SELECT name, docstatus, owner FROM `tabBEI Store Order` WHERE store = %s ORDER BY creation DESC LIMIT 20",
    (wh_name,),
    as_dict=True,
)
if leftover:
    print(f"WARN: {{len(leftover)}} leftover BEI Store Orders against {{wh_name}}:")
    for row in leftover:
        print(f"  {{row['name']}} docstatus={{row['docstatus']}} owner={{row['owner']}}")

try:
    frappe.delete_doc("Warehouse", wh_name, force=1, ignore_permissions=True)
    frappe.db.commit()
    print(f"DELETED: {{wh_name}}")
except Exception as e:
    import traceback
    print(f"DELETE FAILED: {{type(e).__name__}}: {{e}}")
    traceback.print_exc()
    frappe.destroy()
    raise SystemExit(1)

frappe.destroy()
'''

enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/s204_f2_cleanup.py",
    "docker cp /tmp/s204_f2_cleanup.py $BACKEND:/tmp/s204_f2_cleanup.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s204_f2_cleanup.py",
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
        print(inv["StandardOutputContent"][-2500:])
        if inv["StandardErrorContent"]:
            print("STDERR:", inv["StandardErrorContent"][-800:])
        sys.exit(0 if inv["Status"] == "Success" else 1)
