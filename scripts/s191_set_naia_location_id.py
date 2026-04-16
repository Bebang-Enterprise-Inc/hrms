"""Set mosaic_location_id=9001 on HALO-HALO TERMINAL FOOD CORP. (NAIA T3).

Also verify LEGACY77 FOOD CORP. is excluded by the orderable allowlist filter
(archived by S196 SJDM fix — no action needed on the 2481 dupe).

Run via SSM:
  doppler run --project bei-erp --config dev -- python scripts/s191_ssm_set_naia.py
"""
import os
import sys

for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)

if os.environ.get("CONFIRM", "").lower() != "yes":
    print("ERROR: CONFIRM=yes required")
    sys.exit(2)

import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

print("=" * 60)
print("S191 follow-up: set NAIA T3 mosaic_location_id + verify 2481 dupe")
print("=" * 60)

# 1. Set mosaic_location_id on HALO-HALO TERMINAL FOOD CORP.
NAIA_COMPANY = "HALO-HALO TERMINAL FOOD CORP."
current = frappe.db.get_value("Company", NAIA_COMPANY, "mosaic_location_id")
print(f"\n1. {NAIA_COMPANY}: current mosaic_location_id = {current!r}")
if not current:
    frappe.db.set_value("Company", NAIA_COMPANY, "mosaic_location_id", "9001")
    frappe.db.commit()
    verify = frappe.db.get_value("Company", NAIA_COMPANY, "mosaic_location_id")
    print(f"   SET -> {verify}")
else:
    print(f"   SKIP: already set")

# 2. Verify LEGACY77 is archived (won't appear in orderable filter)
LEGACY = "LEGACY77 FOOD CORP."
if frappe.db.exists("Company", LEGACY):
    status = frappe.db.get_value("Company", LEGACY, "operational_status")
    lid = frappe.db.get_value("Company", LEGACY, "mosaic_location_id")
    print(f"\n2. {LEGACY}: operational_status={status!r} mosaic_location_id={lid!r}")
    if status == "Permanently Closed":
        print("   OK: archived — excluded by orderable allowlist filter (no 2481 dupe risk)")
    else:
        print("   WARNING: NOT archived — 2481 dupe may surface in Analytics")
else:
    print(f"\n2. {LEGACY}: does not exist (deleted)")

# 3. Full count: Companies with mosaic_location_id
all_with_lid = frappe.get_all("Company",
    filters={"mosaic_location_id": ["is", "set"]},
    fields=["name", "mosaic_location_id", "operational_status"],
)
orderable_with_lid = [c for c in all_with_lid
    if c.get("operational_status") in ("Active", "Pre-Opening", "Temporarily Closed", "Pipeline")]
print(f"\n3. Companies with mosaic_location_id: {len(all_with_lid)} total, {len(orderable_with_lid)} orderable")

# 4. Companies WITHOUT mosaic_location_id (orderable only)
orderable_all = frappe.get_all("Company",
    filters={
        "entity_category": ["in", ["Store", "Commissary"]],
        "operational_status": ["in", ["Active", "Pre-Opening", "Temporarily Closed", "Pipeline"]],
    },
    fields=["name", "mosaic_location_id"],
)
missing = [c for c in orderable_all if not c.get("mosaic_location_id")]
print(f"\n4. Orderable Companies: {len(orderable_all)} total, {len(missing)} missing mosaic_location_id")
if missing:
    for c in missing:
        print(f"   MISSING: {c['name']}")

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)
frappe.destroy()
