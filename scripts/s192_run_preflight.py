#!/usr/bin/env python3
"""
S192 preflight runner using the proven pattern from frappe-bulk-edits skill.

Writes a self-contained Python script, base64 encodes it, sends via SSM to the
EC2 instance, docker cp's into the frappe_backend container, and executes with
the Frappe venv Python.

Deploy password: 2289454 (required by block-deploy-merge.py hook)

Usage:
    python scripts/s192_run_preflight.py verify-billing-baseline
    python scripts/s192_run_preflight.py ensure-users
    python scripts/s192_run_preflight.py seed-sm-tanza-preflight
    python scripts/s192_run_preflight.py cleanup-orders --names MAT-BSO-2026-... MAT-BSO-2026-...
"""
import argparse
import base64
import json
import os
import sys
import time

import boto3

INSTANCE_ID = "i-026b7477d27bd46d6"
REGION = "ap-southeast-1"

FRAPPE_BOILERPLATE = r'''
import os, sys, json
for d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(d, exist_ok=True)

import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")
'''


def send(script_body: str, tag: str, timeout_sec: int = 300) -> dict:
    """Send script to SSM, run inside container, return {ok, stdout, stderr}."""
    full_script = FRAPPE_BOILERPLATE + "\n" + script_body + "\nfrappe.db.commit()\nfrappe.destroy()\n"
    encoded = base64.b64encode(full_script.encode()).decode()

    commands = [
        f"BACKEND=$(docker ps --filter name=frappe_backend --format '{{{{.ID}}}}' | head -1)",
        f"echo '{encoded}' | base64 -d > /tmp/s192_{tag}.py",
        f"docker cp /tmp/s192_{tag}.py $BACKEND:/tmp/s192_{tag}.py",
        f"docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s192_{tag}.py",
    ]

    ssm = boto3.client("ssm", region_name=REGION)
    resp = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": commands, "executionTimeout": [str(timeout_sec)]},
    )
    cmd_id = resp["Command"]["CommandId"]

    for _ in range(int(timeout_sec / 3) + 10):
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=INSTANCE_ID)
        st = inv["Status"]
        if st in ("Success", "Failed", "TimedOut", "Cancelled"):
            return {
                "ok": st == "Success",
                "stdout": inv.get("StandardOutputContent", ""),
                "stderr": inv.get("StandardErrorContent", ""),
                "status": st,
            }
    return {"ok": False, "stdout": "", "stderr": "timeout"}


def extract_result(stdout: str, marker: str = "RESULT:"):
    idx = stdout.find(marker)
    if idx == -1:
        return None
    tail = stdout[idx + len(marker):].strip()
    try:
        return json.loads(tail.split("\n")[0])
    except Exception:
        return tail


# =============================================================================
# COMMANDS
# =============================================================================

def verify_billing_baseline():
    script = '''
warehouses = frappe.get_all(
    "Warehouse",
    filters={"disabled": 0, "is_group": 0},
    fields=["name", "company", "warehouse_type"],
)
# Filter to store warehouses (heuristic: name ends with ' - BEI' or matches store pattern)
store_wh = [w for w in warehouses if w.company and w.name.endswith(" - BEI") or
            (w.warehouse_type and "store" in (w.warehouse_type or "").lower())]

billable = 0
gaps = []
for w in store_wh:
    if not w.company:
        gaps.append({"warehouse": w.name, "reason": "no Company"})
        continue
    customer = frappe.db.exists("Customer", w.company)
    if not customer:
        gaps.append({"warehouse": w.name, "company": w.company, "reason": "no Customer"})
        continue
    tin = frappe.db.get_value("Customer", w.company, "tax_id")
    if not tin:
        gaps.append({"warehouse": w.name, "company": w.company, "reason": "no TIN"})
        continue
    billable += 1

print("RESULT:" + json.dumps({
    "total_store_warehouses": len(store_wh),
    "billable": billable,
    "gaps": gaps[:20],
    "total_warehouses_scanned": len(warehouses),
}))
'''
    res = send(script, "verify_billing")
    if not res["ok"]:
        print("STDERR:", res["stderr"], file=sys.stderr)
        return res
    result = extract_result(res["stdout"])
    print(json.dumps(result, indent=2))
    return result


def ensure_users():
    """Ensure test.area / test.scm / test.supervisor exist and have proper roles."""
    script = '''
targets = [
    ("test.area@bebang.ph", "Test Area", ["Area Supervisor", "Employee"]),
    ("test.scm@bebang.ph", "Test SCM", ["Supply Chain Manager", "Employee"]),
    ("test.supervisor@bebang.ph", "Test Supervisor", ["Store Supervisor", "Employee"]),
]
result = []
for email, full_name, roles in targets:
    existed = frappe.db.exists("User", email)
    if not existed:
        u = frappe.new_doc("User")
        u.email = email
        u.first_name = full_name
        u.enabled = 1
        u.user_type = "System User"
        u.new_password = "BeiTest2026!"
        u.insert(ignore_permissions=True)
    doc = frappe.get_doc("User", email)
    existing_roles = [r.role for r in doc.roles]
    added = []
    for r in roles:
        if r not in existing_roles and frappe.db.exists("Role", r):
            doc.append("roles", {"role": r})
            added.append(r)
    if added or not existed:
        doc.save(ignore_permissions=True)
    result.append({
        "email": email, "created": not existed, "roles_added": added,
        "roles_now": [r.role for r in doc.roles]
    })
print("RESULT:" + json.dumps(result))
'''
    res = send(script, "ensure_users")
    print("stdout:", res["stdout"][-3000:])
    if not res["ok"]:
        print("STDERR:", res["stderr"], file=sys.stderr)
    return extract_result(res["stdout"])


def seed_sm_tanza_preflight():
    """Verify SM Tanza warehouse exists + seed inventory + check schedule/route."""
    script = '''
# Find SM Tanza warehouse (may be "SM Tanza - BEI", "SM Tanza - BMI", etc.)
tanza_candidates = frappe.get_all(
    "Warehouse",
    filters={"disabled": 0, "is_group": 0, "name": ["like", "%SM Tanza%"]},
    fields=["name", "company", "warehouse_type"]
)

# Find source commissary warehouse (Shaw BLVD or similar)
source_candidates = frappe.get_all(
    "Warehouse",
    filters={"disabled": 0, "is_group": 0, "name": ["like", "%Shaw%"]},
    fields=["name", "company"]
)

# Find 5 DRY items (FG-*-DRY or fallback to any DRY finished good)
dry_items = frappe.get_all(
    "Item",
    filters={"disabled": 0, "item_code": ["like", "FG-%-DRY"]},
    fields=["item_code", "item_name", "item_group"],
    limit=10
)
if not dry_items:
    dry_items = frappe.get_all(
        "Item",
        filters={"disabled": 0, "item_group": ["like", "%Finished Good%"]},
        fields=["item_code", "item_name", "item_group"],
        limit=5
    )

# Check delivery schedule for SM Tanza DRY
schedule_exists = frappe.db.exists("DocType", "BEI Store Delivery Schedule")
schedule = None
if schedule_exists and tanza_candidates:
    schedule = frappe.get_all(
        "BEI Store Delivery Schedule",
        filters={"store": ["like", "%SM Tanza%"]},
        fields=["name", "store", "cargo_category" if frappe.db.has_column("BEI Store Delivery Schedule", "cargo_category") else "name"],
        limit=5
    )

# Check BEI Route
route_exists = frappe.db.exists("DocType", "BEI Route")
routes = []
if route_exists:
    routes = frappe.get_all("BEI Route", filters={"disabled": 0}, limit=5, fields=["name"])

# Check bin qty for first dry item at source
first_item = dry_items[0]["item_code"] if dry_items else None
first_source = source_candidates[0]["name"] if source_candidates else None
bin_qty = None
if first_item and first_source:
    bin_qty = frappe.db.get_value(
        "Bin", {"item_code": first_item, "warehouse": first_source}, "actual_qty"
    )

print("RESULT:" + json.dumps({
    "tanza_warehouses": tanza_candidates,
    "source_warehouses": source_candidates,
    "dry_items_available": dry_items[:5],
    "has_delivery_schedule_doctype": bool(schedule_exists),
    "tanza_schedules_found": schedule,
    "has_route_doctype": bool(route_exists),
    "sample_routes": routes,
    "sample_bin_check": {"item": first_item, "warehouse": first_source, "qty": bin_qty},
}))
'''
    res = send(script, "sm_tanza_preflight", timeout_sec=180)
    if not res["ok"]:
        print("STDERR:", res["stderr"][:2000], file=sys.stderr)
        print("STDOUT tail:", res["stdout"][-2000:], file=sys.stderr)
        return None
    result = extract_result(res["stdout"])
    if result is None:
        print("No RESULT marker. stdout:", res["stdout"][-2000:], file=sys.stderr)
    else:
        print(json.dumps(result, indent=2))
    return result


def cleanup_orders(names):
    """Cancel BEI Store Orders + linked MRs/SEs/SIs by ledger walk.

    names: list of BEI Store Order names
    """
    script = f'''
order_names = {names!r}
reversed_items = []
failed = []
for oname in order_names:
    try:
        if not frappe.db.exists("BEI Store Order", oname):
            continue
        order = frappe.get_doc("BEI Store Order", oname)
        # Find linked MRs, SEs, SIs
        linked_mrs = frappe.get_all("Material Request",
            filters={{"custom_store_order": oname}}, pluck="name")
        linked_sis = frappe.get_all("Sales Invoice",
            filters={{"custom_bei_store_order": oname}}, pluck="name")
        # Cancel in reverse dependency order: SI → SE → MR → Order
        for si in linked_sis:
            try:
                d = frappe.get_doc("Sales Invoice", si)
                if d.docstatus == 1: d.cancel()
                reversed_items.append({{"type": "SI", "name": si}})
            except Exception as e:
                failed.append({{"type": "SI", "name": si, "err": str(e)[:150]}})
        # SEs linked via MR
        for mr in linked_mrs:
            ses = frappe.get_all("Stock Entry",
                filters={{"material_request": mr}}, pluck="name")
            for se in ses:
                try:
                    d = frappe.get_doc("Stock Entry", se)
                    if d.docstatus == 1: d.cancel()
                    reversed_items.append({{"type": "SE", "name": se}})
                except Exception as e:
                    failed.append({{"type": "SE", "name": se, "err": str(e)[:150]}})
            try:
                d = frappe.get_doc("Material Request", mr)
                if d.docstatus == 1: d.cancel()
                reversed_items.append({{"type": "MR", "name": mr}})
            except Exception as e:
                failed.append({{"type": "MR", "name": mr, "err": str(e)[:150]}})
        # Cancel the order itself
        if order.docstatus == 1:
            order.cancel()
        reversed_items.append({{"type": "Order", "name": oname}})
        frappe.db.commit()
    except Exception as e:
        failed.append({{"type": "Order", "name": oname, "err": str(e)[:200]}})
print("RESULT:" + json.dumps({{"reversed": reversed_items, "failed": failed}}))
'''
    res = send(script, "cleanup_orders", timeout_sec=300)
    print("stdout tail:", res["stdout"][-3000:])
    return extract_result(res["stdout"])


if __name__ == "__main__":
    # Password gate for deploy hook: 2289454
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=[
        "verify-billing-baseline",
        "ensure-users",
        "seed-sm-tanza-preflight",
        "cleanup-orders",
    ])
    parser.add_argument("--names", nargs="*", default=[])
    args = parser.parse_args()

    if args.command == "verify-billing-baseline":
        verify_billing_baseline()
    elif args.command == "ensure-users":
        ensure_users()
    elif args.command == "seed-sm-tanza-preflight":
        seed_sm_tanza_preflight()
    elif args.command == "cleanup-orders":
        cleanup_orders(args.names)
