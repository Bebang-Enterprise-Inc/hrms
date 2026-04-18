"""S204: Check WR and SI state for recent orders."""
from __future__ import annotations
import base64, sys, time

SCRIPT = r'''
import os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# Latest WRs
wrs = frappe.db.sql("""SELECT name,status,stock_entry,source_warehouse,target_warehouse,creation,modified FROM `tabBEI Warehouse Receiving` WHERE creation >= DATE_SUB(NOW(), INTERVAL 30 MINUTE) ORDER BY creation DESC""", as_dict=True)
print(f"=== Recent WRs (last 30min): {len(wrs)} ===")
for wr in wrs:
    print(f"  {wr['name']}: status={wr['status']} se={wr['stock_entry']} src={wr['source_warehouse']} tgt={wr['target_warehouse']} creation={wr['creation']}")

# Latest SIs
sis = frappe.db.sql("""SELECT name,docstatus,customer,company,bei_legal_entity,grand_total,custom_bei_store_order,creation FROM `tabSales Invoice` WHERE creation >= DATE_SUB(NOW(), INTERVAL 30 MINUTE) ORDER BY creation DESC""", as_dict=True)
print(f"=== Recent SIs (last 30min): {len(sis)} ===")
for si in sis:
    print(f"  {si['name']}: ds={si['docstatus']} customer={si['customer']} company={si['company']} legal={si['bei_legal_entity']} total={si['grand_total']} order={si['custom_bei_store_order']}")

# Check order 00274 specifically
order = frappe.get_doc("BEI Store Order", "BEI-ORD-2026-00274")
print(f"=== Order 00274: fulfillment_status={getattr(order,'fulfillment_status',None)} ===")

# Check SE 00367 second leg
se2 = frappe.db.sql("""SELECT name,docstatus,stock_entry_type,from_warehouse,to_warehouse,custom_sales_invoice_draft,creation FROM `tabStock Entry` WHERE creation >= DATE_SUB(NOW(), INTERVAL 30 MINUTE) ORDER BY creation DESC""", as_dict=True)
print(f"=== Recent SEs (last 30min): {len(se2)} ===")
for se in se2:
    print(f"  {se['name']}: ds={se['docstatus']} type={se['stock_entry_type']} from={se['from_warehouse']} to={se['to_warehouse']} draft_si={se['custom_sales_invoice_draft']}")

# Last 10 errors
errs = frappe.db.sql("""SELECT name,method,creation,error FROM `tabError Log` WHERE creation >= DATE_SUB(NOW(), INTERVAL 30 MINUTE) ORDER BY creation DESC LIMIT 25""", as_dict=True)
rel = [e for e in errs if any(k in (e.get('method') or '')+' '+(e.get('error') or '') for k in ['warehouse_receiving','S203','S198','complete_warehouse','_submit_dispatch','store_order','sales_invoice','build_bki'])]
print(f"=== Related errors: {len(rel)} ===")
for e in rel[:8]:
    print(f"  [{e['creation']}] {e['method']}: {(e['error'] or '')[:500]}")

frappe.destroy()
'''

enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/s204_check.py",
    "docker cp /tmp/s204_check.py $BACKEND:/tmp/s204_check.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s204_check.py",
]

import boto3
ssm = boto3.client("ssm", region_name="ap-southeast-1")
r = ssm.send_command(
    InstanceIds=["i-026b7477d27bd46d6"],
    DocumentName="AWS-RunShellScript",
    Parameters={"commands": cmds, "executionTimeout": ["240"]},
)
cid = r["Command"]["CommandId"]
print("CommandId:", cid)
for _ in range(80):
    time.sleep(3)
    inv = ssm.get_command_invocation(CommandId=cid, InstanceId="i-026b7477d27bd46d6")
    if inv["Status"] in ("Success", "Failed", "TimedOut"):
        print("STATUS:", inv["Status"])
        print(inv["StandardOutputContent"][-8000:])
        if inv["StandardErrorContent"]:
            print("STDERR:", inv["StandardErrorContent"][-1500:])
        sys.exit(0 if inv["Status"] == "Success" else 1)
