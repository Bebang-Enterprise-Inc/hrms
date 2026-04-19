"""Check the most recent SI from the post-migration browser test."""
import base64, sys, time

SCRIPT = r'''
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

rows = frappe.db.sql(
    """SELECT name, customer, tax_id, grand_total, custom_bei_store_order, creation
       FROM `tabSales Invoice`
       ORDER BY creation DESC LIMIT 5""",
    as_dict=True,
)
for r in rows:
    print(f"{r['name']}  customer={r['customer']!r}  tin={r['tax_id']!r}  total={r['grand_total']}  order={r['custom_bei_store_order']!r}  creation={r['creation']}")

frappe.destroy()
'''
enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/lsi.py",
    "docker cp /tmp/lsi.py $BACKEND:/tmp/lsi.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/lsi.py",
]
import boto3
ssm = boto3.client("ssm", region_name="ap-southeast-1")
r = ssm.send_command(InstanceIds=["i-026b7477d27bd46d6"], DocumentName="AWS-RunShellScript",
    Parameters={"commands": cmds, "executionTimeout": ["120"]})
cid = r["Command"]["CommandId"]
for _ in range(40):
    time.sleep(3)
    inv = ssm.get_command_invocation(CommandId=cid, InstanceId="i-026b7477d27bd46d6")
    if inv["Status"] in ("Success", "Failed", "TimedOut"):
        print(inv["StandardOutputContent"])
        sys.exit(0 if inv["Status"] == "Success" else 1)
