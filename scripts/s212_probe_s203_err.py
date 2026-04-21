#!/usr/bin/env python3
"""Pull full S203 Draft SI Error traceback + recent dispatch-related errors."""
from __future__ import annotations
import base64
import gzip
import json
import pathlib
import subprocess
import sys
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "output" / "l3" / "s212" / "s203_err_full.json"
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

# Full error text (not LEFT truncated)
errs = frappe.db.sql("""
    SELECT name, creation, method, error
    FROM `tabError Log`
    WHERE creation >= '2026-04-21 08:00:00'
      AND (method LIKE '%S203%' OR method LIKE '%dispatch%' OR error LIKE '%S203%'
           OR method LIKE '%Stock Entry%' OR error LIKE '%build_bki_store_sale_invoice%'
           OR error LIKE '%fulfill_store_order%' OR error LIKE '%create_dispatch_transfer%')
    ORDER BY creation DESC LIMIT 20
""", as_dict=True)

# Also pull SE MAT-STE-2026-00621 specifically
se_info = frappe.db.sql("""
    SELECT se.name, se.docstatus, se.custom_sales_invoice_draft,
           se.creation, se.stock_entry_type, sei.item_code, sei.qty, sei.s_warehouse, sei.t_warehouse, sei.material_request
    FROM `tabStock Entry` se
    LEFT JOIN `tabStock Entry Detail` sei ON sei.parent = se.name
    WHERE se.name = 'MAT-STE-2026-00621'
""", as_dict=True)

payload = {"errors": errs, "se_00621": se_info}
compressed = gzip.compress(json.dumps(payload, default=str).encode())
print("__S203_B64_START__")
print(base64.b64encode(compressed).decode())
print("__S203_B64_END__")
frappe.destroy()
'''


def run_in_container(python_script: str, timeout: int = 120) -> str:
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(python_script.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s212_s203.py",
        "docker cp /tmp/s212_s203.py $BACKEND:/tmp/s212_s203.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s212_s203.py",
    ]
    r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": [str(timeout)]})
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
                raise RuntimeError(f"SSM {inv['Status']}")
            return out
    raise TimeoutError()


def main() -> int:
    out = run_in_container(SCRIPT)
    s = out.find("__S203_B64_START__")
    e = out.find("__S203_B64_END__")
    b64 = out[s + len("__S203_B64_START__"):e].strip()
    data = json.loads(gzip.decompress(base64.b64decode(b64)).decode())
    OUT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print(f"Errors found: {len(data['errors'])}")
    print(f"SE 00621 rows: {len(data['se_00621'])}")
    for err in data["errors"]:
        print(f"\n=== {err['creation']} | {err['method']} ===")
        print(err['error'][:3000])
    print("\n=== SE MAT-STE-2026-00621 ===")
    for row in data["se_00621"]:
        print(json.dumps(row, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
