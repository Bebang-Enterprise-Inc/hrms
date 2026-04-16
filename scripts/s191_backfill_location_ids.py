"""Backfill mosaic_location_id on the 3 newly created S196 Companies + verify all.

These Companies were created in S196 Phase 2 Step C with first_provision_done=1
but mosaic_location_id was not set (it wasn't in the plan scope).

Mapping from MOSAIC_POS_API_KEYS.csv:
  Robinsons Galleria South (2515) -> Robinsons Galleria South - Tungsten Capital
  SM Caloocan (2464) -> SM Caloocan - TAJ Food Corp.
  SM Sangandaan (2482) -> SM Sangandaan - Tungsten Capital

The other 5 missing are non-POS entities (no Mosaic terminal):
  BB ESTANCIA FOOD CORP. — Ortigas Estancia (no POS key in Mosaic)
  BEIFRANCHISE FOOD OPC — Greenhills (similarly no dedicated key)
  PERPETUAL FOOD CORP. — no store
  FREEZE DELIGHT INC. — no store
  Bebang Kitchen Inc. — commissary, not a store
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

BACKFILL = {
    "Robinsons Galleria South - Tungsten Capital": "2515",
    "SM Caloocan - TAJ Food Corp.": "2464",
    "SM Sangandaan - Tungsten Capital": "2482",
}

print("=" * 60)
print("S191 backfill: mosaic_location_id on 3 S196 Companies")
print("=" * 60)

for company, lid in BACKFILL.items():
    if not frappe.db.exists("Company", company):
        print(f"  SKIP: {company} not found")
        continue
    current = frappe.db.get_value("Company", company, "mosaic_location_id")
    if current:
        print(f"  SKIP: {company} already has mosaic_location_id={current}")
        continue
    frappe.db.set_value("Company", company, "mosaic_location_id", lid)
    frappe.db.commit()
    verify = frappe.db.get_value("Company", company, "mosaic_location_id")
    print(f"  SET: {company} -> mosaic_location_id={verify}")

# Final audit
orderable_all = frappe.get_all("Company",
    filters={
        "entity_category": ["in", ["Store", "Commissary"]],
        "operational_status": ["in", ["Active", "Pre-Opening", "Temporarily Closed", "Pipeline"]],
    },
    fields=["name", "mosaic_location_id"],
)
with_lid = [c for c in orderable_all if c.get("mosaic_location_id")]
missing = [c for c in orderable_all if not c.get("mosaic_location_id")]
print(f"\nOrderable Companies: {len(orderable_all)} total, {len(with_lid)} with mosaic_location_id, {len(missing)} without")
for c in missing:
    print(f"  no location_id: {c['name']}")

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)
frappe.destroy()
