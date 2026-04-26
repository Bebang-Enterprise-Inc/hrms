#!/usr/bin/env python3
"""S223 diagnostic - inspect state of MRs created by Pattern A probe."""
from __future__ import annotations
import base64
import gzip
import json
import pathlib
import subprocess
import sys
import time

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"
OUT = pathlib.Path(__file__).resolve().parent.parent / "output" / "s223" / "verification" / "mr_state_diag.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

SCRIPT = '''
import json
import frappe

frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()

# The MRs from the Pattern A probe
TARGET_MRS = ["MAT-MR-2026-00436", "MAT-MR-2026-00437"]

result = {}
for mr_name in TARGET_MRS:
    if not frappe.db.exists("Material Request", mr_name):
        result[mr_name] = {"exists": False}
        continue
    mr = frappe.get_doc("Material Request", mr_name)
    result[mr_name] = {
        "exists": True,
        "docstatus": mr.docstatus,
        "status": mr.status,
        "per_ordered": getattr(mr, "per_ordered", None),
        "per_received": getattr(mr, "per_received", None),
        "material_request_type": mr.material_request_type,
        "set_warehouse": mr.set_warehouse,
        "company": mr.company,
        "custom_store_order": getattr(mr, "custom_store_order", None),
        "transaction_date": str(mr.transaction_date),
        "modified": str(mr.modified),
        "all_fields": {k: str(v)[:80] for k, v in mr.as_dict().items() if not k.startswith("_") and k not in ("items", "doctype")},
    }

# Also show ALL recent MRs to understand the population
recent_mrs = frappe.db.sql("""
    SELECT name, docstatus, status, set_warehouse, custom_store_order, material_request_type
    FROM `tabMaterial Request`
    WHERE creation > DATE_SUB(NOW(), INTERVAL 1 HOUR)
    ORDER BY creation DESC
    LIMIT 20
""", as_dict=True)
result["recent_mrs"] = recent_mrs

import gzip as _gz, base64 as _b64
compressed = _gz.compress(json.dumps(result, default=str).encode())
print("__B64_START__")
print(_b64.b64encode(compressed).decode())
print("__B64_END__")
frappe.destroy()
'''


def run(timeout: int = 120) -> str:
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(SCRIPT.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s223diag.py",
        "docker cp /tmp/s223diag.py $BACKEND:/tmp/s223diag.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s223diag.py",
    ]
    r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
                         Parameters={"commands": cmds, "executionTimeout": [str(timeout)]})
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}", flush=True)
    deadline = time.time() + timeout + 30
    while time.time() < deadline:
        time.sleep(8)
        try:
            inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        except ssm.exceptions.InvocationDoesNotExist:
            continue
        if inv["Status"] in ("Success", "Failed", "TimedOut", "Cancelled"):
            out = inv.get("StandardOutputContent", "")
            if inv["Status"] != "Success":
                sys.stderr.write(inv.get("StandardErrorContent", "") + "\n")
            return out
    raise TimeoutError()


def main() -> int:
    out = run()
    s = out.find("__B64_START__")
    e = out.find("__B64_END__")
    if s < 0 or e < 0:
        sys.stderr.write(out[:3000] + "\n")
        return 1
    b64 = out[s + len("__B64_START__"):e].strip()
    data = json.loads(gzip.decompress(base64.b64decode(b64)).decode())
    OUT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print(f"Wrote: {OUT}\n")
    for mr_name in ("MAT-MR-2026-00436", "MAT-MR-2026-00437"):
        d = data.get(mr_name, {})
        print(f"=== {mr_name} ===")
        for k, v in d.items():
            print(f"  {k}: {v}")
        print()
    print("=== Recent MRs (last hour) ===")
    for r in data.get("recent_mrs", [])[:10]:
        print(f"  {r['name']}: docstatus={r['docstatus']}, status={r['status']}, warehouse={r['set_warehouse']}, type={r['material_request_type']}, store_order={r['custom_store_order']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
