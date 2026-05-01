"""Trace SM MARIKINA's failed MR -> SE -> WR chain.

The test reported: Error: No BEI Warehouse Receiving produced for MR MAT-MR-2026-00869

We need to find:
 1. MR MAT-MR-2026-00869 — does it exist? what's its company / set_warehouse / status?
 2. Any Stock Entry that references this MR (against_material_request)
 3. Any BEI Warehouse Receiving with stock_entry = that SE name
 4. The Order linked to this MR (BEI Order)

This will tell us at which exact step the dispatch chain broke."""
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
MR_NAME = "MAT-MR-2026-00900"

# 1. The MR itself
mr = frappe.db.get_value("Material Request", MR_NAME, "*", as_dict=True)
result["mr"] = dict(mr) if mr else {"NOT_FOUND": True}

# 2. MR items
if mr:
    mr_items = frappe.db.sql("""
        SELECT item_code, qty, warehouse
        FROM `tabMaterial Request Item`
        WHERE parent = %(mr)s
    """, {"mr": MR_NAME}, as_dict=True)
    result["mr_items"] = [dict(r) for r in mr_items]

# 3. Stock Entries referencing this MR (via against_material_request OR remarks)
ses = frappe.db.sql("""
    SELECT name, docstatus, stock_entry_type, purpose, from_warehouse, to_warehouse, company, creation, remarks
    FROM `tabStock Entry`
    WHERE creation > NOW() - INTERVAL 6 HOUR
    ORDER BY creation DESC
    LIMIT 50
""", as_dict=True)
# Filter to ones likely connected — match against MR via Stock Entry Detail
ses_for_mr = []
for se in ses:
    items = frappe.db.sql("""
        SELECT material_request, material_request_item, item_code, qty, s_warehouse, t_warehouse
        FROM `tabStock Entry Detail`
        WHERE parent = %(se)s AND material_request = %(mr)s
    """, {"se": se["name"], "mr": MR_NAME}, as_dict=True)
    if items:
        ses_for_mr.append({"se": dict(se), "items": [dict(i) for i in items]})
result["ses_referencing_mr"] = ses_for_mr

# 4. BEI Warehouse Receivings that reference any SE found
if ses_for_mr:
    se_names = [r["se"]["name"] for r in ses_for_mr]
    # Discover schema
    wr_meta = frappe.get_meta("BEI Warehouse Receiving")
    wr_fields = {f.fieldname for f in wr_meta.fields}
    cond_fields = []
    if "stock_entry" in wr_fields:
        cond_fields.append("stock_entry")
    if "material_request" in wr_fields:
        cond_fields.append("material_request")
    result["wr_doctype_fields_relevant"] = cond_fields
    # search WRs by stock_entry
    wrs = frappe.db.sql(f"""
        SELECT name, status, docstatus, target_warehouse, source_warehouse, stock_entry, creation
        FROM `tabBEI Warehouse Receiving`
        WHERE stock_entry IN %(ses)s
    """, {"ses": tuple(se_names)}, as_dict=True)
    result["wrs_found_by_stock_entry"] = [dict(r) for r in wrs]
else:
    result["wrs_found_by_stock_entry"] = "no_ses_to_search"

# 5. Search for any WR with target_warehouse like SM MARIKINA in last 6h (case variants)
wrs_any = frappe.db.sql("""
    SELECT name, status, docstatus, target_warehouse, source_warehouse, stock_entry, creation
    FROM `tabBEI Warehouse Receiving`
    WHERE creation > NOW() - INTERVAL 6 HOUR
      AND (target_warehouse LIKE '%MARIKINA%' OR target_warehouse LIKE '%SMK%')
    ORDER BY creation DESC
    LIMIT 10
""", as_dict=True)
result["wrs_marikina_match_6h"] = [dict(r) for r in wrs_any]

# 6. Look at the BEI Approval Queue for this MR (schema-aware)
try:
    aq_meta = frappe.get_meta("BEI Approval Queue")
    aq_fields = {f.fieldname for f in aq_meta.fields}
    name_field = "document_name" if "document_name" in aq_fields else (
        "reference_name" if "reference_name" in aq_fields else None
    )
    if name_field:
        select_cols = ["name", name_field, "creation"]
        for opt in ["doctype_name", "reference_doctype", "queue_status", "status", "action_type"]:
            if opt in aq_fields:
                select_cols.append(opt)
        aq = frappe.db.sql(f"""
            SELECT {','.join('`'+c+'`' for c in select_cols)}
            FROM `tabBEI Approval Queue`
            WHERE `{name_field}` = %(mr)s
            ORDER BY creation DESC
        """, {"mr": MR_NAME}, as_dict=True)
        result["approval_queue_entries"] = [dict(r) for r in aq]
        result["approval_queue_field_used"] = name_field
    else:
        result["approval_queue_entries"] = "no_compatible_field"
except Exception as e:
    result["approval_queue_entries"] = f"ERROR: {str(e)[:200]}"

# 7. Find the BEI Order linked to this MR (via material_request or BEI Order Item)
try:
    order_meta = frappe.get_meta("BEI Order")
    order_fields = {f.fieldname for f in order_meta.fields}
    if "material_request" in order_fields:
        orders = frappe.db.sql("""
            SELECT name, status, store, creation
            FROM `tabBEI Order`
            WHERE material_request = %(mr)s
        """, {"mr": MR_NAME}, as_dict=True)
        result["orders_for_mr"] = [dict(r) for r in orders]
    else:
        # Try via BEI Order Item child table
        try:
            orders = frappe.db.sql("""
                SELECT DISTINCT bo.name, bo.status, bo.store, bo.creation
                FROM `tabBEI Order` bo
                INNER JOIN `tabBEI Order Item` boi ON boi.parent = bo.name
                WHERE boi.material_request = %(mr)s
            """, {"mr": MR_NAME}, as_dict=True)
            result["orders_for_mr"] = [dict(r) for r in orders]
        except Exception:
            result["orders_for_mr"] = "no_link_found_via_child"
except Exception as e:
    result["orders_for_mr"] = f"ERROR: {str(e)[:200]}"

# 8. Find Bin state for items that should have been transferred
if mr and mr.get("set_warehouse"):
    bins_target = frappe.db.sql("""
        SELECT b.warehouse, b.item_code, b.actual_qty
        FROM `tabBin` b
        INNER JOIN `tabMaterial Request Item` mri ON mri.item_code = b.item_code
        WHERE mri.parent = %(mr)s
          AND b.warehouse = %(wh)s
    """, {"mr": MR_NAME, "wh": mr["set_warehouse"]}, as_dict=True)
    result["target_warehouse_bins"] = [dict(r) for r in bins_target]

print(json.dumps(result, indent=2, default=str))
