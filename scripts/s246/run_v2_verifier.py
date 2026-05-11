#!/usr/bin/env python3
"""SSM wrapper for verify_canonical_v2_probe.py.

Runs the v2 verifier inside the Frappe backend container, returns JSON via gzip+base64.
Output: output/l3/s246/verification/verify_canonical_v2_before.json
        output/l3/s246/audit/per_store_gap.csv
"""
from __future__ import annotations

import base64
import gzip
import json
import sys
import time
import csv
from pathlib import Path

import boto3

INSTANCE_ID = "i-026b7477d27bd46d6"
REGION = "ap-southeast-1"
HERE = Path(__file__).parent
SCRIPT = HERE / "verify_canonical_v2_probe.py"
JSON_OUT = Path(__file__).parent.parent.parent / "output/l3/s246/verification/verify_canonical_v2_before.json"
CSV_OUT = Path(__file__).parent.parent.parent / "output/l3/s246/audit/per_store_gap.csv"


def main() -> int:
    ssm = boto3.client("ssm", region_name=REGION)
    encoded = base64.b64encode(SCRIPT.read_text(encoding="utf-8").encode()).decode()
    cmds = [
        "set -e",
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{encoded}' | base64 -d > /tmp/s246_v2.py",
        "docker cp /tmp/s246_v2.py $BACKEND:/tmp/s246_v2.py",
        "docker exec $BACKEND bash -lc 'cd /home/frappe/frappe-bench && env/bin/python /tmp/s246_v2.py'",
        "docker cp $BACKEND:/tmp/s246_v2_verify_result.json /tmp/s246_v2_verify_result.json",
        "gzip -c /tmp/s246_v2_verify_result.json > /tmp/s246_v2_verify_result.json.gz",
        "echo S246_FILE_BEGIN",
        "base64 -w0 /tmp/s246_v2_verify_result.json.gz; echo",
        "echo S246_FILE_END",
    ]
    resp = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
                             Parameters={"commands": cmds}, TimeoutSeconds=600)
    cmd_id = resp["Command"]["CommandId"]
    print(f"command_id={cmd_id}")
    while True:
        time.sleep(5)
        inv = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Pending", "InProgress", "Delayed"):
            continue
        break
    print(f"final_status={inv['Status']}")
    out_text = inv.get("StandardOutputContent", "")
    if "S246_FILE_BEGIN" not in out_text:
        print(out_text); print(inv.get("StandardErrorContent", ""))
        return 1
    b64 = out_text.split("S246_FILE_BEGIN")[1].split("S246_FILE_END")[0].strip()
    decoded = gzip.decompress(base64.b64decode(b64)).decode("utf-8")
    data = json.loads(decoded)
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print(f"wrote {JSON_OUT}")

    # Build per-store gap CSV
    if data.get("stores"):
        # All keys across all stores
        keys = ["company"]
        for s in data["stores"]:
            for k in s.keys():
                if k not in keys:
                    keys.append(k)
        CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
        with open(CSV_OUT, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            for s in data["stores"]:
                w.writerow({k: s.get(k) for k in keys})
        print(f"wrote {CSV_OUT}")

    # Summary
    summary = data.get("summary", {})
    print()
    print("=== SUMMARY ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print()
    print("=== GLOBAL ===")
    for k, v in data.get("global", {}).items():
        if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
            print(f"  {k}: ({len(v)} items)")
            for item in v[:3]:
                print(f"    - {item}")
        else:
            print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
