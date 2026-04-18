"""S204: Get full traceback of S203 Submit SI errors."""
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

errs = frappe.db.sql("""SELECT name,method,creation,error FROM `tabError Log` WHERE method LIKE '%S203%' OR method LIKE '%Submit SI%' ORDER BY creation DESC LIMIT 8""", as_dict=True)
print(f"=== Submit SI errors ({len(errs)}) ===")
for e in errs[:5]:
    print(f"--- [{e['creation']}] {e['method']} ---")
    print(e['error'])
    print()

# Also try to manually submit ACC-SINV-2026-00006 to see real error
print("=== Manual submit attempt ACC-SINV-2026-00006 ===")
try:
    si = frappe.get_doc("Sales Invoice", "ACC-SINV-2026-00006")
    print(f"  customer: {si.customer}  company: {si.company}  legal: {si.bei_legal_entity}  tax_id: {si.tax_id}  total: {si.grand_total}")
    print(f"  docstatus: {si.docstatus}")
    si.submit()
    frappe.db.commit()
    print(f"  SUBMITTED OK: docstatus={si.docstatus}")
except Exception as e:
    import traceback
    print(f"  EXCEPTION: {e}")
    print(traceback.format_exc()[:3000])

frappe.destroy()
'''
enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/s204_subm.py",
    "docker cp /tmp/s204_subm.py $BACKEND:/tmp/s204_subm.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s204_subm.py",
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
            print("STDERR:", inv["StandardErrorContent"][-1000:])
        sys.exit(0)
