#!/usr/bin/env python3
"""S212 deploy verification — probe hq.bebang.ph for S212 patches in live code."""
from __future__ import annotations
import base64
import sys
import time

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"

CHECK = r'''
import importlib
import sys

results = {}

# DEFECT-1: frappe.db.commit() after mr.submit() in hrms/api/store.py
try:
    import hrms.api.store as store_mod
    src = open(store_mod.__file__).read()
    idx = src.find("mr.submit()")
    results["defect_1_commit"] = "frappe.db.commit()" in src[idx:idx+800]
    results["defect_1_exists_check"] = 'frappe.db.exists("Material Request"' in src
except Exception as e:
    results["defect_1_err"] = str(e)

# DEFECT-2: _reconcile_si_qty_from_wr in hrms/api/warehouse.py
try:
    import hrms.api.warehouse as wh_mod
    src = open(wh_mod.__file__).read()
    results["defect_2_helper"] = "def _reconcile_si_qty_from_wr" in src
    results["defect_2_wire"] = "_reconcile_si_qty_from_wr(si_doc, receiving_name)" in src
except Exception as e:
    results["defect_2_err"] = str(e)

print("=== DEPLOY CHECK ===")
for k, v in results.items():
    print(f"{k}: {v}")
print("=== END ===")
'''


def main() -> int:
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(CHECK.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s212_verify.py",
        "docker cp /tmp/s212_verify.py $BACKEND:/tmp/s212_verify.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python -c 'import sys; sys.path.insert(0, \"/home/frappe/frappe-bench/apps/hrms\"); exec(open(\"/tmp/s212_verify.py\").read())'",
    ]
    r = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": ["60"]},
    )
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}")
    deadline = time.time() + 90
    while time.time() < deadline:
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut", "Cancelled"):
            out = inv.get("StandardOutputContent", "")
            err = inv.get("StandardErrorContent", "")
            print(out)
            if err:
                sys.stderr.write(err)
            return 0 if inv["Status"] == "Success" else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
