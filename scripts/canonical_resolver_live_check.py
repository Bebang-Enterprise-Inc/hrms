"""Verify live resolver behavior on all 49 stores post-migration.

For each store:
  - Run resolve_store_buyer_entity on the canonical Warehouse
  - Confirm buyer_entity_name == per-store Company name
  - Confirm a non-internal Customer exists with that customer_name
  - Print TIN that would land on the SI
"""
from __future__ import annotations
import base64, sys, time

SCRIPT = r'''
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

from hrms.utils.supply_chain_contracts import resolve_store_buyer_entity

stores = frappe.db.sql(
    """SELECT name, parent_company FROM `tabCompany`
       WHERE entity_category = 'Store'
         AND (operational_status IS NULL OR operational_status NOT IN ('Permanently Closed','Dormant'))
       ORDER BY name""",
    as_dict=True,
)

rows = []
for co in stores:
    ps_co = co["name"]
    parent = co["parent_company"]

    # Canonical warehouse should be named ps_co
    wh_info = frappe.db.get_value("Warehouse", ps_co, ["name", "company", "warehouse_name", "disabled"], as_dict=True)
    if not wh_info or wh_info.get("disabled"):
        rows.append({"ps_co": ps_co, "status": "WH_MISSING_OR_DISABLED", "detail": str(wh_info)})
        continue

    entity_row = resolve_store_buyer_entity(warehouse_docname=ps_co)
    ben = entity_row.get("buyer_entity_name")
    status = entity_row.get("buyer_entity_status")

    # What Customer would build_bki_store_sale_invoice pick?
    cust_name = frappe.db.get_value("Customer", {"customer_name": ben}, "name") if ben else None
    cust_tin = frappe.db.get_value("Customer", cust_name, "tax_id") if cust_name else None
    is_internal = frappe.db.get_value("Customer", cust_name, "is_internal_customer") if cust_name else None

    # Assert per-store canonical contract
    if ben != ps_co:
        rows.append({"ps_co": ps_co, "status": "RESOLVER_WRONG_BEN", "detail": f"ben={ben!r} (expected {ps_co!r})"})
        continue
    if not cust_name:
        rows.append({"ps_co": ps_co, "status": "CUST_NOT_FOUND", "detail": f"ben={ben!r}"})
        continue
    if is_internal:
        rows.append({"ps_co": ps_co, "status": "CUST_IS_INTERNAL", "detail": f"cust={cust_name!r} is_internal=1"})
        continue

    rows.append({
        "ps_co": ps_co,
        "status": "OK",
        "ben": ben,
        "cust": cust_name,
        "tin": cust_tin,
        "wh_company": wh_info["company"],
    })

ok = [r for r in rows if r["status"] == "OK"]
not_ok = [r for r in rows if r["status"] != "OK"]
print(f"OK: {len(ok)}/{len(rows)}")
for r in not_ok:
    print(f"  [{r['status']}] {r['ps_co']}: {r.get('detail', '')}")

# TIN sample
print()
print("Sample (first 10):")
for r in ok[:10]:
    print(f"  {r['ps_co']}")
    print(f"    -> buyer={r['cust']}  TIN={r['tin']!r}  wh_company={r['wh_company']!r}")

# TIN check: are there distinct TINs or do all siblings share one?
from collections import defaultdict
by_tin = defaultdict(list)
for r in ok:
    by_tin[r["tin"]].append(r["ps_co"])
print()
print(f"Distinct TINs in use: {len(by_tin)}")
for tin, stores_list in sorted(by_tin.items(), key=lambda x: -len(x[1]))[:10]:
    print(f"  {tin!r}: {len(stores_list)} stores")

frappe.destroy()
'''

enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/live_check.py",
    "docker cp /tmp/live_check.py $BACKEND:/tmp/live_check.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/live_check.py",
]
import boto3
ssm = boto3.client("ssm", region_name="ap-southeast-1")
r = ssm.send_command(InstanceIds=["i-026b7477d27bd46d6"], DocumentName="AWS-RunShellScript",
    Parameters={"commands": cmds, "executionTimeout": ["180"]})
cid = r["Command"]["CommandId"]
print("CommandId:", cid)
for _ in range(60):
    time.sleep(3)
    inv = ssm.get_command_invocation(CommandId=cid, InstanceId="i-026b7477d27bd46d6")
    if inv["Status"] in ("Success", "Failed", "TimedOut"):
        print("STATUS:", inv["Status"])
        print(inv["StandardOutputContent"][-4000:])
        if inv["StandardErrorContent"]:
            print("STDERR:", inv["StandardErrorContent"][-1000:])
        sys.exit(0 if inv["Status"] == "Success" else 1)
