#!/usr/bin/env python3
"""SSM-execute multi_store_smoke.py inside the Frappe backend container.

Live-fire — creates+cancels+deletes test SIs for 49 stores. All artifacts
cleaned up by the in-script finally block.

Timeout: 30 min (5-10s per store * 49 stores = ~5-8 min real, with safety margin).
"""
from __future__ import annotations

import base64
import gzip
import json
import sys
import time
from pathlib import Path

import boto3

INSTANCE_ID = "i-026b7477d27bd46d6"
REGION = "ap-southeast-1"
HERE = Path(__file__).parent
SCRIPT = HERE / "multi_store_smoke.py"
OUT = HERE / "sweep_result.json"


def main() -> int:
    ssm = boto3.client("ssm", region_name=REGION)
    encoded = base64.b64encode(SCRIPT.read_text(encoding="utf-8").encode()).decode()

    cmds = [
        "set -e",
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        'if [ -z "$BACKEND" ]; then echo "BACKEND_NOT_FOUND" && exit 1; fi',
        f"echo '{encoded}' | base64 -d > /tmp/s244_sweep.py",
        "docker cp /tmp/s244_sweep.py $BACKEND:/tmp/s244_sweep.py",
        "docker exec $BACKEND bash -lc 'cd /home/frappe/frappe-bench && env/bin/python /tmp/s244_sweep.py'",
        "docker cp $BACKEND:/tmp/s244_sweep_result.json /tmp/s244_sweep_result.json",
        "gzip -c /tmp/s244_sweep_result.json > /tmp/s244_sweep_result.json.gz",
        "echo S244_FILE_BEGIN",
        "base64 -w0 /tmp/s244_sweep_result.json.gz; echo",
        "echo S244_FILE_END",
    ]

    resp = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds},
        TimeoutSeconds=1800,
    )
    cmd_id = resp["Command"]["CommandId"]
    print(f"command_id={cmd_id}", flush=True)

    last_status = None
    while True:
        time.sleep(10)
        inv = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=INSTANCE_ID)
        status = inv["Status"]
        if status != last_status:
            print(f"  status={status}", flush=True)
            last_status = status
        if status in ("Pending", "InProgress", "Delayed"):
            continue
        break

    print(f"final_status={status}")
    out_text = inv.get("StandardOutputContent", "")
    err_text = inv.get("StandardErrorContent", "")

    if "S244_FILE_BEGIN" in out_text and "S244_FILE_END" in out_text:
        b64_body = out_text.split("S244_FILE_BEGIN")[1].split("S244_FILE_END")[0].strip()
        try:
            decoded_gz = base64.b64decode(b64_body)
            decoded = gzip.decompress(decoded_gz).decode("utf-8")
            data = json.loads(decoded)
            OUT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
            print(f"wrote {OUT} ({len(decoded)} bytes)")
            print()
            print("=== VERDICT COUNTS ===")
            for k, v in (data.get("verdict_counts") or {}).items():
                print(f"  {k}: {v}")
            print()
            print(f"remaining_in_tracker: {len(data.get('remaining_in_tracker', []))}")
            cl = data.get("cleanup_log") or []
            print(f"cleanup_log entries: {len(cl)}")
            for line in cl[:10]:
                print(f"  - {line}")
            return 0
        except Exception as e:
            print(f"PARSE_ERROR: {e}")
            return 2

    print("--- STDOUT ---")
    print(out_text)
    print("--- STDERR ---")
    print(err_text)
    return 1


if __name__ == "__main__":
    sys.exit(main())
