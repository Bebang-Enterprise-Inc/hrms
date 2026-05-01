"""Inspect MR-00709 (SM MARIKINA WR-missing) + AYALA VERMOSA order/MR state."""
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

result = {}

# MR-00709
mr_name = "MAT-MR-2026-00709"
if frappe.db.exists("Material Request", mr_name):
    mr = frappe.db.get_value("Material Request", mr_name,
        ["name","docstatus","status","material_request_type","set_warehouse","custom_source_warehouse","custom_destination_warehouse","custom_cargo_lane","creation","modified"], as_dict=True)
    result["MR-00709"] = mr
    items = frappe.db.sql("""
        SELECT item_code, qty, warehouse, from_warehouse, ordered_qty, received_qty
        FROM `tabMaterial Request Item`
        WHERE parent = %s
    """, mr_name, as_dict=True)
    result["MR-00709_items"] = items

    # Check if any BEI Warehouse Receiving exists — use parent table linked_material_request or filter by remarks
    if frappe.db.exists("DocType", "BEI Warehouse Receiving"):
        wr_meta = frappe.get_meta("BEI Warehouse Receiving")
        wr_fields = [f.fieldname for f in wr_meta.fields]
        result["WR_doctype_fields"] = wr_fields[:40]
        # Try common patterns for MR linkage
        wrs = frappe.db.sql("""
            SELECT name, status, source_warehouse, target_warehouse, source_type, creation, remarks
            FROM `tabBEI Warehouse Receiving`
            WHERE creation > NOW() - INTERVAL 6 HOUR
            ORDER BY creation DESC LIMIT 20
        """, as_dict=True)
        # Filter for the MR
        result["MR-00709_WR_recent"] = [w for w in wrs if mr_name in (w.get("remarks") or "")][:5]
        result["recent_WRs_count"] = len(wrs)

# AYALA VERMOSA order BEI-ORD-2026-00577
ord_name = "BEI-ORD-2026-00577"
if frappe.db.exists("BEI Order", ord_name):
    o = frappe.db.get_value("BEI Order", ord_name,
        ["name","docstatus","status","store","cargo_category","creation"], as_dict=True)
    result["ORD-00577"] = o
    o_items = frappe.db.sql("""
        SELECT item_code, qty_requested, qty_approved, source_warehouse, group_resolution_status
        FROM `tabBEI Order Item`
        WHERE parent = %s
    """, ord_name, as_dict=True)
    result["ORD-00577_items"] = o_items
    # Was an MR ever created for it? (use remarks pattern)
    mrs = frappe.db.sql("""
        SELECT name, docstatus, status, set_warehouse, creation FROM `tabMaterial Request`
        WHERE remarks LIKE %s
        ORDER BY creation DESC LIMIT 5
    """, f"%{ord_name}%", as_dict=True)
    result["ORD-00577_MRs"] = mrs

# Bin state for AYALA VERMOSA's likely route (PCS-BKI)
PCS = "PINNACLE COLD STORAGE SOLUTIONS - BKI"
for it in ["PM001","FG001","FG002","KL001","KL004"]:
    bin_q = frappe.db.get_value("Bin", {"item_code": it, "warehouse": PCS}, ["actual_qty","projected_qty"], as_dict=True)
    result.setdefault("PCS_BINS_NOW", {})[it] = bin_q

print(json.dumps(result, indent=2, default=str))
