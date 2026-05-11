#!/usr/bin/env python3
"""SSM-execute probe_sweep_aftermath.py."""
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
SCRIPT = HERE / "probe_sweep_aftermath.py"
OUT = HERE / "aftermath_result.json"


def main() -> int:
    ssm = boto3.client("ssm", region_name=REGION)
    encoded = base64.b64encode(SCRIPT.read_text(encoding="utf-8").encode()).decode()
    cmds = [
        "set -e",
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{encoded}' | base64 -d > /tmp/s244_aftermath.py",
        "docker cp /tmp/s244_aftermath.py $BACKEND:/tmp/s244_aftermath.py",
        "docker exec $BACKEND bash -lc 'cd /home/frappe/frappe-bench && env/bin/python /tmp/s244_aftermath.py'",
        "docker cp $BACKEND:/tmp/s244_aftermath.json /tmp/s244_aftermath.json",
        "gzip -c /tmp/s244_aftermath.json > /tmp/s244_aftermath.json.gz",
        "echo S244_FILE_BEGIN",
        "base64 -w0 /tmp/s244_aftermath.json.gz; echo",
        "echo S244_FILE_END",
    ]
    resp = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
                             Parameters={"commands": cmds}, TimeoutSeconds=600)
    cmd_id = resp["Command"]["CommandId"]
    print(f"command_id={cmd_id}", flush=True)
    while True:
        time.sleep(5)
        inv = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Pending", "InProgress", "Delayed"):
            continue
        break
    print(f"final_status={inv['Status']}")
    out_text = inv.get("StandardOutputContent", "")
    if "S244_FILE_BEGIN" in out_text:
        b64 = out_text.split("S244_FILE_BEGIN")[1].split("S244_FILE_END")[0].strip()
        decoded = gzip.decompress(base64.b64decode(b64)).decode("utf-8")
        data = json.loads(decoded)
        OUT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        print(f"wrote {OUT}")
        print(f"  error_log_count={data.get('error_log_count')}")
        print(f"  leftover_si_count={data.get('leftover_si_count')}")
        print(f"  leftover_pi_count={data.get('leftover_pi_count')}")
        print(f"  orphan_pi_count={data.get('orphan_pi_count')}")
        return 0
    print(out_text); print(inv.get("StandardErrorContent", ""))
    return 1


if __name__ == "__main__":
    sys.exit(main())
