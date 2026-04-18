"""S204: Trace why validate_inter_company_party fails for Draft SI when submitted via user session."""
import base64, sys, time

SCRIPT = r'''
import os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()

# Try submit as test.supervisor (the accepter)
for user in ["Administrator", "test.supervisor@bebang.ph", "test.scm@bebang.ph"]:
    print(f"\n=== Try submit ACC-SINV-2026-00005 as {user} ===")
    frappe.set_user(user)
    try:
        si = frappe.get_doc("Sales Invoice", "ACC-SINV-2026-00005")
        if si.docstatus != 0:
            print(f"  Already docstatus={si.docstatus}, skipping")
            continue
        # Re-fetch fresh
        frappe.db.rollback()
        si = frappe.get_doc("Sales Invoice", "ACC-SINV-2026-00005")
        si.submit()
        frappe.db.commit()
        print(f"  SUBMITTED OK docstatus={si.docstatus}")
    except Exception as e:
        import traceback
        print(f"  EXCEPTION: {type(e).__name__}: {e}")
        # Print just the relevant last frames
        tb = traceback.format_exc()
        # Extract just the last error + immediate context
        lines = tb.splitlines()
        for ln in lines[-30:]:
            print("  ", ln)

# Check current customer state
frappe.set_user("Administrator")
cust = frappe.get_doc("Customer", "BEBANG MEGA INC.")
companies = [c.company for c in (cust.companies or [])]
print(f"\n=== Customer BEBANG MEGA INC. ===")
print(f"  is_internal_customer: {cust.is_internal_customer}")
print(f"  companies: {companies}")
print(f"  represents_company: {getattr(cust, 'represents_company', None)}")

frappe.destroy()
'''
enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/s204_trace.py",
    "docker cp /tmp/s204_trace.py $BACKEND:/tmp/s204_trace.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s204_trace.py",
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
        print(inv["StandardOutputContent"][-5000:])
        if inv["StandardErrorContent"]:
            print("STDERR:", inv["StandardErrorContent"][-1000:])
        sys.exit(0)
