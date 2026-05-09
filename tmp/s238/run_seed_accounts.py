#!/usr/bin/env python3
"""SSM-execute scripts/s238/seed_pi_generator_accounts.py with chunked read."""

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
SEEDER = WORKTREE / "scripts" / "s238" / "seed_pi_generator_accounts.py"


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
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    ssm = boto3.client("ssm", region_name=REGION)
    seeder_b64 = base64.b64encode(SEEDER.read_text(encoding="utf-8").encode()).decode()
    flag = "--apply" if args.apply else ""
    mode = "apply" if args.apply else "dry-run"

    cmds_run = [
        "set -e",
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{seeder_b64}' | base64 -d > /tmp/s238_seed_accounts.py",
        "docker cp /tmp/s238_seed_accounts.py $BACKEND:/tmp/s238_seed_accounts.py",
        f"docker exec $BACKEND bash -lc 'cd /home/frappe/frappe-bench && env/bin/python /tmp/s238_seed_accounts.py {flag}'",
        "docker cp $BACKEND:/tmp/s238_seed_accounts_result.json /tmp/s238_seed_accounts_result.json",
        "wc -c /tmp/s238_seed_accounts_result.json",
    ]
    inv1 = _run(ssm, cmds_run)
    print(f"[{mode}] Run status:", inv1["Status"])
    print(inv1.get("StandardOutputContent", "")[-1500:])

    if inv1["Status"] != "Success":
        print(inv1.get("StandardErrorContent", ""))
        return 1

    size_line = [
        ln for ln in inv1.get("StandardOutputContent", "").splitlines()
        if "/tmp/s238_seed_accounts_result.json" in ln and ln.strip().split()[0].isdigit()
    ]
    file_size = int(size_line[-1].strip().split()[0]) if size_line else 0
    if file_size == 0:
        return 2

    chunks: list[str] = []
    chunk_size = 10000
    offset = 0
    while offset < file_size:
        cmds_chunk = [
            f"dd if=/tmp/s238_seed_accounts_result.json bs=1 skip={offset} count={chunk_size} 2>/dev/null | base64 -w0",
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

    if args.apply:
        out = WORKTREE / "output" / "s238" / "verification" / "seed_accounts_ledger.json"
    else:
        out = WORKTREE / "tmp" / "s238" / f"seed_dry_run_accounts_{int(time.time())}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(parsed, indent=2, default=str), encoding="utf-8")
    print(f"WROTE: {out.relative_to(WORKTREE)}")
    print(
        f"\nmode={parsed['mode']} created={parsed['total_created']} "
        f"existed={parsed['total_existed']} errors={parsed['total_errors']}"
    )
    return 0 if parsed["total_errors"] == 0 else 4


if __name__ == "__main__":
    sys.exit(main())
