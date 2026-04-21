#!/usr/bin/env python3
"""S212 defect probe: for every MR in the ledger that didn't make it to WR,
read its current state + related Stock Entry state from the backend."""
from __future__ import annotations
import base64
import gzip
import json
import pathlib
import subprocess
import sys
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
LEDGER = REPO_ROOT / "output" / "l3" / "s212" / "sweep_ledger.json"
OUT = REPO_ROOT / "output" / "l3" / "s212" / "stuck_mr_probe.json"

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"


def _script(mr_names):
    return f'''
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

mr_names = {json.dumps(list(mr_names))}
results = []
for mr_name in mr_names:
    # Pull all columns so we can see actual MR state
    mr = frappe.db.sql("SELECT * FROM `tabMaterial Request` WHERE name=%s", (mr_name,), as_dict=True)
    if mr:
        # Keep just the useful ones
        allowed = ["name","docstatus","status","per_ordered","per_received","custom_store_order","set_warehouse","material_request_type","modified"]
        mr_row = {{k: mr[0].get(k) for k in allowed if k in mr[0]}}
    else:
        mr_row = None
    ses = frappe.db.sql("""SELECT se.name, se.docstatus, se.creation, sei.material_request_item, sei.qty
                          FROM `tabStock Entry` se
                          JOIN `tabStock Entry Detail` sei ON sei.parent=se.name
                          WHERE sei.material_request=%s LIMIT 20""", (mr_name,), as_dict=True)
    results.append({{"mr": mr_row, "stock_entries": ses}})

compressed = gzip.compress(json.dumps(results, default=str).encode())
print("__PROBE_B64_START__")
print(base64.b64encode(compressed).decode())
print("__PROBE_B64_END__")
frappe.destroy()
'''


def run_in_container(python_script: str, timeout: int = 120) -> str:
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(python_script.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s212_probe.py",
        "docker cp /tmp/s212_probe.py $BACKEND:/tmp/s212_probe.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s212_probe.py",
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
    entries = json.loads(LEDGER.read_text(encoding="utf-8"))
    mrs = [e["payload"]["name"] for e in entries if e.get("kind") == "mr-create"]
    wrs_by_store = {e["payload"]["store"] for e in entries if e.get("kind") == "wr-create"}
    stuck_mrs = []
    for e in entries:
        if e.get("kind") == "mr-create":
            mr_store = e["payload"]["store"]
            if mr_store not in wrs_by_store:
                stuck_mrs.append(e["payload"]["name"])
    print(f"[S212] all MRs: {len(mrs)}, stuck at dispatch: {len(stuck_mrs)}")
    print(f"[S212] stuck: {stuck_mrs}")
    if not stuck_mrs:
        return 0
    out = run_in_container(_script(stuck_mrs))
    s = out.find("__PROBE_B64_START__")
    e = out.find("__PROBE_B64_END__")
    b64 = out[s + len("__PROBE_B64_START__"):e].strip()
    data = json.loads(gzip.decompress(base64.b64decode(b64)).decode())
    OUT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print(f"[S212] wrote {OUT}")
    print()
    for row in data:
        mr = row.get("mr")
        ses = row.get("stock_entries") or []
        print(f"  MR={mr['name'] if mr else '?'} status={mr['status'] if mr else '?'} docstatus={mr['docstatus'] if mr else '?'} per_transferred={mr['per_transferred'] if mr else '?'}")
        print(f"     linked SEs: {len(ses)}")
        for se in ses:
            print(f"       SE={se['name']} docstatus={se['docstatus']} qty={se.get('qty')} created={se.get('creation')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
