#!/usr/bin/env python3
"""SSM-execute probe_phase3_completeness.py."""

from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

import boto3

INSTANCE_ID = "i-026b7477d27bd46d6"
REGION = "ap-southeast-1"
WORKTREE = Path(__file__).resolve().parent.parent.parent
SCRIPT = Path(__file__).parent / "probe_phase3_completeness.py"


def _run(ssm, cmds, timeout=600):
    resp = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds},
        TimeoutSeconds=timeout,
    )
    cmd_id = resp["Command"]["CommandId"]
    while True:
        time.sleep(4)
        inv = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=INSTANCE_ID)
        if inv["Status"] not in ("Pending", "InProgress", "Delayed"):
            return inv


def main() -> int:
    ssm = boto3.client("ssm", region_name=REGION)
    encoded = base64.b64encode(SCRIPT.read_text(encoding="utf-8").encode()).decode()
    cmds_run = [
        "set -e",
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{encoded}' | base64 -d > /tmp/s243_phase3.py",
        "docker cp /tmp/s243_phase3.py $BACKEND:/tmp/s243_phase3.py",
        "docker exec $BACKEND bash -lc 'cd /home/frappe/frappe-bench && env/bin/python /tmp/s243_phase3.py'",
        "docker cp $BACKEND:/tmp/s243_phase3_result.json /tmp/s243_phase3_result.json",
        "wc -c /tmp/s243_phase3_result.json",
    ]
    inv1 = _run(ssm, cmds_run)
    print("Run status:", inv1["Status"])
    print(inv1.get("StandardOutputContent", "")[-500:])

    if inv1["Status"] != "Success":
        print(inv1.get("StandardErrorContent", ""))
        return 1

    size_line = [
        ln for ln in inv1.get("StandardOutputContent", "").splitlines()
        if "/tmp/s243_phase3_result.json" in ln and ln.strip().split()[0].isdigit()
    ]
    file_size = int(size_line[-1].strip().split()[0]) if size_line else 0
    if file_size == 0:
        return 2

    chunks: list[str] = []
    chunk_size = 10000
    offset = 0
    while offset < file_size:
        cmds_chunk = [
            f"dd if=/tmp/s243_phase3_result.json bs=1 skip={offset} count={chunk_size} 2>/dev/null | base64 -w0",
        ]
        inv_chunk = _run(ssm, cmds_chunk, timeout=120)
        if inv_chunk["Status"] != "Success":
            return 3
        chunks.append(inv_chunk.get("StandardOutputContent", "").strip())
        offset += chunk_size

    raw = b""
    for c in chunks:
        raw += base64.b64decode(c)
    parsed = json.loads(raw.decode("utf-8"))

    out = WORKTREE / "output" / "s243" / "verification" / "coa_complete_count.json"
    out.write_text(json.dumps(parsed, indent=2, default=str), encoding="utf-8")
    print(f"WROTE: {out.relative_to(WORKTREE)}")
    print(f"complete={parsed.get('complete_stores')}/{parsed.get('checked_stores')}")
    if parsed.get("incomplete_stores"):
        print(f"INCOMPLETE: {parsed['incomplete_stores']}")
    return 0 if parsed.get("status") == "OK" else 4


if __name__ == "__main__":
    sys.exit(main())
