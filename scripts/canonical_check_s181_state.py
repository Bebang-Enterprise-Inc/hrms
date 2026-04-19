"""Check whether S181 Company fields are populated or empty post-migration."""
import base64, sys, time

SCRIPT = r'''
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# Sample 5 stores' S181 fields
samples = ["SM TANZA - BEBANG MEGA INC.", "AYALA EVO CITY - BEBANG MEGA INC.",
           "THE GRID ROCKWELL - TASTECARTEL CORP.", "SM MEGAMALL - BEBANG ENTERPRISE INC.",
           "ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC"]

print("=" * 80)
print("S181 Company field state (post-canonical migration)")
print("=" * 80)

for name in samples:
    row = frappe.db.sql(
        """SELECT name, entity_category, store_ownership_type, mosaic_location_id,
                  city, operational_status, pos_system, branch_tin, bir_rdo_code,
                  first_provision_done, full_address, tax_id
           FROM `tabCompany` WHERE name = %s""",
        (name,), as_dict=True,
    )
    if not row:
        print(f"\n{name!r}: NOT FOUND")
        continue
    r = row[0]
    print(f"\n{name!r}")
    print(f"  entity_category:      {r.get('entity_category')!r}")
    print(f"  store_ownership_type: {r.get('store_ownership_type')!r}")
    print(f"  mosaic_location_id:   {r.get('mosaic_location_id')!r}")
    print(f"  city:                 {r.get('city')!r}")
    print(f"  operational_status:   {r.get('operational_status')!r}")
    print(f"  pos_system:           {r.get('pos_system')!r}")
    print(f"  branch_tin:           {r.get('branch_tin')!r}")
    print(f"  bir_rdo_code:         {r.get('bir_rdo_code')!r}")
    print(f"  first_provision_done: {r.get('first_provision_done')!r}")
    print(f"  tax_id:               {r.get('tax_id')!r}")

# Overall count
print()
print("=" * 80)
print("Aggregate state across all 49 stores:")
print("=" * 80)
counts = frappe.db.sql(
    """SELECT
         SUM(CASE WHEN entity_category IS NULL OR entity_category = '' THEN 1 ELSE 0 END) as blank_entity_cat,
         SUM(CASE WHEN store_ownership_type IS NULL OR store_ownership_type = '' THEN 1 ELSE 0 END) as blank_ownership,
         SUM(CASE WHEN mosaic_location_id IS NULL OR mosaic_location_id = '' THEN 1 ELSE 0 END) as blank_mosaic,
         SUM(CASE WHEN city IS NULL OR city = '' THEN 1 ELSE 0 END) as blank_city,
         SUM(CASE WHEN operational_status IS NULL OR operational_status = '' THEN 1 ELSE 0 END) as blank_status,
         SUM(CASE WHEN first_provision_done = 1 THEN 1 ELSE 0 END) as marked_provisioned,
         COUNT(*) as total
       FROM `tabCompany` WHERE entity_category = 'Store'
          OR (entity_category IS NULL AND name IN (
              SELECT DISTINCT warehouse.company FROM `tabWarehouse` warehouse WHERE warehouse.is_group = 0
          ))""",
    as_dict=True,
)[0]
print(f"  Total Store-companies examined: {counts['total']}")
print(f"  Blank entity_category:          {counts['blank_entity_cat']}")
print(f"  Blank store_ownership_type:     {counts['blank_ownership']}")
print(f"  Blank mosaic_location_id:       {counts['blank_mosaic']}")
print(f"  Blank city:                     {counts['blank_city']}")
print(f"  Blank operational_status:       {counts['blank_status']}")
print(f"  first_provision_done=1:         {counts['marked_provisioned']}")

# Also check the 4 non-store entities
print()
print("Non-store entities (Head Office / Commissary / Holding / Franchisor):")
non_store = frappe.db.sql(
    """SELECT name, entity_category, first_provision_done FROM `tabCompany`
       WHERE name IN ('BEBANG ENTERPRISE INC.', 'BEBANG KITCHEN INC.', 'BEBANG FRANCHISE CORP.', 'IRRESISTIBLE INFUSIONS INC.')""",
    as_dict=True,
)
for r in non_store:
    print(f"  {r['name']!r}: entity_category={r['entity_category']!r}  first_provision_done={r['first_provision_done']!r}")

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
            print("STDERR:", inv["StandardErrorContent"][-1000:])
        sys.exit(0 if inv["Status"] == "Success" else 1)
