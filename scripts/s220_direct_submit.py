#!/usr/bin/env python3
"""S220 direct-compare — submit fresh orders to ARANETA + FESTIVAL MALL, inspect backend state."""
import base64, gzip, json, pathlib, sys, time

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"
OUT = pathlib.Path(__file__).resolve().parent.parent / "output" / "l3" / "s220" / "direct_submit_probe.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

SCRIPT = '''
import json, base64, gzip
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("test.area@bebang.ph")

from hrms.api.store import submit_order, get_orderable_items

def submit_for_wh(wh_name):
    # Get orderable items
    items_resp = get_orderable_items(wh_name, None, 0)
    picks = []
    # Filter to DRY items only
    dry = [i for i in (items_resp.get("items") or []) if (i.get("cargo_category") or i.get("delivery_lane", "")) in ("DRY", "Dry")]
    for i in dry[:3]:
        sug = float(i.get("suggested_qty") or 0)
        if sug <= 0:
            continue
        # Force deviation: pick qty != suggested
        qty = max(1, int(sug / 2))
        if qty == int(sug):
            qty = max(1, qty - 1)
        picks.append({
            "item_code": i["item_code"],
            "qty_requested": qty,
            "suggested_qty": sug,
            "recommended_qty": sug,
            "unit_price": i.get("unit_price", 0),
            "deviation_reason": "Stock Correction" if qty != sug else "",
        })
    if not picks:
        return {"error": "no picks available", "wh": wh_name}
    result = submit_order(
        store=wh_name, cargo_category="DRY", notes="S220 probe",
        delivery_date=None, items=picks,
    )
    return {"picks": picks, "result": result, "wh": wh_name}


def inspect(order_name):
    if not order_name:
        return None
    doc = frappe.get_doc("BEI Store Order", order_name)
    queue = frappe.db.sql(
        """SELECT name, status, assigned_approver FROM `tabBEI Approval Queue`
           WHERE reference_doctype='BEI Store Order' AND reference_name=%s""",
        (order_name,), as_dict=True,
    )
    items = frappe.db.sql(
        """SELECT item_code, qty_requested, suggested_qty, is_edited
           FROM `tabBEI Store Order Item` WHERE parent=%s""",
        (order_name,), as_dict=True,
    )
    return {
        "order": order_name,
        "status": doc.status,
        "approval_stage": doc.approval_stage,
        "requires_dual_approval": doc.requires_dual_approval,
        "queue_entries": queue,
        "items": items,
        "edited_count": sum(1 for i in items if i["is_edited"]),
    }


aranete_result = submit_for_wh("ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC")
festival_result = submit_for_wh("FESTIVAL MALL ALABANG - BEBANG FESTIVAL INC.")

frappe.db.commit()

aranete_order = (aranete_result.get("result") or {}).get("name")
festival_order = (festival_result.get("result") or {}).get("name")

# Now check UI filter from test.area perspective
from hrms.api.ordering import get_order_review_queue
ui = get_order_review_queue(date=None, status=None)
visible = {o["name"] for o in ui.get("orders", [])}

payload = {
    "aranete_submit": aranete_result,
    "festival_submit": festival_result,
    "aranete_backend_state": inspect(aranete_order),
    "festival_backend_state": inspect(festival_order),
    "ui_visible_to_test_area": {
        "total": len(ui.get("orders", [])),
        "aranete_visible": aranete_order in visible if aranete_order else False,
        "festival_visible": festival_order in visible if festival_order else False,
    },
}

# Cleanup
frappe.set_user("Administrator")
for name in (aranete_order, festival_order):
    if name:
        try:
            doc = frappe.get_doc("BEI Store Order", name)
            if doc.docstatus == 0:
                frappe.delete_doc("BEI Store Order", name, force=1)
            elif doc.docstatus == 1:
                doc.cancel()
            frappe.db.commit()
        except Exception:
            pass

compressed = gzip.compress(json.dumps(payload, default=str).encode())
print("__B64_START__")
print(base64.b64encode(compressed).decode())
print("__B64_END__")
frappe.destroy()
'''


def run(timeout=180):
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(SCRIPT.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s220d.py",
        "docker cp /tmp/s220d.py $BACKEND:/tmp/s220d.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s220d.py",
    ]
    r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": [str(timeout)]})
    cid = r["Command"]["CommandId"]; print(f"CommandId: {cid}")
    deadline = time.time() + timeout + 30
    while time.time() < deadline:
        time.sleep(4)
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
print("=== ARANETA (PASS-pattern) ===")
ar = data.get("aranete_backend_state") or {}
print(f"  Order={ar.get('order')} status={ar.get('status')} stage={ar.get('approval_stage')}")
print(f"  requires_dual={ar.get('requires_dual_approval')} edited_lines={ar.get('edited_count')}")
print(f"  Queue entries: {len(ar.get('queue_entries') or [])}")
for q in ar.get("queue_entries") or []:
    print(f"    - {q['name']} | status={q['status']} | approver={q['assigned_approver']}")
print()
print("=== FESTIVAL MALL (FAIL-pattern) ===")
fs = data.get("festival_backend_state") or {}
print(f"  Order={fs.get('order')} status={fs.get('status')} stage={fs.get('approval_stage')}")
print(f"  requires_dual={fs.get('requires_dual_approval')} edited_lines={fs.get('edited_count')}")
print(f"  Queue entries: {len(fs.get('queue_entries') or [])}")
for q in fs.get("queue_entries") or []:
    print(f"    - {q['name']} | status={q['status']} | approver={q['assigned_approver']}")
print()
ui = data.get("ui_visible_to_test_area") or {}
print(f"=== UI FILTER (test.area view) ===")
print(f"  Total orders visible: {ui.get('total')}")
print(f"  ARANETA visible: {ui.get('aranete_visible')}")
print(f"  FESTIVAL visible: {ui.get('festival_visible')}")
