"""S225 — verify PR #694 (Phase 6 defects, ACTUAL ship) deployment to production.

Replaces s225_poll_pr692_deploy.py. The prior verifier had a multi-line regex bug
on defect_1: "S225 follow-up.*defaulting source to store warehouse" required both
phrases on the same line, but in hrms/api/store.py:3940-3941 they're split across
two f-string concatenated lines. This verifier uses single-line distinctive markers
(see HANDOFF_NEXT_SESSION.md LESSON B).
"""
from __future__ import annotations
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "s225" / "verification" / "pr694_deploy_check.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

INSTANCE_ID = "i-026b7477d27bd46d6"
EXPECTED_MERGE_SHA = "73b89feb8"  # PR #694 merge

# Single-line markers chosen to be distinctive AND on one source line each.
DEFECT_MARKERS = [
    ("defect_1_source_route_missing",
     "hrms/api/store.py",
     "S225 Source Route Missing"),
    ("defect_2_approve_order_idempotency",
     "hrms/api/store.py",
     "S225 follow-up.*mirror the S224 Pattern B"),
    ("defect_3_warehouse_queue_ordered",
     "hrms/api/warehouse.py",
     "Pending.*Partially Ordered.*Ordered"),
    ("defect_4_lock_wait_try_except",
     "hrms/api/warehouse.py",
     "lock-wait info is best-effort"),
    ("defect_5_sentry_set_scope_patch",
     "hrms/utils/sentry.py",
     "_patch_frappe_set_scope_for_non_request_contexts"),
    ("defect_6_sales_dashboard_non_pos",
     "hrms/api/sales_dashboard.py",
     "stop spamming Sentry on every dashboard load"),
    ("defect_7_mosaic_on_conflict",
     "hrms/api/mosaic_webhook.py",
     "on_conflict=order_id,product_id,line_number"),
]


def probe_container() -> dict:
    import boto3
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        "echo '=== APPS_HRMS MTIME ==='",
        "docker exec $BACKEND stat -c '%Y %n' /home/frappe/frappe-bench/apps/hrms/hrms/api/store.py 2>&1 || echo MTIME_UNAVAILABLE",
    ]
    for key, rel_path, marker in DEFECT_MARKERS:
        full_path = f"/home/frappe/frappe-bench/apps/hrms/{rel_path}"
        cmds.append(f"echo '=== {key} ==='")
        cmds.append(f'docker exec $BACKEND grep -c "{marker}" {full_path} 2>&1 || echo MISSING')

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

    def _has_marker(section_key, min_count=1):
        lines = sections.get(section_key) or []
        for ln in lines:
            ln = ln.strip()
            if ln == "MISSING" or ln == "0":
                return False
            try:
                n = int(ln)
                return n >= min_count
            except ValueError:
                continue
        return False

    apps_mtime = (sections.get("APPS_HRMS MTIME") or [""])[0].strip()

    deployed = {key: _has_marker(key) for key, _, _ in DEFECT_MARKERS}
    all_present = all(deployed.values())

    return {
        "checked_at_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "ssm_command_id": cid,
        "ssm_status": inv["Status"],
        "expected_merge_sha": EXPECTED_MERGE_SHA,
        "container_apps_hrms_mtime": apps_mtime,
        "all_7_defects_present": all_present,
        "per_defect": deployed,
        "raw_output": output,
    }


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-wait-min", type=int, default=10)
    ap.add_argument("--once", action="store_true", default=True)
    args = ap.parse_args()

    deadline = time.time() + args.max_wait_min * 60
    attempt = 0
    while True:
        attempt += 1
        evidence = probe_container()
        OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")

        if evidence.get("all_7_defects_present"):
            print(f"\nALL 7 DEFECTS DEPLOYED at {evidence['checked_at_local']}")
            print(f"Container apps/hrms mtime: {evidence['container_apps_hrms_mtime']}")
            for k, v in evidence["per_defect"].items():
                print(f"  [ok] {k}: {v}")
            print(f"\nEvidence: {OUT}")
            return 0

        present_count = sum(1 for v in evidence["per_defect"].values() if v)
        print(f"Attempt {attempt}: {present_count}/7 defects present in container")
        for k, v in evidence["per_defect"].items():
            mark = "[ok]" if v else "[--]"
            print(f"  {mark} {k}")

        if args.once or time.time() > deadline:
            print(f"\nFAIL: only {present_count}/7 deployed after {args.max_wait_min}min")
            print(f"Evidence: {OUT}")
            return 1

        print(f"  Waiting 30s... ({int((deadline - time.time())/60)}min budget remaining)", flush=True)
        time.sleep(30)


if __name__ == "__main__":
    sys.exit(main())
