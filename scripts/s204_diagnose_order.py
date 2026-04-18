"""S204 diagnose: SE/WR state for a given order."""
from __future__ import annotations
import base64, sys, time, subprocess

ORDER = sys.argv[1] if len(sys.argv) > 1 else "BEI-ORD-2026-00272"

SCRIPT = rf'''
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

order_name = "{ORDER}"
print(f"=== ORDER {{order_name}} ===")
o = frappe.get_doc("BEI Store Order", order_name)
print(f"  status: {{o.status}}  approval_stage: {{o.approval_stage}}  store: {{o.store}}  company: {{o.company}}")

mrs = frappe.db.sql(f"""SELECT name,docstatus,status,material_request_type,company,custom_finance_treatment,custom_target_company,set_from_warehouse,set_warehouse FROM `tabMaterial Request` WHERE custom_store_order='{{order_name}}' """, as_dict=True)
print(f"=== MRs ({{len(mrs)}}) ===")
for mr in mrs:
    print(f"  {{mr['name']}}: status={{mr['status']}} type={{mr['material_request_type']}} company={{mr['company']}} ft={{mr['custom_finance_treatment']}} target={{mr['custom_target_company']}} from={{mr['set_from_warehouse']}} to={{mr['set_warehouse']}}")

# Stock Entries linked via MR
mr_names = [m['name'] for m in mrs]
if mr_names:
    mr_in = "','".join(mr_names)
    ses = frappe.db.sql(f"""SELECT DISTINCT se.name,se.docstatus,se.stock_entry_type,se.purpose,se.from_warehouse,se.to_warehouse,se.custom_sales_invoice_draft FROM `tabStock Entry` se JOIN `tabStock Entry Detail` sed ON sed.parent=se.name WHERE sed.material_request IN ('{{mr_in}}')""", as_dict=True)
else:
    ses = []
print(f"=== SEs ({{len(ses)}}) ===")
for se in ses:
    print(f"  {{se['name']}}: ds={{se['docstatus']}} type={{se['stock_entry_type']}} purpose={{se['purpose']}} from={{se['from_warehouse']}} to={{se['to_warehouse']}} draft_si={{se['custom_sales_invoice_draft']}}")

if ses:
    se_in = "','".join([s['name'] for s in ses])
    wrs = frappe.db.sql(f"""SELECT name,status,stock_entry,source_warehouse,target_warehouse FROM `tabBEI Warehouse Receiving` WHERE stock_entry IN ('{{se_in}}')""", as_dict=True)
else:
    wrs = []
print(f"=== WRs ({{len(wrs)}}) ===")
for wr in wrs:
    print(f"  {{wr['name']}}: status={{wr['status']}} se={{wr['stock_entry']}} src={{wr['source_warehouse']}} tgt={{wr['target_warehouse']}}")

# Recent errors
errs = frappe.db.sql("""SELECT name,method,creation,error FROM `tabError Log` WHERE creation >= DATE_SUB(NOW(), INTERVAL 10 MINUTE) ORDER BY creation DESC LIMIT 20""", as_dict=True)
hits = [e for e in errs if order_name in (e.get('error') or '') or 'S198' in (e.get('method') or '') or 'warehouse_receiving' in (e.get('method') or '')]
print(f"=== RELATED ERRORS (last 10 min): {{len(hits)}} ===")
for e in hits[:6]: print(f"  [{{e['creation']}}] {{e['method']}}: {{(e['error'] or '')[:400]}}")

# BEI Settings commissary
commissary = frappe.db.get_single_value("BEI Settings", "commissary_company")
print(f"=== BEI Settings.commissary_company = {{commissary!r}} ===")

frappe.destroy()
'''

enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/s204_diag.py",
    "docker cp /tmp/s204_diag.py $BACKEND:/tmp/s204_diag.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s204_diag.py",
]

import boto3
ssm = boto3.client("ssm", region_name="ap-southeast-1")
r = ssm.send_command(
    InstanceIds=["i-026b7477d27bd46d6"],
    DocumentName="AWS-RunShellScript",
    Parameters={"commands": cmds, "executionTimeout": ["180"]},
)
cid = r["Command"]["CommandId"]
print("CommandId:", cid)
for _ in range(50):
    time.sleep(3)
    inv = ssm.get_command_invocation(CommandId=cid, InstanceId="i-026b7477d27bd46d6")
    if inv["Status"] in ("Success", "Failed", "TimedOut"):
        print("STATUS:", inv["Status"])
        print(inv["StandardOutputContent"][-5000:])
        if inv["StandardErrorContent"]:
            print("STDERR:", inv["StandardErrorContent"][-800:])
        sys.exit(0 if inv["Status"] == "Success" else 1)
