#!/usr/bin/env python3
"""S212 defect probe — read Frappe Error Log for the sweep window."""
from __future__ import annotations
import base64
import gzip
import json
import pathlib
import subprocess
import sys
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "output" / "l3" / "s212" / "frappe_error_log_probe.json"
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

# Errors in the sweep window (2026-04-21 08:00 to now)
errors = frappe.db.sql("""
    SELECT name, creation, method, error
    FROM `tabError Log`
    WHERE creation >= '2026-04-21 08:00:00'
      AND (method LIKE '%dispatch%' OR method LIKE '%fulfill%' OR method LIKE '%stock%'
           OR method LIKE '%warehouse%' OR method LIKE '%commissary%' OR method LIKE '%store%'
           OR method LIKE '%MR%' OR method LIKE '%Material%' OR error LIKE '%MAT-MR-2026-00258%'
           OR error LIKE '%MAT-MR-2026-00260%' OR error LIKE '%MAT-MR-2026-00262%'
           OR error LIKE '%dispatch%' OR error LIKE '%Stock Entry%')
    ORDER BY creation DESC LIMIT 50
""", as_dict=True)

# Also pull generic errors in window (first 20)
generic = frappe.db.sql("""
    SELECT name, creation, method, LEFT(error, 500) as error_head
    FROM `tabError Log`
    WHERE creation >= '2026-04-21 08:00:00'
    ORDER BY creation DESC LIMIT 20
""", as_dict=True)

payload = {"scoped_errors": errors, "all_errors_window": generic}
compressed = gzip.compress(json.dumps(payload, default=str).encode())
print("__ERR_B64_START__")
print(base64.b64encode(compressed).decode())
print("__ERR_B64_END__")
frappe.destroy()
'''


def run_in_container(python_script: str, timeout: int = 120) -> str:
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(python_script.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s212_err.py",
        "docker cp /tmp/s212_err.py $BACKEND:/tmp/s212_err.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s212_err.py",
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
                sys.stderr.write(err)
                raise RuntimeError(f"SSM failed: {inv['Status']}")
            return out
    raise TimeoutError("SSM timeout")


def main() -> int:
    out = run_in_container(SCRIPT)
    s = out.find("__ERR_B64_START__")
    e = out.find("__ERR_B64_END__")
    b64 = out[s + len("__ERR_B64_START__"):e].strip()
    data = json.loads(gzip.decompress(base64.b64decode(b64)).decode())
    OUT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    scoped = data.get("scoped_errors", [])
    generic = data.get("all_errors_window", [])
    print(f"[S212] scoped errors: {len(scoped)}")
    print(f"[S212] all errors in window: {len(generic)}")
    for err in scoped[:5]:
        print(f"  - {err.get('creation')} | {err.get('method')} | {(err.get('error') or '')[:200]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
