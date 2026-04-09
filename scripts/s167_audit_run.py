"""Run s167_audit_orphans.py inside the Frappe backend container via SSM.

Captures the S167_AUDIT_BEGIN/END JSON blob and writes it to
output/l3/s167/audit_orphans.json.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time

import boto3

INSTANCE_ID = "i-026b7477d27bd46d6"
REGION = "ap-southeast-1"
SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "s167_audit_orphans.py")
OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "l3", "s167"
)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def main() -> int:
    with open(SCRIPT_PATH, encoding="utf-8") as f:
        script_src = f.read()
    encoded = base64.b64encode(script_src.encode()).decode()

    commands = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        "if [ -z \"$BACKEND\" ]; then echo 'ERROR: no frappe_backend container'; exit 2; fi",
        f"echo '{encoded}' | base64 -d > /tmp/s167_audit_orphans.py",
        "docker cp /tmp/s167_audit_orphans.py $BACKEND:/tmp/s167_audit_orphans.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s167_audit_orphans.py",
    ]

    ssm = boto3.client("ssm", region_name=REGION)
    print("Sending SSM command...", flush=True)
    resp = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": commands, "executionTimeout": ["600"]},
    )
    command_id = resp["Command"]["CommandId"]
    print(f"Command ID: {command_id}", flush=True)

    for _ in range(60):
        time.sleep(5)
        inv = ssm.get_command_invocation(CommandId=command_id, InstanceId=INSTANCE_ID)
        status = inv["Status"]
        print(f"  status: {status}", flush=True)
        if status in {"Success", "Failed", "Cancelled", "TimedOut"}:
            stdout = inv.get("StandardOutputContent") or ""
            stderr = inv.get("StandardErrorContent") or ""
            print("=" * 70)
            if stderr:
                print("STDERR (tail):")
                print(stderr[-2000:])
            if "S167_AUDIT_BEGIN" not in stdout or "S167_AUDIT_END" not in stdout:
                print("FATAL: audit markers missing")
                print("STDOUT tail:")
                print(stdout[-4000:])
                return 2
            begin = stdout.index("S167_AUDIT_BEGIN") + len("S167_AUDIT_BEGIN")
            end = stdout.index("S167_AUDIT_END")
            payload = stdout[begin:end].strip()
            report = json.loads(payload)
            out_path = os.path.join(OUTPUT_DIR, "audit_orphans.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, default=str)
            print(f"wrote {out_path}")
            print(json.dumps(report, indent=2, default=str)[:6000])
            return 0 if report.get("ok") else 1

    print("Timed out")
    return 3


if __name__ == "__main__":
    sys.exit(main())
