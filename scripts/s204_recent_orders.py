"""Report recent BEI Store Orders + MRs for diagnosis."""
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

# Orders by test.area in last hour
rows = frappe.db.sql("""SELECT name,store,status,approval_stage,creation FROM `tabBEI Store Order` WHERE owner='test.area@bebang.ph' AND creation >= DATE_SUB(NOW(), INTERVAL 60 MINUTE) ORDER BY creation DESC""", as_dict=True)
print(f"=== test.area orders (last 60min): {len(rows)} ===")
for r in rows:
    print(f"  {r['name']}: store={r['store']} status={r['status']} stage={r['approval_stage']} creation={r['creation']}")

# Any error logs related to ordering/approval in last 30min
errs = frappe.db.sql("""SELECT name,method,creation,error FROM `tabError Log` WHERE creation >= DATE_SUB(NOW(), INTERVAL 30 MINUTE) AND (method LIKE '%ordering%' OR method LIKE '%approve%' OR method LIKE '%Store Order%' OR error LIKE '%SM Megamall%' OR error LIKE '%MEGAMALL%') ORDER BY creation DESC LIMIT 5""", as_dict=True)
print(f"\n=== Ordering/approval errors (last 30min): {len(errs)} ===")
for e in errs[:3]:
    print(f"  [{e['creation']}] {e['method']}: {(e['error'] or '')[:400]}")

frappe.destroy()
'''
enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/s204_ro.py",
    "docker cp /tmp/s204_ro.py $BACKEND:/tmp/s204_ro.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s204_ro.py",
]
import boto3
ssm = boto3.client("ssm", region_name="ap-southeast-1")
r = ssm.send_command(InstanceIds=["i-026b7477d27bd46d6"], DocumentName="AWS-RunShellScript",
    Parameters={"commands": cmds, "executionTimeout": ["120"]})
cid = r["Command"]["CommandId"]
print("CommandId:", cid)
for _ in range(40):
    time.sleep(3)
    inv = ssm.get_command_invocation(CommandId=cid, InstanceId="i-026b7477d27bd46d6")
    if inv["Status"] in ("Success","Failed","TimedOut"):
        print("STATUS:", inv["Status"])
        print(inv["StandardOutputContent"][-3500:])
        sys.exit(0)
