#!/usr/bin/env python3
"""Call get_orderable_items directly from inside the frappe_backend container."""
import base64, time, boto3

TEST = r'''
import os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()

for store in [
    "SM Tanza - BEI",
    "Bebang Enterprise Inc. - SM Megamall - BEI-SMG",
    "The Grid - Rockwell - BEI",
]:
    try:
        from hrms.api.store import get_orderable_items
        result = get_orderable_items(store=store)
        items = result.get("items", result.get("data", {}).get("items", []))
        total = len(items) if items else 0
        with_sug = sum(1 for i in items if i.get("suggested_qty", 0) > 0) if items else 0
        samples = [{"code": i.get("item_code"), "suggested": i.get("suggested_qty"), "source_wh": i.get("source_warehouse")} for i in (items or [])[:3]]
        print(f"STORE={store} total={total} withSug={with_sug}")
        for s in samples:
            print("  ", s)
    except Exception as e:
        import traceback
        print(f"STORE={store} EXC {type(e).__name__}: {str(e)[:200]}")
        traceback.print_exc()
frappe.destroy()
'''
enc = base64.b64encode(TEST.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/s192_test_or.py",
    "docker cp /tmp/s192_test_or.py $BACKEND:/tmp/s192_test_or.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s192_test_or.py",
]
ssm = boto3.client("ssm", region_name="ap-southeast-1")
r = ssm.send_command(InstanceIds=["i-026b7477d27bd46d6"], DocumentName="AWS-RunShellScript",
    Parameters={"commands": cmds, "executionTimeout": ["120"]})
cid = r["Command"]["CommandId"]
print("CommandId:", cid)
for _ in range(40):
    time.sleep(3)
    inv = ssm.get_command_invocation(CommandId=cid, InstanceId="i-026b7477d27bd46d6")
    if inv["Status"] in ("Success","Failed","TimedOut"):
        print("STATUS:", inv["Status"])
        print(inv["StandardOutputContent"][:5000])
        if inv["StandardErrorContent"]:
            print("STDERR:", inv["StandardErrorContent"][-800:])
        break
