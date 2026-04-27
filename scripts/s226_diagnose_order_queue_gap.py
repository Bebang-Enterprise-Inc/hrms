"""S226 (defect investigation) — diagnose why sweep test orders don't appear in approval queue.

S225 Phase 1 sweep failed for 4/6 stores with the message:
  "OrderApprovalPage.approve: order BEI-ORD-2026-XXXXX did not appear in the approval queue
   after 6 navigation attempts. S223 DEFECT-11 fix should make this path visible."

This script probes production to determine:
  1. What status do these test orders actually have?
  2. Is there a BEI Approval Queue row for each? If so, who is the assigned_approver?
  3. Would get_order_review_queue (called as test.area / test.scm) return them?
  4. What approval_stage does the order have?

Run from worktree:
    python scripts/s226_diagnose_order_queue_gap.py

Output:
    output/s225/verification/order_queue_gap_diagnosis.json
"""
from __future__ import annotations
import base64
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "s225" / "verification" / "order_queue_gap_diagnosis.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

INSTANCE_ID = "i-026b7477d27bd46d6"

# Test orders from the failed sweep (per ledger)
SUSPECT_ORDERS = [
    "BEI-ORD-2026-00403", "BEI-ORD-2026-00404",  # AYALA FAIRVIEW TERRACES (failed)
    "BEI-ORD-2026-00405", "BEI-ORD-2026-00406",  # AYALA UP TOWN CENTER (flaky)
    "BEI-ORD-2026-00407", "BEI-ORD-2026-00408",  # NAIA T3 (failed)
    "BEI-ORD-2026-00409", "BEI-ORD-2026-00410",  # ORTIGAS ESTANCIA (failed)
    "BEI-ORD-2026-00411", "BEI-ORD-2026-00412",  # ROBINSONS ANTIPOLO (failed)
    "BEI-ORD-2026-00413", "BEI-ORD-2026-00414",  # ROBINSONS IMUS (flaky)
]

INNER = r'''
import os, json
for d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/private/files",
]:
    os.makedirs(d, exist_ok=True)

import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

SUSPECT_ORDERS = __SUSPECT_ORDERS__

# 1) Read each order
order_rows = []
for name in SUSPECT_ORDERS:
    if not frappe.db.exists("BEI Store Order", name):
        order_rows.append({"name": name, "exists": False})
        continue
    fields = ["name", "store", "status", "submitted_by", "creation",
              "order_date", "delivery_date", "docstatus"]
    # Check which optional approval-trail fields exist on this site (custom fields may vary)
    optional_fields = ["approved_at", "scm_approved_at", "approval_stage", "approved_by",
                       "scm_approved_by", "auto_approved"]
    meta = frappe.get_meta("BEI Store Order")
    for f in optional_fields:
        if meta.has_field(f):
            fields.append(f)
    row = frappe.db.get_value("BEI Store Order", name, fields, as_dict=True)
    if row:
        row["exists"] = True
        order_rows.append(row)

# 2) Read BEI Approval Queue rows for each
queue_by_order = {}
for name in SUSPECT_ORDERS:
    # Discover available columns once
    queue_meta = frappe.get_meta("BEI Approval Queue")
    base_cols = ["name", "status", "assigned_approver", "creation"]
    optional_cols = ["approved_by", "approved_at", "submitted_at", "queue_type", "stage", "rejection_reason"]
    cols_to_select = list(base_cols)
    for c in optional_cols:
        if queue_meta.has_field(c):
            cols_to_select.append(c)
    col_csv = ", ".join(f"`{c}`" for c in cols_to_select)
    queue_rows = frappe.db.sql(
        f"SELECT {col_csv} FROM `tabBEI Approval Queue` "
        "WHERE reference_doctype = 'BEI Store Order' AND reference_name = %s ORDER BY creation",
        (name,), as_dict=True,
    )
    queue_by_order[name] = queue_rows

# 3) Run get_order_review_queue as test.area and as test.scm
from hrms.api.ordering import get_order_review_queue

queue_results = {}
for user in ["test.area@bebang.ph", "test.scm@bebang.ph"]:
    if not frappe.db.exists("User", user):
        queue_results[user] = {"error": "user_not_found"}
        continue
    frappe.set_user(user)
    try:
        q = get_order_review_queue(date=None, status=None)
        # Just keep the names + statuses to compare
        queue_results[user] = {
            "total": q["total"],
            "names": [o["name"] for o in q["orders"]],
            "names_in_suspect_list": [o["name"] for o in q["orders"] if o["name"] in SUSPECT_ORDERS],
        }
    except Exception as e:
        queue_results[user] = {"error": str(e)[:400]}
frappe.set_user("Administrator")

# 4) Also try with status="Pending Approval" filter (matches the UI default)
queue_results_pending = {}
for user in ["test.area@bebang.ph", "test.scm@bebang.ph"]:
    if not frappe.db.exists("User", user):
        queue_results_pending[user] = {"error": "user_not_found"}
        continue
    frappe.set_user(user)
    try:
        q = get_order_review_queue(date=None, status="Pending Approval")
        queue_results_pending[user] = {
            "total": q["total"],
            "names_in_suspect_list": [o["name"] for o in q["orders"] if o["name"] in SUSPECT_ORDERS],
        }
    except Exception as e:
        queue_results_pending[user] = {"error": str(e)[:400]}
frappe.set_user("Administrator")

# 5) Cross-tab: for each suspect order, what's the visibility verdict?
verdict = []
queue_no_filter_test_area = set(queue_results.get("test.area@bebang.ph", {}).get("names_in_suspect_list", []))
queue_pending_test_area = set(queue_results_pending.get("test.area@bebang.ph", {}).get("names_in_suspect_list", []))
queue_no_filter_test_scm = set(queue_results.get("test.scm@bebang.ph", {}).get("names_in_suspect_list", []))
queue_pending_test_scm = set(queue_results_pending.get("test.scm@bebang.ph", {}).get("names_in_suspect_list", []))

order_by_name = {r["name"]: r for r in order_rows if r.get("exists")}
queue_by_name = queue_by_order

for name in SUSPECT_ORDERS:
    order = order_by_name.get(name, {})
    queues = queue_by_name.get(name, [])
    pending_queue_rows = [q for q in queues if q["status"] == "Pending"]
    verdict.append({
        "order_name": name,
        "exists": bool(order.get("exists")) if order else False,
        "store": order.get("store") if order else None,
        "status": order.get("status") if order else None,
        "approved_at": str(order.get("approved_at")) if order and order.get("approved_at") else None,
        "scm_approved_at": str(order.get("scm_approved_at")) if order and order.get("scm_approved_at") else None,
        "approval_stage": order.get("approval_stage") if order else None,
        "approval_queue_pending_count": len(pending_queue_rows),
        "approval_queue_pending_assignees": [q["assigned_approver"] for q in pending_queue_rows],
        "approval_queue_all_statuses": [q["status"] for q in queues],
        "visible_to_test_area_no_filter": name in queue_no_filter_test_area,
        "visible_to_test_area_pending_filter": name in queue_pending_test_area,
        "visible_to_test_scm_no_filter": name in queue_no_filter_test_scm,
        "visible_to_test_scm_pending_filter": name in queue_pending_test_scm,
    })

# 6) Confirm test.area and test.scm roles
roles = {}
for u in ["test.area@bebang.ph", "test.scm@bebang.ph"]:
    if frappe.db.exists("User", u):
        roles[u] = frappe.get_roles(u)
    else:
        roles[u] = "user_not_found"

trimmed_queue_results = {
    user: {
        "total": data.get("total"),
        "names_in_suspect_list": data.get("names_in_suspect_list", []),
    }
    for user, data in queue_results.items() if isinstance(data, dict)
}
payload = {
    "orders": order_rows,
    "approval_queue_by_order": queue_by_order,
    "queue_no_filter_summary": trimmed_queue_results,
    "queue_pending_filter_summary": queue_results_pending,
    "verdict": verdict,
    "user_roles": roles,
}
with open("/tmp/s226_diagnose_output.json", "w") as fh:
    json.dump(payload, fh, default=str, indent=2)
print("WROTE /tmp/s226_diagnose_output.json size=", os.path.getsize("/tmp/s226_diagnose_output.json"))

# Print compact verdict to stdout — this is the key diagnostic signal
print("=== VERDICT_BEGIN ===")
print(json.dumps(verdict, default=str))
print("=== VERDICT_END ===")
print("=== ROLES_BEGIN ===")
print(json.dumps(roles, default=str))
print("=== ROLES_END ===")
print("=== QUEUE_SUMMARY_BEGIN ===")
print(json.dumps({"no_filter": trimmed_queue_results, "pending_filter": queue_results_pending}, default=str))
print("=== QUEUE_SUMMARY_END ===")
'''


def main() -> int:
    import boto3
    inner = INNER.replace("__SUSPECT_ORDERS__", repr(SUSPECT_ORDERS))
    enc = base64.b64encode(inner.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s226_diagnose.py",
        "docker cp /tmp/s226_diagnose.py $BACKEND:/tmp/s226_diagnose.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s226_diagnose.py",
        # Persist output file from container to host for follow-up inspection
        "docker cp $BACKEND:/tmp/s226_diagnose_output.json /tmp/s226_diagnose_output.json",
        "ls -la /tmp/s226_diagnose_output.json",
    ]
    ssm = boto3.client("ssm", region_name="ap-southeast-1")
    r = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": ["180"]},
    )
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}", flush=True)
    inv = None
    for _ in range(60):
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut"):
            break
    if inv is None:
        print("SSM did not complete", flush=True)
        return 2
    stdout = inv.get("StandardOutputContent", "")
    stderr = inv.get("StandardErrorContent", "")

    # Extract the compact verdict / roles / queue summary blocks from stdout
    def _between(text, begin, end):
        if begin not in text or end not in text:
            return None
        i = text.index(begin) + len(begin)
        j = text.index(end)
        return text[i:j].strip()

    verdict = None
    roles_data = None
    queue_summary = None
    try:
        v = _between(stdout, "=== VERDICT_BEGIN ===", "=== VERDICT_END ===")
        if v:
            verdict = json.loads(v)
        r = _between(stdout, "=== ROLES_BEGIN ===", "=== ROLES_END ===")
        if r:
            roles_data = json.loads(r)
        q = _between(stdout, "=== QUEUE_SUMMARY_BEGIN ===", "=== QUEUE_SUMMARY_END ===")
        if q:
            queue_summary = json.loads(q)
    except Exception as e:
        print(f"WARN: parse error on stdout blocks: {e}", flush=True)

    # Pull the full JSON via base64 in a separate SSM call (so it isn't fighting for stdout space)
    full_data = None
    try:
        follow = ssm.send_command(
            InstanceIds=[INSTANCE_ID],
            DocumentName="AWS-RunShellScript",
            Parameters={
                "commands": [
                    # Split into chunks of 20 KB pre-base64 (so each base64 chunk is ~27 KB).
                    # Use head + dd to slice the file
                    "echo '=== CHUNK_COUNT ==='",
                    "FSIZE=$(stat -c '%s' /tmp/s226_diagnose_output.json)",
                    "CHUNKSIZE=18000",
                    "NCHUNKS=$(( (FSIZE + CHUNKSIZE - 1) / CHUNKSIZE ))",
                    "echo $NCHUNKS",
                    "echo '=== END_CHUNK_COUNT ==='",
                    "for i in $(seq 0 $((NCHUNKS-1))); do "
                    "  echo \"=== CHUNK_${i}_BEGIN ===\";"
                    "  dd if=/tmp/s226_diagnose_output.json bs=$CHUNKSIZE count=1 skip=$i 2>/dev/null | base64 -w0;"
                    "  echo;"
                    "  echo \"=== CHUNK_${i}_END ===\";"
                    "done",
                ],
                "executionTimeout": ["60"],
            },
        )
        cid2 = follow["Command"]["CommandId"]
        inv2 = None
        for _ in range(20):
            time.sleep(2)
            inv2 = ssm.get_command_invocation(CommandId=cid2, InstanceId=INSTANCE_ID)
            if inv2["Status"] in ("Success", "Failed", "TimedOut"):
                break
        if inv2 and inv2["Status"] == "Success":
            chunked_stdout = inv2["StandardOutputContent"]
            cc = _between(chunked_stdout, "=== CHUNK_COUNT ===", "=== END_CHUNK_COUNT ===")
            if cc and cc.strip().isdigit():
                n = int(cc.strip())
                import base64 as _b64
                pieces = []
                for i in range(n):
                    p = _between(chunked_stdout, f"=== CHUNK_{i}_BEGIN ===", f"=== CHUNK_{i}_END ===")
                    if p is None:
                        break
                    pieces.append(_b64.b64decode(p.strip()))
                if pieces and len(pieces) == n:
                    raw = b"".join(pieces).decode("utf-8")
                    full_data = json.loads(raw)
    except Exception as e:
        print(f"WARN: chunked retrieval failed: {e}", flush=True)

    out_payload = {
        "checked_at_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "ssm_command_id": cid,
        "ssm_status": inv["Status"],
        "verdict": verdict,
        "user_roles": roles_data,
        "queue_summary": queue_summary,
        "full_data": full_data,
        "raw_stderr": stderr[-2000:],
    }
    OUT.write_text(json.dumps(out_payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {OUT}", flush=True)

    # Print a quick verdict summary
    print("\n=== Verdict summary ===")
    for v in (verdict or []):
        print(f"  {v['order_name']:25s} exists={v['exists']:1}  status={v['status']}  "
              f"approved_at={v['approved_at']}  pending_q={v['approval_queue_pending_count']}  "
              f"area_no_filter={v['visible_to_test_area_no_filter']}  area_pending={v['visible_to_test_area_pending_filter']}  "
              f"scm_no_filter={v['visible_to_test_scm_no_filter']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
