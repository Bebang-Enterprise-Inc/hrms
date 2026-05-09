#!/usr/bin/env python3
"""Run all 3 Phase 2 seeders via SSM, dry-run + apply."""

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
SEEDERS = [
    ("scripts/s238/seed_bki_trade_supplier.py",       "/tmp/s238_seed_supplier_result.json"),
    ("scripts/s238/install_bki_si_reference_field.py", "/tmp/s238_install_si_ref_field_result.json"),
    ("scripts/s238/install_bei_settings_toggles.py",   "/tmp/s238_install_toggle_result.json"),
]


def _run(ssm, cmds, timeout=300):
    resp = ssm.send_command(
        InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds}, TimeoutSeconds=timeout,
    )
    cmd_id = resp["Command"]["CommandId"]
    while True:
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=INSTANCE_ID)
        if inv["Status"] not in ("Pending", "InProgress", "Delayed"):
            return inv


def _read_file(ssm, container_path: str) -> dict | None:
    """Read JSON from container /tmp via base64 chunk."""
    cmds = [f"base64 -w0 {container_path}"]
    inv = _run(ssm, cmds)
    if inv["Status"] != "Success":
        return None
    b64 = inv.get("StandardOutputContent", "").strip()
    try:
        return json.loads(base64.b64decode(b64).decode("utf-8"))
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    flag = "--apply" if args.apply else ""
    mode = "apply" if args.apply else "dry-run"

    ssm = boto3.client("ssm", region_name=REGION)
    overall: dict = {"mode": mode, "results": {}}

    for script_path, container_result_path in SEEDERS:
        local_script = WORKTREE / script_path
        b64 = base64.b64encode(local_script.read_text(encoding="utf-8").encode()).decode()
        script_basename = local_script.name
        cmds = [
            "set -e",
            "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
            f"echo '{b64}' | base64 -d > /tmp/{script_basename}",
            f"docker cp /tmp/{script_basename} $BACKEND:/tmp/{script_basename}",
            f"docker exec $BACKEND bash -lc 'cd /home/frappe/frappe-bench && env/bin/python /tmp/{script_basename} {flag}'",
            f"docker cp $BACKEND:{container_result_path} {container_result_path}",
        ]
        inv = _run(ssm, cmds, timeout=300)
        print(f"[{mode}] {script_basename}: {inv['Status']}")
        if inv["Status"] != "Success":
            print(inv.get("StandardErrorContent", "")[-500:])
            overall["results"][script_basename] = {"status": "ssm_error"}
            continue
        # Read result
        result = _read_file(ssm, container_result_path)
        overall["results"][script_basename] = result or {"status": "read_error"}
        if result:
            print(f"  -> {result.get('status')}")

    suffix = "_apply" if args.apply else "_dry_run"
    out = WORKTREE / "output" / "s238" / "verification" / f"phase2_seeders{suffix}.json"
    if not args.apply:
        out = WORKTREE / "tmp" / "s238" / f"phase2_seeders{suffix}_{int(time.time())}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(overall, indent=2, default=str), encoding="utf-8")
    print(f"\nWROTE: {out.relative_to(WORKTREE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
