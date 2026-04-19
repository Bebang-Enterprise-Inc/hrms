"""Compare get_orderable_items output for working store (SM TANZA) vs broken (AYALA EVO CITY)."""
import base64, sys, time

SCRIPT = r'''
import frappe, json
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("test.area@bebang.ph")

from hrms.api.store import get_orderable_items

for wh in ("SM TANZA - BEBANG MEGA INC.", "AYALA EVO CITY - BEBANG MEGA INC."):
    try:
        r = get_orderable_items(store=wh)
        items = r.get("items", []) if isinstance(r, dict) else []
        print(f"{wh!r}: {len(items)} items; sample: {[i.get('item_code') for i in items[:3]]}")
    except Exception as e:
        print(f"{wh!r}: EXCEPTION {type(e).__name__}: {e}")

# Also: is there a store-level item catalog?
# Check if resolve_warehouse does anything weird
from hrms.api.store import resolve_warehouse
for wh in ("SM TANZA - BEBANG MEGA INC.", "AYALA EVO CITY - BEBANG MEGA INC.", "AYALA EVO CITY"):
    try:
        print(f"resolve_warehouse({wh!r}) = {resolve_warehouse(wh)!r}")
    except Exception as e:
        print(f"resolve_warehouse({wh!r}) exc: {e}")

# Check _is_orderable_store
try:
    from hrms.api.store import _is_orderable_store
    print(f"_is_orderable_store(SM TANZA - BEBANG MEGA INC.): {_is_orderable_store('SM TANZA - BEBANG MEGA INC.')}")
    print(f"_is_orderable_store(AYALA EVO CITY - BEBANG MEGA INC.): {_is_orderable_store('AYALA EVO CITY - BEBANG MEGA INC.')}")
except ImportError:
    pass

frappe.destroy()
'''
enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/probe.py",
    "docker cp /tmp/probe.py $BACKEND:/tmp/probe.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/probe.py",
]
import boto3
ssm = boto3.client("ssm", region_name="ap-southeast-1")
r = ssm.send_command(InstanceIds=["i-026b7477d27bd46d6"], DocumentName="AWS-RunShellScript",
    Parameters={"commands": cmds, "executionTimeout": ["120"]})
cid = r["Command"]["CommandId"]
for _ in range(40):
    time.sleep(3)
    inv = ssm.get_command_invocation(CommandId=cid, InstanceId="i-026b7477d27bd46d6")
    if inv["Status"] in ("Success", "Failed", "TimedOut"):
        print(inv["StandardOutputContent"])
        sys.exit(0 if inv["Status"] == "Success" else 1)
