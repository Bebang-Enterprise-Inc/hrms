#!/usr/bin/env python3
"""S209 P3-T2: revert `custom_area_supervisor` for every warehouse captured
in `output/l3/s209/area_access_snapshot.json`.

Reads the snapshot produced by `s209_grant_test_area_access.py` and restores
each warehouse to its pre-sweep value (blank if there was no prior assignment).
Idempotent — warehouses already matching the snapshot value are left alone.
"""
from __future__ import annotations
import argparse
import base64
import gzip
import json
import pathlib
import sys
import time


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SNAPSHOT_PATH = REPO_ROOT / "output/l3/s209/area_access_snapshot.json"
ACCESS_LOG = REPO_ROOT / "output/l3/s209/access_changes.log"

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"


def _build_revert_script(snapshot: list[dict]) -> str:
    snap_json = json.dumps(snapshot)
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

snapshot = {snap_json}

reverted = 0
skipped = 0
errors = []
for row in snapshot:
    name = row.get("name")
    prior = (row.get("prior_value") or "") or None  # empty string -> NULL
    try:
        current = frappe.db.get_value("Warehouse", name, "custom_area_supervisor")
        current = current or None
        if current == prior:
            skipped += 1
            continue
        frappe.db.sql(
            "UPDATE `tabWarehouse` SET custom_area_supervisor = %(p)s, modified = NOW() WHERE name = %(n)s",
            {{"p": prior, "n": name}},
        )
        reverted += 1
    except Exception as e:
        errors.append({{"name": name, "error": str(e)}})

frappe.db.commit()

payload = {{"reverted": reverted, "skipped": skipped, "errors": errors, "total": len(snapshot)}}
blob = gzip.compress(json.dumps(payload).encode())
print("__S209_REVERT_START__")
print(base64.b64encode(blob).decode())
print("__S209_REVERT_END__")

frappe.destroy()
'''


def run_in_container(python_script: str, timeout: int = 180) -> str:
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(python_script.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s209_revert.py",
        "docker cp /tmp/s209_revert.py $BACKEND:/tmp/s209_revert.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s209_revert.py",
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


def extract_payload(stdout: str) -> dict:
    s = stdout.find("__S209_REVERT_START__")
    e = stdout.find("__S209_REVERT_END__")
    if s < 0 or e < 0:
        raise RuntimeError("Could not find revert markers in SSM output")
    return json.loads(gzip.decompress(
        base64.b64decode(stdout[s + len("__S209_REVERT_START__"):e].strip())
    ).decode())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default=str(SNAPSHOT_PATH))
    args = ap.parse_args()

    snap_path = pathlib.Path(args.snapshot)
    if not snap_path.exists():
        sys.stderr.write(f"[ERROR] snapshot {snap_path} not found\n")
        return 1

    snapshot = json.loads(snap_path.read_text(encoding="utf-8"))
    if not snapshot:
        print("[S209] snapshot empty — nothing to revert")
        return 0

    print(f"[S209] Reverting {len(snapshot)} warehouses from snapshot...")
    out = run_in_container(_build_revert_script(snapshot))
    payload = extract_payload(out)

    with ACCESS_LOG.open("a", encoding="utf-8") as f:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        f.write(
            f"[{ts}] REVERT total={payload['total']} reverted={payload['reverted']} "
            f"skipped={payload['skipped']} errors={len(payload['errors'])}\n"
        )

    print(
        f"[S209] reverted={payload['reverted']} skipped={payload['skipped']} "
        f"errors={len(payload['errors'])}"
    )
    if payload["errors"]:
        for err in payload["errors"][:10]:
            sys.stderr.write(f"  [error] {err['name']}: {err['error']}\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
