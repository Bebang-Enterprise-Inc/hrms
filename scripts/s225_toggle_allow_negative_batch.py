"""S225 Phase 3 — toggle Stock Settings.allow_negative_stock for batch.

Frappe v15 SABB validation rejects Material Transfer when an auto-allocated
batch goes negative. This is a guard, not a real shortage — the warehouse
Bin total is positive, but the specific batch ERPNext picked for allocation
is empty.

For the S225 consolidation, we need to migrate ALL stock out of the duplicate
warehouse. Whatever batch ERPNext picks may be empty (BACKFILL batches were
written to the wrong warehouse historically). Enabling Allow Negative Stock
for Batch temporarily lets the SE submit; after migration the duplicate Bin
is 0 anyway and gets disabled, so no real-world negative stock results.

Run from worktree:
    python scripts/s225_toggle_allow_negative_batch.py --enable
    python scripts/s225_toggle_allow_negative_batch.py --disable
"""
from __future__ import annotations
import argparse
import base64
import json
import sys
import time


INSTANCE_ID = "i-026b7477d27bd46d6"


def _build(enable: bool) -> str:
    val = "1" if enable else "0"
    return f'''
import os, json
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/private/files"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# Discover relevant fields on Stock Settings
meta = frappe.get_meta("Stock Settings")
fields_of_interest = [f.fieldname for f in meta.fields if "negative" in f.fieldname.lower() or "batch" in f.fieldname.lower()]
before = {{}}
for f in fields_of_interest:
    before[f] = frappe.db.get_single_value("Stock Settings", f)

# Set both global allow_negative_stock and the batch-specific variant if present
desired = int({val})
to_set = []
for fname in ["allow_negative_stock", "allow_negative_stock_for_batch"]:
    if meta.has_field(fname):
        frappe.db.set_single_value("Stock Settings", fname, desired)
        to_set.append(fname)

frappe.db.commit()

after = {{}}
for f in fields_of_interest:
    after[f] = frappe.db.get_single_value("Stock Settings", f)

print(json.dumps({{"before": before, "after": after, "set_fields": to_set, "desired": desired}}, default=str))
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--enable", action="store_true")
    grp.add_argument("--disable", action="store_true")
    args = ap.parse_args()
    enable = args.enable

    import boto3
    inner = _build(enable)
    enc = base64.b64encode(inner.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s225_toggle.py",
        "docker cp /tmp/s225_toggle.py $BACKEND:/tmp/s225_toggle.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s225_toggle.py",
    ]
    ssm = boto3.client("ssm", region_name="ap-southeast-1")
    r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
                         Parameters={"commands": cmds, "executionTimeout": ["60"]})
    cid = r["Command"]["CommandId"]
    inv = None
    for _ in range(20):
        time.sleep(2)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut"):
            break
    print(inv.get("StandardOutputContent", ""))
    if inv["Status"] != "Success":
        print(f"FAIL: {inv.get('StandardErrorContent', '')[:1500]}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
