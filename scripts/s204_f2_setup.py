"""S204 F2 setup: create a test Warehouse whose company is NULL.

Purpose: F2 negative scenario asserts `hrms/api/store.py::submit_order`
throws the S190 guard message ("Store warehouse {0} has no Company set")
when the target Warehouse.company is empty.

Approach:
1. If `S204-F2-TEST-NULL-CO` exists, wipe it cleanly.
2. Re-create with a valid company + `is_group=0` + `custom_area_supervisor`
   so Frappe's mandatory-field DocType validation passes.
3. Use direct DB `frappe.db.set_value(..., update_modified=False)` to NULL
   the company field. This bypasses DocType validation while keeping all
   other fields intact.
4. Confirm `Warehouse.company IS NULL` via SQL readback.

The resulting warehouse is discoverable by `get_my_stores(test.area)` because
it has `custom_area_supervisor=test.area@bebang.ph` + `is_group=0 + disabled=0`.

Safe to rerun: fully idempotent, wipes and re-creates each time.

Cleanup: scripts/s204_f2_cleanup.py (run after F2 test completes).
"""
from __future__ import annotations
import base64
import sys
import time

WH_NAME = "S204-F2-TEST-NULL-CO"
SEED_COMPANY = "BEBANG ENTERPRISE INC."  # mandatory for DocType insert; cleared after
AREA_SUPER = "test.area@bebang.ph"

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
seed_company = "{SEED_COMPANY}"
area_supervisor = "{AREA_SUPER}"

# 1. Clean up any pre-existing instance
if frappe.db.exists("Warehouse", wh_name):
    try:
        frappe.db.sql("DELETE FROM `tabBin` WHERE warehouse = %s", (wh_name,))
        frappe.db.sql("DELETE FROM `tabStock Ledger Entry` WHERE warehouse = %s", (wh_name,))
        frappe.delete_doc("Warehouse", wh_name, force=1, ignore_permissions=True)
        frappe.db.commit()
        print(f"deleted pre-existing: {{wh_name}}")
    except Exception as e:
        print(f"cleanup ERR: {{type(e).__name__}}: {{e}}")

# 2. Insert fresh with valid company (needed to pass Warehouse DocType mandatory)
wh = frappe.new_doc("Warehouse")
wh.warehouse_name = wh_name
wh.is_group = 0
wh.disabled = 0
wh.company = seed_company
# custom_area_supervisor is the Warehouse Link → User field used by
# supervisor._get_area_supervisor_stores to surface stores for area users.
wh.custom_area_supervisor = area_supervisor
try:
    wh.insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"created: {{wh.name}} company={{wh.company!r}} area_super={{wh.custom_area_supervisor!r}}")
except Exception as e:
    import traceback
    print(f"CREATE FAILED: {{type(e).__name__}}: {{e}}")
    traceback.print_exc()
    frappe.destroy()
    raise SystemExit(1)

# 3. NULL the company via direct db set_value (bypasses DocType validation)
frappe.db.set_value("Warehouse", wh.name, "company", None, update_modified=False)
frappe.db.commit()

# 4. Verify
row = frappe.db.sql(
    "SELECT name, warehouse_name, company, is_group, disabled, custom_area_supervisor "
    "FROM `tabWarehouse` WHERE name = %s", (wh.name,), as_dict=True,
)
print(f"final_row: {{row}}")
if row and row[0].get("company"):
    print(f"WARNING: company not cleared! still={{row[0]['company']!r}}")
    frappe.destroy()
    raise SystemExit(2)

# 5. Sanity-check: the runtime `get_my_stores` endpoint (supervisor.py)
# uses `frappe.get_all(..., ignore_permissions=True by default)` so the
# warehouse should be discoverable without needing Warehouse read permission
# for test.area. `has_permission` returning False here is expected because
# Warehouse DocType permissions default-deny for non-system users — the
# get_my_stores endpoint bypasses that via get_all.
frappe.set_user(area_supervisor)
my = frappe.get_all(
    "Warehouse",
    filters={{"custom_area_supervisor": area_supervisor, "is_group": 0}},
    fields=["name", "warehouse_name", "company"],
    order_by="warehouse_name",
    ignore_permissions=True,
)
frappe.set_user("Administrator")
visible = [w for w in my if w["name"] == wh_name]
print(f"test.area store-visibility (ignore_permissions=True): {{visible}}")
if not visible:
    print("WARNING: F2 warehouse still not visible; browser test may fail at selectStore")
    # Do NOT fail here — the test itself is the source of truth.

print(f"FINAL_NAME: {{wh.name}}")
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
        print(inv["StandardOutputContent"][-3000:])
        if inv["StandardErrorContent"]:
            print("STDERR:", inv["StandardErrorContent"][-1000:])
        sys.exit(0 if inv["Status"] == "Success" else 1)
