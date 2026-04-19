"""Check the backend state for the rows showing em-dashes in the UI."""
import base64, sys, time

SCRIPT = r'''
import frappe, json
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# Stores visible as em-dashes in the UI (from Sam's screenshot)
blank_in_ui = [
    "Ayala Fairview Terraces",
    "Ayala Market! Market!",
    "Ayala Solenad 2",
    "Ayala UP Town Center",
    "BF Homes Paranaque (Aguirre Ave.)",
    "Ever Gotesco Commonwealth",
    "Festival Mall Alabang",
    "Lucky China Town",
]

# Call the live list_stores endpoint to see what it actually returns
from hrms.api.company_master import list_stores
result = list_stores()
rows = result.get("stores", []) if isinstance(result, dict) else []
print(f"list_stores returned {len(rows)} rows")
print()

# Print state for each blank-in-UI store
print("=" * 90)
print("Rows for stores showing em-dashes in UI:")
print("=" * 90)
for store in blank_in_ui:
    matching = [r for r in rows if r.get("store_name") == store or r.get("store_name", "").lower() == store.lower()]
    if not matching:
        print(f"\n{store!r}: NO ROW from list_stores")
        continue
    for m in matching:
        print(f"\n{store!r}")
        print(f"  company:              {m.get('company')!r}")
        print(f"  entity_category:      {m.get('entity_category')!r}")
        print(f"  store_ownership_type: {m.get('store_ownership_type')!r}")
        print(f"  operational_status:   {m.get('operational_status')!r}")
        print(f"  city:                 {m.get('city')!r}")
        print(f"  mosaic_location_id:   {m.get('mosaic_location_id')!r}")
        print(f"  first_provision_done: {m.get('first_provision_done')!r}")

# Also print full list of store_name -> company mapping
print()
print("=" * 90)
print("Full list: store_name -> company")
print("=" * 90)
for r in rows:
    if r.get("row_kind") == "store":
        print(f"  {r.get('store_name')!r:50s}  company={r.get('company')!r}")

frappe.destroy()
'''

enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/chk.py",
    "docker cp /tmp/chk.py $BACKEND:/tmp/chk.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/chk.py",
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
        if inv["StandardErrorContent"]:
            print("STDERR:", inv["StandardErrorContent"][-1500:])
        sys.exit(0 if inv["Status"] == "Success" else 1)
