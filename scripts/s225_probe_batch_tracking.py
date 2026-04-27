"""S225 Phase 4 task 0 — probe Item.has_batch_no (audit W-1).

The Bin-only FOR UPDATE lock is sufficient for non-batch items because Bin's actual_qty
is the serialized authority. For batch-tracked items (has_batch_no=1), batch allocation
reads from tabBatch which the Bin lock does NOT cover — concurrent dispatches could pass
the Bin check but race on the SABB allocation in se.submit().

Scope:
  - FG004 (canonical Pattern A failure item per Sentry root-cause writeup)
  - All items present in BACKFILL-20260421-FG004-* batches
  - All items in duplicate warehouses' Bin (Phase 2 audit list)

Run from worktree:
    python scripts/s225_probe_batch_tracking.py

Output:
    output/s225/verification/batch_tracking_probe.json
"""
from __future__ import annotations
import base64
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "s225" / "verification" / "batch_tracking_probe.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

INSTANCE_ID = "i-026b7477d27bd46d6"

INNER = r'''
import os, json
for d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/private/files",
]:
    os.makedirs(d, exist_ok=True)

import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# Pattern A canonical item + items in BACKFILL FG004 batches
direct_items = ["FG004"]
backfill_items = [r["item_code"] for r in frappe.db.sql("""
    SELECT DISTINCT item_code
    FROM `tabStock Ledger Entry`
    WHERE batch_no LIKE 'BACKFILL%FG004%'
""", as_dict=True)]

# All distinct items active in any non-disabled, non-group warehouse with non-zero stock
# (safe upper bound on what create_stock_transfer might touch under Pattern A)
items_in_active_warehouses = [r["item_code"] for r in frappe.db.sql("""
    SELECT DISTINCT b.item_code
    FROM `tabBin` b
    JOIN `tabWarehouse` w ON w.name = b.warehouse
    WHERE w.disabled = 0 AND w.is_group = 0 AND b.actual_qty > 0
""", as_dict=True)]

union = sorted({*direct_items, *backfill_items, *items_in_active_warehouses})

batch_info = {}
for ic in union:
    row = frappe.db.get_value("Item", ic, ["name", "item_name", "has_batch_no", "has_serial_no"], as_dict=True)
    if row:
        batch_info[ic] = {
            "item_name": row.get("item_name"),
            "has_batch_no": int(row.get("has_batch_no") or 0),
            "has_serial_no": int(row.get("has_serial_no") or 0),
        }

batch_tracked = [ic for ic, info in batch_info.items() if info["has_batch_no"] == 1]
non_batch = [ic for ic, info in batch_info.items() if info["has_batch_no"] == 0]

print(json.dumps({
    "direct_pattern_a_items": direct_items,
    "backfill_items_resolved": backfill_items,
    "items_in_active_warehouses_count": len(items_in_active_warehouses),
    "total_unique_items_probed": len(union),
    "batch_info": batch_info,
    "batch_tracked_items": batch_tracked,
    "non_batch_items": non_batch,
    "must_lock_tabBatch": len(batch_tracked) > 0,
}))
'''


def main() -> int:
    import boto3
    enc = base64.b64encode(INNER.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s225_probe_batch.py",
        "docker cp /tmp/s225_probe_batch.py $BACKEND:/tmp/s225_probe_batch.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s225_probe_batch.py",
    ]
    ssm = boto3.client("ssm", region_name="ap-southeast-1")
    r = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": ["180"]},
    )
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}", flush=True)
    inv = None
    for _ in range(60):
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut"):
            break
    if inv is None:
        print("SSM did not complete", flush=True)
        return 2

    stdout = inv.get("StandardOutputContent", "")
    inner_result = None
    for line in stdout.splitlines()[::-1]:
        s = line.strip()
        if s.startswith("{") and s.endswith("}"):
            try:
                inner_result = json.loads(s)
                break
            except json.JSONDecodeError:
                continue
    if not inner_result:
        print(f"FAIL: no JSON. stderr={inv.get('StandardErrorContent','')[:1000]}", flush=True)
        return 1

    inner_result["checked_at_local"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    OUT.write_text(json.dumps(inner_result, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}", flush=True)
    print(f"Total items probed: {inner_result['total_unique_items_probed']}", flush=True)
    print(f"Batch-tracked: {len(inner_result['batch_tracked_items'])} -> must_lock_tabBatch={inner_result['must_lock_tabBatch']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
