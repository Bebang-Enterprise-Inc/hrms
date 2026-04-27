"""S226 — one-time data cleanup for orphaned BEI Approval Queue rows.

Background: prior L3 sweep runs (S213-S225) cancelled BEI Store Orders without
cascading the cancel to the queue rows referencing them. The result: ~144 Pending
queue rows whose referenced order is Cancelled (docstatus=2), Approved
(approval_stage=Fully Approved), or deleted entirely. The accumulation
broke get_order_review_queue's visibility filter (S226 backend fix).

This script marks each orphaned Pending row as Rejected with a clear rejection_reason.
Default is dry-run; pass --commit to apply.

Run from worktree:
    python scripts/s226_cleanup_orphan_queue_rows.py            # dry run
    python scripts/s226_cleanup_orphan_queue_rows.py --commit   # apply

Output:
    output/s226/cleanup_orphan_queue_rows_dry_run.json
    output/s226/cleanup_orphan_queue_rows_applied.json
"""
from __future__ import annotations
import argparse
import base64
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "output" / "s226"
OUT_DIR.mkdir(parents=True, exist_ok=True)

INSTANCE_ID = "i-026b7477d27bd46d6"


def _build_inner(commit: bool) -> str:
    return f'''
import os, json
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/private/files"]:
    os.makedirs(d, exist_ok=True)

import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

COMMIT = {commit}

# Find all Pending BEI Approval Queue rows for BEI Store Order references.
candidates = frappe.db.sql("""
    SELECT q.name, q.reference_name, q.assigned_approver, q.creation
    FROM `tabBEI Approval Queue` q
    WHERE q.reference_doctype = 'BEI Store Order' AND q.status = 'Pending'
    ORDER BY q.creation
""", as_dict=True)

orphans = []
for row in candidates:
    order_name = row["reference_name"]
    order = frappe.db.get_value(
        "BEI Store Order",
        order_name,
        ["docstatus", "status", "approval_stage"],
        as_dict=True,
    )
    if not order:
        # Order deleted entirely -> orphan
        orphans.append({{"queue_name": row["name"], "order_name": order_name,
                         "assignee": row["assigned_approver"], "reason": "ORDER_DELETED"}})
        continue
    if order["docstatus"] == 2:
        orphans.append({{"queue_name": row["name"], "order_name": order_name,
                         "assignee": row["assigned_approver"], "reason": "ORDER_CANCELLED",
                         "order_status": order["status"]}})
        continue
    if order["status"] in ("Approved", "Cancelled", "Closed", "Stopped") or order["approval_stage"] in ("Fully Approved", "Single Approval"):
        orphans.append({{"queue_name": row["name"], "order_name": order_name,
                         "assignee": row["assigned_approver"], "reason": "ORDER_FULLY_APPROVED",
                         "order_status": order["status"], "approval_stage": order["approval_stage"]}})
        continue

# Apply (or dry-run report) the cleanup
applied = []
errors = []
has_rejection_field = frappe.get_meta("BEI Approval Queue").has_field("rejection_reason")
if COMMIT:
    for o in orphans:
        try:
            if o["reason"] == "ORDER_DELETED":
                # Validation hook fails .save() because reference_name is missing.
                # Use direct UPDATE — safe because BEI Approval Queue has no GL/SLE dependencies
                # and we are only flipping status + reason on a row whose referenced order no
                # longer exists.
                if has_rejection_field:
                    frappe.db.sql(
                        "UPDATE `tabBEI Approval Queue` SET status='Rejected', rejection_reason=%s, modified=NOW(), modified_by=%s WHERE name=%s",
                        (
                            f"S226 orphan cleanup: order {{o['order_name']}} ORDER_DELETED; queue row left Pending by prior sweep cancel without cascade",
                            "Administrator",
                            o["queue_name"],
                        ),
                    )
                else:
                    frappe.db.sql(
                        "UPDATE `tabBEI Approval Queue` SET status='Rejected', modified=NOW(), modified_by=%s WHERE name=%s",
                        ("Administrator", o["queue_name"]),
                    )
            else:
                queue_doc = frappe.get_doc("BEI Approval Queue", o["queue_name"])
                queue_doc.status = "Rejected"
                if has_rejection_field:
                    queue_doc.rejection_reason = (
                        f"S226 orphan cleanup: order {{o['order_name']}} is {{o['reason']}}; "
                        f"queue row left Pending by prior sweep cancel without cascade"
                    )
                queue_doc.flags.ignore_permissions = True
                queue_doc.save(ignore_permissions=True)
            applied.append({{"queue_name": o["queue_name"], "order_name": o["order_name"], "reason": o["reason"]}})
        except Exception as e:
            errors.append({{"queue_name": o["queue_name"], "error": str(e)[:300]}})
    frappe.db.commit()

# Sanity: count remaining Pending after cleanup
remaining = frappe.db.sql(
    "SELECT COUNT(*) FROM `tabBEI Approval Queue` "
    "WHERE reference_doctype='BEI Store Order' AND status='Pending'"
)[0][0]

# Group orphans by reason
from collections import Counter
reason_counter = Counter(o["reason"] for o in orphans)

result = {{
    "committed": COMMIT,
    "candidate_pending_total": len(candidates),
    "orphan_count": len(orphans),
    "orphan_reasons": dict(reason_counter),
    "applied_count": len(applied),
    "errors_count": len(errors),
    "remaining_pending_after": remaining,
    "errors_sample": errors[:10],
    "orphans_sample": orphans[:20],
}}
print("=== RESULT_BEGIN ===")
print(json.dumps(result, default=str))
print("=== RESULT_END ===")
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="Apply cleanup (default: dry-run)")
    args = ap.parse_args()

    import boto3
    inner = _build_inner(args.commit)
    enc = base64.b64encode(inner.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s226_cleanup.py",
        "docker cp /tmp/s226_cleanup.py $BACKEND:/tmp/s226_cleanup.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s226_cleanup.py",
    ]
    ssm = boto3.client("ssm", region_name="ap-southeast-1")
    r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
                         Parameters={"commands": cmds, "executionTimeout": ["240"]})
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}", flush=True)
    inv = None
    for _ in range(80):
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut"):
            break
    if inv is None:
        return 2
    stdout = inv.get("StandardOutputContent", "")
    if "=== RESULT_BEGIN ===" not in stdout or "=== RESULT_END ===" not in stdout:
        print(f"FAIL.\nstderr={inv.get('StandardErrorContent', '')[:1500]}\nstdout tail={stdout[-2000:]}")
        return 1
    s = stdout.index("=== RESULT_BEGIN ===") + len("=== RESULT_BEGIN ===")
    e = stdout.index("=== RESULT_END ===")
    data = json.loads(stdout[s:e].strip())

    suffix = "applied" if args.commit else "dry_run"
    out_path = OUT_DIR / f"cleanup_orphan_queue_rows_{suffix}.json"
    out_path.write_text(json.dumps({
        "ssm_command_id": cid,
        "ssm_status": inv["Status"],
        "result": data,
    }, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {out_path}\n")

    print(f"Candidate Pending rows: {data['candidate_pending_total']}")
    print(f"Orphans (need cleanup): {data['orphan_count']}")
    print(f"Orphan reasons: {data['orphan_reasons']}")
    if args.commit:
        print(f"Applied: {data['applied_count']}")
        print(f"Errors: {data['errors_count']}")
    print(f"Remaining Pending after this run: {data['remaining_pending_after']}")
    if data["orphans_sample"]:
        print(f"\nFirst {len(data['orphans_sample'])} orphans:")
        for o in data["orphans_sample"]:
            print(f"  {o['queue_name']:25} -> order {o['order_name']:25} ({o['reason']}) assignee={o['assignee']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
