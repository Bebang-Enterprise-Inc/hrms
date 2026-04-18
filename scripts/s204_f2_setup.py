"""S204 F2 setup: Create a test Warehouse with company=NULL for F2 scenario.

F2 tests that order submission against a warehouse without a Company stamped
raises "Store warehouse ... has no Company set" (S190 guard).

Prints the warehouse docname to stdout on the last non-empty line.
Cleanup: scripts/s204_f2_cleanup.py
"""
import base64, sys, time

WH_NAME = "S204-F2-TEST - <co>"  # placeholder — BEI Warehouse won't accept; we use empty suffix
WH_REAL = "S204-F2-TEST-WAREHOUSE"

SCRIPT = rf'''
import os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

wh_name = "{WH_REAL}"
# Delete if pre-existing
if frappe.db.exists("Warehouse", wh_name):
    try:
        frappe.delete_doc("Warehouse", wh_name, force=1, ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        print(f"existing WH cleanup ERR: {{e}}")

# Need to create with a parent warehouse at the All Warehouses level, with company empty
wh = frappe.new_doc("Warehouse")
wh.warehouse_name = wh_name
wh.is_group = 0
wh.company = ""  # or try None
try:
    wh.insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"CREATED: {{wh.name}} company={{wh.company!r}}")
except Exception as e:
    print(f"CREATE ERROR: {{type(e).__name__}}: {{e}}")
    # Try with sql direct
    import traceback
    traceback.print_exc()

# Grant test.area access: add this warehouse to test.area's Area Supervisor mapping?
# Skipped — not needed; test will submit and assert ValidationError from backend.

# Print final name
if frappe.db.exists("Warehouse", wh_name):
    print(f"FINAL_NAME: {{frappe.db.get_value('Warehouse', wh_name, 'name')}}")

frappe.destroy()
'''

enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/s204_f2_setup.py",
    "docker cp /tmp/s204_f2_setup.py $BACKEND:/tmp/s204_f2_setup.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s204_f2_setup.py",
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
        print(inv["StandardOutputContent"][-2500:])
        sys.exit(0 if inv["Status"] == "Success" else 1)
