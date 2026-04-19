"""Check if S037 CSV loads in the deployed container."""
import base64, sys, time

SCRIPT = r'''
import os
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

from hrms.api.company_master import _load_s037_rows, _S037_RELPATH

# Where is the CSV expected to be
hrms_app = frappe.get_app_path("hrms")
csv_path = os.path.normpath(os.path.join(hrms_app, *_S037_RELPATH))
print(f"Expected S037 CSV path: {csv_path}")
print(f"Exists: {os.path.exists(csv_path)}")

rows = _load_s037_rows()
print(f"Loaded {len(rows)} rows from S037")

if rows:
    for r in rows[:5]:
        print(f"  {r.get('store_name')!r} -> buyer={r.get('buyer_entity_name')!r}")

# List what's in the data_seed dir
data_seed_dir = os.path.join(hrms_app, "data_seed")
print(f"\ndata_seed/ contents:")
if os.path.isdir(data_seed_dir):
    for f in os.listdir(data_seed_dir):
        print(f"  {f}")
else:
    print("  (dir not found)")

# Now call list_stores as if from the frontend and count
from hrms.api.company_master import list_stores
result = list_stores()
print(f"\nlist_stores() returned {type(result).__name__}")
if isinstance(result, list):
    print(f"  as list: len={len(result)}")
elif isinstance(result, dict):
    print(f"  as dict: keys={list(result.keys())}")
    if "stores" in result:
        print(f"  stores count: {len(result['stores'])}")
frappe.destroy()
'''

enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/pr.py",
    "docker cp /tmp/pr.py $BACKEND:/tmp/pr.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/pr.py",
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
