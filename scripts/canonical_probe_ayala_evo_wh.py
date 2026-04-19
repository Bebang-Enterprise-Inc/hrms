"""Probe AYALA EVO warehouse visibility for test.area."""
import base64, sys, time

SCRIPT = r'''
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# Ayala Evo warehouse
wh = frappe.db.get_value("Warehouse", "AYALA EVO CITY - BEBANG MEGA INC.", ["name", "warehouse_name", "company", "custom_area_supervisor", "disabled"], as_dict=True)
print(f"AYALA EVO CITY canonical: {wh}")

# All warehouses visible to test.area (via get_all with ignore_permissions=False)
frappe.set_user("test.area@bebang.ph")
rows = frappe.get_all(
    "Warehouse",
    filters={"custom_area_supervisor": "test.area@bebang.ph", "is_group": 0, "disabled": 0},
    fields=["name", "warehouse_name"],
    order_by="warehouse_name",
)
frappe.set_user("Administrator")
print(f"\ntest.area visible warehouses ({len(rows)}):")
for r in rows:
    print(f"  name={r['name']!r}  warehouse_name={r['warehouse_name']!r}")
frappe.destroy()
'''
enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/probe.py",
    "docker cp /tmp/probe.py $BACKEND:/tmp/probe.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/probe.py",
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
