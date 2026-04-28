"""S225 LESSON F verify — Stock Settings allow_negative_stock both reverted to 0.

Phase 3 temporarily toggled allow_negative_stock + allow_negative_stock_for_batch
to 1 to permit Material Transfer through batches with backfill-era negative state.
At closeout, both MUST be 0.

Run from worktree:
    python scripts/s225_verify_stock_settings_reverted.py
"""
from __future__ import annotations
import base64
import json
import sys
import time

INSTANCE_ID = "i-026b7477d27bd46d6"

INNER = """
import os, json
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

result = {
    "allow_negative_stock": frappe.db.get_single_value("Stock Settings", "allow_negative_stock"),
    "allow_negative_stock_for_batch": frappe.db.get_single_value("Stock Settings", "allow_negative_stock_for_batch"),
}
print(json.dumps(result, default=str))
"""


def main() -> int:
    import boto3
    enc = base64.b64encode(INNER.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s225_verify_stock.py",
        "docker cp /tmp/s225_verify_stock.py $BACKEND:/tmp/s225_verify_stock.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s225_verify_stock.py",
    ]
    ssm = boto3.client("ssm", region_name="ap-southeast-1")
    r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
                         Parameters={"commands": cmds, "executionTimeout": ["90"]})
    cid = r["Command"]["CommandId"]
    inv = None
    for _ in range(30):
        time.sleep(2)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut"):
            break

    out = inv.get("StandardOutputContent", "").strip()
    err = inv.get("StandardErrorContent", "").strip()
    print(out)
    if err:
        print("STDERR:", err[:500])

    # Find the JSON line
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            data = json.loads(line)
            both_zero = (
                int(data.get("allow_negative_stock") or 0) == 0
                and int(data.get("allow_negative_stock_for_batch") or 0) == 0
            )
            print(f"\nBoth flags reverted to 0: {both_zero}")
            return 0 if both_zero else 1
    print("\nFAIL: no JSON line found in output")
    return 2


if __name__ == "__main__":
    sys.exit(main())
