"""S226 — probe BEI Approval Queue rows directly to understand the multi-row pattern.

The s226_diagnose script showed several test orders had 6 Pending queue rows each.
This probes the queue itself (independent of order existence) to see:
  - How many Pending rows per reference order
  - Who the assigned_approver is on each
  - Whether stage / queue_type fields differentiate them
"""
from __future__ import annotations
import base64
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "s225" / "verification" / "queue_rows_probe.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

INSTANCE_ID = "i-026b7477d27bd46d6"

INNER = r'''
import os, json
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/private/files"]:
    os.makedirs(d, exist_ok=True)

import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# Discover columns
meta = frappe.get_meta("BEI Approval Queue")
cols = ["name", "status", "reference_doctype", "reference_name", "assigned_approver", "creation"]
for c in ["approved_by", "approved_at", "submitted_at", "queue_type", "stage", "step", "approval_stage", "rejection_reason"]:
    if meta.has_field(c):
        cols.append(c)
col_csv = ", ".join(f"`{c}`" for c in cols)

# Get all queue rows for our suspect orders
SUSPECT = ['BEI-ORD-2026-00403','BEI-ORD-2026-00404','BEI-ORD-2026-00405','BEI-ORD-2026-00406',
           'BEI-ORD-2026-00407','BEI-ORD-2026-00408','BEI-ORD-2026-00409','BEI-ORD-2026-00410',
           'BEI-ORD-2026-00411','BEI-ORD-2026-00412','BEI-ORD-2026-00413','BEI-ORD-2026-00414']

placeholders = ",".join(["%s"] * len(SUSPECT))
sql = (f"SELECT {col_csv} FROM `tabBEI Approval Queue` "
       f"WHERE reference_doctype='BEI Store Order' AND reference_name IN ({placeholders}) "
       "ORDER BY reference_name, creation")
rows = frappe.db.sql(sql, tuple(SUSPECT), as_dict=True)

# Also count per-reference how many Pending vs Approved vs Rejected
from collections import Counter
per_order = {}
for r in rows:
    n = r["reference_name"]
    per_order.setdefault(n, []).append(r)

summary = []
for ref, qrs in per_order.items():
    by_status = Counter(q["status"] for q in qrs)
    pending = [q for q in qrs if q["status"] == "Pending"]
    summary.append({
        "ref": ref,
        "total_rows": len(qrs),
        "by_status": dict(by_status),
        "pending_assignees": [q["assigned_approver"] for q in pending],
        "all_assignees": [q["assigned_approver"] for q in qrs],
        "stages": [q.get("stage") or q.get("queue_type") or q.get("step") or "?" for q in qrs],
    })

# Also check: what's the distribution of 'Pending' BEI Approval Queue rows in total (non-orphan)?
pending_total = frappe.db.sql(
    "SELECT COUNT(*) FROM `tabBEI Approval Queue` WHERE reference_doctype='BEI Store Order' AND status='Pending'"
)[0][0]

# Multi-row pending pattern across ALL orders
multi_pending = frappe.db.sql("""
    SELECT reference_name, COUNT(*) as n_pending,
           GROUP_CONCAT(DISTINCT assigned_approver) AS approvers
    FROM `tabBEI Approval Queue`
    WHERE reference_doctype='BEI Store Order' AND status='Pending'
    GROUP BY reference_name
    HAVING n_pending > 1
    ORDER BY n_pending DESC
    LIMIT 20
""", as_dict=True)

# Are these reference orders existing?
existing = {}
for ref in per_order:
    existing[ref] = frappe.db.exists("BEI Store Order", ref)

result = {
    "schema_columns": cols,
    "suspect_orders_queue_rows": rows,
    "per_order_summary": summary,
    "existing_per_ref": existing,
    "global_pending_total": pending_total,
    "multi_pending_pattern": multi_pending,
}
with open("/tmp/s226_probe_output.json", "w") as fh:
    json.dump(result, fh, default=str, indent=2)

# Print only the small summary fields to stdout
small = {
    "schema_columns": cols,
    "per_order_summary": summary,
    "existing_per_ref": existing,
    "global_pending_total": pending_total,
    "multi_pending_pattern": multi_pending,
}
print("=== RESULT_BEGIN ===")
print(json.dumps(small, default=str))
print("=== RESULT_END ===")
'''


def main() -> int:
    import boto3
    enc = base64.b64encode(INNER.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s226_probe.py",
        "docker cp /tmp/s226_probe.py $BACKEND:/tmp/s226_probe.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s226_probe.py",
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
    stdout = inv.get("StandardOutputContent", "")
    if "=== RESULT_BEGIN ===" not in stdout:
        print(f"FAIL. stderr={inv.get('StandardErrorContent', '')[:1500]}", flush=True)
        return 1
    s = stdout.index("=== RESULT_BEGIN ===") + len("=== RESULT_BEGIN ===")
    e = stdout.index("=== RESULT_END ===")
    data = json.loads(stdout[s:e].strip())
    OUT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {OUT}")

    # Quick summary
    print("\n=== Per-suspect-order summary ===")
    for s_ in data["per_order_summary"]:
        print(f"  {s_['ref']:25s}  rows={s_['total_rows']:2}  by_status={s_['by_status']}  "
              f"pending_assignees={s_['pending_assignees']}  exists={data['existing_per_ref'].get(s_['ref'])}")
    print(f"\nGlobal pending count: {data['global_pending_total']}")
    print(f"\nMulti-pending pattern (any order with >1 Pending row):")
    for m in data["multi_pending_pattern"][:10]:
        print(f"  {m['reference_name']:25s}  n_pending={m['n_pending']}  approvers={m['approvers']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
