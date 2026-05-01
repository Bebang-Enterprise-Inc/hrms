"""S225 comprehensive fix — sweep #4:
  1. Add BEI Routes for 5 stores currently hitting defect #1 fallback
     (geography per Route Planner UI 2026-04-29 screenshot):
       - NAIA T3 (Pasay airport)               → 3MD Logistics - Camangyanan - BKI (North)
       - ORTIGAS ESTANCIA (Pasig)              → 3MD Logistics - Camangyanan - BKI (North)
       - ORTIGAS GREENHILLS (San Juan)         → 3MD Logistics - Camangyanan - BKI (North)
       - ROBINSONS ANTIPOLO (Antipolo, Rizal)  → 3MD Logistics - Camangyanan - BKI (North)
       - SM STA. ROSA (Laguna)                 → Pinnacle Cold Storage Solutions - BKI (South)
     × 3 cargo types each (DRY, FC, FM) = 15 routes total
  2. Toggle Stock Settings allow_negative_stock + allow_negative_stock_for_batch = 1
  3. Narrow seed: PM001/KL001/KL004 at both hubs (only items currently low/empty)

CEO authorization 2026-04-30: explicit approval to add routes based on geography.
"""
import os, json
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

# Per Route Planner UI screenshot 2026-04-29:
#   3MD Marilao (North): NAIA T3, Estancia, Greenhills, Robinsons Antipolo
#   Pinnacle Calamba (South): SM Sta Rosa
ROUTE_BACKFILL = [
    ("NAIA T3 - HALO-HALO TERMINAL FOOD CORP.", HUB_3MD, "north"),
    ("ORTIGAS ESTANCIA - BB ESTANCIA FOOD CORP.", HUB_3MD, "north"),
    ("ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC", HUB_3MD, "north"),
    ("ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.", HUB_3MD, "north"),
    ("SM STA. ROSA - SWEET HARMONY FOOD CORP.", PCS_BKI, "south"),
]
CARGO_TYPES = ["DRY", "FC", "FM"]

result = {
    "stock_settings_pre": {
        "allow_negative_stock": frappe.db.get_single_value("Stock Settings", "allow_negative_stock"),
        "allow_negative_stock_for_batch": frappe.db.get_single_value("Stock Settings", "allow_negative_stock_for_batch"),
    },
    "routes_created": [],
    "routes_skipped_existing": [],
    "ses_created": [],
    "errors": [],
}

# ---------- 1. Add BEI Routes ----------
for store, hub, zone in ROUTE_BACKFILL:
    for cargo in CARGO_TYPES:
        try:
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

            store_short = store.split(" - ")[0]  # e.g., "NAIA T3"
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
                "doctype": "BEI Route",
                "name": route.name,
                "route_name": route.route_name,
                "cargo": cargo,
                "store": store,
                "hub": hub,
                "zone": zone,
                "action_to_reverse": "DELETE",
            })
        except Exception as e:
            frappe.db.rollback()
            result["errors"].append({
                "step": "route", "store": store, "cargo": cargo, "error": str(e)[:300],
            })

# ---------- 2. Toggle Stock Settings ----------
frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 1)
frappe.db.set_single_value("Stock Settings", "allow_negative_stock_for_batch", 1)
frappe.db.commit()
result["stock_settings_post"] = {
    "allow_negative_stock": frappe.db.get_single_value("Stock Settings", "allow_negative_stock"),
    "allow_negative_stock_for_batch": frappe.db.get_single_value("Stock Settings", "allow_negative_stock_for_batch"),
}

# ---------- 3. Narrow seed (only the items historically failing) ----------
SEED_LABEL = "S229 sweep4 narrow seed (2026-04-30)"
SEED_QTY = 500
SEED_ITEMS = ["PM001", "KL001", "KL004"]
HUBS = [PCS_BKI, HUB_3MD]

for item_code in SEED_ITEMS:
    if not frappe.db.exists("Item", item_code):
        result["errors"].append({"step": "seed", "item": item_code, "error": "ITEM_NOT_IN_MASTER"})
        continue
    stock_uom = frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"
    for hub in HUBS:
        try:
            cur = float(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": hub}, "actual_qty") or 0)
            if cur >= SEED_QTY:
                continue
            qty_to_add = SEED_QTY - cur if cur > 0 else SEED_QTY
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
            result["ses_created"].append({
                "name": se.name, "item": item_code, "qty": qty_to_add, "warehouse": hub,
            })
        except Exception as e:
            frappe.db.rollback()
            result["errors"].append({"step": "seed", "item": item_code, "warehouse": hub, "error": str(e)[:200]})

result["summary"] = {
    "routes_created": len(result["routes_created"]),
    "routes_skipped_existing": len(result["routes_skipped_existing"]),
    "ses_created": len(result["ses_created"]),
    "errors": len(result["errors"]),
}

print(json.dumps(result, indent=2, default=str))
