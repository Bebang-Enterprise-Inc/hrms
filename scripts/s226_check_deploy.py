"""S226 deploy verification — check container for the EXISTS subquery + on_cancel hook."""
from __future__ import annotations
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "s225" / "verification" / "s226_deploy_check.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

INSTANCE_ID = "i-026b7477d27bd46d6"


def main() -> int:
    import boto3
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        "echo '=== ORDERING EXISTS marker (S226 visibility fix) ==='",
        'docker exec $BACKEND grep -n "S226: visibility must check ANY Pending row" /home/frappe/frappe-bench/apps/hrms/hrms/api/ordering.py | head -3',
        "echo '=== ORDERING EXISTS subquery present ==='",
        'docker exec $BACKEND grep -n "qx.assigned_approver = %(current_user)s" /home/frappe/frappe-bench/apps/hrms/hrms/api/ordering.py | head -3',
        "echo '=== BEI Store Order on_cancel hook (S226 cascade) ==='",
        'docker exec $BACKEND grep -n "S226: when an order is cancelled" /home/frappe/frappe-bench/apps/hrms/hrms/hr/doctype/bei_store_order/bei_store_order.py | head -3',
        "echo '=== _close_pending_approval_queue_rows helper present ==='",
        'docker exec $BACKEND grep -n "_close_pending_approval_queue_rows" /home/frappe/frappe-bench/apps/hrms/hrms/hr/doctype/bei_store_order/bei_store_order.py | head -3',
        "echo '=== APPS HRMS MTIME ==='",
        "docker exec $BACKEND stat -c '%Y %n' /home/frappe/frappe-bench/apps/hrms/hrms/api/ordering.py",
        "docker exec $BACKEND stat -c '%Y %n' /home/frappe/frappe-bench/apps/hrms/hrms/hr/doctype/bei_store_order/bei_store_order.py",
    ]
    ssm = boto3.client("ssm", region_name="ap-southeast-1")
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
    if inv is None:
        return 2
    output = inv.get("StandardOutputContent", "")
    print(output)

    # Parse the sections
    sections: dict[str, list[str]] = {}
    current = None
    for line in output.splitlines():
        if line.startswith("=== ") and line.endswith(" ==="):
            current = line.strip("= ").strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)

    has_visibility_marker = any(
        "S226: visibility must check ANY Pending row" in ln
        for ln in sections.get("ORDERING EXISTS marker (S226 visibility fix)", [])
    )
    has_exists_subquery = any(
        "qx.assigned_approver = %(current_user)s" in ln
        for ln in sections.get("ORDERING EXISTS subquery present", [])
    )
    has_oncancel_marker = any(
        "S226: when an order is cancelled" in ln
        for ln in sections.get("BEI Store Order on_cancel hook (S226 cascade)", [])
    )
    has_helper = any(
        "_close_pending_approval_queue_rows" in ln
        for ln in sections.get("_close_pending_approval_queue_rows helper present", [])
    )

    evidence = {
        "checked_at_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "ssm_command_id": cid,
        "ssm_status": inv["Status"],
        "container_has_visibility_marker": has_visibility_marker,
        "container_has_exists_subquery": has_exists_subquery,
        "container_has_oncancel_marker": has_oncancel_marker,
        "container_has_close_pending_helper": has_helper,
        "raw_output": output,
    }
    OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")

    all_present = has_visibility_marker and has_exists_subquery and has_oncancel_marker and has_helper
    if all_present:
        print("\nPASS: S226 deployed (4/4 markers found)")
        return 0
    print(f"\nFAIL: S226 not yet deployed. visibility={has_visibility_marker} exists={has_exists_subquery} oncancel={has_oncancel_marker} helper={has_helper}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
