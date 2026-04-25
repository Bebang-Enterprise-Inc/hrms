#!/usr/bin/env python3
"""S223 Pattern A probe - direct SSM call to create_stock_transfer for failing Pattern A stores.

Captures the actual backend exception/response for AYALA SOLENAD (Pattern A representative)
vs ARANETA GATEWAY (control - works) so we can identify the specific failure mode WITHOUT
needing live browser access.

For each store:
1. Submit a fresh DRY order via test.area
2. Approve via test.area approve_order (first approval)
3. SCM approve via approve_material_request
4. Call create_stock_transfer directly with same params the UI would send
5. Capture: exception type, error message, full traceback, MR state, source warehouse stock

Outputs: output/s223/verification/pattern_a_probe_results.json
"""
from __future__ import annotations
import base64
import gzip
import json
import pathlib
import subprocess
import sys
import time

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"
OUT = pathlib.Path(__file__).resolve().parent.parent / "output" / "s223" / "verification" / "pattern_a_probe_results.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

# Probe targets
PATTERN_A_STORE = "AYALA SOLENAD - HFFM SOLENAD FOOD SERVICES INC."  # representative failing store
CONTROL_STORE = "ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC"  # known PASS in S221+S222

SCRIPT = '''
import json, traceback, time
import frappe

frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()

PATTERN_A_STORE = ''' + json.dumps(PATTERN_A_STORE) + '''
CONTROL_STORE = ''' + json.dumps(CONTROL_STORE) + '''

from hrms.api.store import submit_order, get_orderable_items, approve_order
from hrms.api.warehouse import (
    create_stock_transfer,
    approve_material_request,
    get_pending_material_requests,
)


def probe_store(wh_name):
    """Probe one store: submit -> approve -> dispatch and capture error if any."""
    result = {"wh": wh_name, "stages": {}, "created_docs": []}

    try:
        # Stage 1: submit order as test.area
        frappe.set_user("test.area@bebang.ph")
        items_resp = get_orderable_items(wh_name, None, 0)
        dry = [i for i in (items_resp.get("items") or [])
               if (i.get("cargo_category") or i.get("delivery_lane", "")) in ("DRY", "Dry")]
        if not dry:
            result["stages"]["submit"] = {"error": "no DRY items"}
            return result
        picks = []
        for i in dry[:3]:
            sug = float(i.get("suggested_qty") or 0)
            qty = max(1, int(sug)) if sug > 0 else 5
            picks.append({
                "item_code": i["item_code"],
                "qty_requested": qty,
                "suggested_qty": sug,
                "recommended_qty": sug,
                "unit_price": i.get("unit_price", 0),
                "deviation_reason": "" if qty == int(sug) else "Stock Correction",
            })
        sub_result = submit_order(store=wh_name, cargo_category="DRY",
                                  notes="S223 Pattern A probe",
                                  delivery_date=None, items=picks)
        order_name = (sub_result or {}).get("name")
        result["stages"]["submit"] = {"order_name": order_name, "ok": bool(order_name),
                                       "submit_resp": sub_result}
        if order_name:
            result["created_docs"].append(("BEI Store Order", order_name))
        if not order_name:
            return result

        # Stage 2: approve order via test.area approve_order
        try:
            doc = frappe.get_doc("BEI Store Order", order_name)
            if doc.status not in ("Approved",):
                approve_resp = approve_order(order_name=order_name)
                result["stages"]["approve_order"] = {"resp": approve_resp}
            else:
                result["stages"]["approve_order"] = {"already_approved": True}
        except Exception as e:
            result["stages"]["approve_order"] = {
                "error": "%s: %s" % (type(e).__name__, str(e)[:300]),
                "tb": traceback.format_exc()[:500],
            }
        frappe.db.commit()

        # Stage 3: SCM approve to create MR
        time.sleep(1)
        frappe.set_user("test.scm@bebang.ph")
        # Find MR for this store. After scm approval the MR may already exist
        # or may need to be created by approve_material_request
        mr_name = frappe.db.get_value("Material Request",
                                      {"custom_store_order": order_name},
                                      "name")
        result["stages"]["mr_lookup_pre_scm"] = {"mr_name": mr_name}

        if mr_name:
            mr_doc = frappe.get_doc("Material Request", mr_name)
            if mr_doc.status not in ("Ordered", "Partially Ordered", "Transferred"):
                try:
                    approved_items_payload = json.dumps([
                        {"item_code": p["item_code"], "approved_qty": p["qty_requested"]}
                        for p in picks
                    ])
                    am_resp = approve_material_request(mr_name=mr_name,
                                                       approved_items=approved_items_payload)
                    result["stages"]["scm_approve"] = {"resp": am_resp, "mr_name": mr_name}
                except Exception as e:
                    result["stages"]["scm_approve"] = {
                        "error": "%s: %s" % (type(e).__name__, str(e)[:300]),
                        "tb": traceback.format_exc()[:500],
                    }
        frappe.db.commit()
        time.sleep(1)

        # Re-resolve MR
        mr_name = frappe.db.get_value("Material Request",
                                      {"custom_store_order": order_name, "docstatus": 1},
                                      "name")
        result["stages"]["mr_lookup_post_scm"] = {"mr_name": mr_name}

        if not mr_name:
            result["stages"]["mr_lookup_post_scm"]["error"] = "no submitted MR found"
            return result

        if mr_name:
            result["created_docs"].append(("Material Request", mr_name))

        # Stage 4: probe create_stock_transfer with the actual data
        mr = frappe.get_doc("Material Request", mr_name)
        # Determine source warehouse from MR.set_from_warehouse or item.from_warehouse
        source_wh = getattr(mr, "set_from_warehouse", None) or getattr(mr, "from_warehouse", None)
        if not source_wh and mr.items:
            for it in mr.items:
                if it.from_warehouse:
                    source_wh = it.from_warehouse
                    break
        target_wh = mr.set_warehouse or wh_name
        items_for_transfer = [
            {"item_code": it.item_code, "qty": float(it.qty), "uom": it.uom, "mr_item_name": it.name}
            for it in mr.items
        ]
        result["stages"]["dispatch_setup"] = {
            "mr_name": mr_name, "source_wh": source_wh, "target_wh": target_wh,
            "item_count": len(items_for_transfer), "mr_status": mr.status,
        }

        # Probe stock at source warehouse
        stock_probes = []
        for it in mr.items[:3]:
            actual_qty = frappe.db.sql(
                "SELECT SUM(actual_qty) as q FROM `tabBin` WHERE warehouse=%s AND item_code=%s",
                (source_wh or "", it.item_code), as_dict=True,
            )
            stock_probes.append({
                "item_code": it.item_code,
                "needed_qty": float(it.qty),
                "available_qty": float((actual_qty[0].get("q") if actual_qty else 0) or 0),
            })
        result["stages"]["stock_probe"] = stock_probes

        # The actual create_stock_transfer call
        try:
            frappe.db.savepoint("s223_dispatch_probe")
            cst_result = create_stock_transfer(
                source_warehouse=source_wh,
                target_warehouse=target_wh,
                items=json.dumps(items_for_transfer),
                mr_name=mr_name,
                remarks="S223 probe - savepoint rollback",
            )
            result["stages"]["create_stock_transfer"] = {
                "ok": True, "result": cst_result,
            }
            # Roll back so we don't leave a dangling SE
            frappe.db.rollback(save_point="s223_dispatch_probe")
        except Exception as e:
            result["stages"]["create_stock_transfer"] = {
                "ok": False,
                "exception_type": type(e).__name__,
                "exception_msg": str(e)[:1500],
                "traceback": traceback.format_exc()[:3000],
            }
            try:
                frappe.db.rollback(save_point="s223_dispatch_probe")
            except Exception:
                pass

    except Exception as e:
        result["fatal_error"] = "%s: %s" % (type(e).__name__, str(e)[:500])
        result["fatal_tb"] = traceback.format_exc()[:1500]

    return result


def cleanup_docs(docs):
    """Cancel/delete created docs to keep the env clean."""
    frappe.set_user("Administrator")
    cleaned = []
    for dt, name in reversed(docs):  # MR first, then Order
        try:
            doc = frappe.get_doc(dt, name)
            if doc.docstatus == 1:
                doc.cancel()
            elif doc.docstatus == 0:
                frappe.delete_doc(dt, name, force=1)
            cleaned.append((dt, name, "ok"))
        except Exception as e:
            cleaned.append((dt, name, "fail:%s" % type(e).__name__))
    frappe.db.commit()
    return cleaned


payload = {"control": probe_store(CONTROL_STORE),
           "pattern_a": probe_store(PATTERN_A_STORE)}

# Cleanup all created docs
all_docs = payload["control"].get("created_docs", []) + payload["pattern_a"].get("created_docs", [])
payload["cleanup"] = cleanup_docs(all_docs)

import gzip as _gz, base64 as _b64
compressed = _gz.compress(json.dumps(payload, default=str).encode())
print("__B64_START__")
print(_b64.b64encode(compressed).decode())
print("__B64_END__")
frappe.destroy()
'''


def run(timeout: int = 600) -> str:
    """Execute the probe via SSM with docker exec pattern from s220."""
    import boto3

    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(SCRIPT.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        "if [ -z \"$BACKEND\" ]; then echo 'NO_BACKEND_CONTAINER' >&2; exit 1; fi",
        f"echo '{enc}' | base64 -d > /tmp/s223pa.py",
        "docker cp /tmp/s223pa.py $BACKEND:/tmp/s223pa.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s223pa.py",
    ]
    r = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": [str(timeout)]},
    )
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}", flush=True)
    deadline = time.time() + timeout + 30
    while time.time() < deadline:
        time.sleep(8)
        try:
            inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        except ssm.exceptions.InvocationDoesNotExist:
            continue
        status = inv["Status"]
        if status in ("Success", "Failed", "TimedOut", "Cancelled"):
            out = inv.get("StandardOutputContent", "")
            if status != "Success":
                sys.stderr.write("[stderr]\n" + inv.get("StandardErrorContent", "") + "\n")
            return out
        # Print progress
        print(f"  status={status}...", flush=True)
    raise TimeoutError(f"probe timed out after {timeout}s")


def main() -> int:
    out = run()
    s = out.find("__B64_START__")
    e = out.find("__B64_END__")
    if s < 0 or e < 0:
        sys.stderr.write("[probe output - no markers]\n" + out[:5000] + "\n")
        return 1
    b64 = out[s + len("__B64_START__"):e].strip()
    data = json.loads(gzip.decompress(base64.b64decode(b64)).decode())
    OUT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print(f"Wrote: {OUT}")

    print()
    print("=" * 70)
    for label in ("control", "pattern_a"):
        store_data = data[label]
        wh = store_data["wh"]
        print(f"=== {label.upper()}: {wh} ===")
        cst = store_data.get("stages", {}).get("create_stock_transfer", {})
        if cst.get("ok"):
            res = cst.get("result", {})
            print(f"  create_stock_transfer OK -> SE: {res.get('data', {}).get('name', '?')}")
        else:
            print(f"  create_stock_transfer FAILED:")
            print(f"    exception: {cst.get('exception_type', '?')}")
            print(f"    msg: {cst.get('exception_msg', '?')[:300]}")
        stk = store_data.get("stages", {}).get("stock_probe", [])
        for s_p in stk:
            print(f"    stock {s_p['item_code']}: needed={s_p['needed_qty']} avail={s_p['available_qty']}")
    print()
    print(f"Cleanup: {data.get('cleanup', [])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
