# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Commissary Supervisor APIs
Handles production tracking, inventory monitoring, and store order fulfillment.

Author: Claude Code
Date: 2026-02-02
"""
import frappe
from frappe import _
import json
from frappe.utils import today, add_days, flt


def get_commissary_warehouse():
    """Get the commissary warehouse name (handles test vs production)."""
    # Check if TEST-COMMISSARY exists and has stock
    test_commissary = "TEST-COMMISSARY - BEI"
    prod_commissary = "Commissary - BEI"

    if frappe.db.exists("Warehouse", test_commissary):
        # Check if it has any stock
        stock = frappe.db.sql("""
            SELECT COUNT(*) FROM `tabBin` WHERE warehouse = %s AND actual_qty > 0
        """, test_commissary)[0][0]
        if stock > 0:
            return test_commissary

    return prod_commissary


# ============================================================
# 1. DASHBOARD / SUMMARY
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
    # This is an approximation - for FG items, use target_di/2 as safety threshold
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

    # FQI issues (last 7 days) - disabled until DocType is created
    fqi_issues = 0
    # TODO: Enable when BEI FQI Report DocType is created
    # if frappe.db.exists("DocType", "BEI FQI Report"):
    #     fqi_issues = frappe.db.count(
    #         "BEI FQI Report",
    #         filters={
    #             "inspection_date": [">=", add_days(today_date, -7)],
    #             "status": "Failed"
    #         }
    #     )

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
# 2. PRODUCTION TRACKING
# ============================================================

@frappe.whitelist()
def get_production_items():
    """
    Get finished goods that commissary produces.
    Returns items with current stock levels.
    """
    commissary_warehouse = get_commissary_warehouse()

    # Get FG items (item_group = "Finished Goods") or any items with stock
    items = frappe.db.sql("""
        SELECT DISTINCT
            i.name as item_code,
            i.item_name,
            i.description,
            i.stock_uom,
            i.valuation_rate as standard_rate,
            i.item_group
        FROM `tabItem` i
        LEFT JOIN `tabBin` b ON b.item_code = i.name AND b.warehouse = %s
        WHERE i.disabled = 0
        AND i.is_stock_item = 1
        AND (i.item_group = 'Finished Goods' OR b.actual_qty > 0)
        ORDER BY i.item_name
    """, commissary_warehouse, as_dict=True)

    # Add current stock for each item
    for item in items:
        bin_qty = frappe.db.get_value(
            "Bin",
            {"item_code": item["item_code"], "warehouse": commissary_warehouse},
            "actual_qty"
        ) or 0
        item["current_stock"] = flt(bin_qty)

        # Get today's production
        item["today_produced"] = flt(frappe.db.sql("""
            SELECT IFNULL(SUM(sed.qty), 0)
            FROM `tabStock Entry` se
            JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
            WHERE se.stock_entry_type = 'Manufacture'
            AND se.posting_date = %s
            AND sed.item_code = %s
            AND sed.t_warehouse = %s
            AND se.docstatus = 1
        """, (today(), item["item_code"], commissary_warehouse))[0][0] or 0)

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
        # Item doesn't use batch tracking - skip batch_no
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

    # Create Stock Entry for production output (Material Receipt for now)
    # Note: True Manufacture type requires BOM setup
    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Receipt"  # Use Material Receipt since we don't have BOM
    se.company = "Bebang Enterprise Inc."
    se.posting_date = today()
    se.posting_time = frappe.utils.nowtime()
    se.to_warehouse = commissary_warehouse
    se.remarks = remarks or f"Production batch: {batch_no or 'No batch'}"

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
        # Auto-create batch if it doesn't exist (only for batch-tracked items)
        if batch_no and batch_no.strip():
            valid_batch = get_or_create_batch(batch_no, item_data["item_code"])
            if valid_batch:
                item_row["batch_no"] = valid_batch
        se.append("items", item_row)

    se.insert()
    se.submit()

    return {
        "success": True,
        "data": {
            "name": se.name,
            "total_qty": sum(i.qty for i in se.items),
            "items_count": len(se.items)
        },
        "message": f"Production recorded: {se.name}"
    }


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


# ============================================================
# 3. INVENTORY MONITORING
# ============================================================

@frappe.whitelist()
def get_inventory_levels(item_group=None, show_low_stock_only=False):
    """
    Get current inventory levels at commissary.
    Uses per-product thresholds instead of hardcoded values.
    """
    commissary_warehouse = get_commissary_warehouse()

    conditions = "WHERE b.warehouse = %s AND i.disabled = 0 AND i.is_stock_item = 1"
    params = [commissary_warehouse]

    if item_group:
        conditions += " AND i.item_group = %s"
        params.append(item_group)

    # Get all items first, then apply product-specific thresholds
    items = frappe.db.sql("""
        SELECT
            b.item_code,
            i.item_name,
            i.item_group,
            i.stock_uom as uom,
            b.actual_qty as current_qty,
            i.valuation_rate
        FROM `tabBin` b
        JOIN `tabItem` i ON i.name = b.item_code
        {conditions}
        ORDER BY i.item_name
    """.format(conditions=conditions), params, as_dict=True)

    result = []
    for item in items:
        # Get product-specific thresholds
        threshold = get_product_threshold(item["item_code"])
        # Use target_di as a proxy for reorder level (days of stock = quantity threshold for now)
        # For a proper calculation, we'd need avg daily consumption
        safety_stock = threshold["target_di"] // 2  # Half of target DI
        reorder_level = threshold["target_di"]

        # Determine stock status
        qty = flt(item["current_qty"])
        if qty <= 0:
            stock_status = "Out of Stock"
        elif qty < safety_stock:
            stock_status = "Low Stock"
        elif qty < reorder_level:
            stock_status = "Reorder"
        else:
            stock_status = "OK"

        # Skip if filtering for low stock only
        if (show_low_stock_only == "1" or show_low_stock_only is True) and stock_status == "OK":
            continue

        item["safety_stock"] = safety_stock
        item["reorder_level"] = reorder_level
        item["stock_status"] = stock_status
        item["value"] = qty * flt(item["valuation_rate"] or 0)
        item["shelf_life"] = threshold["shelf_life"]
        item["storage_temp"] = threshold["storage_temp"]
        result.append(item)

    # Sort by status priority
    status_order = {"Out of Stock": 0, "Low Stock": 1, "Reorder": 2, "OK": 3}
    result.sort(key=lambda x: (status_order.get(x["stock_status"], 99), x["item_name"]))

    return {"success": True, "data": result}


@frappe.whitelist()
def get_low_stock_alerts():
    """
    Get items below safety stock or reorder level.
    Uses per-product thresholds instead of hardcoded values.
    """
    commissary_warehouse = get_commissary_warehouse()

    # Get all items with stock
    items = frappe.db.sql("""
        SELECT
            b.item_code,
            i.item_name,
            i.item_group,
            i.stock_uom as uom,
            b.actual_qty as current_qty
        FROM `tabBin` b
        JOIN `tabItem` i ON i.name = b.item_code
        WHERE b.warehouse = %s
        AND i.disabled = 0
        AND i.is_stock_item = 1
        ORDER BY i.item_name
    """, commissary_warehouse, as_dict=True)

    alerts = []
    for item in items:
        # Get product-specific thresholds
        threshold = get_product_threshold(item["item_code"])
        safety_stock = threshold["target_di"] // 2
        reorder_level = threshold["target_di"]

        qty = flt(item["current_qty"])

        # Determine alert level based on product-specific thresholds
        if qty <= 0:
            alert_level = "critical"
        elif qty < safety_stock:
            alert_level = "warning"
        elif qty < reorder_level:
            alert_level = "info"
        else:
            continue  # No alert needed

        alerts.append({
            "item_code": item["item_code"],
            "item_name": item["item_name"],
            "item_group": item["item_group"],
            "uom": item["uom"],
            "current_qty": qty,
            "safety_stock": safety_stock,
            "reorder_level": reorder_level,
            "alert_level": alert_level,
            "shelf_life": threshold["shelf_life"],
            "storage_temp": threshold["storage_temp"]
        })

    # Sort by alert level priority
    alert_order = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda x: (alert_order.get(x["alert_level"], 99), x["item_name"]))

    return {
        "success": True,
        "data": alerts,
        "summary": {
            "critical": sum(1 for a in alerts if a["alert_level"] == "critical"),
            "warning": sum(1 for a in alerts if a["alert_level"] == "warning"),
            "info": sum(1 for a in alerts if a["alert_level"] == "info")
        }
    }


@frappe.whitelist()
def get_item_groups():
    """
    Get item groups for filtering.
    """
    groups = frappe.get_all(
        "Item Group",
        filters={"is_group": 0},
        fields=["name", "parent_item_group"],
        order_by="name"
    )
    return {"success": True, "data": groups}


# ============================================================
# 4. STORE ORDER FULFILLMENT
# ============================================================

@frappe.whitelist()
def get_pending_store_orders():
    """
    Get pending Material Requests from stores, grouped by priority.
    """
    commissary_warehouse = get_commissary_warehouse()

    mrs = frappe.get_all(
        "Material Request",
        filters={
            "status": ["in", ["Pending", "Partially Ordered"]],
            "docstatus": 1,
            "material_request_type": "Material Transfer"
        },
        fields=[
            "name", "transaction_date", "schedule_date",
            "status", "set_warehouse"
        ],
        order_by="schedule_date asc"
    )

    # Enrich with store info and items
    from datetime import datetime, date
    for mr in mrs:
        # Store name
        mr["store_name"] = mr["set_warehouse"].replace(" - BEI", "") if mr["set_warehouse"] else "Unknown"

        # Calculate urgency (days until due)
        if mr["schedule_date"]:
            schedule = mr["schedule_date"]
            if isinstance(schedule, str):
                schedule = datetime.strptime(schedule, "%Y-%m-%d").date()
            days_until = (schedule - date.today()).days
            mr["days_until_due"] = days_until
            if days_until < 0:
                mr["urgency"] = "overdue"
            elif days_until == 0:
                mr["urgency"] = "today"
            elif days_until <= 1:
                mr["urgency"] = "urgent"
            else:
                mr["urgency"] = "normal"
        else:
            mr["days_until_due"] = None
            mr["urgency"] = "normal"

        # Get items with availability
        items = frappe.db.sql("""
            SELECT
                mri.item_code,
                mri.item_name,
                mri.qty as requested_qty,
                IFNULL(mri.ordered_qty, 0) as ordered_qty,
                mri.qty - IFNULL(mri.ordered_qty, 0) as pending_qty,
                mri.uom,
                IFNULL(b.actual_qty, 0) as available_qty
            FROM `tabMaterial Request Item` mri
            LEFT JOIN `tabBin` b ON b.item_code = mri.item_code AND b.warehouse = %s
            WHERE mri.parent = %s
        """, (commissary_warehouse, mr["name"]), as_dict=True)

        mr["items"] = items
        mr["items_count"] = len(items)
        mr["can_fulfill"] = all(i["available_qty"] >= i["pending_qty"] for i in items) if items else False
        mr["partial_fulfill"] = any(i["available_qty"] > 0 for i in items) and not mr["can_fulfill"]

    # Sort by urgency
    urgency_order = {"overdue": 0, "today": 1, "urgent": 2, "normal": 3}
    mrs.sort(key=lambda x: (urgency_order.get(x["urgency"], 99), x.get("schedule_date") or "9999-99-99"))

    return {"success": True, "data": mrs}


@frappe.whitelist()
def get_order_summary():
    """
    Get summary of pending orders by store.
    """
    summary = frappe.db.sql("""
        SELECT
            mr.set_warehouse as store,
            COUNT(mr.name) as order_count,
            SUM(
                (SELECT COUNT(*) FROM `tabMaterial Request Item` mri WHERE mri.parent = mr.name)
            ) as total_items
        FROM `tabMaterial Request` mr
        WHERE mr.status IN ('Pending', 'Partially Ordered')
        AND mr.docstatus = 1
        AND mr.material_request_type = 'Material Transfer'
        GROUP BY mr.set_warehouse
        ORDER BY order_count DESC
    """, as_dict=True)

    for s in summary:
        s["store_name"] = s["store"].replace(" - BEI", "") if s["store"] else "Unknown"

    return {"success": True, "data": summary}


# ============================================================
# 5. QUALITY TRACKING
# ============================================================

@frappe.whitelist()
def get_fqi_summary(days=7):
    """
    Get FQI (Food Quality Inspection) summary from stores.
    Note: BEI FQI Report DocType not yet created - returns empty for now.
    """
    # TODO: Enable when BEI FQI Report DocType is created with proper schema
    return {"success": True, "data": [], "message": "FQI tracking not yet configured"}


@frappe.whitelist()
def get_returns_pending():
    """
    Get pending returns from stores.
    """
    returns = frappe.get_all(
        "Stock Entry",
        filters={
            "stock_entry_type": "Material Transfer",
            "docstatus": 1,
            "remarks": ["like", "%return%"]
        },
        fields=[
            "name", "posting_date", "from_warehouse",
            "remarks", "total_outgoing_value"
        ],
        order_by="posting_date desc",
        limit=20
    )

    for ret in returns:
        ret["store_name"] = ret["from_warehouse"].replace(" - BEI", "") if ret["from_warehouse"] else "Unknown"
        ret["item_count"] = frappe.db.count("Stock Entry Detail", {"parent": ret["name"]})

    return {"success": True, "data": returns}


# ============================================================
# 6. STOCK TRANSFER (Create dispatch from commissary)
# ============================================================

@frappe.whitelist()
def create_dispatch_transfer(target_warehouse, items, mr_name=None, remarks=None):
    """
    Create Stock Entry (Material Transfer) for dispatch from commissary.

    Args:
        target_warehouse: Destination warehouse (store)
        items: JSON array of {item_code, qty, uom}
        mr_name: Optional Material Request reference
        remarks: Optional notes
    """
    if isinstance(items, str):
        items = json.loads(items)

    if not items:
        frappe.throw(_("No items to transfer"))

    commissary_warehouse = get_commissary_warehouse()

    # Create Stock Entry
    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Transfer"
    se.company = "Bebang Enterprise Inc."
    se.posting_date = today()
    se.posting_time = frappe.utils.nowtime()
    se.from_warehouse = commissary_warehouse
    se.to_warehouse = target_warehouse
    se.remarks = remarks or f"Dispatch to {target_warehouse}"

    for item_data in items:
        item = frappe.get_doc("Item", item_data["item_code"])

        se.append("items", {
            "item_code": item_data["item_code"],
            "item_name": item.item_name,
            "description": item.description,
            "qty": flt(item_data["qty"]),
            "uom": item_data.get("uom") or item.stock_uom,
            "stock_uom": item.stock_uom,
            "conversion_factor": 1,
            "s_warehouse": commissary_warehouse,
            "t_warehouse": target_warehouse,
            "material_request": mr_name
        })

    if not se.items:
        frappe.throw(_("No items to transfer"))

    se.insert()
    se.submit()

    return {
        "success": True,
        "data": {
            "name": se.name,
            "total_qty": sum(i.qty for i in se.items),
            "items_count": len(se.items)
        },
        "message": f"Dispatch {se.name} created successfully"
    }


# ============================================================
# 7. ORDER DETAIL & FULFILLMENT
# ============================================================

@frappe.whitelist()
def get_order_detail(mr_name):
    """
    Get detailed information about a Material Request for fulfillment.

    Args:
        mr_name: Material Request name (e.g., 'MAT-MR-2026-00002')
    """
    if not mr_name:
        frappe.throw(_("Material Request name is required"))

    mr = frappe.get_doc("Material Request", mr_name)
    commissary_warehouse = get_commissary_warehouse()

    items = []
    for item in mr.items:
        # Get current stock in commissary
        stock = frappe.db.get_value(
            "Bin",
            {"item_code": item.item_code, "warehouse": commissary_warehouse},
            "actual_qty"
        ) or 0

        items.append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "qty": item.qty,  # Alias for frontend compatibility
            "qty_requested": item.qty,
            "qty_ordered": item.ordered_qty or 0,
            "qty_received": item.received_qty or 0,
            "qty_pending": item.qty - (item.received_qty or 0),
            "uom": item.uom,
            "current_stock": flt(stock),
            "can_fulfill": flt(stock) >= (item.qty - (item.received_qty or 0))
        })

    return {
        "success": True,
        "data": {
            "name": mr.name,
            "mr_name": mr.name,  # Alias for frontend compatibility
            "set_warehouse": mr.set_warehouse or "",
            "transaction_date": str(mr.transaction_date) if mr.transaction_date else "",
            "schedule_date": str(mr.schedule_date) if mr.schedule_date else "",
            "status": mr.status,
            "owner": mr.owner,
            "items": items
        }
    }


@frappe.whitelist()
def fulfill_store_order(mr_name, items):
    """
    Fulfill a Material Request by creating a Stock Entry (Material Transfer).

    Args:
        mr_name: Material Request name
        items: JSON array of {item_code, qty_to_fulfill, uom}
    """
    if isinstance(items, str):
        items = json.loads(items)

    if not items:
        frappe.throw(_("No items to fulfill"))

    mr = frappe.get_doc("Material Request", mr_name)
    commissary_warehouse = get_commissary_warehouse()

    # Get target warehouse from header or first item
    target_warehouse = mr.set_warehouse
    if not target_warehouse and mr.items:
        target_warehouse = mr.items[0].warehouse

    if not target_warehouse:
        frappe.throw(_("Material Request has no target warehouse set"))

    # Build item_code to MR item name mapping
    mr_item_map = {item.item_code: item.name for item in mr.items}

    # Create Stock Entry
    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Transfer"
    se.company = "Bebang Enterprise Inc."
    se.posting_date = today()
    se.posting_time = frappe.utils.nowtime()
    se.from_warehouse = commissary_warehouse
    se.to_warehouse = target_warehouse
    se.remarks = f"Fulfillment for {mr_name}"

    for item_data in items:
        qty = flt(item_data.get("qty_to_fulfill") or item_data.get("fulfilled_qty") or item_data.get("qty"))
        if qty <= 0:
            continue

        item_code = item_data["item_code"]
        item = frappe.get_doc("Item", item_code)

        # Get the MR item reference (required by ERPNext validation)
        mr_item_name = item_data.get("material_request_item") or mr_item_map.get(item_code)

        se.append("items", {
            "item_code": item_code,
            "item_name": item.item_name,
            "description": item.description,
            "qty": qty,
            "uom": item_data.get("uom") or item.stock_uom,
            "stock_uom": item.stock_uom,
            "conversion_factor": 1,
            "s_warehouse": commissary_warehouse,
            "t_warehouse": target_warehouse,
            "material_request": mr_name,
            "material_request_item": mr_item_name
        })

    if not se.items:
        frappe.throw(_("No valid items to fulfill"))

    se.insert()
    se.submit()

    return {
        "success": True,
        "data": {
            "name": se.name,
            "mr_name": mr_name,
            "total_qty": sum(i.qty for i in se.items),
            "items_count": len(se.items)
        },
        "message": f"Order fulfilled: {se.name}"
    }


@frappe.whitelist()
def get_ready_for_pickup():
    """
    Get Stock Entries that are ready for pickup/dispatch.
    These are submitted Material Transfer entries from commissary.
    """
    commissary_warehouse = get_commissary_warehouse()

    # Get recent Material Transfer stock entries from commissary
    entries = frappe.get_all(
        "Stock Entry",
        filters={
            "stock_entry_type": "Material Transfer",
            "from_warehouse": commissary_warehouse,
            "docstatus": 1,
            "posting_date": [">=", frappe.utils.add_days(today(), -7)]  # Last 7 days
        },
        fields=["name", "posting_date", "to_warehouse", "remarks", "owner"],
        order_by="posting_date desc",
        limit=50
    )

    result = []
    for entry in entries:
        # Get items for this entry
        items = frappe.get_all(
            "Stock Entry Detail",
            filters={"parent": entry.name},
            fields=["item_code", "item_name", "qty", "uom"]
        )

        result.append({
            "name": entry.name,
            "posting_date": str(entry.posting_date) if entry.posting_date else "",
            "target_warehouse": entry.to_warehouse,
            "remarks": entry.remarks,
            "owner": entry.owner,
            "items_count": len(items),
            "total_qty": sum(i.qty for i in items),
            "items": items[:5]  # First 5 items for preview
        })

    return {
        "success": True,
        "data": result
    }


# ============================================================
# 8. DAYS INVENTORY & SHIFT TRACKING (Phase 1 Enhancements)
# ============================================================

# Product-specific thresholds based on MANCOM data and questionnaire responses
PRODUCT_THRESHOLDS = {
    # Frozen products (60 days shelf life)
    "FG020": {"shelf_life": 60, "target_di": 14, "yellow_alert": 16, "red_alert": 21, "storage_temp": "-18C"},
    # Short shelf life products (14-15 days)
    "FG001": {"shelf_life": 15, "target_di": 7, "yellow_alert": 10, "red_alert": 12, "storage_temp": "0-4C"},  # Leche Flan
    "FG004": {"shelf_life": 15, "target_di": 7, "yellow_alert": 10, "red_alert": 12, "storage_temp": "0-4C"},  # Buko Pandan Jelly
    "FG005": {"shelf_life": 15, "target_di": 7, "yellow_alert": 10, "red_alert": 12, "storage_temp": "0-4C"},  # Vanilla White Jelly
    "FG006": {"shelf_life": 14, "target_di": 7, "yellow_alert": 10, "red_alert": 12, "storage_temp": "-18C"},  # Coconut Jelly
    "FG007": {"shelf_life": 14, "target_di": 7, "yellow_alert": 10, "red_alert": 12, "storage_temp": "0-4C"},  # Coconut Syrup
    "FG009": {"shelf_life": 21, "target_di": 10, "yellow_alert": 14, "red_alert": 18, "storage_temp": "0-4C"},  # Sago
    "FG012": {"shelf_life": 21, "target_di": 10, "yellow_alert": 14, "red_alert": 18, "storage_temp": "0-4C"},  # Melted Ube
    "FG015": {"shelf_life": 30, "target_di": 14, "yellow_alert": 20, "red_alert": 25, "storage_temp": "0-4C"},  # BP Sauce
    # Long shelf life products
    "FG003": {"shelf_life": 180, "target_di": 30, "yellow_alert": 45, "red_alert": 60, "storage_temp": "20-25C"},  # Rice Crispies
    "FG014": {"shelf_life": 60, "target_di": 14, "yellow_alert": 21, "red_alert": 30, "storage_temp": "20-25C"},  # Pistachio Mix
}

# Default thresholds for items not in the lookup
DEFAULT_THRESHOLD = {"shelf_life": 30, "target_di": 14, "yellow_alert": 21, "red_alert": 30, "storage_temp": "ambient"}


def get_product_threshold(item_code):
    """
    Get product-specific thresholds, checking custom fields first then fallback to lookup.
    """
    # First check if item has custom fields set
    custom_fields = frappe.db.get_value(
        "Item",
        item_code,
        ["custom_shelf_life_days", "custom_reorder_days", "custom_storage_temp_min", "custom_storage_temp_max"],
        as_dict=True
    )

    if custom_fields and custom_fields.get("custom_shelf_life_days"):
        shelf_life = custom_fields["custom_shelf_life_days"]
        target_di = custom_fields.get("custom_reorder_days") or max(7, shelf_life // 4)
        return {
            "shelf_life": shelf_life,
            "target_di": target_di,
            "yellow_alert": int(target_di * 1.5),
            "red_alert": int(target_di * 2),
            "storage_temp": f"{custom_fields.get('custom_storage_temp_min', 0)}-{custom_fields.get('custom_storage_temp_max', 25)}C"
        }

    # Check for FG code prefix match
    for code_prefix, threshold in PRODUCT_THRESHOLDS.items():
        if item_code.startswith(code_prefix):
            return threshold

    return DEFAULT_THRESHOLD


@frappe.whitelist()
def get_days_inventory():
    """
    Calculate Days Inventory (DI) for each finished goods product.

    Formula: DI = Current Stock / Average Daily Consumption (7-day rolling)
    Target: 14 days (MANCOM standard for most products)

    Returns:
        - item_code, item_name
        - current_stock: Current quantity in commissary
        - avg_daily_consumption: 7-day rolling average of outgoing qty
        - days_inventory: Calculated DI (current_stock / avg_daily_consumption)
        - target_di: Target days inventory for this product
        - status: 'ok', 'yellow', 'red', 'overstocked'
        - shelf_life: Product shelf life in days
    """
    commissary_warehouse = get_commissary_warehouse()
    today_date = today()
    date_7_days_ago = add_days(today_date, -7)

    # Get all FG items with current stock
    items = frappe.db.sql("""
        SELECT
            b.item_code,
            i.item_name,
            i.item_group,
            i.stock_uom as uom,
            b.actual_qty as current_stock
        FROM `tabBin` b
        JOIN `tabItem` i ON i.name = b.item_code
        WHERE b.warehouse = %s
        AND i.disabled = 0
        AND i.is_stock_item = 1
        AND (i.item_group = 'Finished Goods' OR i.item_code LIKE 'FG%%')
        ORDER BY i.item_name
    """, commissary_warehouse, as_dict=True)

    result = []
    for item in items:
        # Calculate 7-day consumption (outgoing stock from commissary)
        consumption = frappe.db.sql("""
            SELECT IFNULL(SUM(ABS(sed.qty)), 0) as total_out
            FROM `tabStock Entry` se
            JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
            WHERE se.docstatus = 1
            AND se.posting_date BETWEEN %s AND %s
            AND sed.s_warehouse = %s
            AND sed.item_code = %s
        """, (date_7_days_ago, today_date, commissary_warehouse, item["item_code"]))[0][0] or 0

        # Calculate average daily consumption
        avg_daily = flt(consumption / 7, 2)

        # Get product-specific thresholds
        threshold = get_product_threshold(item["item_code"])

        # Calculate days inventory
        if avg_daily > 0:
            days_inv = flt(item["current_stock"] / avg_daily, 1)
        else:
            # No consumption = infinite DI (overstocked or no demand)
            days_inv = 999 if item["current_stock"] > 0 else 0

        # Determine status based on thresholds
        target_di = threshold["target_di"]
        if days_inv == 0:
            status = "out_of_stock"
        elif days_inv < target_di * 0.5:
            status = "critical"
        elif days_inv < target_di:
            status = "low"
        elif days_inv <= threshold["yellow_alert"]:
            status = "ok"
        elif days_inv <= threshold["red_alert"]:
            status = "overstocked_warning"
        else:
            status = "overstocked"

        result.append({
            "item_code": item["item_code"],
            "item_name": item["item_name"],
            "item_group": item["item_group"],
            "uom": item["uom"],
            "current_stock": flt(item["current_stock"]),
            "avg_daily_consumption": avg_daily,
            "total_7day_consumption": flt(consumption),
            "days_inventory": days_inv if days_inv < 999 else None,
            "target_di": target_di,
            "yellow_alert": threshold["yellow_alert"],
            "red_alert": threshold["red_alert"],
            "shelf_life": threshold["shelf_life"],
            "storage_temp": threshold["storage_temp"],
            "status": status
        })

    # Sort by status priority (critical first)
    status_order = {"out_of_stock": 0, "critical": 1, "low": 2, "ok": 3, "overstocked_warning": 4, "overstocked": 5}
    result.sort(key=lambda x: (status_order.get(x["status"], 99), x["item_name"]))

    # Summary stats
    summary = {
        "total_items": len(result),
        "out_of_stock": sum(1 for r in result if r["status"] == "out_of_stock"),
        "critical": sum(1 for r in result if r["status"] == "critical"),
        "low": sum(1 for r in result if r["status"] == "low"),
        "ok": sum(1 for r in result if r["status"] == "ok"),
        "overstocked": sum(1 for r in result if r["status"] in ["overstocked_warning", "overstocked"])
    }

    return {
        "success": True,
        "data": result,
        "summary": summary,
        "target_di_standard": 14,
        "calculation_period": f"{date_7_days_ago} to {today_date}"
    }


@frappe.whitelist()
def get_current_shift():
    """
    Get the current production shift based on time of day.

    Shifts (from Bryan's questionnaire):
    - AM Shift: 5:00 AM - 2:00 PM
    - PM Shift: 4:00 PM - 1:00 AM
    - Dispatch: 4:00 AM

    Returns current shift info and next shift details.
    """
    from datetime import datetime

    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute
    current_time = current_hour + (current_minute / 60)

    # Define shifts
    shifts = {
        "dispatch": {"start": 4, "end": 5, "label": "Dispatch", "break_time": None},
        "am": {"start": 5, "end": 14, "label": "AM Shift", "break_time": "9:00 AM"},
        "pm": {"start": 16, "end": 25, "label": "PM Shift", "break_time": "8:00 PM"},  # 25 = 1 AM next day
        "gap_am_pm": {"start": 14, "end": 16, "label": "Between Shifts", "break_time": None},
        "night": {"start": 1, "end": 4, "label": "Night (Post-PM)", "break_time": None}
    }

    # Determine current shift
    # Handle PM shift that crosses midnight
    if current_hour >= 16 or current_hour < 1:
        current_shift = "pm"
        shift_info = shifts["pm"]
    elif 1 <= current_hour < 4:
        current_shift = "night"
        shift_info = shifts["night"]
    elif 4 <= current_hour < 5:
        current_shift = "dispatch"
        shift_info = shifts["dispatch"]
    elif 5 <= current_hour < 14:
        current_shift = "am"
        shift_info = shifts["am"]
    else:  # 14 <= current_hour < 16
        current_shift = "gap_am_pm"
        shift_info = shifts["gap_am_pm"]

    # Calculate time remaining in shift
    shift_end = shift_info["end"]
    if shift_end > 24:
        shift_end -= 24
    if current_hour < shift_info["start"] and shift_info["end"] > 24:
        # We're in the post-midnight part of PM shift
        hours_remaining = shift_end - current_hour
    else:
        hours_remaining = (shift_end - current_hour) % 24

    # Determine next shift
    if current_shift == "dispatch":
        next_shift = "AM Shift starts at 5:00 AM"
    elif current_shift == "am":
        next_shift = "PM Shift starts at 4:00 PM"
    elif current_shift == "pm" or current_shift == "night":
        next_shift = "Dispatch at 4:00 AM"
    else:
        next_shift = "PM Shift starts at 4:00 PM"

    return {
        "success": True,
        "data": {
            "current_shift": shift_info["label"],
            "shift_code": current_shift,
            "current_time": now.strftime("%I:%M %p"),
            "hours_remaining": round(hours_remaining, 1),
            "break_time": shift_info["break_time"],
            "next_shift": next_shift,
            "staffing": {
                "am": 11,
                "pm": 8,
                "supervisor_ratio": "1:20"
            }
        }
    }


# ============================================================
# 9. PRODUCTIVITY & WEEKLY METRICS (Phase 2 Enhancements)
# ============================================================

@frappe.whitelist()
def get_productivity_metrics(date_from=None, date_to=None):
    """
    Calculate productivity metrics (kg/manhour) for commissary operations.

    Returns:
        - total_output_kg: Sum of production output in kg
        - total_manhours: From BEI Weekly Labor Plan or estimated
        - productivity: total_output_kg / total_manhours
        - breakdown_by_product: Output breakdown by FG product
        - breakdown_by_activity: Manhours by activity (Common Packing, Frozen Milk, Cooking)

    Target productivity: ~50 kg/manhour
    """
    commissary_warehouse = get_commissary_warehouse()

    if not date_from:
        date_from = add_days(today(), -7)
    if not date_to:
        date_to = today()

    # Get production output (Material Receipt to commissary = production)
    output_data = frappe.db.sql("""
        SELECT
            sed.item_code,
            i.item_name,
            SUM(sed.qty) as total_qty,
            i.stock_uom as uom
        FROM `tabStock Entry` se
        JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
        JOIN `tabItem` i ON i.name = sed.item_code
        WHERE se.docstatus = 1
        AND se.stock_entry_type IN ('Material Receipt', 'Manufacture')
        AND se.posting_date BETWEEN %s AND %s
        AND sed.t_warehouse = %s
        GROUP BY sed.item_code
        ORDER BY total_qty DESC
    """, (date_from, date_to, commissary_warehouse), as_dict=True)

    # Calculate total output in KG
    total_output_kg = 0
    breakdown_by_product = []
    for row in output_data:
        # Convert to KG based on UOM
        qty_kg = row["total_qty"]
        if row["uom"] in ["Gram", "g"]:
            qty_kg = row["total_qty"] / 1000
        elif row["uom"] in ["Barrel", "barrel"]:
            qty_kg = row["total_qty"] * 2.5  # ~2.5kg per barrel

        total_output_kg += qty_kg
        breakdown_by_product.append({
            "item_code": row["item_code"],
            "item_name": row["item_name"],
            "qty": flt(row["total_qty"]),
            "qty_kg": flt(qty_kg, 2),
            "uom": row["uom"],
            "percentage": 0  # Will calculate after total
        })

    # Calculate percentages
    for item in breakdown_by_product:
        if total_output_kg > 0:
            item["percentage"] = flt((item["qty_kg"] / total_output_kg) * 100, 1)

    # Estimate manhours based on MANCOM ratios
    # From MANCOM: WW5 had 669 manhours for 26.3K kg output
    # Breakdown: Common Packing 38.3%, Frozen Milk 34.2%, Cooking 27.5%
    # Try to get from BEI Weekly Labor Plan if available
    manhours = None
    try:
        if frappe.db.exists("DocType", "BEI Weekly Labor Plan"):
            labor_data = frappe.db.sql("""
                SELECT SUM(total_hours) as total_manhours
                FROM `tabBEI Weekly Labor Plan`
                WHERE start_date <= %s AND end_date >= %s
            """, (date_to, date_from))
            if labor_data and labor_data[0][0]:
                manhours = flt(labor_data[0][0])
    except Exception:
        pass

    # If no labor plan data, estimate based on MANCOM ratio (~39.3 kg/manhour)
    if not manhours:
        # Estimate: ~25 manhours per 1000 kg (from 669 hours / 26.3K kg)
        manhours = flt(total_output_kg / 1000 * 25.4, 1)
        manhours_source = "estimated"
    else:
        manhours_source = "labor_plan"

    # Calculate productivity
    productivity = flt(total_output_kg / manhours, 2) if manhours > 0 else 0

    # Estimate activity breakdown based on MANCOM ratios
    breakdown_by_activity = [
        {"activity": "Common Packing", "manhours": flt(manhours * 0.383, 1), "percentage": 38.3},
        {"activity": "Frozen Milk", "manhours": flt(manhours * 0.342, 1), "percentage": 34.2},
        {"activity": "Cooking", "manhours": flt(manhours * 0.275, 1), "percentage": 27.5},
    ]

    return {
        "success": True,
        "data": {
            "date_from": date_from,
            "date_to": date_to,
            "total_output_kg": flt(total_output_kg, 2),
            "total_manhours": flt(manhours, 1),
            "manhours_source": manhours_source,
            "productivity_kg_per_hour": productivity,
            "target_productivity": 50,
            "productivity_status": "above_target" if productivity >= 50 else "below_target",
            "breakdown_by_product": breakdown_by_product,
            "breakdown_by_activity": breakdown_by_activity
        }
    }


@frappe.whitelist()
def get_weekly_summary(work_week=None):
    """
    Get MANCOM-format weekly summary for a specific work week.

    Work week format: "WW5" or "2026-W05" or ISO week number
    If not provided, returns current week.

    Returns KPIs in MANCOM slide format:
        - output_by_product
        - manhours_by_activity
        - productivity_kg_per_hour
        - days_inventory
        - wastage
        - week_on_week_comparison
    """
    from datetime import datetime, timedelta

    # Parse work week and get date range
    if not work_week:
        # Current week
        today_dt = datetime.strptime(today(), "%Y-%m-%d")
        week_start = today_dt - timedelta(days=today_dt.weekday())
        week_end = week_start + timedelta(days=6)
        week_number = today_dt.isocalendar()[1]
    else:
        # Parse work week (handle WW5, 2026-W05, or just 5)
        if work_week.upper().startswith("WW"):
            week_number = int(work_week[2:])
        elif "-W" in work_week:
            week_number = int(work_week.split("-W")[1])
        else:
            week_number = int(work_week)

        # Get the Monday of that week (assume current year)
        year = datetime.now().year
        week_start = datetime.strptime(f"{year}-W{week_number:02d}-1", "%Y-W%W-%w")
        week_end = week_start + timedelta(days=6)

    date_from = week_start.strftime("%Y-%m-%d")
    date_to = week_end.strftime("%Y-%m-%d")

    # Get productivity metrics for this week
    productivity = get_productivity_metrics(date_from, date_to)["data"]

    # Get days inventory
    di_data = get_days_inventory()["data"]

    # Get previous week for comparison
    prev_week_start = week_start - timedelta(days=7)
    prev_week_end = prev_week_start + timedelta(days=6)
    prev_productivity = get_productivity_metrics(
        prev_week_start.strftime("%Y-%m-%d"),
        prev_week_end.strftime("%Y-%m-%d")
    )["data"]

    # Calculate week-on-week changes
    output_change = 0
    productivity_change = 0
    if prev_productivity["total_output_kg"] > 0:
        output_change = flt(
            ((productivity["total_output_kg"] - prev_productivity["total_output_kg"]) /
             prev_productivity["total_output_kg"]) * 100, 1
        )
    if prev_productivity["productivity_kg_per_hour"] > 0:
        productivity_change = flt(
            ((productivity["productivity_kg_per_hour"] - prev_productivity["productivity_kg_per_hour"]) /
             prev_productivity["productivity_kg_per_hour"]) * 100, 1
        )

    # Get wastage (Stock Entry with purpose containing "waste" or "spoilage")
    wastage = frappe.db.sql("""
        SELECT IFNULL(SUM(sed.qty), 0) as wastage_qty
        FROM `tabStock Entry` se
        JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
        WHERE se.docstatus = 1
        AND se.posting_date BETWEEN %s AND %s
        AND (se.remarks LIKE '%%waste%%' OR se.remarks LIKE '%%spoil%%' OR se.stock_entry_type = 'Material Issue')
    """, (date_from, date_to))[0][0] or 0

    return {
        "success": True,
        "data": {
            "work_week": f"WW{week_number}",
            "date_range": f"{date_from} to {date_to}",
            "output": {
                "total_kg": productivity["total_output_kg"],
                "by_product": productivity["breakdown_by_product"],
                "change_from_last_week": output_change
            },
            "manhours": {
                "total": productivity["total_manhours"],
                "source": productivity["manhours_source"],
                "by_activity": productivity["breakdown_by_activity"]
            },
            "productivity": {
                "kg_per_hour": productivity["productivity_kg_per_hour"],
                "target": 50,
                "status": productivity["productivity_status"],
                "change_from_last_week": productivity_change
            },
            "days_inventory": {
                "items": di_data[:10],  # Top 10 items
                "summary": {
                    "total_items": len(di_data),
                    "below_target": sum(1 for d in di_data if d["status"] in ["critical", "low"]),
                    "at_target": sum(1 for d in di_data if d["status"] == "ok"),
                    "overstocked": sum(1 for d in di_data if d["status"] in ["overstocked_warning", "overstocked"])
                }
            },
            "wastage": {
                "total_kg": flt(wastage, 2),
                "target": 0
            }
        }
    }


@frappe.whitelist()
def get_delivery_routes():
    """
    Get delivery routes with store assignments.

    Routes from Bryan's questionnaire:
    - North: 7 routes
    - South: 8 routes
    - Total: 15 routes serving 50+ stores
    """
    # Hard-coded route data from Bryan's questionnaire response
    routes = {
        "north": [
            {"route": "North-1", "truck": 1, "stores": ["Clark", "Pulilan", "Marilao"]},
            {"route": "North-2", "truck": 2, "stores": ["Fairview Terraces", "SM Caloocan", "SJDM"]},
            {"route": "North-3", "truck": 3, "stores": ["Ever Commonwealth", "Uptown Center", "SM North"]},
            {"route": "North-4", "truck": 4, "stores": ["Valenzuela", "Sangandaan", "Grand Central"]},
            {"route": "North-5", "truck": 5, "stores": ["Lucky Chinatown", "SM Manila", "Megamall"]},
            {"route": "North-6", "truck": 6, "stores": ["CTT Morato", "Araneta Gateway", "Marikina"]},
            {"route": "North-7", "truck": 7, "stores": ["East Ortigas", "Robinson Antipolo", "Taytay", "St. Lucia"]},
        ],
        "south": [
            {"route": "South-1", "truck": 1, "stores": ["Paseo Makati", "Grid Rockwell", "Uptown BGC"]},
            {"route": "South-2", "truck": 2, "stores": ["Market Market", "Venice Grand Canal", "Vista Taguig"]},
            {"route": "South-3", "truck": 3, "stores": ["MOA", "PITX", "NAIA T3"]},
            {"route": "South-4", "truck": 4, "stores": ["Bicutan", "BF Homes", "Southmall"]},
            {"route": "South-5", "truck": 5, "stores": ["Sta Rosa", "Solenad", "D'Verde Calamba"]},
            {"route": "South-6", "truck": 6, "stores": ["Evo City Kawit", "Robinson Gen Trias", "SM Tanza"]},
            {"route": "South-7", "truck": 7, "stores": ["Festival Alabang", "Terminal Alabang", "Galleria South"]},
            {"route": "South-8", "truck": 8, "stores": ["Robinson Imus", "Ayala Vermosa"]},
        ]
    }

    # Try to get today's dispatch trips if BEI Distribution Trip exists
    todays_trips = []
    try:
        if frappe.db.exists("DocType", "BEI Distribution Trip"):
            trips = frappe.get_all(
                "BEI Distribution Trip",
                filters={"dispatch_date": today()},
                fields=["name", "route_name", "driver", "vehicle", "status", "total_stops"]
            )
            todays_trips = trips
    except Exception:
        pass

    # Calculate summary
    total_stores = sum(len(r["stores"]) for r in routes["north"]) + sum(len(r["stores"]) for r in routes["south"])

    return {
        "success": True,
        "data": {
            "routes": routes,
            "summary": {
                "north_routes": len(routes["north"]),
                "south_routes": len(routes["south"]),
                "total_routes": len(routes["north"]) + len(routes["south"]),
                "total_stores": total_stores,
                "dispatch_time": "4:00 AM",
                "order_deadline": "12:00 PM (previous day)",
                "lead_time": "1 day"
            },
            "todays_trips": todays_trips,
            "external_hubs": [
                {"name": "3MD", "type": "Wet & Dry", "location": "Bulacan", "contact": "Vlad Ferrer"},
                {"name": "JENTEC", "type": "Dry", "location": "Pasig", "contact": "Beverly Que"},
                {"name": "RCS", "type": "Frozen", "location": "Taytay", "contact": "Joey Ancheta"},
                {"name": "PINNACLE", "type": "Wet & Dry", "location": "Laguna", "contact": "Daryl Alano"},
            ]
        }
    }


# ============================================================
# 10. EXTERNAL HUB TRACKING (Phase 3)
# ============================================================

@frappe.whitelist()
def get_hub_inventory(hub_code=None):
    """
    Get inventory levels at external hubs.

    Args:
        hub_code: Optional specific hub code (3MD, JENTEC, RCS, PINNACLE)
                  If not provided, returns all hubs.

    Returns hub information with current inventory items.
    """
    # Check if BEI External Hub DocType exists
    if not frappe.db.exists("DocType", "BEI External Hub"):
        # Return hardcoded data if DocType not yet created
        default_hubs = [
            {"hub_code": "3MD", "hub_name": "3MD Logistics", "hub_type": "Wet & Dry",
             "location": "Bulacan", "contact_person": "Vlad Ferrer", "items": []},
            {"hub_code": "JENTEC", "hub_name": "JENTEC Warehouse", "hub_type": "Dry",
             "location": "Pasig", "contact_person": "Beverly Que", "items": []},
            {"hub_code": "RCS", "hub_name": "RCS Cold Storage", "hub_type": "Frozen",
             "location": "Taytay", "contact_person": "Joey Ancheta", "items": []},
            {"hub_code": "PINNACLE", "hub_name": "Pinnacle Logistics", "hub_type": "Wet & Dry",
             "location": "Laguna", "contact_person": "Daryl Alano", "items": []},
        ]
        if hub_code:
            hubs = [h for h in default_hubs if h["hub_code"] == hub_code.upper()]
        else:
            hubs = default_hubs

        return {
            "success": True,
            "data": hubs,
            "source": "default",
            "message": "BEI External Hub DocType not yet created. Showing default data."
        }

    # Get from DocType
    filters = {"is_active": 1}
    if hub_code:
        filters["hub_code"] = hub_code.upper()

    hubs = frappe.get_all(
        "BEI External Hub",
        filters=filters,
        fields=["hub_code", "hub_name", "hub_type", "location",
                "contact_person", "contact_phone", "contact_email",
                "lead_time_days", "notes"]
    )

    # Get items for each hub
    for hub in hubs:
        items = frappe.get_all(
            "BEI Hub Item",
            filters={"parent": hub["hub_code"], "parenttype": "BEI External Hub"},
            fields=["item_code", "item_name", "current_qty", "uom", "last_updated"]
        )
        hub["items"] = items
        hub["total_items"] = len(items)
        hub["total_qty"] = sum(i.get("current_qty", 0) for i in items)

    return {
        "success": True,
        "data": hubs,
        "source": "doctype"
    }


@frappe.whitelist()
def update_hub_inventory(hub_code, item_code, qty, uom=None):
    """
    Update inventory level for an item at an external hub.

    Args:
        hub_code: Hub code (3MD, JENTEC, RCS, PINNACLE)
        item_code: Item code
        qty: New quantity
        uom: Unit of measure (optional, defaults to stock UOM)
    """
    if not frappe.db.exists("DocType", "BEI External Hub"):
        frappe.throw("BEI External Hub DocType not yet created. Please run bench migrate.")

    hub_code = hub_code.upper()
    if not frappe.db.exists("BEI External Hub", hub_code):
        frappe.throw(f"Hub {hub_code} not found")

    if not frappe.db.exists("Item", item_code):
        frappe.throw(f"Item {item_code} not found")

    hub = frappe.get_doc("BEI External Hub", hub_code)

    # Find existing item or add new
    item_found = False
    for item in hub.items:
        if item.item_code == item_code:
            item.current_qty = flt(qty)
            item.last_updated = frappe.utils.now()
            if uom:
                item.uom = uom
            item_found = True
            break

    if not item_found:
        # Add new item
        item_doc = frappe.get_doc("Item", item_code)
        hub.append("items", {
            "item_code": item_code,
            "item_name": item_doc.item_name,
            "current_qty": flt(qty),
            "uom": uom or item_doc.stock_uom,
            "last_updated": frappe.utils.now()
        })

    hub.save()

    return {
        "success": True,
        "message": f"Updated {item_code} at {hub_code}: {qty}",
        "data": {
            "hub_code": hub_code,
            "item_code": item_code,
            "new_qty": flt(qty)
        }
    }


# ============================================================
# 11. HUB TRANSFER (NEW - Task #3)
# ============================================================

# Distribution hub warehouse mapping
DISTRIBUTION_HUBS = {
    "3MD": "3MD Logistics - Camangyanan - BEI",
    "JENTEC": "Jentec Storage Inc. - BEI",
    "RCS": "Royal Cold Storage - Taytay - BEI",
    "PINNACLE": "Pinnacle Cold Storage - BEI",
}


@frappe.whitelist()
def get_distribution_hubs():
    """
    Get list of available distribution hubs for transfer.
    """
    hubs = []
    for code, warehouse in DISTRIBUTION_HUBS.items():
        # Check if warehouse exists
        exists = frappe.db.exists("Warehouse", warehouse)
        hub_info = {
            "hub_code": code,
            "warehouse": warehouse,
            "exists": exists,
            "hub_type": "Cold + Dry" if code in ["3MD", "PINNACLE"] else ("Frozen" if code == "RCS" else "Dry")
        }

        # Get current stock count if warehouse exists
        if exists:
            stock_count = frappe.db.sql("""
                SELECT COUNT(DISTINCT item_code) as items, SUM(actual_qty) as total_qty
                FROM `tabBin` WHERE warehouse = %s AND actual_qty > 0
            """, warehouse, as_dict=True)[0]
            hub_info["items_count"] = stock_count.get("items") or 0
            hub_info["total_qty"] = flt(stock_count.get("total_qty") or 0)

        hubs.append(hub_info)

    return {"success": True, "data": hubs}


@frappe.whitelist()
def create_hub_transfer(destination_hub, items, remarks=None):
    """
    Create Stock Entry (Material Transfer) from Commissary to Distribution Hub.

    Args:
        destination_hub: Hub code (3MD, JENTEC, RCS, PINNACLE)
        items: JSON array of {item_code, qty, batch_no (optional)}
        remarks: Optional notes

    Returns:
        Stock Entry name and details
    """
    if isinstance(items, str):
        items = json.loads(items)

    if not items:
        frappe.throw(_("No items to transfer"))

    destination_hub = destination_hub.upper()
    if destination_hub not in DISTRIBUTION_HUBS:
        frappe.throw(_(f"Invalid hub code: {destination_hub}. Valid codes: {', '.join(DISTRIBUTION_HUBS.keys())}"))

    target_warehouse = DISTRIBUTION_HUBS[destination_hub]

    # Verify warehouse exists
    if not frappe.db.exists("Warehouse", target_warehouse):
        frappe.throw(_(f"Warehouse {target_warehouse} does not exist. Please create it first."))

    commissary_warehouse = get_commissary_warehouse()

    # Create Stock Entry
    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Transfer"
    se.company = "Bebang Enterprise Inc."
    se.posting_date = today()
    se.posting_time = frappe.utils.nowtime()
    se.from_warehouse = commissary_warehouse
    se.to_warehouse = target_warehouse
    se.remarks = remarks or f"Hub Transfer to {destination_hub}"

    for item_data in items:
        item = frappe.get_doc("Item", item_data["item_code"])

        # Validate sufficient stock
        current_stock = frappe.db.get_value(
            "Bin",
            {"item_code": item_data["item_code"], "warehouse": commissary_warehouse},
            "actual_qty"
        ) or 0

        qty = flt(item_data["qty"])
        if qty > current_stock:
            frappe.throw(_(f"Insufficient stock for {item.item_name}. Available: {current_stock}, Requested: {qty}"))

        item_row = {
            "item_code": item_data["item_code"],
            "item_name": item.item_name,
            "description": item.description,
            "qty": qty,
            "uom": item_data.get("uom") or item.stock_uom,
            "stock_uom": item.stock_uom,
            "conversion_factor": 1,
            "s_warehouse": commissary_warehouse,
            "t_warehouse": target_warehouse,
        }

        # Handle batch if provided
        if item_data.get("batch_no"):
            valid_batch = get_or_create_batch(item_data["batch_no"], item_data["item_code"])
            if valid_batch:
                item_row["batch_no"] = valid_batch

        se.append("items", item_row)

    se.insert()
    se.submit()

    return {
        "success": True,
        "data": {
            "name": se.name,
            "destination_hub": destination_hub,
            "target_warehouse": target_warehouse,
            "total_qty": sum(i.qty for i in se.items),
            "items_count": len(se.items)
        },
        "message": f"Transfer {se.name} to {destination_hub} created successfully"
    }


@frappe.whitelist()
def get_transfer_history(destination_hub=None, date_from=None, date_to=None, limit=50):
    """
    Get history of transfers from Commissary to Distribution Hubs.

    Args:
        destination_hub: Optional filter by hub code
        date_from: Optional start date
        date_to: Optional end date
        limit: Max results (default 50)
    """
    commissary_warehouse = get_commissary_warehouse()

    # Build warehouse filter
    if destination_hub:
        destination_hub = destination_hub.upper()
        if destination_hub not in DISTRIBUTION_HUBS:
            frappe.throw(_(f"Invalid hub code: {destination_hub}"))
        target_warehouses = [DISTRIBUTION_HUBS[destination_hub]]
    else:
        target_warehouses = list(DISTRIBUTION_HUBS.values())

    # Build date filter
    date_filter = ""
    params = [commissary_warehouse]

    if date_from and date_to:
        date_filter = "AND se.posting_date BETWEEN %s AND %s"
        params.extend([date_from, date_to])
    elif date_from:
        date_filter = "AND se.posting_date >= %s"
        params.append(date_from)
    elif date_to:
        date_filter = "AND se.posting_date <= %s"
        params.append(date_to)

    # Query transfers
    warehouse_placeholders = ", ".join(["%s"] * len(target_warehouses))
    params.extend(target_warehouses)
    params.append(int(limit))

    transfers = frappe.db.sql(f"""
        SELECT
            se.name,
            se.posting_date,
            se.to_warehouse,
            se.remarks,
            se.owner,
            se.docstatus,
            COUNT(sed.item_code) as items_count,
            SUM(sed.qty) as total_qty
        FROM `tabStock Entry` se
        JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
        WHERE se.stock_entry_type = 'Material Transfer'
        AND se.from_warehouse = %s
        AND se.to_warehouse IN ({warehouse_placeholders})
        AND se.docstatus = 1
        {date_filter}
        GROUP BY se.name
        ORDER BY se.posting_date DESC, se.creation DESC
        LIMIT %s
    """, params, as_dict=True)

    # Add hub code to each transfer
    warehouse_to_hub = {v: k for k, v in DISTRIBUTION_HUBS.items()}
    for t in transfers:
        t["hub_code"] = warehouse_to_hub.get(t["to_warehouse"], "UNKNOWN")
        t["total_qty"] = flt(t["total_qty"])

    return {
        "success": True,
        "data": transfers,
        "summary": {
            "total_transfers": len(transfers),
            "total_qty": sum(t["total_qty"] for t in transfers)
        }
    }


# ============================================================
# 12. RAW MATERIAL REORDER ALERTS (NEW - Task #4)
# ============================================================

@frappe.whitelist()
def get_rm_reorder_alerts():
    """
    Get raw materials that are below reorder level in Commissary.

    Uses reorder_level field on Item if set, otherwise estimates based on
    7-day consumption average x 3 (lead time buffer).

    Returns items needing reorder with suggested quantities.
    """
    commissary_warehouse = get_commissary_warehouse()
    today_date = today()
    date_7_days_ago = add_days(today_date, -7)

    # Get all raw material items (item_group contains 'Raw' or item_code starts with RM)
    rm_items = frappe.db.sql("""
        SELECT
            i.name as item_code,
            i.item_name,
            i.item_group,
            i.stock_uom as uom,
            i.reorder_level,
            i.safety_stock,
            IFNULL(b.actual_qty, 0) as current_qty
        FROM `tabItem` i
        LEFT JOIN `tabBin` b ON b.item_code = i.name AND b.warehouse = %s
        WHERE i.disabled = 0
        AND i.is_stock_item = 1
        AND (
            i.item_group LIKE '%%Raw%%'
            OR i.item_code LIKE 'RM%%'
            OR i.item_group = 'Raw Materials'
        )
        ORDER BY i.item_name
    """, commissary_warehouse, as_dict=True)

    alerts = []
    for item in rm_items:
        # Calculate 7-day consumption
        consumption = frappe.db.sql("""
            SELECT IFNULL(SUM(ABS(sed.qty)), 0) as total_out
            FROM `tabStock Entry` se
            JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
            WHERE se.docstatus = 1
            AND se.posting_date BETWEEN %s AND %s
            AND sed.s_warehouse = %s
            AND sed.item_code = %s
        """, (date_7_days_ago, today_date, commissary_warehouse, item["item_code"]))[0][0] or 0

        avg_daily = flt(consumption / 7, 2)

        # Determine reorder level (use Item field if set, otherwise estimate)
        if item["reorder_level"] and item["reorder_level"] > 0:
            reorder_level = flt(item["reorder_level"])
        else:
            # Estimate: 3 days of consumption (lead time buffer)
            reorder_level = flt(avg_daily * 3, 2)

        # Determine safety stock
        if item["safety_stock"] and item["safety_stock"] > 0:
            safety_stock = flt(item["safety_stock"])
        else:
            # Estimate: 1 day of consumption
            safety_stock = flt(avg_daily, 2)

        current_qty = flt(item["current_qty"])

        # Check if needs reorder
        if current_qty <= 0:
            alert_level = "critical"
            status = "Out of Stock"
        elif current_qty < safety_stock:
            alert_level = "critical"
            status = "Below Safety Stock"
        elif current_qty < reorder_level:
            alert_level = "warning"
            status = "Reorder Needed"
        else:
            continue  # No alert needed

        # Calculate suggested order quantity (target = 7 days supply)
        target_qty = flt(avg_daily * 7, 2)
        suggested_qty = max(target_qty - current_qty, reorder_level)

        alerts.append({
            "item_code": item["item_code"],
            "item_name": item["item_name"],
            "item_group": item["item_group"],
            "uom": item["uom"],
            "current_qty": current_qty,
            "reorder_level": reorder_level,
            "safety_stock": safety_stock,
            "avg_daily_consumption": avg_daily,
            "suggested_order_qty": flt(suggested_qty, 2),
            "alert_level": alert_level,
            "status": status
        })

    # Sort by alert level priority
    alert_order = {"critical": 0, "warning": 1}
    alerts.sort(key=lambda x: (alert_order.get(x["alert_level"], 99), x["item_name"]))

    return {
        "success": True,
        "data": alerts,
        "summary": {
            "total_alerts": len(alerts),
            "critical": sum(1 for a in alerts if a["alert_level"] == "critical"),
            "warning": sum(1 for a in alerts if a["alert_level"] == "warning")
        }
    }


# ============================================================
# 13. RAW MATERIAL REQUISITION (NEW - Task #5)
# ============================================================

@frappe.whitelist()
def create_rm_requisition(items, required_by_date=None, remarks=None):
    """
    Create Material Request for raw materials from Commissary.

    Args:
        items: JSON array of {item_code, qty, uom (optional)}
        required_by_date: When materials are needed (defaults to 3 days from now)
        remarks: Optional notes

    Returns:
        Material Request name and details
    """
    if isinstance(items, str):
        items = json.loads(items)

    if not items:
        frappe.throw(_("No items to request"))

    commissary_warehouse = get_commissary_warehouse()

    # Default required_by_date to 3 days from now (standard lead time)
    if not required_by_date:
        required_by_date = add_days(today(), 3)

    # Create Material Request
    mr = frappe.new_doc("Material Request")
    mr.material_request_type = "Purchase"
    mr.company = "Bebang Enterprise Inc."
    mr.transaction_date = today()
    mr.schedule_date = required_by_date
    mr.set_warehouse = commissary_warehouse
    mr.remarks = remarks or "Raw Material Requisition from Commissary"

    for item_data in items:
        item = frappe.get_doc("Item", item_data["item_code"])

        mr.append("items", {
            "item_code": item_data["item_code"],
            "item_name": item.item_name,
            "description": item.description,
            "qty": flt(item_data["qty"]),
            "uom": item_data.get("uom") or item.stock_uom,
            "stock_uom": item.stock_uom,
            "conversion_factor": 1,
            "warehouse": commissary_warehouse,
            "schedule_date": required_by_date
        })

    mr.insert()
    mr.submit()

    return {
        "success": True,
        "data": {
            "name": mr.name,
            "items_count": len(mr.items),
            "total_qty": sum(i.qty for i in mr.items),
            "required_by_date": str(required_by_date),
            "status": mr.status
        },
        "message": f"Material Request {mr.name} created successfully"
    }


@frappe.whitelist()
def get_my_requisitions(status=None, limit=50):
    """
    Get Material Requests created from Commissary.

    Args:
        status: Optional filter by status (Pending, Ordered, Received, etc.)
        limit: Max results (default 50)

    Returns list of requisitions with item details.
    """
    commissary_warehouse = get_commissary_warehouse()

    filters = {
        "material_request_type": "Purchase",
        "set_warehouse": commissary_warehouse,
        "docstatus": ["in", [0, 1]]  # Draft or Submitted
    }

    if status:
        filters["status"] = status

    mrs = frappe.get_all(
        "Material Request",
        filters=filters,
        fields=[
            "name", "transaction_date", "schedule_date",
            "status", "owner", "remarks", "docstatus"
        ],
        order_by="transaction_date desc",
        limit=int(limit)
    )

    for mr in mrs:
        # Get items
        items = frappe.get_all(
            "Material Request Item",
            filters={"parent": mr["name"]},
            fields=["item_code", "item_name", "qty", "ordered_qty", "received_qty", "uom"]
        )
        mr["items"] = items
        mr["items_count"] = len(items)
        mr["total_qty"] = sum(i.get("qty", 0) for i in items)
        mr["total_ordered"] = sum(i.get("ordered_qty", 0) for i in items)
        mr["total_received"] = sum(i.get("received_qty", 0) for i in items)

        # Calculate fulfillment percentage
        if mr["total_qty"] > 0:
            mr["fulfillment_pct"] = flt((mr["total_received"] / mr["total_qty"]) * 100, 1)
        else:
            mr["fulfillment_pct"] = 0

    return {
        "success": True,
        "data": mrs,
        "summary": {
            "total": len(mrs),
            "pending": sum(1 for m in mrs if m["status"] in ["Pending", "Draft"]),
            "ordered": sum(1 for m in mrs if m["status"] == "Ordered"),
            "partially_received": sum(1 for m in mrs if m["status"] == "Partially Received"),
            "received": sum(1 for m in mrs if m["status"] == "Received")
        }
    }


@frappe.whitelist()
def get_rm_for_requisition():
    """
    Get raw materials available for requisition with current stock and alerts.
    Combines inventory levels with reorder recommendations.
    """
    # Get reorder alerts first
    alerts_data = get_rm_reorder_alerts()
    alerts = {a["item_code"]: a for a in alerts_data["data"]}

    commissary_warehouse = get_commissary_warehouse()

    # Get all raw materials
    rm_items = frappe.db.sql("""
        SELECT
            i.name as item_code,
            i.item_name,
            i.item_group,
            i.stock_uom as uom,
            IFNULL(b.actual_qty, 0) as current_qty
        FROM `tabItem` i
        LEFT JOIN `tabBin` b ON b.item_code = i.name AND b.warehouse = %s
        WHERE i.disabled = 0
        AND i.is_stock_item = 1
        AND (
            i.item_group LIKE '%%Raw%%'
            OR i.item_code LIKE 'RM%%'
            OR i.item_group = 'Raw Materials'
        )
        ORDER BY i.item_name
    """, commissary_warehouse, as_dict=True)

    result = []
    for item in rm_items:
        item_data = {
            "item_code": item["item_code"],
            "item_name": item["item_name"],
            "item_group": item["item_group"],
            "uom": item["uom"],
            "current_qty": flt(item["current_qty"]),
            "needs_reorder": item["item_code"] in alerts,
            "suggested_qty": 0,
            "alert_level": None
        }

        # Add alert data if available
        if item["item_code"] in alerts:
            alert = alerts[item["item_code"]]
            item_data["suggested_qty"] = alert["suggested_order_qty"]
            item_data["alert_level"] = alert["alert_level"]
            item_data["reorder_level"] = alert["reorder_level"]

        result.append(item_data)

    # Sort: items needing reorder first
    result.sort(key=lambda x: (0 if x["needs_reorder"] else 1, x["item_name"]))

    return {
        "success": True,
        "data": result,
        "alerts_count": len(alerts)
    }


# ============================================================
# 9. QUALITY INSPECTION
# ============================================================

@frappe.whitelist()
def get_pending_inspections():
    """
    Get production batches awaiting quality inspection.
    Returns Stock Entries (Manufacture) that don't have a linked QI.
    """
    commissary_warehouse = get_commissary_warehouse()

    # Get manufacture entries from last 7 days without QI
    pending = frappe.db.sql("""
        SELECT
            se.name,
            se.posting_date,
            sed.item_code,
            sed.item_name,
            sed.qty,
            sed.uom,
            i.quality_inspection_template
        FROM `tabStock Entry` se
        JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
        JOIN `tabItem` i ON i.name = sed.item_code
        WHERE se.stock_entry_type = 'Manufacture'
        AND se.docstatus = 1
        AND sed.t_warehouse = %s
        AND se.posting_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
        AND i.inspection_required_before_delivery = 1
        AND NOT EXISTS (
            SELECT 1 FROM `tabQuality Inspection` qi
            WHERE qi.reference_name = se.name
            AND qi.item_code = sed.item_code
            AND qi.docstatus != 2
        )
        ORDER BY se.posting_date DESC
    """, commissary_warehouse, as_dict=True)

    return {
        "success": True,
        "data": pending,
        "total": len(pending)
    }


@frappe.whitelist()
def create_quality_inspection(stock_entry_name, item_code, inspected_by=None, readings=None, status="Accepted"):
    """
    Create a quality inspection record for a production batch.

    Args:
        stock_entry_name: Reference Stock Entry
        item_code: Item being inspected
        inspected_by: Inspector name (defaults to current user)
        readings: Dict of {specification: reading_value}
        status: "Accepted" or "Rejected"
    """
    if isinstance(readings, str):
        readings = json.loads(readings)

    # Get the Stock Entry Detail
    sed = frappe.db.get_value(
        "Stock Entry Detail",
        {"parent": stock_entry_name, "item_code": item_code},
        ["qty", "batch_no"],
        as_dict=True
    )

    if not sed:
        return {"success": False, "error": f"Item {item_code} not found in Stock Entry {stock_entry_name}"}

    # Get the QI template for this item
    template = frappe.db.get_value("Item", item_code, "quality_inspection_template")

    # Create QI
    qi = frappe.new_doc("Quality Inspection")
    qi.inspection_type = "Outgoing"
    qi.reference_type = "Stock Entry"
    qi.reference_name = stock_entry_name
    qi.item_code = item_code
    qi.sample_size = sed.qty
    qi.inspected_by = inspected_by or frappe.session.user
    qi.status = status
    qi.batch_no = sed.batch_no

    # If template exists, populate readings
    if template:
        qi.quality_inspection_template = template
        template_doc = frappe.get_doc("Quality Inspection Template", template)
        for param in template_doc.item_quality_inspection_parameter:
            reading = {
                "specification": param.specification,
                "value": param.value,
                "status": "Accepted"
            }
            # Override with provided readings
            if readings and param.specification in readings:
                reading["reading_1"] = readings[param.specification]
            qi.append("readings", reading)
    elif readings:
        # Create readings from provided data
        for spec, value in readings.items():
            qi.append("readings", {
                "specification": spec,
                "reading_1": value,
                "status": "Accepted"
            })

    qi.insert()
    qi.submit()

    return {
        "success": True,
        "message": f"Quality Inspection {qi.name} created",
        "data": {"name": qi.name, "status": qi.status}
    }


@frappe.whitelist()
def get_inspection_history(item_code=None, days=30):
    """
    Get quality inspection history.

    Args:
        item_code: Filter by specific item (optional)
        days: Number of days to look back (default 30)
    """
    filters = {
        "docstatus": 1,
        "inspection_type": "Outgoing",
        "creation": [">=", add_days(today(), -int(days))]
    }

    if item_code:
        filters["item_code"] = item_code

    inspections = frappe.get_all(
        "Quality Inspection",
        filters=filters,
        fields=[
            "name", "item_code", "item_name", "status",
            "inspected_by", "sample_size", "batch_no",
            "reference_name", "modified"
        ],
        order_by="modified desc",
        limit=100
    )

    # Get summary stats
    total = len(inspections)
    accepted = len([i for i in inspections if i.status == "Accepted"])
    rejected = len([i for i in inspections if i.status == "Rejected"])

    return {
        "success": True,
        "data": inspections,
        "summary": {
            "total": total,
            "accepted": accepted,
            "rejected": rejected,
            "acceptance_rate": round(accepted / total * 100, 1) if total > 0 else 0
        }
    }


@frappe.whitelist()
def get_inspection_details(inspection_name):
    """Get full details of a quality inspection including readings."""
    qi = frappe.get_doc("Quality Inspection", inspection_name)

    return {
        "success": True,
        "data": {
            "name": qi.name,
            "item_code": qi.item_code,
            "item_name": qi.item_name,
            "status": qi.status,
            "inspected_by": qi.inspected_by,
            "sample_size": qi.sample_size,
            "batch_no": qi.batch_no,
            "reference_name": qi.reference_name,
            "readings": [
                {
                    "specification": r.specification,
                    "value": r.value,
                    "reading_1": r.reading_1,
                    "status": r.status
                }
                for r in qi.readings
            ]
        }
    }


# ============================================================
# 10. PRODUCTION PLANNING
# ============================================================

@frappe.whitelist()
def get_production_suggestions():
    """
    Get production suggestions based on stock levels and demand.
    Suggests FG items that are below safety stock or have pending orders.
    """
    commissary_warehouse = get_commissary_warehouse()

    # Get FG items with current stock and pending demand
    suggestions = frappe.db.sql("""
        SELECT
            i.item_code,
            i.item_name,
            i.stock_uom,
            COALESCE(bin.actual_qty, 0) as current_stock,
            COALESCE(bin.reserved_qty, 0) as reserved_qty,
            COALESCE(
                (SELECT SUM(mri.qty - mri.ordered_qty)
                 FROM `tabMaterial Request Item` mri
                 JOIN `tabMaterial Request` mr ON mr.name = mri.parent
                 WHERE mri.item_code = i.item_code
                 AND mr.docstatus = 1
                 AND mr.status NOT IN ('Stopped', 'Cancelled')
                ), 0
            ) as pending_demand,
            b.name as bom_name
        FROM `tabItem` i
        LEFT JOIN `tabBin` bin ON bin.item_code = i.name AND bin.warehouse = %s
        LEFT JOIN `tabBOM` b ON b.item = i.name AND b.is_active = 1 AND b.is_default = 1
        WHERE i.item_group = 'Finished Goods'
        AND i.disabled = 0
        ORDER BY pending_demand DESC, current_stock ASC
    """, commissary_warehouse, as_dict=True)

    result = []
    for item in suggestions:
        # Calculate suggested production qty
        target_stock = 100  # Default safety stock
        gap = target_stock - item.current_stock + item.pending_demand

        if gap > 0 and item.bom_name:
            result.append({
                "item_code": item.item_code,
                "item_name": item.item_name,
                "uom": item.stock_uom,
                "current_stock": flt(item.current_stock),
                "pending_demand": flt(item.pending_demand),
                "suggested_qty": flt(gap, 0),
                "bom_name": item.bom_name,
                "priority": "high" if item.pending_demand > 0 else "normal"
            })

    return {
        "success": True,
        "data": result,
        "total": len(result)
    }


@frappe.whitelist()
def create_work_order(item_code, qty, planned_start_date=None, remarks=None):
    """
    Create a Work Order for a Finished Good item.

    Args:
        item_code: FG item to produce
        qty: Quantity to produce
        planned_start_date: When to start (defaults to today)
        remarks: Optional notes
    """
    commissary_warehouse = get_commissary_warehouse()

    # Get the default BOM for this item
    bom = frappe.db.get_value(
        "BOM",
        {"item": item_code, "is_active": 1, "is_default": 1},
        ["name", "quantity"],
        as_dict=True
    )

    if not bom:
        return {"success": False, "error": f"No active BOM found for item {item_code}"}

    # Create Work Order
    wo = frappe.new_doc("Work Order")
    wo.production_item = item_code
    wo.bom_no = bom.name
    wo.qty = flt(qty)
    wo.fg_warehouse = commissary_warehouse
    wo.wip_warehouse = commissary_warehouse  # Same warehouse for simplicity
    wo.company = "Bebang Enterprise Inc."
    wo.planned_start_date = planned_start_date or today()
    wo.expected_delivery_date = planned_start_date or today()

    if remarks:
        wo.remarks = remarks

    wo.insert()

    return {
        "success": True,
        "message": f"Work Order {wo.name} created",
        "data": {
            "name": wo.name,
            "item_code": wo.production_item,
            "qty": wo.qty,
            "bom_no": wo.bom_no,
            "status": wo.status
        }
    }


@frappe.whitelist()
def get_work_orders(status=None, days=7):
    """
    Get Work Orders for commissary production.

    Args:
        status: Filter by status (optional)
        days: Days to look back (default 7)
    """
    filters = {
        "fg_warehouse": ["like", "%Commissary%"],
        "creation": [">=", add_days(today(), -int(days))]
    }

    if status:
        filters["status"] = status

    work_orders = frappe.get_all(
        "Work Order",
        filters=filters,
        fields=[
            "name", "production_item", "item_name", "qty",
            "produced_qty", "status", "planned_start_date",
            "expected_delivery_date", "bom_no"
        ],
        order_by="creation desc",
        limit=50
    )

    # Calculate completion percentage
    for wo in work_orders:
        wo["completion_pct"] = round(wo.produced_qty / wo.qty * 100, 1) if wo.qty > 0 else 0

    # Summary by status
    summary = {}
    for wo in work_orders:
        status = wo.status
        if status not in summary:
            summary[status] = {"count": 0, "qty": 0}
        summary[status]["count"] += 1
        summary[status]["qty"] += wo.qty

    return {
        "success": True,
        "data": work_orders,
        "summary": summary
    }


@frappe.whitelist()
def start_work_order(work_order_name):
    """Start a work order (submit if draft, begin manufacturing)."""
    wo = frappe.get_doc("Work Order", work_order_name)

    if wo.docstatus == 0:
        wo.submit()

    if wo.status == "Submitted":
        # Create Stock Entry for Material Transfer for Manufacture
        se = frappe.new_doc("Stock Entry")
        se.stock_entry_type = "Material Transfer for Manufacture"
        se.work_order = wo.name
        se.from_bom = 1
        se.bom_no = wo.bom_no
        se.fg_completed_qty = wo.qty
        se.company = wo.company

        # Get items from BOM
        se.get_items()
        se.insert()
        se.submit()

        return {
            "success": True,
            "message": f"Work Order {wo.name} started. Material transferred.",
            "data": {"work_order": wo.name, "stock_entry": se.name}
        }

    return {
        "success": False,
        "error": f"Work Order is in status {wo.status}, cannot start"
    }


@frappe.whitelist()
def complete_work_order(work_order_name, qty_produced=None):
    """Complete a work order by creating manufacture stock entry."""
    wo = frappe.get_doc("Work Order", work_order_name)

    if wo.status not in ["Submitted", "In Process"]:
        return {
            "success": False,
            "error": f"Work Order is in status {wo.status}, cannot complete"
        }

    qty = flt(qty_produced) or wo.qty - wo.produced_qty

    # Create Stock Entry for Manufacture
    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Manufacture"
    se.work_order = wo.name
    se.from_bom = 1
    se.bom_no = wo.bom_no
    se.fg_completed_qty = qty
    se.company = wo.company

    se.get_items()
    se.insert()
    se.submit()

    # Refresh work order status
    wo.reload()

    return {
        "success": True,
        "message": f"Manufactured {qty} units of {wo.production_item}",
        "data": {
            "work_order": wo.name,
            "stock_entry": se.name,
            "produced_qty": wo.produced_qty,
            "status": wo.status
        }
    }
