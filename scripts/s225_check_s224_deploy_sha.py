"""S225 Phase 1 task 1b — verify deployed Docker container has S224 PR #687 code.

Audit B-5 fix: PR-merged != deployed. Sam's deploy is a separate manual step from PR merge.
This script probes the live container to confirm S224 idempotency + fuzzy resolver are in
the code the container is actually running.

Run from the worktree:
    python scripts/s225_check_s224_deploy_sha.py

Output:
    output/s225/verification/s224_deploy_sha_check.json
"""
from __future__ import annotations
import json
import pathlib
import sys
import time

OUT = pathlib.Path(__file__).resolve().parent.parent / "output" / "s225" / "verification" / "s224_deploy_sha_check.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

INSTANCE_ID = "i-026b7477d27bd46d6"
EXPECTED_S224_MERGE_SHA = "b6355e35c10edef2828afb3a283386874a7e728e"


def main() -> int:
    import boto3

    ssm = boto3.client("ssm", region_name="ap-southeast-1")

    # Single SSM command bundle: get container HEAD, grep idempotency marker,
    # grep fuzzy resolver marker, all in one call.
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        "echo '=== CONTAINER GIT HEAD ==='",
        "(docker exec $BACKEND git -C /home/frappe/frappe-bench/apps/hrms rev-parse HEAD 2>&1) || echo 'GIT_UNAVAILABLE'",
        "echo '=== APPS_HRMS MTIME (sanity check) ==='",
        "docker exec $BACKEND stat -c '%Y %n' /home/frappe/frappe-bench/apps/hrms/hrms/api/warehouse.py 2>&1 || echo 'STAT_UNAVAILABLE'",
        "echo '=== PATTERN B (already_approved in approve_material_request) ==='",
        'docker exec $BACKEND grep -n "already_approved" /home/frappe/frappe-bench/apps/hrms/hrms/api/warehouse.py | head -5',
        "echo '=== PATTERN B (current_status == Ordered idempotency block) ==='",
        'docker exec $BACKEND grep -n "current_status == \\"Ordered\\"" /home/frappe/frappe-bench/apps/hrms/hrms/api/warehouse.py | head -3',
        "echo '=== PATTERN C (Ambiguous store identifier in resolve_warehouse) ==='",
        'docker exec $BACKEND grep -n "Ambiguous store identifier" /home/frappe/frappe-bench/apps/hrms/hrms/api/store.py | head -3',
        "echo '=== PATTERN C (case-insensitive substring fallback marker) ==='",
        'docker exec $BACKEND grep -n "S224: case-insensitive substring fallback" /home/frappe/frappe-bench/apps/hrms/hrms/api/store.py | head -3',
    ]

    r = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": ["120"]},
    )
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}", flush=True)

    inv = None
    for _ in range(40):
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut"):
            break

    if inv is None or inv["Status"] not in ("Success", "Failed"):
        print(f"SSM did not complete: status={inv['Status'] if inv else 'no-inv'}", flush=True)
        return 2

    output = inv.get("StandardOutputContent", "")
    print(output)

    container_sha = ""
    container_apps_mtime = ""
    has_idempotency = False
    has_idempotency_status_check = False
    has_fuzzy_resolver_throw = False
    has_s224_marker = False

    # Sections are delimited by '=== HEADER ===' lines. Within each section the grep
    # output is just `<line_number>:<file_content>` (no path) because each grep was
    # given a single file. So the per-section content is the evidence.
    sections: dict[str, list[str]] = {}
    current = None
    for line in output.splitlines():
        if line.startswith("=== ") and line.endswith(" ==="):
            current = line.strip("= ").strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)

    git_head_lines = sections.get("CONTAINER GIT HEAD", [])
    for cand in git_head_lines:
        cand = cand.strip()
        if len(cand) == 40 and all(c in "0123456789abcdef" for c in cand):
            container_sha = cand
            break

    mtime_lines = sections.get("APPS_HRMS MTIME (sanity check)", [])
    if mtime_lines:
        container_apps_mtime = mtime_lines[0].strip()

    has_idempotency = any("already_approved" in ln for ln in sections.get("PATTERN B (already_approved in approve_material_request)", []))
    has_idempotency_status_check = any('current_status == "Ordered"' in ln for ln in sections.get("PATTERN B (current_status == Ordered idempotency block)", []))
    has_fuzzy_resolver_throw = any("Ambiguous store identifier" in ln for ln in sections.get("PATTERN C (Ambiguous store identifier in resolve_warehouse)", []))
    has_s224_marker = any("S224: case-insensitive substring fallback" in ln for ln in sections.get("PATTERN C (case-insensitive substring fallback marker)", []))

    # FOR UPDATE on Bin will be checked separately during Phase 4.5 wait-for-deploy.
    # Phase 1 only validates S224 — the S224 PR did NOT add FOR UPDATE in create_stock_transfer.
    container_has_for_update = False

    evidence = {
        "checked_at_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "ssm_command_id": cid,
        "ssm_status": inv["Status"],
        "instance_id": INSTANCE_ID,
        "expected_s224_merge_sha": EXPECTED_S224_MERGE_SHA,
        "container_code_sha": container_sha,
        "container_sha_matches_expected": container_sha == EXPECTED_S224_MERGE_SHA,
        "container_apps_hrms_mtime": container_apps_mtime,
        "container_code_has_idempotency": has_idempotency,
        "container_code_has_idempotency_status_check": has_idempotency_status_check,
        "container_code_has_fuzzy_resolver_throw": has_fuzzy_resolver_throw,
        "container_code_has_s224_comment_marker": has_s224_marker,
        "container_code_has_for_update": container_has_for_update,
        "raw_output": output,
    }

    OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}", flush=True)

    # PASS criteria: ALL of (already_approved, current_status==Ordered, Ambiguous identifier, S224 marker)
    # must be present. Container git SHA is best-effort — apps may be vendored without .git.
    deployed_ok = has_idempotency and has_idempotency_status_check and has_fuzzy_resolver_throw and has_s224_marker
    if not deployed_ok:
        print("\nFAIL: deployed container missing S224 code", flush=True)
        print(f"  has_idempotency={has_idempotency}  has_idempotency_status_check={has_idempotency_status_check}", flush=True)
        print(f"  has_fuzzy_resolver_throw={has_fuzzy_resolver_throw}  has_s224_marker={has_s224_marker}", flush=True)
        return 1
    print("\nPASS: deployed container has Pattern B + C fixes (4/4 markers found)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
