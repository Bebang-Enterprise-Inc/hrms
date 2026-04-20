#!/usr/bin/env python3
"""S212 Phase 0 — capture current Fiscal Year 2026 companies list.

Emits output/l3/s212/fy_2026_before.json with the structure:
    {"total_stores": N, "fy_2026_companies": [name, ...]}

Reuses the S209 SSM + gzip+base64 pattern.
"""
from __future__ import annotations
import base64
import gzip
import json
import pathlib
import subprocess
import sys
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "output" / "l3" / "s212"
OUT_DIR.mkdir(parents=True, exist_ok=True)

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"


SCRIPT = '''
import os
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass

import json, base64, gzip
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# Active per-store Companies
stores = frappe.db.sql(
    """SELECT name FROM `tabCompany`
       WHERE entity_category = 'Store'
         AND (operational_status IS NULL OR operational_status NOT IN ('Permanently Closed','Dormant'))
       ORDER BY name""",
    as_dict=True,
)

# Fiscal Year 2026 companies child rows
fy_rows = frappe.db.sql(
    """SELECT company FROM `tabFiscal Year Company`
       WHERE parent = '2026' ORDER BY company""",
    as_dict=True,
)

payload = {
    "total_stores": len(stores),
    "store_companies": [s["name"] for s in stores],
    "fy_2026_companies": [r["company"] for r in fy_rows],
}
compressed = gzip.compress(json.dumps(payload).encode())
print("__FY_B64_START__")
print(base64.b64encode(compressed).decode())
print("__FY_B64_END__")

frappe.destroy()
'''


def run_in_container(python_script: str, timeout: int = 120) -> str:
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(python_script.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s212_fy_state.py",
        "docker cp /tmp/s212_fy_state.py $BACKEND:/tmp/s212_fy_state.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s212_fy_state.py",
    ]
    r = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": [str(timeout)]},
    )
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}")
    deadline = time.time() + timeout + 30
    while time.time() < deadline:
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut", "Cancelled"):
            out = inv.get("StandardOutputContent", "")
            err = inv.get("StandardErrorContent", "")
            if inv["Status"] != "Success":
                sys.stderr.write(f"[SSM {inv['Status']}]\n{err}\n")
                raise RuntimeError(f"SSM command failed: {inv['Status']}")
            return out
    raise TimeoutError(f"SSM command {cid} did not complete")


def extract_between(haystack: str, start: str, end: str) -> str:
    s = haystack.find(start)
    e = haystack.find(end)
    if s < 0 or e < 0:
        raise RuntimeError(f"Could not find markers {start}/{end}")
    return haystack[s + len(start):e].strip()


def main() -> int:
    out = run_in_container(SCRIPT)
    b64 = extract_between(out, "__FY_B64_START__", "__FY_B64_END__")
    payload = json.loads(gzip.decompress(base64.b64decode(b64)).decode())
    dest = OUT_DIR / "fy_2026_before.json"
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[S212] Wrote {dest}")
    print(f"[S212] Store Companies: {payload['total_stores']}")
    print(f"[S212] FY 2026 Companies currently linked: {len(payload['fy_2026_companies'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
