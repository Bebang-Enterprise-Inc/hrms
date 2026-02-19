# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Commissary Dashboard & Production Tracking APIs.
Split from commissary.py (P0-11) for maintainability.
"""

import frappe
from frappe import _
import json
from frappe.utils import today, add_days, flt

from hrms.api.commissary import get_commissary_warehouse
from hrms.utils.bei_config import get_company


# ============================================================
# DASHBOARD / SUMMARY
# ============================================================

@frappe.whitelist()
def get_commissary_dashboard():
    """
    Get commissary supervisor dashboard summary.
    """
    commissary_warehouse = get_commissary_warehouse()
    today_date = today()

    # Today's production (Stock Entries with type=Manufacture)
    todays_production = frappe.db.count(
        "Stock Entry",
        filters={
            "stock_entry_type": "Manufacture",
            "posting_date": today_date,
            "to_warehouse": commissary_warehouse
        }
    )

    # Low stock alerts (items below product-specific reorder level)
    low_stock_count = frappe.db.sql("""
        SELECT COUNT(DISTINCT b.item_code)
        FROM `tabBin` b
        JOIN `tabItem` i ON i.name = b.item_code
        WHERE b.warehouse = %s
        AND (
            b.actual_qty <= 0
            OR (i.item_code LIKE 'FG%%' AND b.actual_qty < 7)
            OR (i.item_code NOT LIKE 'FG%%' AND b.actual_qty < IFNULL(i.safety_stock, 10))
        )
        AND i.is_stock_item = 1
    """, commissary_warehouse)[0][0] or 0

    # Pending store orders
    pending_orders = frappe.db.count(
        "Material Request",
        filters={
            "status": ["in", ["Pending", "Partially Ordered"]],
            "docstatus": 1,
            "material_request_type": "Material Transfer"
        }
    )

    # Today's dispatches
    todays_dispatches = frappe.db.count(
        "Stock Entry",
        filters={
            "stock_entry_type": "Material Transfer",
            "posting_date": today_date,
            "from_warehouse": commissary_warehouse
        }
    )

    # FQI issues (last 7 days)
    fqi_issues = frappe.db.count("BEI FQI Report", {
        "status": ["in", ["Open", "Under Review"]],
        "creation": [">=", add_days(today_date, -7)]
    })

    # Recent production activity
    recent_production = frappe.get_all(
        "Stock Entry",
        filters={
            "stock_entry_type": "Manufacture",
            "posting_date": [">=", add_days(today_date, -3)],
            "to_warehouse": commissary_warehouse,
            "docstatus": 1
        },
        fields=["name", "posting_date", "total_outgoing_value", "remarks"],
        order_by="posting_date desc",
        limit=5
    )

    # Current stock summary
    stock_summary = frappe.db.sql("""
        SELECT
            COUNT(DISTINCT b.item_code) as total_items,
            SUM(b.actual_qty) as total_qty,
            SUM(b.actual_qty * IFNULL(i.valuation_rate, 0)) as total_value
        FROM `tabBin` b
        JOIN `tabItem` i ON i.name = b.item_code
        WHERE b.warehouse = %s
        AND b.actual_qty > 0
    """, commissary_warehouse, as_dict=True)[0]

    return {
        "success": True,
        "data": {
            "commissary_warehouse": commissary_warehouse,
            "todays_production": todays_production,
            "low_stock_count": low_stock_count,
            "pending_orders": pending_orders,
            "todays_dispatches": todays_dispatches,
            "fqi_issues": fqi_issues,
            "recent_production": recent_production,
            "stock_summary": {
                "total_items": stock_summary.get("total_items") or 0,
                "total_qty": flt(stock_summary.get("total_qty") or 0),
                "total_value": flt(stock_summary.get("total_value") or 0)
            }
        }
    }


# ============================================================
# PRODUCTION TRACKING
# ============================================================

@frappe.whitelist()
def get_production_items():
    """
    Get finished goods that commissary produces.
    Returns items with current stock levels.
    """
    commissary_warehouse = get_commissary_warehouse()

    # P0-12: Batch query — get items + stock in one query (was N+1)
    items = frappe.db.sql("""
        SELECT DISTINCT
            i.name as item_code,
            i.item_name,
            i.description,
            i.stock_uom,
            i.valuation_rate as standard_rate,
            i.item_group,
            IFNULL(b.actual_qty, 0) as current_stock
        FROM `tabItem` i
        LEFT JOIN `tabBin` b ON b.item_code = i.name AND b.warehouse = %s
        WHERE i.disabled = 0
        AND i.is_stock_item = 1
        AND (i.item_group = 'Finished Goods' OR b.actual_qty > 0)
        ORDER BY i.item_name
    """, commissary_warehouse, as_dict=True)

    # P0-12: Batch query — get today's production for ALL items in one query (was N+1)
    today_production = frappe.db.sql("""
        SELECT sed.item_code, SUM(sed.qty) as total_produced
        FROM `tabStock Entry` se
        JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
        WHERE se.stock_entry_type = 'Manufacture'
        AND se.posting_date = %s
        AND sed.t_warehouse = %s
        AND se.docstatus = 1
        GROUP BY sed.item_code
    """, (today(), commissary_warehouse), as_dict=True)
    production_map = {r.item_code: flt(r.total_produced) for r in today_production}

    for item in items:
        item["current_stock"] = flt(item["current_stock"])
        item["today_produced"] = production_map.get(item["item_code"], 0.0)

    return {"success": True, "data": items}


def get_or_create_batch(batch_id, item_code):
    """
    Get existing batch or create a new one.
    Frappe requires Batch documents to exist before referencing in Stock Entry.
    """
    batch_id = batch_id.strip()
    if not batch_id:
        return None

    # Check if batch already exists
    if frappe.db.exists("Batch", batch_id):
        return batch_id

    # Check if item has batch tracking enabled
    has_batch_no = frappe.db.get_value("Item", item_code, "has_batch_no")
    if not has_batch_no:
        return None

    # Create new batch
    batch = frappe.new_doc("Batch")
    batch.batch_id = batch_id
    batch.item = item_code
    batch.manufacturing_date = today()
    batch.insert(ignore_permissions=True)

    return batch.name


@frappe.whitelist()
def submit_production_output(items, batch_no=None, remarks=None):
    """
    Record production batch output.
    Creates Stock Entry with type=Manufacture.

    Args:
        items: JSON array of {item_code, qty, uom}
        batch_no: Optional batch reference (will auto-create if doesn't exist)
        remarks: Optional production notes
    """
    if isinstance(items, str):
        items = json.loads(items)

    if not items:
        frappe.throw(_("No items to record"))

    commissary_warehouse = get_commissary_warehouse()

    se = frappe.new_doc("Stock Entry")
    se.company = get_company()
    se.posting_date = today()
    se.posting_time = frappe.utils.nowtime()
    se.to_warehouse = commissary_warehouse
    se.remarks = remarks or f"Production batch: {batch_no or 'No batch'}"

    # Try Manufacture type if BOM exists (auto-deducts raw materials)
    # Fall back to Material Receipt if no BOM available
    first_item_code = items[0]["item_code"] if items else None
    bom = None
    if first_item_code:
        bom = frappe.db.get_value(
            "BOM",
            {"item": first_item_code, "is_active": 1, "is_default": 1, "docstatus": 1},
            ["name", "quantity"],
            as_dict=True
        )

    if bom:
        # Use Manufacture type - auto-deducts RM from BOM
        se.stock_entry_type = "Manufacture"
        se.from_bom = 1
        se.bom_no = bom.name
        se.fg_completed_qty = sum(flt(i["qty"]) for i in items)
        se.from_warehouse = commissary_warehouse  # RM source
        se.get_items()

        # Only add FG if not already present from BOM
        fg_already_present = any(
            item.item_code == first_item_code and item.is_finished_item
            for item in se.items
        )
        item = frappe.get_doc("Item", first_item_code)
        if not fg_already_present:
            fg_row = se.append("items", {
                "item_code": first_item_code,
                "item_name": item.item_name,
                "description": item.description,
                "qty": se.fg_completed_qty,
                "uom": item.stock_uom,
                "stock_uom": item.stock_uom,
                "conversion_factor": 1,
                "t_warehouse": commissary_warehouse,
                "is_finished_item": 1,
                "is_scrap_item": 0,
            })
        else:
            # Get reference to the existing FG row for batch assignment below
            fg_row = next(
                i for i in se.items
                if i.item_code == first_item_code and i.is_finished_item
            )

        # Override batch on FG if provided
        if batch_no and batch_no.strip():
            valid_batch = get_or_create_batch(batch_no, first_item_code)
            if valid_batch:
                fg_row.batch_no = valid_batch
    else:
        # Fallback: Material Receipt (no RM deduction)
        se.stock_entry_type = "Material Receipt"

        for item_data in items:
            item = frappe.get_doc("Item", item_data["item_code"])

            item_row = {
                "item_code": item_data["item_code"],
                "item_name": item.item_name,
                "description": item.description,
                "qty": flt(item_data["qty"]),
                "uom": item_data.get("uom") or item.stock_uom,
                "stock_uom": item.stock_uom,
                "conversion_factor": 1,
                "t_warehouse": commissary_warehouse,
            }
            if batch_no and batch_no.strip():
                valid_batch = get_or_create_batch(batch_no, item_data["item_code"])
                if valid_batch:
                    item_row["batch_no"] = valid_batch
            se.append("items", item_row)

    se.insert()
    se.submit()

    # G-051: FEFO warnings — check if older batches were skipped
    fefo_warnings = _check_fefo_warnings(se, commissary_warehouse)

    result = {
        "success": True,
        "data": {
            "name": se.name,
            "total_qty": sum(i.qty for i in se.items),
            "items_count": len(se.items)
        },
        "message": f"Production recorded: {se.name}"
    }
    if fefo_warnings:
        result["fefo_warnings"] = fefo_warnings
    return result


def _check_fefo_warnings(stock_entry, warehouse):
    """G-051: Check if any items in the Stock Entry used a newer batch when older ones exist."""
    warnings = []
    for item in stock_entry.items:
        if not item.batch_no or not item.s_warehouse:
            continue
        # Find oldest available batch for this item
        oldest = frappe.db.sql("""
            SELECT b.name, b.expiry_date
            FROM `tabBatch` b
            JOIN `tabStock Ledger Entry` sle ON sle.batch_no = b.name
            WHERE sle.item_code = %s AND sle.warehouse = %s
            AND b.expiry_date IS NOT NULL AND b.expiry_date > CURDATE()
            GROUP BY b.name HAVING SUM(sle.actual_qty) > 0
            ORDER BY b.expiry_date ASC LIMIT 1
        """, (item.item_code, item.s_warehouse), as_dict=True)

        if oldest and oldest[0].name != item.batch_no:
            used_expiry = frappe.db.get_value("Batch", item.batch_no, "expiry_date")
            if used_expiry and oldest[0].expiry_date and used_expiry > oldest[0].expiry_date:
                warnings.append({
                    "item_code": item.item_code,
                    "used_batch": item.batch_no,
                    "used_expiry": str(used_expiry),
                    "older_batch": oldest[0].name,
                    "older_expiry": str(oldest[0].expiry_date),
                })
    return warnings


@frappe.whitelist()
def get_production_history(date_from=None, date_to=None, limit=20):
    """
    Get production history.
    """
    commissary_warehouse = get_commissary_warehouse()

    filters = {
        "stock_entry_type": ["in", ["Manufacture", "Material Receipt"]],
        "to_warehouse": commissary_warehouse,
        "docstatus": 1
    }

    if date_from and date_to:
        filters["posting_date"] = ["between", [date_from, date_to]]
    elif date_from:
        filters["posting_date"] = [">=", date_from]
    elif date_to:
        filters["posting_date"] = ["<=", date_to]

    entries = frappe.get_all(
        "Stock Entry",
        filters=filters,
        fields=["name", "posting_date", "remarks", "owner"],
        order_by="posting_date desc",
        limit=int(limit)
    )

    # Add item details for each entry
    for entry in entries:
        items = frappe.get_all(
            "Stock Entry Detail",
            filters={"parent": entry["name"]},
            fields=["item_code", "item_name", "qty", "uom"]
        )
        entry["items"] = items
        entry["total_qty"] = sum(i.get("qty", 0) for i in items)
        entry["items_count"] = len(items)

    return {"success": True, "data": entries}
