"""S226 — pull the full BEI Approval Queue timeline for a single order to understand
why so many entries get created.
"""
from __future__ import annotations
import base64, json, pathlib, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "s225" / "verification" / "timeline_one_order.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

INSTANCE_ID = "i-026b7477d27bd46d6"
TARGET_ORDER = "BEI-ORD-2026-00408"

INNER = f'''
import os, json
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/private/files"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

TARGET = "{TARGET_ORDER}"

# Pull all queue rows for this order
rows = frappe.db.sql("""
    SELECT name, status, assigned_approver, approved_by, approved_at,
           submitted_at, creation, modified
    FROM `tabBEI Approval Queue`
    WHERE reference_doctype='BEI Store Order' AND reference_name=%s
    ORDER BY creation
""", (TARGET,), as_dict=True)

# Pull the order's audit trail (Comment doctype)
comments = frappe.db.sql("""
    SELECT name, comment_type, content, owner, creation
    FROM `tabComment`
    WHERE reference_doctype='BEI Store Order' AND reference_name=%s
    ORDER BY creation
""", (TARGET,), as_dict=True)

# Pull associated MR if any
mr_rows = frappe.db.sql("""
    SELECT name, status, custom_store_order, creation
    FROM `tabMaterial Request`
    WHERE custom_store_order=%s
    ORDER BY creation
""", (TARGET,), as_dict=True)

# Pull ToDo entries for this order
todos = frappe.db.sql("""
    SELECT name, allocated_to, status, owner, creation
    FROM `tabToDo`
    WHERE reference_type='BEI Store Order' AND reference_name=%s
    ORDER BY creation
""", (TARGET,), as_dict=True)

# Compress everything to a small payload
out = {{
    "queue_rows": [
        {{
            "name": r["name"],
            "status": r["status"],
            "assigned": r["assigned_approver"],
            "approved_by": r.get("approved_by"),
            "approved_at": str(r.get("approved_at")) if r.get("approved_at") else None,
            "creation": str(r["creation"]),
        }} for r in rows
    ],
    "comments": [
        {{"creation": str(c["creation"]), "owner": c["owner"], "content": c["content"][:200]}}
        for c in comments
    ],
    "material_requests": [
        {{"name": m["name"], "status": m["status"], "creation": str(m["creation"])}} for m in mr_rows
    ],
    "todos": [
        {{"name": t["name"], "allocated_to": t["allocated_to"], "status": t["status"], "creation": str(t["creation"])}}
        for t in todos
    ],
}}
print("=== TIMELINE_BEGIN ===")
print(json.dumps(out, default=str))
print("=== TIMELINE_END ===")
'''


def main() -> int:
    import boto3
    enc = base64.b64encode(INNER.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s226_timeline.py",
        "docker cp /tmp/s226_timeline.py $BACKEND:/tmp/s226_timeline.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s226_timeline.py",
    ]
    ssm = boto3.client("ssm", region_name="ap-southeast-1")
    r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
                         Parameters={"commands": cmds, "executionTimeout": ["120"]})
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
    if "=== TIMELINE_BEGIN ===" not in stdout or "=== TIMELINE_END ===" not in stdout:
        print(f"FAIL stderr={inv.get('StandardErrorContent', '')[:1500]}\nstdout tail={stdout[-2000:]}")
        return 1
    s = stdout.index("=== TIMELINE_BEGIN ===") + len("=== TIMELINE_BEGIN ===")
    e = stdout.index("=== TIMELINE_END ===")
    data = json.loads(stdout[s:e].strip())
    OUT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {OUT}\n")

    print(f"=== Queue rows for {TARGET_ORDER} (chronological) ===")
    for q in data["queue_rows"]:
        print(f"  {q['creation']}  {q['status']:8}  assigned={q['assigned']:25}  approved_by={q.get('approved_by') or '-':25}  qname={q['name']}")
    print(f"\n=== Order comments (timeline of what happened) ===")
    for c in data["comments"][-30:]:
        print(f"  {c['creation']}  by={c['owner']}  {c['content'][:150]}")
    print(f"\n=== Material Requests for this order ===")
    for m in data["material_requests"]:
        print(f"  {m['creation']}  {m['name']:30}  status={m['status']}")
    print(f"\n=== ToDo entries ===")
    for t in data["todos"]:
        print(f"  {t['creation']}  {t['name']:30}  allocated={t['allocated_to']:25}  status={t['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
