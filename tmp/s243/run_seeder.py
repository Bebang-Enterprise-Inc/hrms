#!/usr/bin/env python3
"""S243 SSM wrapper — uploads seeder + gap_analysis to backend container,
runs in dry-run or commit mode, retrieves the seed_ledger JSON.

Usage:
  python tmp/s243/run_seeder.py --dry-run
  python tmp/s243/run_seeder.py            (commit-mode default)
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path

import boto3

INSTANCE_ID = "i-026b7477d27bd46d6"
REGION = "ap-southeast-1"
WORKTREE = Path(__file__).resolve().parent.parent.parent
SEEDER = WORKTREE / "scripts" / "s243" / "seed_canonical_coa_for_4_stores.py"
GAP_FILE = WORKTREE / "output" / "s243" / "verification" / "coa_gap_analysis.json"


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
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    ssm = boto3.client("ssm", region_name=REGION)

    seeder_b64 = base64.b64encode(SEEDER.read_text(encoding="utf-8").encode()).decode()
    gap_b64 = base64.b64encode(GAP_FILE.read_text(encoding="utf-8").encode()).decode()

    seeder_arg = "--dry-run" if args.dry_run else ""
    mode_label = "dry-run" if args.dry_run else "commit"

    cmds_run = [
        "set -e",
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        # Upload seeder
        f"echo '{seeder_b64}' | base64 -d > /tmp/s243_seeder.py",
        "docker cp /tmp/s243_seeder.py $BACKEND:/tmp/s243_seeder.py",
        # Upload gap analysis to absolute path inside container; seeder reads via S243_GAP_PATH env var
        f"echo '{gap_b64}' | base64 -d > /tmp/s243_gap.json",
        "docker cp /tmp/s243_gap.json $BACKEND:/tmp/s243_gap.json",
        # Execute from frappe-bench cwd (Frappe's logger expects this for log path resolution)
        f"docker exec -e S243_GAP_PATH=/tmp/s243_gap.json $BACKEND bash -lc 'cd /home/frappe/frappe-bench && env/bin/python /tmp/s243_seeder.py {seeder_arg}'",
        # Copy result back
        "docker cp $BACKEND:/tmp/s243_seed_result.json /tmp/s243_seed_result.json",
        "wc -c /tmp/s243_seed_result.json",
    ]
    inv1 = _run(ssm, cmds_run)
    print(f"[{mode_label}] Run status:", inv1["Status"])
    print(inv1.get("StandardOutputContent", "")[-1500:])

    if inv1["Status"] != "Success":
        print("RUN FAILED")
        print(inv1.get("StandardErrorContent", ""))
        return 1

    # Get file size from final wc line
    size_line = [
        ln for ln in inv1.get("StandardOutputContent", "").splitlines()
        if "/tmp/s243_seed_result.json" in ln and ln.strip().split()[0].isdigit()
    ]
    file_size = int(size_line[-1].strip().split()[0]) if size_line else 0
    if file_size == 0:
        print("Could not determine result file size")
        return 2

    # Chunked read
    chunks: list[str] = []
    chunk_size = 10000
    offset = 0
    while offset < file_size:
        cmds_chunk = [
            f"dd if=/tmp/s243_seed_result.json bs=1 skip={offset} count={chunk_size} 2>/dev/null | base64 -w0",
        ]
        inv_chunk = _run(ssm, cmds_chunk, timeout=120)
        if inv_chunk["Status"] != "Success":
            print(f"Chunk {offset} read failed")
            return 3
        chunks.append(inv_chunk.get("StandardOutputContent", "").strip())
        offset += chunk_size

    raw_bytes = b""
    for c in chunks:
        raw_bytes += base64.b64decode(c)
    parsed = json.loads(raw_bytes.decode("utf-8"))

    # Output destination depends on mode
    if args.dry_run:
        out_path = WORKTREE / "tmp" / "s243" / f"seed_dry_run_{int(time.time())}.log"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(parsed, indent=2, default=str), encoding="utf-8")
        # Also write to canonical name for plan verify
        canonical = WORKTREE / "output" / "s243" / "verification" / "seed_dry_run_report.json"
        canonical.parent.mkdir(parents=True, exist_ok=True)
        canonical.write_text(json.dumps(parsed, indent=2, default=str), encoding="utf-8")
        print(f"WROTE: {out_path.relative_to(WORKTREE)}")
        print(f"WROTE: {canonical.relative_to(WORKTREE)}")
    else:
        canonical = WORKTREE / "output" / "s243" / "verification" / "seed_ledger.json"
        canonical.parent.mkdir(parents=True, exist_ok=True)
        canonical.write_text(json.dumps(parsed, indent=2, default=str), encoding="utf-8")
        print(f"WROTE: {canonical.relative_to(WORKTREE)}")

    print(
        f"\nmode={parsed['mode']} "
        f"created={parsed['total_created']} existed={parsed['total_existed']} "
        f"errors={parsed['total_errors']} rollback={parsed.get('rollback_confirmed')}"
    )
    return 0 if parsed["total_errors"] == 0 else 4


if __name__ == "__main__":
    sys.exit(main())
