"""S204: Inspect validate_inter_company_party source + try submit with trace."""
import base64, sys, time

SCRIPT = r'''
import os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass
import frappe, inspect
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()

# Read the validate_inter_company_party source
from erpnext.accounts.doctype.sales_invoice import sales_invoice
src = inspect.getsource(sales_invoice.validate_inter_company_party)
print("=== validate_inter_company_party source ===")
print(src)

# Also try to submit as test.supervisor (explicit logging/trace)
print("\n=== Try submit brand-new draft SI as test.supervisor ===")
# Find a current Draft SI
draft_sis = frappe.db.sql("SELECT name FROM `tabSales Invoice` WHERE docstatus=0 AND company='BEBANG KITCHEN INC.' AND creation >= DATE_SUB(NOW(), INTERVAL 60 MINUTE) ORDER BY creation DESC LIMIT 3", as_dict=True)
print(f"  Found {len(draft_sis)} recent Draft SIs: {[s['name'] for s in draft_sis]}")

if draft_sis:
    frappe.set_user("test.supervisor@bebang.ph")
    si_name = draft_sis[0]["name"]
    print(f"\n  Attempting submit {si_name} as test.supervisor...")
    try:
        si = frappe.get_doc("Sales Invoice", si_name)
        print(f"    docstatus={si.docstatus} customer={si.customer} company={si.company}")
        si.submit()
        frappe.db.commit()
        print(f"    SUBMITTED OK as test.supervisor")
    except Exception as e:
        import traceback
        print(f"    EXCEPTION {type(e).__name__}: {e}")
        tb = traceback.format_exc()
        print(tb[-3500:])

frappe.destroy()
'''
enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/s204_vi.py",
    "docker cp /tmp/s204_vi.py $BACKEND:/tmp/s204_vi.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s204_vi.py",
]
import boto3
ssm = boto3.client("ssm", region_name="ap-southeast-1")
r = ssm.send_command(InstanceIds=["i-026b7477d27bd46d6"], DocumentName="AWS-RunShellScript",
    Parameters={"commands": cmds, "executionTimeout": ["240"]})
cid = r["Command"]["CommandId"]
print("CommandId:", cid)
for _ in range(80):
    time.sleep(3)
    inv = ssm.get_command_invocation(CommandId=cid, InstanceId="i-026b7477d27bd46d6")
    if inv["Status"] in ("Success","Failed","TimedOut"):
        print("STATUS:", inv["Status"])
        print(inv["StandardOutputContent"][-6000:])
        if inv["StandardErrorContent"]:
            print("STDERR:", inv["StandardErrorContent"][-800:])
        sys.exit(0)
