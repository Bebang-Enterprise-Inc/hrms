"""S225 comprehensive test data seeding — runs INSIDE production Frappe container.

Seeds all data the L3 sweep needs:
  1. Toggle Stock Settings allow_negative_stock + allow_negative_stock_for_batch = 1
     (covers BACKFILL-20260421-* batches that are intentionally negative from Phase 3)
  2. Add 7 missing BEI Routes (per Route Planner UI — Sam's screenshot 2026-04-29)
     × 3 cargo types each (DRY, FC, FM) = 21 routes
  3. Material Receipt SEs for every orderable Finished Goods, Packaging Material,
     Kit, and Group item at PINNACLE COLD STORAGE - BKI + 3MD LOGISTICS - CAMANGYANAN - BKI
     (the two main hubs); buffer = 1000 units per item per hub

Returns full teardown ledger as JSON for the closeout reverser.
"""
import os, json, sys
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
from frappe.utils import nowdate, now_datetime
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

PCS_BKI = "PINNACLE COLD STORAGE SOLUTIONS - BKI"
HUB_3MD = "3MD Logistics - Camangyanan - BKI"
SEED_QTY = 1000  # generous buffer per item per hub
SEED_LABEL = "S229 retest seed: comprehensive (2026-04-29)"

result = {
    "timestamp": now_datetime().isoformat(),
    "stock_settings_pre": {},
    "stock_settings_post": {},
    "bei_routes_created": [],
    "stock_entries_created": [],
    "errors": [],
    "items_enumerated": 0,
    "items_seeded": 0,
}

# ---------- Step 1: Toggle Stock Settings ----------
result["stock_settings_pre"] = {
    "allow_negative_stock": frappe.db.get_single_value("Stock Settings", "allow_negative_stock"),
    "allow_negative_stock_for_batch": frappe.db.get_single_value("Stock Settings", "allow_negative_stock_for_batch"),
}
frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 1)
frappe.db.set_single_value("Stock Settings", "allow_negative_stock_for_batch", 1)
frappe.db.commit()
result["stock_settings_post"] = {
    "allow_negative_stock": frappe.db.get_single_value("Stock Settings", "allow_negative_stock"),
    "allow_negative_stock_for_batch": frappe.db.get_single_value("Stock Settings", "allow_negative_stock_for_batch"),
}

# ---------- Step 2: Add missing BEI Routes ----------
# Per Sam's Route Planner UI screenshot 2026-04-29:
#   3MD Marilao (North): NAIA T3, Estancia, Greenhills, Robinsons Antipolo
#   Pinnacle Calamba (South): Robinsons General Trias, Robinsons Imus, SM Sta Rosa
ROUTE_BACKFILL = [
    # (store_pattern_in_warehouse_name, hub, label)
    ("NAIA T3 - HALO-HALO TERMINAL FOOD CORP.", HUB_3MD, "S229 backfill: NAIA T3 → 3MD per Route Planner"),
    ("ORTIGAS ESTANCIA - BB ESTANCIA FOOD CORP.", HUB_3MD, "S229 backfill: ORTIGAS ESTANCIA → 3MD per Route Planner"),
    ("ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC", HUB_3MD, "S229 backfill: ORTIGAS GREENHILLS → 3MD per Route Planner"),
    ("ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.", HUB_3MD, "S229 backfill: ROBINSONS ANTIPOLO → 3MD per Route Planner"),
    ("ROBINSONS GENERAL TRIAS - BEBANG MEGA INC.", PCS_BKI, "S229 backfill: ROBINSONS GENERAL TRIAS → PCS-BKI per Route Planner"),
    ("ROBINSONS IMUS - BEBANG MEGA INC.", PCS_BKI, "S229 backfill: ROBINSONS IMUS → PCS-BKI per Route Planner"),
    ("SM STA. ROSA - SWEET HARMONY FOOD CORP.", PCS_BKI, "S229 backfill: SM STA. ROSA → PCS-BKI per Route Planner"),
]

CARGO_TYPES = ["DRY", "FC", "FM"]

# Verify BEI Route doctype exists (it does per earlier probes)
if not frappe.db.exists("DocType", "BEI Route"):
    result["errors"].append({"step": "routes", "error": "BEI Route DocType does not exist"})
else:
    for store, hub, label in ROUTE_BACKFILL:
        for cargo in CARGO_TYPES:
            try:
                # Check if a route for this (store, cargo) already exists
                existing = frappe.db.sql("""
                    SELECT r.name FROM `tabBEI Route` r
                    JOIN `tabBEI Route Stop` s ON s.parent = r.name
                    WHERE COALESCE(r.active, 1) = 1
                      AND r.cargo_type = %(cargo)s
                      AND s.store = %(store)s
                """, {"cargo": cargo, "store": store}, as_dict=True)
                if existing:
                    result["bei_routes_created"].append({
                        "store": store, "cargo": cargo, "hub": hub,
                        "status": "ALREADY_EXISTS",
                        "existing_name": existing[0]["name"],
                    })
                    continue

                route = frappe.new_doc("BEI Route")
                route.route_code = f"S229-{cargo}-{store[:30]}"  # fits route_code field
                route.cargo_type = cargo
                route.source_warehouse = hub
                route.active = 1
                # Add stop
                route.append("stops", {
                    "store": store,
                    "stop_order": 1,
                })
                route.insert(ignore_permissions=True)
                if hasattr(route, "submit"):
                    try:
                        route.submit()
                    except Exception:
                        pass  # may not be submittable
                frappe.db.commit()
                result["bei_routes_created"].append({
                    "doctype": "BEI Route",
                    "name": route.name,
                    "store": store,
                    "cargo": cargo,
                    "hub": hub,
                    "label": label,
                    "action_to_reverse": "DELETE",
                })
            except Exception as e:
                frappe.db.rollback()
                result["errors"].append({
                    "step": "routes",
                    "store": store, "cargo": cargo,
                    "error": str(e)[:300],
                })

# ---------- Step 3: Enumerate items + seed at both hubs ----------
# Items the test could pick (per OrderBuilder default + Sentry historical):
# - All Finished Goods (FG*)
# - All Packaging Materials (PM*)
# - All Kits (KL*)
# - GRP-FRESH-RIPE-MANGO (GRP-* group items)
ITEM_GROUP_FILTERS = [
    ["item_group", "in", ["Finished Goods", "Packaging Materials", "Kit"]],
    ["is_stock_item", "=", 1],
    ["disabled", "=", 0],
]
items_to_seed = frappe.get_all("Item",
    filters=ITEM_GROUP_FILTERS,
    fields=["name", "item_code", "item_group", "stock_uom", "has_batch_no"],
    limit_page_length=200)

# Also add GRP- prefixed items from any group
grp_items = frappe.get_all("Item",
    filters=[["item_code", "like", "GRP-%"], ["is_stock_item", "=", 1], ["disabled", "=", 0]],
    fields=["name", "item_code", "item_group", "stock_uom", "has_batch_no"],
    limit_page_length=50)
seen = {i["name"] for i in items_to_seed}
for g in grp_items:
    if g["name"] not in seen:
        items_to_seed.append(g)

result["items_enumerated"] = len(items_to_seed)
HUBS = [PCS_BKI, HUB_3MD]

for item in items_to_seed:
    item_code = item["item_code"]
    stock_uom = item["stock_uom"] or "Nos"
    for hub in HUBS:
        try:
            # Get current actual_qty
            cur_qty = float(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": hub}, "actual_qty") or 0)
            if cur_qty >= SEED_QTY:
                # Already enough stock
                continue

            qty_to_add = SEED_QTY - cur_qty if cur_qty > 0 else SEED_QTY
            company = frappe.db.get_value("Warehouse", hub, "company")

            se = frappe.new_doc("Stock Entry")
            se.stock_entry_type = "Material Receipt"
            se.purpose = "Material Receipt"
            se.posting_date = nowdate()
            se.posting_time = now_datetime().strftime("%H:%M:%S")
            se.set_posting_time = 1
            se.company = company
            se.append("items", {
                "item_code": item_code,
                "qty": qty_to_add,
                "uom": stock_uom,
                "stock_uom": stock_uom,
                "conversion_factor": 1,
                "t_warehouse": hub,
                "basic_rate": 1.0,
                "allow_zero_valuation_rate": 1,
            })
            se.remarks = SEED_LABEL
            se.insert(ignore_permissions=True)
            se.submit()
            frappe.db.commit()
            result["stock_entries_created"].append({
                "doctype": "Stock Entry",
                "name": se.name,
                "item_code": item_code,
                "qty": qty_to_add,
                "warehouse": hub,
                "label": SEED_LABEL,
                "action_to_reverse": "CANCEL",
            })
            result["items_seeded"] += 1
        except Exception as e:
            frappe.db.rollback()
            err_msg = str(e)[:300]
            result["errors"].append({
                "step": "seed_stock",
                "item": item_code,
                "warehouse": hub,
                "error": err_msg,
            })

result["summary"] = {
    "items_enumerated": result["items_enumerated"],
    "stock_entries_created": len(result["stock_entries_created"]),
    "bei_routes_created": len([r for r in result["bei_routes_created"] if r.get("action_to_reverse") == "DELETE"]),
    "bei_routes_skipped_existing": len([r for r in result["bei_routes_created"] if r.get("status") == "ALREADY_EXISTS"]),
    "errors": len(result["errors"]),
}

print(json.dumps(result, indent=2, default=str))
