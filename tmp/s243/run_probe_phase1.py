#!/usr/bin/env python3
"""SSM-execute probe_phase1_reference.py — writes JSON to container /tmp,
docker cp's it out, then SSM cat's the host file back via a 2nd command
(splits the read across several smaller SSM responses to avoid the 24KB cap)."""

from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

import boto3

INSTANCE_ID = "i-026b7477d27bd46d6"
REGION = "ap-southeast-1"
SCRIPT = Path(__file__).parent / "probe_phase1_reference.py"
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "s243" / "verification"


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

    # Stage 1: run the probe (writes /tmp/s243_phase1_result.json inside container,
    # then docker cp's it to host /tmp/s243_phase1_result.json).
    cmds_run = [
        "set -e",
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{encoded}' | base64 -d > /tmp/s243_phase1.py",
        "docker cp /tmp/s243_phase1.py $BACKEND:/tmp/s243_phase1.py",
        "docker exec $BACKEND bash -lc 'cd /home/frappe/frappe-bench && env/bin/python /tmp/s243_phase1.py'",
        "docker cp $BACKEND:/tmp/s243_phase1_result.json /tmp/s243_phase1_result.json",
        "wc -c /tmp/s243_phase1_result.json",
    ]
    inv1 = _run(ssm, cmds_run)
    print("Run status:", inv1["Status"])
    print(inv1.get("StandardOutputContent", "")[-500:])

    if inv1["Status"] != "Success":
        print("RUN FAILED")
        print(inv1.get("StandardErrorContent", ""))
        return 1

    # Stage 2: chunked base64 read (SSM stdout cap ~24KB → split file into 10KB chunks).
    # File size from stage 1 final line e.g. "42965 /tmp/s243_phase1_result.json"
    size_line = [ln for ln in inv1.get("StandardOutputContent", "").splitlines() if "/tmp/s243_phase1_result.json" in ln and ln.strip().split()[0].isdigit()]
    file_size = int(size_line[-1].strip().split()[0]) if size_line else 0
    if file_size == 0:
        print("Could not parse file size from stage 1 output")
        return 2
    print(f"File size: {file_size} bytes; reading in 10KB chunks")

    chunks: list[str] = []
    chunk_size = 10000
    offset = 0
    while offset < file_size:
        cmds_chunk = [
            f"dd if=/tmp/s243_phase1_result.json bs=1 skip={offset} count={chunk_size} 2>/dev/null | base64 -w0",
        ]
        inv_chunk = _run(ssm, cmds_chunk, timeout=120)
        if inv_chunk["Status"] != "Success":
            print(f"CHUNK {offset} READ FAILED")
            return 3
        chunk = inv_chunk.get("StandardOutputContent", "").strip()
        chunks.append(chunk)
        offset += chunk_size
        print(f"  chunk {len(chunks)} read (offset={offset}, b64 len={len(chunk)})")

    try:
        full_b64 = "".join(chunks)
        # Each chunk is independently base64-encoded — decode each separately and concat raw bytes
        raw_bytes = b""
        for c in chunks:
            raw_bytes += base64.b64decode(c)
        decoded = raw_bytes.decode("utf-8")
        parsed = json.loads(decoded)
    except Exception as e:
        print(f"Decode/parse error: {e}")
        return 4

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "reference_bare_name_coa.json").write_text(
        json.dumps(parsed, indent=2, default=str), encoding="utf-8"
    )
    print(f"WROTE: output/s243/verification/reference_bare_name_coa.json (status={parsed.get('status')}, consistent={parsed.get('convention_consistent')})")
    return 0 if parsed.get("status") == "OK" else 5


if __name__ == "__main__":
    sys.exit(main())
