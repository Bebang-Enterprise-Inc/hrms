#!/usr/bin/env python3
"""
S159: Send container fix script to EC2 via AWS SSM.

Usage:
  python scripts/s159_run_container.py
  python scripts/s159_run_container.py --dry-run
"""

import base64
import json
import sys
import time
from pathlib import Path

import boto3

INSTANCE_ID = "i-026b7477d27bd46d6"
REGION = "ap-southeast-1"
SCRIPT_PATH = Path(__file__).parent / "s159_container_fix_boms_v4.py"


def main():
    dry_run = "--dry-run" in sys.argv

    script = SCRIPT_PATH.read_text(encoding="utf-8")
    encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")

    print(f"Script: {SCRIPT_PATH} ({len(script)} bytes)")
    print(f"Encoded: {len(encoded)} bytes")

    if dry_run:
        print("[DRY RUN] Would send to EC2 instance", INSTANCE_ID)
        return

    ssm = boto3.client("ssm", region_name=REGION)

    commands = [
        "set -e",
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        'echo "Found backend container: $BACKEND"',
        "if [ -z \"$BACKEND\" ]; then echo 'ERROR: No frappe_backend container found'; exit 1; fi",
        f"echo '{encoded}' | base64 -d > /tmp/s159_fix_boms.py",
        "docker cp /tmp/s159_fix_boms.py $BACKEND:/tmp/s159_fix_boms.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s159_fix_boms.py",
    ]

    print(f"Sending command to {INSTANCE_ID}...")
    resp = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={
            "commands": commands,
            "executionTimeout": ["600"],
        },
        Comment="S159: Fix BOM data -- company assignments + missing products",
    )

    command_id = resp["Command"]["CommandId"]
    print(f"Command ID: {command_id}")
    print("Waiting for completion...")

    # Poll for result
    for attempt in range(60):
        time.sleep(5)
        try:
            result = ssm.get_command_invocation(
                CommandId=command_id,
                InstanceId=INSTANCE_ID,
            )
        except ssm.exceptions.InvocationDoesNotExist:
            continue

        status = result["Status"]
        if status in ("Pending", "InProgress", "Delayed"):
            if attempt % 6 == 0:
                print(f"  Status: {status} ({attempt * 5}s)")
            continue

        # Done
        stdout = result.get("StandardOutputContent", "")
        stderr = result.get("StandardErrorContent", "")

        print(f"\nStatus: {status}")
        if stdout:
            print("--- STDOUT ---")
            print(stdout)
        if stderr:
            print("--- STDERR ---")
            print(stderr)

        if status == "Success" and "S159-CONTAINER-DONE" in stdout:
            print("\nS159 container script completed successfully.")
        else:
            print(f"\nWARNING: Script ended with status={status}")
            sys.exit(1)
        return

    print("ERROR: Timed out waiting for SSM command")
    sys.exit(1)


if __name__ == "__main__":
    main()
