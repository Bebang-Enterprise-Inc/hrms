"""Summary-only BEI Route probe to fit SSM 24KB limit."""
import os, json
from collections import Counter
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

result = {}

# 1. Route counts
result["bei_route_doctype_exists"] = bool(frappe.db.exists("DocType", "BEI Route"))
total_routes = frappe.db.count("BEI Route", filters={"active": 1})
total_stops = frappe.db.count("BEI Route Stop")
result["total_active_routes"] = total_routes
result["total_stops"] = total_stops

# 2. Cargo type distribution
ctypes = frappe.db.sql("""SELECT cargo_type, COUNT(*) AS n
                          FROM `tabBEI Route`
                          WHERE COALESCE(active,1)=1
                          GROUP BY cargo_type
                          ORDER BY n DESC""", as_dict=True)
result["cargo_type_distribution"] = ctypes

# 3. Source warehouse distribution
swhs = frappe.db.sql("""SELECT source_warehouse, COUNT(*) AS n
                        FROM `tabBEI Route`
                        WHERE COALESCE(active,1)=1
                        GROUP BY source_warehouse
                        ORDER BY n DESC""", as_dict=True)
result["source_warehouse_distribution"] = swhs

# 4. PM001 + FG001 metadata
for it in ["PM001","FG001"]:
    d = frappe.get_doc("Item", it)
    result[f"{it}_meta"] = {
        "item_name": d.item_name,
        "item_group": d.item_group,
        "cargo_category": getattr(d, "cargo_category", None),
        "lane": getattr(d, "lane", None),
    }

# 5. For each failed store, how many routes? what cargo types?
failed_stores = [
    "AYALA MARKET MARKET", "AYALA SOLENAD", "AYALA VERMOSA",
    "MEGAWORLD PASEO CENTER", "NAIA T3",
    "ORTIGAS ESTANCIA", "ORTIGAS GREENHILLS",
    "ROBINSONS ANTIPOLO", "ROBINSONS GENERAL TRIAS", "ROBINSONS IMUS",
    "SM BICUTAN", "SM MARIKINA", "SM SOUTHMALL", "SM STA. ROSA",
]
result["failed_stores_routes"] = {}
for store in failed_stores:
    rows = frappe.db.sql("""
        SELECT s.store, r.cargo_type, r.source_warehouse, r.active
        FROM `tabBEI Route Stop` s
        JOIN `tabBEI Route` r ON r.name = s.parent
        WHERE UPPER(s.store) LIKE %(pat)s
        ORDER BY r.cargo_type
    """, {"pat": f"%{store}%"}, as_dict=True)
    result["failed_stores_routes"][store] = rows

# 6. What does the resolver pick for SM STA. ROSA + DRY? Run it directly.
from hrms.utils.supply_chain_contracts import resolve_route_source_warehouse
result["resolver_test"] = {}
for store in ["SM Sta. Rosa - SWEET HARMONY FOOD CORP.", "AYALA MARKET MARKET - BEBANG MARKET MARKET INC.", "NAIA T3 - HALO-HALO TERMINAL FOOD CORP."]:
    for cargo in ["DRY", "FROZEN", "FRESH", "FC", "FM"]:
        result["resolver_test"][f"{store}|{cargo}"] = resolve_route_source_warehouse(store, cargo)

print(json.dumps(result, indent=2, default=str))
