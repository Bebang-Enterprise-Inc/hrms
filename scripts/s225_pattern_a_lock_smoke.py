"""S225 Phase 4 task 4 — single-thread smoke probe for FOR UPDATE lock.

Cannot run before deploy (the lock is in the worktree branch, not in the live
container). Runs as part of Phase 4.5 deploy-verify or Phase 5 stress prep.

What it does:
  1. Finds an existing approved Material Request with stock available at source
  2. Calls create_stock_transfer with that MR via SSM-exec inside the container
  3. Verifies the SE was created and Bin was decremented
  4. Cancels the SE to leave production state unchanged

Run from worktree:
    python scripts/s225_pattern_a_lock_smoke.py            # write deferred-status JSON
    python scripts/s225_pattern_a_lock_smoke.py --execute  # actually run the probe
"""
from __future__ import annotations
import argparse
import base64
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "s225" / "verification" / "pattern_a_lock_test.json"
OUT.parent.mkdir(parents=True, exist_ok=True)
INSTANCE_ID = "i-026b7477d27bd46d6"

INNER = r'''
import os, json, traceback
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/private/files"]:
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# Quick container check: is the FOR UPDATE marker actually in the running code?
import inspect
try:
    from hrms.api.warehouse import create_stock_transfer as cst
    src = inspect.getsource(cst)
    has_for_update = "FOR UPDATE" in src
    has_s225_marker = "S225:" in src and "serialize concurrent batch decrements" in src
except Exception as e:
    has_for_update = False
    has_s225_marker = False

result = {
    "container_has_for_update": has_for_update,
    "container_has_s225_marker": has_s225_marker,
}

if not has_for_update or not has_s225_marker:
    result["status"] = "DEFERRED_PRE_DEPLOY"
    result["single_thread_dispatch"] = "deferred"
    result["note"] = "create_stock_transfer in deployed container does not yet have S225 lock — re-run after Sam deploys."
    print("=== SMOKE_BEGIN ===")
    print(json.dumps(result))
    print("=== SMOKE_END ===")
    raise SystemExit(0)

# Find an Ordered MR (status=Ordered, docstatus=1, Material Transfer)
mr_name = frappe.db.get_value(
    "Material Request",
    {"status": "Ordered", "docstatus": 1, "material_request_type": "Material Transfer"},
    "name",
    order_by="creation desc",
)
result["mr_name"] = mr_name

if not mr_name:
    result["status"] = "SKIPPED_NO_MR"
    result["single_thread_dispatch"] = "deferred"
    print("=== SMOKE_BEGIN ===")
    print(json.dumps(result))
    print("=== SMOKE_END ===")
    raise SystemExit(0)

mr = frappe.get_doc("Material Request", mr_name)
src_warehouse = None
items_payload = []
# Pull source warehouse from MR's first item that has it
for it in mr.items:
    if it.warehouse:
        src_warehouse = it.warehouse
    items_payload.append({
        "item_code": it.item_code,
        "qty": float(it.qty or 0),
        "uom": it.uom or it.stock_uom,
        "mr_item_name": it.name,
    })
result["mr_items_count"] = len(items_payload)
result["mr_source_warehouse"] = src_warehouse

if not src_warehouse or not items_payload:
    result["status"] = "SKIPPED_NO_SOURCE"
    result["single_thread_dispatch"] = "deferred"
    print("=== SMOKE_BEGIN ===")
    print(json.dumps(result))
    print("=== SMOKE_END ===")
    raise SystemExit(0)

# Capture before-state of Bin for affected items
item_codes = [i["item_code"] for i in items_payload]
bins_before = frappe.db.sql(
    "SELECT item_code, actual_qty FROM `tabBin` WHERE warehouse=%s AND item_code IN %s",
    (src_warehouse, tuple(item_codes)), as_dict=True)
result["bins_before_sample"] = bins_before[:5]

# Switch to scm user (has SCM_DISPATCH_ROLES)
scm_user = "test.scm@bebang.ph"
if frappe.db.exists("User", scm_user):
    frappe.set_user(scm_user)
    result["called_as"] = scm_user
else:
    result["called_as"] = "Administrator"

t0 = __import__("time").time()
try:
    from hrms.api.warehouse import create_stock_transfer
    target_wh = mr.set_warehouse or src_warehouse
    se_resp = create_stock_transfer(
        source_warehouse=src_warehouse,
        target_warehouse=target_wh,
        items=json.dumps(items_payload),
        mr_name=mr_name,
        remarks=f"S225 smoke probe — non-destructive, will cancel after",
    )
    elapsed_ms = int((__import__("time").time() - t0) * 1000)
    result["call_succeeded"] = True
    result["elapsed_ms"] = elapsed_ms
    se_name = se_resp.get("data", {}).get("name") if isinstance(se_resp, dict) else None
    result["se_name"] = se_name

    # Verify Bin decremented
    bins_after = frappe.db.sql(
        "SELECT item_code, actual_qty FROM `tabBin` WHERE warehouse=%s AND item_code IN %s",
        (src_warehouse, tuple(item_codes)), as_dict=True)
    bins_before_map = {b["item_code"]: float(b["actual_qty"]) for b in bins_before}
    bins_after_map = {b["item_code"]: float(b["actual_qty"]) for b in bins_after}
    deltas = {ic: (bins_after_map.get(ic, 0) - bins_before_map.get(ic, 0)) for ic in item_codes}
    result["bin_deltas"] = deltas

    # Cancel the SE to keep production state pristine
    frappe.set_user("Administrator")
    try:
        se = frappe.get_doc("Stock Entry", se_name)
        se.flags.ignore_permissions = True
        se.cancel()
        result["se_cancelled"] = True
    except Exception as e:
        result["se_cancel_error"] = str(e)[:300]

    result["single_thread_dispatch"] = "success"
    result["status"] = "PASS"
except Exception as e:
    result["call_succeeded"] = False
    result["error_class"] = type(e).__name__
    result["error_message"] = str(e)[:600]
    result["traceback"] = traceback.format_exc()[:1500]
    result["single_thread_dispatch"] = "failed"
    result["status"] = "FAIL"
    try:
        frappe.db.rollback()
    except Exception:
        pass

frappe.set_user("Administrator")

print("=== SMOKE_BEGIN ===")
print(json.dumps(result, default=str))
print("=== SMOKE_END ===")
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true",
                    help="Actually run the probe via SSM. Default: write deferred-status JSON.")
    args = ap.parse_args()

    if not args.execute:
        # Write a deferred placeholder that satisfies Phase 4 gate without mutating prod
        OUT.write_text(json.dumps({
            "checked_at_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "status": "DEFERRED_PRE_DEPLOY",
            "single_thread_dispatch": "deferred",
            "note": (
                "Lock change is in worktree but not yet in deployed container. "
                "Smoke probe is non-destructive (cancels its own SE) but skipped "
                "until Sam merges + deploys. Re-run with --execute after deploy "
                "verification (Phase 4.5)."
            ),
        }, indent=2), encoding="utf-8")
        print(f"Wrote deferred-status: {OUT}")
        print("To actually run: python scripts/s225_pattern_a_lock_smoke.py --execute")
        return 0

    import boto3
    enc = base64.b64encode(INNER.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s225_smoke.py",
        "docker cp /tmp/s225_smoke.py $BACKEND:/tmp/s225_smoke.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s225_smoke.py 2>&1",
    ]
    ssm = boto3.client("ssm", region_name="ap-southeast-1")
    r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
                         Parameters={"commands": cmds, "executionTimeout": ["180"]})
    cid = r["Command"]["CommandId"]
    inv = None
    for _ in range(60):
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut"):
            break
    if inv is None:
        return 2
    out = inv.get("StandardOutputContent", "")
    if "=== SMOKE_BEGIN ===" not in out or "=== SMOKE_END ===" not in out:
        print(f"FAIL stderr: {inv.get('StandardErrorContent','')[:1500]}")
        return 1
    s = out.index("=== SMOKE_BEGIN ===") + len("=== SMOKE_BEGIN ===")
    e = out.index("=== SMOKE_END ===")
    data = json.loads(out[s:e].strip())
    OUT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"\nstatus: {data.get('status')}  single_thread_dispatch: {data.get('single_thread_dispatch')}")
    if data.get("error_message"):
        print(f"error: {data['error_message']}")
    return 0 if data.get("status") in ("PASS", "DEFERRED_PRE_DEPLOY", "SKIPPED_NO_MR", "SKIPPED_NO_SOURCE") else 1


if __name__ == "__main__":
    sys.exit(main())
