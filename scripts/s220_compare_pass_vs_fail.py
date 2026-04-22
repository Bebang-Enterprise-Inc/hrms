#!/usr/bin/env python3
"""S220 — compare one PASSING vs one FAILING order's backend state to find UI filter divergence."""
import base64, gzip, json, pathlib, sys, time

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"
OUT = pathlib.Path(__file__).resolve().parent.parent / "output" / "l3" / "s220" / "pass_vs_fail_probe.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

# Fresh orders from the most recent sweep (S219). Check the pass/fail state.
SCRIPT = '''
import json, base64, gzip
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()

# Find recent orders matching known PASS (ARANETA) and FAIL (FESTIVAL MALL) stores
def last_order_for_store_name_like(pattern):
    rows = frappe.db.sql(
        """SELECT name, store, status, approval_stage, owner, creation, is_bulk_order,
                  is_emergency, submitted_by, approved_by, approved_at
           FROM `tabBEI Store Order`
           WHERE store LIKE %s AND creation >= '2026-04-22 09:00:00'
           ORDER BY creation DESC LIMIT 1""",
        (f"%{pattern}%",), as_dict=True,
    )
    return rows[0] if rows else None

pass_order = last_order_for_store_name_like("ARANETA GATEWAY")
fail_order = last_order_for_store_name_like("FESTIVAL MALL ALABANG")

def enrich(order):
    if not order:
        return None
    # Full order doc
    doc = frappe.get_doc("BEI Store Order", order["name"])
    # Approval queue entries
    queue = frappe.db.sql(
        """SELECT name, status, assigned_approver, submitted_at, reference_name
           FROM `tabBEI Approval Queue`
           WHERE reference_doctype='BEI Store Order' AND reference_name=%s""",
        (order["name"],), as_dict=True,
    )
    # ToDo assignments
    todos = frappe.db.sql(
        """SELECT name, allocated_to, description, status
           FROM `tabToDo` WHERE reference_type='BEI Store Order' AND reference_name=%s""",
        (order["name"],), as_dict=True,
    )
    # Items with is_edited status
    items = frappe.db.sql(
        """SELECT item_code, qty_requested, suggested_qty, is_edited, deviation_reason
           FROM `tabBEI Store Order Item` WHERE parent=%s""",
        (order["name"],), as_dict=True,
    )
    return {
        "order": order,
        "docstatus": doc.docstatus,
        "requires_dual_approval": getattr(doc, "requires_dual_approval", None),
        "approval_stage": doc.approval_stage,
        "queue_entries": queue,
        "todos": todos,
        "items": items,
    }

payload = {
    "pass_example": enrich(pass_order),
    "fail_example": enrich(fail_order),
}

# Also run the UI filter query as test.area would see it
from hrms.api.ordering import get_order_review_queue as queue_fn
frappe.set_user("test.area@bebang.ph")
try:
    result = queue_fn(date=None, status=None)
    # Filter to just these two orders
    both_names = [o["name"] for o in [pass_order, fail_order] if o]
    payload["ui_filter_visible_to_test_area"] = [
        {"name": o["name"], "status": o["status"], "approval_stage": o.get("approval_stage"),
         "current_approver": o.get("current_approver"), "approval_queue_name": o.get("approval_queue_name")}
        for o in result.get("orders", [])
        if o["name"] in both_names
    ]
    payload["ui_filter_total_orders_visible"] = len(result.get("orders", []))
except Exception as e:
    payload["ui_filter_error"] = repr(e)
finally:
    frappe.set_user("Administrator")

compressed = gzip.compress(json.dumps(payload, default=str).encode())
print("__B64_START__")
print(base64.b64encode(compressed).decode())
print("__B64_END__")
frappe.destroy()
'''


def run(timeout=120):
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(SCRIPT.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s220.py",
        "docker cp /tmp/s220.py $BACKEND:/tmp/s220.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s220.py",
    ]
    r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": [str(timeout)]})
    cid = r["Command"]["CommandId"]; print(f"CommandId: {cid}")
    deadline = time.time() + timeout + 30
    while time.time() < deadline:
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut", "Cancelled"):
            out = inv.get("StandardOutputContent", "")
            if inv["Status"] != "Success":
                sys.stderr.write(inv.get("StandardErrorContent", ""))
            return out
    raise TimeoutError()

out = run()
s = out.find("__B64_START__"); e = out.find("__B64_END__")
if s < 0:
    print(out); sys.exit(1)
b64 = out[s+len("__B64_START__"):e].strip()
data = json.loads(gzip.decompress(base64.b64decode(b64)).decode())
OUT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
print(f"Wrote {OUT}")
print()
print("=== PASS EXAMPLE (ARANETA) ===")
if data.get("pass_example"):
    p = data["pass_example"]
    print(f"  Order: {p['order']['name']} | status={p['order']['status']} | stage={p['order']['approval_stage']}")
    print(f"  owner={p['order']['owner']} | approved_by={p['order'].get('approved_by')}")
    print(f"  Queue entries: {len(p['queue_entries'])}")
    for q in p["queue_entries"]:
        print(f"    - {q['name']} | status={q['status']} | approver={q['assigned_approver']}")
    print(f"  Items (first 2):")
    for i in p["items"][:2]:
        print(f"    - {i['item_code']}: qty_req={i['qty_requested']} sug={i['suggested_qty']} edited={i['is_edited']}")
print()
print("=== FAIL EXAMPLE (FESTIVAL MALL) ===")
if data.get("fail_example"):
    f = data["fail_example"]
    print(f"  Order: {f['order']['name']} | status={f['order']['status']} | stage={f['order']['approval_stage']}")
    print(f"  owner={f['order']['owner']} | approved_by={f['order'].get('approved_by')}")
    print(f"  Queue entries: {len(f['queue_entries'])}")
    for q in f["queue_entries"]:
        print(f"    - {q['name']} | status={q['status']} | approver={q['assigned_approver']}")
    print(f"  Items (first 2):")
    for i in f["items"][:2]:
        print(f"    - {i['item_code']}: qty_req={i['qty_requested']} sug={i['suggested_qty']} edited={i['is_edited']}")
print()
print(f"=== UI FILTER (test.area) ===")
print(f"  Total orders visible: {data.get('ui_filter_total_orders_visible')}")
for o in data.get("ui_filter_visible_to_test_area", []):
    print(f"  - {o['name']} | status={o['status']} | stage={o.get('approval_stage')} | approver={o.get('current_approver')}")
