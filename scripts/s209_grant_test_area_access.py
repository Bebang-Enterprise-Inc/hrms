#!/usr/bin/env python3
"""S209 P3-T1: grant test.area@bebang.ph access to all 49 canonical warehouses.

For each canonical per-store Warehouse the script:
  1. Captures the pre-sweep value of `custom_area_supervisor` to
     `output/l3/s209/area_access_snapshot.json`.
  2. Sets `custom_area_supervisor = test.area@bebang.ph`.

Idempotent: a warehouse already set to `test.area@bebang.ph` is left alone and
recorded with its prior-saved snapshot (if any). Use `--warehouse <name>` to
limit to a single warehouse for debugging.

Phase 6 revert: `scripts/s209_revert_test_area_access.py` reads the snapshot
and restores each warehouse's captured value (blank if there was no prior
assignment).

Canonical safety: reads tabWarehouse only where the warehouse `company` is a
per-store Company (entity_category='Store'). Does NOT touch parent-Company
warehouses, sub-warehouses (FINISHED GOODS / STORES / GOODS IN TRANSIT / WORK
IN PROGRESS), or non-canonical test warehouses.
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
TEST_SUPERVISOR = "test.area@bebang.ph"


def _build_script(target_supervisor: str, only_warehouse: str | None) -> str:
    only_literal = "None" if not only_warehouse else f'"{only_warehouse}"'
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

target = "{target_supervisor}"
only = {only_literal}

# Canonical per-store warehouses (exact-name match with per-store Company)
filter_single = "AND w.name = %(only)s" if only else ""
rows = frappe.db.sql(f"""
    SELECT w.name, IFNULL(w.custom_area_supervisor, \\'\\') AS current_value
    FROM `tabWarehouse` w
    WHERE w.company IN (
        SELECT name FROM `tabCompany`
        WHERE entity_category = \\'Store\\'
          AND (operational_status IS NULL OR operational_status NOT IN (\\'Permanently Closed\\', \\'Dormant\\'))
    )
      AND w.disabled = 0
      AND w.is_group = 0
      AND w.warehouse_name NOT IN (\\'FINISHED GOODS\\', \\'GOODS IN TRANSIT\\', \\'STORES\\', \\'WORK IN PROGRESS\\')
      AND w.name = w.company  -- canonical exact-name match
      {{filter_single}}
    ORDER BY w.name
""".format(filter_single=filter_single), {{"only": only}}, as_dict=True)

snapshot = []
mutated = 0
for r in rows:
    prior = r["current_value"] or ""
    snapshot.append({{"name": r["name"], "prior_value": prior}})
    if prior != target:
        frappe.db.sql(
            "UPDATE `tabWarehouse` SET custom_area_supervisor = %(s)s, modified = NOW() WHERE name = %(n)s",
            {{"s": target, "n": r["name"]}},
        )
        mutated += 1

frappe.db.commit()

payload = {{"snapshot": snapshot, "target": target, "mutated": mutated, "total": len(rows)}}
blob = gzip.compress(json.dumps(payload).encode())
print("__S209_GRANT_START__")
print(base64.b64encode(blob).decode())
print("__S209_GRANT_END__")

frappe.destroy()
'''


def run_in_container(python_script: str, timeout: int = 180) -> str:
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(python_script.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s209_grant.py",
        "docker cp /tmp/s209_grant.py $BACKEND:/tmp/s209_grant.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s209_grant.py",
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
    s = stdout.find("__S209_GRANT_START__")
    e = stdout.find("__S209_GRANT_END__")
    if s < 0 or e < 0:
        raise RuntimeError("Could not find grant markers in SSM output")
    blob_b64 = stdout[s + len("__S209_GRANT_START__"):e].strip()
    return json.loads(gzip.decompress(base64.b64decode(blob_b64)).decode())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--warehouse", help="Only touch this warehouse (debug)")
    ap.add_argument("--supervisor", default=TEST_SUPERVISOR, help="Supervisor to grant")
    args = ap.parse_args()

    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Load existing snapshot (idempotent re-run) — preserve earliest captured prior value
    existing_snap: list[dict] = []
    if SNAPSHOT_PATH.exists():
        try:
            existing_snap = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        except Exception:
            existing_snap = []
    by_name = {e["name"]: e for e in existing_snap}

    print(f"[S209] Granting {args.supervisor} on canonical warehouses...")
    out = run_in_container(_build_script(args.supervisor, args.warehouse))
    payload = extract_payload(out)

    # Merge with prior snapshot: prior_value for each warehouse should be the
    # value at the FIRST grant invocation. If a warehouse is already in snapshot,
    # keep the existing prior_value (it's already been sbstituted by this script).
    merged_snap: list[dict] = []
    for row in payload["snapshot"]:
        if row["name"] in by_name:
            merged_snap.append(by_name[row["name"]])
        else:
            merged_snap.append(row)

    SNAPSHOT_PATH.write_text(json.dumps(merged_snap, indent=2), encoding="utf-8")

    with ACCESS_LOG.open("a", encoding="utf-8") as f:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        f.write(
            f"[{ts}] GRANT target={args.supervisor} total={payload['total']} "
            f"mutated={payload['mutated']}\n"
        )

    print(
        f"[S209] total={payload['total']} mutated={payload['mutated']} "
        f"already_set={payload['total'] - payload['mutated']} "
        f"snapshot={SNAPSHOT_PATH}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
