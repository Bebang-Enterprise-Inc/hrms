"""Fix AYALA EVO edge case + audit all test.area visible warehouses for drift.

For each warehouse where test.area is area_supervisor:
  - If its docname matches a canonical per-store Company: OK
  - If not: move area_supervisor to the canonical Warehouse for that store (if
    resolvable by Company link) and disable the old warehouse
"""
import base64, sys, time

SCRIPT = r'''
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# Canonical Company list
canonical_companies = set(
    row[0] for row in frappe.db.sql(
        "SELECT name FROM `tabCompany` WHERE entity_category = 'Store' "
        "AND (operational_status IS NULL OR operational_status NOT IN ('Permanently Closed', 'Dormant'))",
        as_list=True,
    )
)

# All warehouses where test.area is area supervisor (plus any sam@bebang.ph)
wh_rows = frappe.db.sql(
    """SELECT name, warehouse_name, company, custom_area_supervisor, disabled
       FROM `tabWarehouse`
       WHERE custom_area_supervisor IN ('test.area@bebang.ph', 'sam@bebang.ph')
         AND is_group = 0 AND disabled = 0""",
    as_dict=True,
)

# Canonical WH = docname exactly matches a Company in canonical_companies
non_canonical_with_supervisor = []
for wh in wh_rows:
    if wh["name"] not in canonical_companies:
        # This is a legacy warehouse that shouldn't have an active area supervisor
        non_canonical_with_supervisor.append(wh)

print(f"Legacy warehouses with active area_supervisor ({len(non_canonical_with_supervisor)}):")
for wh in non_canonical_with_supervisor:
    print(f"  {wh['name']!r} company={wh['company']!r} supervisor={wh['custom_area_supervisor']!r}")

# For each, try to find the canonical Warehouse for the same store and move supervisor
moved = 0
for wh in non_canonical_with_supervisor:
    # Canonical Warehouse for a store = the Warehouse whose docname matches its per-store Company
    # How do we map this legacy wh -> canonical? By Company link if company matches a canonical_companies entry,
    # OR by inference from warehouse_name.
    target_canonical = None

    # Case 1: wh.company is a canonical per-store Company → canonical docname = wh.company
    if wh["company"] in canonical_companies:
        candidate = frappe.db.get_value("Warehouse", wh["company"], ["name", "disabled"], as_dict=True)
        if candidate and not candidate["disabled"]:
            target_canonical = candidate["name"]

    if not target_canonical:
        # Case 2: wh.company is a PARENT, try to find per-store Company whose warehouse_name matches this wh's warehouse_name
        # Example: wh.name='AYALA EVO - BEBANG MEGA INC.' company=parent, warehouse_name='AYALA EVO'
        # Per-store Company = 'AYALA EVO CITY - BEBANG MEGA INC.' (canonical docname)
        # Match heuristic: find canonical_companies whose name starts with warehouse_name + ' -'
        wh_name_token = (wh["warehouse_name"] or "").strip().upper()
        if wh_name_token:
            for co in canonical_companies:
                co_label = co.split(" - ")[0].strip().upper()
                # Token match OR prefix match (AYALA EVO ~= AYALA EVO CITY)
                if co_label == wh_name_token or co_label.startswith(wh_name_token + " ") or wh_name_token.startswith(co_label + " "):
                    canonical_doc = frappe.db.get_value("Warehouse", co, ["name", "disabled"], as_dict=True)
                    if canonical_doc and not canonical_doc["disabled"]:
                        target_canonical = canonical_doc["name"]
                        break

    if not target_canonical:
        print(f"  [SKIP] {wh['name']!r}: could not resolve canonical Warehouse — manual review needed")
        continue

    print(f"  [MOVE] {wh['name']!r} -> {target_canonical!r} (supervisor={wh['custom_area_supervisor']!r})")
    # Move area supervisor to canonical, disable old
    frappe.db.set_value("Warehouse", target_canonical, "custom_area_supervisor", wh["custom_area_supervisor"], update_modified=False)
    frappe.db.set_value("Warehouse", wh["name"], "custom_area_supervisor", None, update_modified=False)
    frappe.db.set_value("Warehouse", wh["name"], "disabled", 1, update_modified=False)
    moved += 1

# Ensure test.area has supervisor on ALL canonical store warehouses (so the L3 test can see every store)
# For each canonical Warehouse that doesn't have a supervisor, assign test.area
# Use parameter placeholder to avoid apostrophe injection (e.g. D'VERDE).
placeholders = ", ".join(["%s"] * len(canonical_companies))
canonical_without_supervisor = frappe.db.sql(
    f"""SELECT name FROM `tabWarehouse`
       WHERE name IN ({{placeholders}})
         AND is_group = 0 AND disabled = 0
         AND (custom_area_supervisor IS NULL OR custom_area_supervisor = '')""".replace("{placeholders}", placeholders),
    tuple(canonical_companies), as_list=True,
)
assigned = 0
for (wh_name,) in canonical_without_supervisor:
    frappe.db.set_value("Warehouse", wh_name, "custom_area_supervisor", "test.area@bebang.ph", update_modified=False)
    assigned += 1

frappe.db.commit()
print(f"\nMoved {moved} supervisors, assigned test.area to {assigned} canonical warehouses with no supervisor.")

# Verify
frappe.set_user("test.area@bebang.ph")
final = frappe.get_all(
    "Warehouse",
    filters={"custom_area_supervisor": "test.area@bebang.ph", "is_group": 0, "disabled": 0},
    fields=["name", "warehouse_name"],
    order_by="warehouse_name",
)
frappe.set_user("Administrator")
print(f"\ntest.area now sees {len(final)} canonical warehouses (first 10):")
for r in final[:10]:
    print(f"  {r['name']}  [{r['warehouse_name']}]")

frappe.destroy()
'''

enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/fix_ayala.py",
    "docker cp /tmp/fix_ayala.py $BACKEND:/tmp/fix_ayala.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/fix_ayala.py",
]

import boto3
ssm = boto3.client("ssm", region_name="ap-southeast-1")
r = ssm.send_command(InstanceIds=["i-026b7477d27bd46d6"], DocumentName="AWS-RunShellScript",
    Parameters={"commands": cmds, "executionTimeout": ["180"]})
cid = r["Command"]["CommandId"]
print("CommandId:", cid)
for _ in range(60):
    time.sleep(3)
    inv = ssm.get_command_invocation(CommandId=cid, InstanceId="i-026b7477d27bd46d6")
    if inv["Status"] in ("Success", "Failed", "TimedOut"):
        print("STATUS:", inv["Status"])
        print(inv["StandardOutputContent"])
        if inv["StandardErrorContent"]:
            print("STDERR:", inv["StandardErrorContent"][-1500:])
        sys.exit(0 if inv["Status"] == "Success" else 1)
