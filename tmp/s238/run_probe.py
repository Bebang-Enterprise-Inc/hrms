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
PROBE = Path(__file__).parent / "probe_phase0_state.py"


def main() -> int:
    ssm = boto3.client("ssm", region_name=REGION)
    encoded = base64.b64encode(PROBE.read_text(encoding="utf-8").encode()).decode()

    cmds = [
        "set -e",
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        'if [ -z "$BACKEND" ]; then echo "BACKEND_NOT_FOUND" && exit 1; fi',
        f"echo '{encoded}' | base64 -d > /tmp/s238_probe_phase0.py",
        "docker cp /tmp/s238_probe_phase0.py $BACKEND:/tmp/s238_probe_phase0.py",
        "docker exec $BACKEND bash -lc 'cd /home/frappe/frappe-bench && env/bin/python /tmp/s238_probe_phase0.py'",
    ]

    resp = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds},
        TimeoutSeconds=600,
    )
    cmd_id = resp["Command"]["CommandId"]
    print(f"command_id={cmd_id}", flush=True)

    # Poll
    while True:
        time.sleep(5)
        inv = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=INSTANCE_ID)
        status = inv["Status"]
        if status in ("Pending", "InProgress", "Delayed"):
            print(f"  status={status}", flush=True)
            continue
        break

    print(f"final_status={status}")
    print("--- STDOUT ---")
    print(inv.get("StandardOutputContent", ""))
    print("--- STDERR ---")
    print(inv.get("StandardErrorContent", ""))

    out_text = inv.get("StandardOutputContent", "")
    if "S238_PROBE_BEGIN" in out_text and "S238_PROBE_END" in out_text:
        body = out_text.split("S238_PROBE_BEGIN")[1].split("S238_PROBE_END")[0].strip()
        try:
            parsed = json.loads(body)
            (Path(__file__).parent / "phase0_probe_result.json").write_text(
                json.dumps(parsed, indent=2, default=str), encoding="utf-8"
            )
            print(f"WROTE: tmp/s238/phase0_probe_result.json (status={parsed.get('status')})")
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            return 2

    return 0 if status == "Success" else 1


if __name__ == "__main__":
    sys.exit(main())
