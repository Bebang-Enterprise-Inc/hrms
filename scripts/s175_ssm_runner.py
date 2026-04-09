#!/usr/bin/env python3
"""S175 SSM Runner — common helper for executing Frappe Python scripts inside
the hq.bebang.ph Frappe backend container via AWS SSM.

Usage (from a phase script):

    from s175_ssm_runner import run_on_frappe
    stdout, stderr, status = run_on_frappe(payload_script_path, tag="phase0")

- Base64-encodes the payload
- Ships it via SSM send-command to i-026b7477d27bd46d6 (ap-southeast-1)
- docker cp into frappe_backend container
- Exec via Frappe venv Python
- Polls until complete
- Returns (stdout, stderr, status)

Writes raw stdout/stderr to output/s175/<tag>_raw_stdout.log / _raw_stderr.log.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
from pathlib import Path

import boto3

INSTANCE_ID = "i-026b7477d27bd46d6"
REGION = "ap-southeast-1"
REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "output" / "s175"


def run_on_frappe(payload_script_path: str | Path, tag: str, timeout_seconds: int = 900):
    """Run a local Python script on the Frappe backend container.

    Returns (stdout, stderr, ssm_status).
    Writes raw stdout/stderr to output/s175/<tag>_raw_stdout.log and _raw_stderr.log.
    """
    payload = Path(payload_script_path).read_text(encoding="utf-8")
    encoded = base64.b64encode(payload.encode("utf-8")).decode("ascii")

    remote_path = f"/tmp/s175_{tag}.py"
    container_path = f"/tmp/s175_{tag}.py"

    commands = [
        f"BACKEND=$(docker ps --filter name=frappe_backend --format '{{{{.ID}}}}' | head -1) && "
        f"if [ -z \"$BACKEND\" ]; then echo 'NO BACKEND CONTAINER'; exit 11; fi && "
        f"echo '{encoded}' | base64 -d > {remote_path} && "
        f"docker cp {remote_path} $BACKEND:{container_path} && "
        f"docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python {container_path}"
    ]

    ssm = boto3.client("ssm", region_name=REGION)
    resp = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": commands, "executionTimeout": [str(timeout_seconds)]},
    )
    command_id = resp["Command"]["CommandId"]
    print(f"[s175/{tag}] SSM CommandId={command_id}")

    # Poll
    deadline = time.time() + timeout_seconds + 30
    status = "Pending"
    inv = None
    while time.time() < deadline:
        time.sleep(4)
        try:
            inv = ssm.get_command_invocation(CommandId=command_id, InstanceId=INSTANCE_ID)
        except ssm.exceptions.InvocationDoesNotExist:
            continue
        status = inv["Status"]
        if status in ("Success", "Failed", "Cancelled", "TimedOut"):
            break

    if inv is None:
        raise RuntimeError(f"SSM invocation never registered for {tag}")

    stdout = inv.get("StandardOutputContent", "") or ""
    stderr = inv.get("StandardErrorContent", "") or ""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{tag}_raw_stdout.log").write_text(stdout, encoding="utf-8")
    (OUTPUT_DIR / f"{tag}_raw_stderr.log").write_text(stderr, encoding="utf-8")

    print(f"[s175/{tag}] status={status} stdout={len(stdout)}B stderr={len(stderr)}B")
    return stdout, stderr, status


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: s175_ssm_runner.py <payload.py> <tag>")
        sys.exit(1)
    out, err, st = run_on_frappe(sys.argv[1], sys.argv[2])
    print("STATUS:", st)
    if st != "Success":
        print("STDERR:")
        print(err[-2000:])
        sys.exit(1)
    print(out[-2000:])
