"""Add BEI Routes for the 3 PRECONDITION_BLOCKED stores from sweep-v9/v10.

These stores had ZERO BEI Routes, which caused get_orderable_items() to return
an empty list. The Playwright test then threw 'No orderable items at all' and
called test.skip() — which masked the real problem (no routes) as a benign skip.

Geographic source-hub assignment (per BEI Route Planner UI logic):
  - AYALA EVO CITY (Cavite, south of Manila)            → Pinnacle Cold (south)
  - ROBINSONS PLACE DASMARINAS (Dasmariñas, Cavite)     → Pinnacle Cold (south)
  - XENTROMALL MONTALBAN (Rodriguez Rizal, north-east)  → 3MD Logistics (north)

3 cargo types each (DRY, FC, FM) = 9 routes total.

Idempotent — if a route already exists for store+cargo, skip it.
"""
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

PCS_BKI = "Pinnacle Cold Storage Solutions - BKI"
HUB_3MD = "3MD Logistics - Camangyanan - BKI"

# Per geography
ROUTE_BACKFILL = [
    ("AYALA EVO CITY - BEBANG MEGA INC.", PCS_BKI, "south-Cavite"),
    ("ROBINSONS PLACE DASMARINAS - FREEZE DELIGHT INC.", PCS_BKI, "south-Cavite"),
    ("XENTROMALL MONTALBAN - PERPETUAL FOOD CORP.", HUB_3MD, "north-Rizal"),
]
CARGO_TYPES = ["DRY", "FC", "FM"]

result = {
    "routes_created": [],
    "routes_skipped_existing": [],
    "errors": [],
}

# Verify each store warehouse exists before creating routes
for store, hub, _zone in ROUTE_BACKFILL:
    if not frappe.db.exists("Warehouse", store):
        result["errors"].append({"store": store, "error": f"Warehouse '{store}' does not exist"})

if not result["errors"]:
    for store, hub, zone in ROUTE_BACKFILL:
        for cargo in CARGO_TYPES:
            try:
                # Idempotency check
                existing = frappe.db.sql("""
                    SELECT r.name FROM `tabBEI Route` r
                    JOIN `tabBEI Route Stop` s ON s.parent = r.name
                    WHERE COALESCE(r.active,1) = 1
                      AND r.cargo_type = %(cargo)s
                      AND s.store = %(store)s
                    LIMIT 1
                """, {"cargo": cargo, "store": store}, as_dict=True)
                if existing:
                    result["routes_skipped_existing"].append({
                        "store": store, "cargo": cargo, "existing": existing[0]["name"],
                    })
                    continue

                store_short = store.split(" - ")[0]
                route = frappe.new_doc("BEI Route")
                route.route_name = f"{store_short} - {cargo}"
                route.cargo_type = cargo
                route.source_warehouse = hub
                route.active = 1
                route.append("stops", {
                    "store": store,
                    "stop_order": 1,
                })
                route.insert(ignore_permissions=True)
                frappe.db.commit()
                result["routes_created"].append({
                    "name": route.name,
                    "route_name": route.route_name,
                    "store": store,
                    "cargo": cargo,
                    "source_warehouse": hub,
                    "zone": zone,
                })
            except Exception as e:
                frappe.db.rollback()
                result["errors"].append({
                    "store": store, "cargo": cargo, "error": str(e)[:300],
                })

# Verify by re-querying
verify = {}
for store, _, _ in ROUTE_BACKFILL:
    routes = frappe.db.sql("""
        SELECT br.name, br.cargo_type, br.source_warehouse, br.active
        FROM `tabBEI Route Stop` brs
        INNER JOIN `tabBEI Route` br ON br.name = brs.parent
        WHERE brs.store = %(s)s AND br.active = 1
    """, {"s": store}, as_dict=True)
    verify[store] = [dict(r) for r in routes]
result["post_verify"] = verify

print(json.dumps(result, indent=2, default=str))
