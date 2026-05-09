#!/usr/bin/env python3
"""SSM-execute probe_phase0_state.py inside the Frappe backend container."""

from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

import boto3

INSTANCE_ID = "i-026b7477d27bd46d6"
REGION = "ap-southeast-1"
SCRIPT = Path(__file__).parent / "probe_phase0_state.py"
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "s243" / "verification"


def main() -> int:
    ssm = boto3.client("ssm", region_name=REGION)
    encoded = base64.b64encode(SCRIPT.read_text(encoding="utf-8").encode()).decode()

    cmds = [
        "set -e",
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        'if [ -z "$BACKEND" ]; then echo "BACKEND_NOT_FOUND" && exit 1; fi',
        f"echo '{encoded}' | base64 -d > /tmp/s243_phase0_probe.py",
        "docker cp /tmp/s243_phase0_probe.py $BACKEND:/tmp/s243_phase0_probe.py",
        "docker exec $BACKEND bash -lc 'cd /home/frappe/frappe-bench && env/bin/python /tmp/s243_phase0_probe.py'",
    ]

    resp = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds},
        TimeoutSeconds=600,
    )
    cmd_id = resp["Command"]["CommandId"]
    print(f"command_id={cmd_id}", flush=True)

    while True:
        time.sleep(4)
        inv = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=INSTANCE_ID)
        status = inv["Status"]
        if status in ("Pending", "InProgress", "Delayed"):
            print(f"  status={status}", flush=True)
            continue
        break

    print(f"final_status={status}")
    out_text = inv.get("StandardOutputContent", "")
    err_text = inv.get("StandardErrorContent", "")
    if "S243_PHASE0_BEGIN" in out_text and "S243_PHASE0_END" in out_text:
        body = out_text.split("S243_PHASE0_BEGIN")[1].split("S243_PHASE0_END")[0].strip()
        try:
            parsed = json.loads(body)
            (OUTPUT_DIR / "before_state.json").write_text(
                json.dumps(parsed, indent=2, default=str), encoding="utf-8"
            )
            print(f"WROTE: output/s243/verification/before_state.json (status={parsed.get('status')})")
            return 0 if parsed.get("status") == "OK" else 2
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            return 3
    print("--- STDOUT ---")
    print(out_text[-3000:])
    if err_text.strip():
        print("--- STDERR ---")
        print(err_text)
    return 1 if status != "Success" else 4


if __name__ == "__main__":
    sys.exit(main())
