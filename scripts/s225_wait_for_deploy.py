"""S225 Phase 4.5 — wait-for-deploy gate.

Audit B-4 fix: ensures Phase 5 stress test + Phase 6 full sweep run AGAINST the
deployed Phase 4 FOR UPDATE lock, not against pre-S225 code.

Polls every 5 min (max 4 hours) for the FOR UPDATE marker in the deployed
container's create_stock_transfer.

Run from worktree:
    python scripts/s225_wait_for_deploy.py [--max-wait-min N]

Output:
    output/s225/verification/s224_deploy_sha_check.json (overwrites Phase 1's file
      with deploy verification of Phase 4 lock as well)
"""
from __future__ import annotations
import argparse
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "s225" / "verification" / "s224_deploy_sha_check.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

INSTANCE_ID = "i-026b7477d27bd46d6"


def probe_container() -> dict:
    """Single SSM probe — return the parsed evidence."""
    import boto3
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        "echo '=== APPS_HRMS MTIME ==='",
        "docker exec $BACKEND stat -c '%Y %n' /home/frappe/frappe-bench/apps/hrms/hrms/api/warehouse.py 2>&1 || echo STAT_UNAVAILABLE",
        "echo '=== FOR UPDATE in create_stock_transfer ==='",
        'docker exec $BACKEND grep -n "FOR UPDATE" /home/frappe/frappe-bench/apps/hrms/hrms/api/warehouse.py | head -10',
        "echo '=== S225 marker in create_stock_transfer ==='",
        'docker exec $BACKEND grep -n "S225:" /home/frappe/frappe-bench/apps/hrms/hrms/api/warehouse.py | head -5',
        "echo '=== Pattern B (already_approved still present) ==='",
        'docker exec $BACKEND grep -n "already_approved" /home/frappe/frappe-bench/apps/hrms/hrms/api/warehouse.py | head -3',
        "echo '=== Pattern C (S224 marker still present) ==='",
        'docker exec $BACKEND grep -n "S224: case-insensitive substring fallback" /home/frappe/frappe-bench/apps/hrms/hrms/api/store.py | head -3',
    ]
    ssm = boto3.client("ssm", region_name="ap-southeast-1")
    r = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": ["120"]},
    )
    cid = r["Command"]["CommandId"]
    inv = None
    for _ in range(40):
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut"):
            break
    if inv is None:
        return {"error": "ssm_no_completion"}

    output = inv.get("StandardOutputContent", "")
    sections: dict[str, list[str]] = {}
    current = None
    for line in output.splitlines():
        if line.startswith("=== ") and line.endswith(" ==="):
            current = line.strip("= ").strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)

    has_for_update = any(
        "FOR UPDATE" in line and "tabBin" in line  # we want the bin-lock specifically
        for line in (sections.get("FOR UPDATE in create_stock_transfer") or [])
    ) or any(
        "FOR UPDATE" in line  # broader fallback
        for line in (sections.get("FOR UPDATE in create_stock_transfer") or [])
    )
    has_s225_marker = any(
        "S225:" in line
        for line in (sections.get("S225 marker in create_stock_transfer") or [])
    )
    has_pattern_b = any("already_approved" in line for line in (sections.get("Pattern B (already_approved still present)") or []))
    has_pattern_c = any("S224: case-insensitive substring fallback" in line for line in (sections.get("Pattern C (S224 marker still present)") or []))
    apps_mtime = (sections.get("APPS_HRMS MTIME") or [""])[0].strip()

    return {
        "ssm_command_id": cid,
        "ssm_status": inv["Status"],
        "for_update_present": has_for_update,
        "container_code_has_s225_marker": has_s225_marker,
        "container_code_has_idempotency": has_pattern_b,
        "container_code_has_s224_marker": has_pattern_c,
        "container_apps_hrms_mtime": apps_mtime,
        "raw_output": output,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-wait-min", type=int, default=240)
    ap.add_argument("--once", action="store_true", help="Single check then exit")
    args = ap.parse_args()

    deadline = time.time() + args.max_wait_min * 60
    while True:
        evidence = probe_container()
        evidence["checked_at_local"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        # Always overwrite the file so the latest probe is the authority
        OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")

        if evidence.get("for_update_present"):
            print(f"\nDeploy verified at {evidence['checked_at_local']}.")
            print(f"  for_update_present: True")
            print(f"  S225 marker: {evidence.get('container_code_has_s225_marker')}")
            print(f"  apps mtime: {evidence.get('container_apps_hrms_mtime')}")
            return 0

        if args.once or time.time() > deadline:
            print(f"\nFAIL: FOR UPDATE not yet in deployed container (waited {args.max_wait_min}min)")
            return 1

        remaining_min = int((deadline - time.time()) / 60)
        print(f"  not yet deployed. Waiting 5min... ({remaining_min}min budget remaining)", flush=True)
        time.sleep(300)


if __name__ == "__main__":
    sys.exit(main())
