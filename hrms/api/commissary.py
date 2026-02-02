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

    # Low stock alerts (items below reorder level)
    low_stock_count = frappe.db.sql("""
        SELECT COUNT(DISTINCT b.item_code)
        FROM `tabBin` b
        JOIN `tabItem` i ON i.name = b.item_code
        WHERE b.warehouse = %s
        AND b.actual_qty < IFNULL(i.safety_stock, 10)
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


@frappe.whitelist()
def submit_production_output(items, batch_no=None, remarks=None):
    """
    Record production batch output.
    Creates Stock Entry with type=Manufacture.

    Args:
        items: JSON array of {item_code, qty, uom}
        batch_no: Optional batch reference
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

        se.append("items", {
            "item_code": item_data["item_code"],
            "item_name": item.item_name,
            "description": item.description,
            "qty": flt(item_data["qty"]),
            "uom": item_data.get("uom") or item.stock_uom,
            "stock_uom": item.stock_uom,
            "conversion_factor": 1,
            "t_warehouse": commissary_warehouse,
            "batch_no": batch_no
        })

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
    """
    commissary_warehouse = get_commissary_warehouse()

    conditions = "WHERE b.warehouse = %s AND i.disabled = 0 AND i.is_stock_item = 1"
    params = [commissary_warehouse]

    if item_group:
        conditions += " AND i.item_group = %s"
        params.append(item_group)

    if show_low_stock_only == "1" or show_low_stock_only is True:
        conditions += " AND b.actual_qty < IFNULL(i.safety_stock, 10)"

    items = frappe.db.sql("""
        SELECT
            b.item_code,
            i.item_name,
            i.item_group,
            i.stock_uom as uom,
            b.actual_qty as current_qty,
            IFNULL(i.safety_stock, 10) as safety_stock,
            IFNULL(i.reorder_level, 20) as reorder_level,
            i.valuation_rate,
            CASE
                WHEN b.actual_qty <= 0 THEN 'Out of Stock'
                WHEN b.actual_qty < IFNULL(i.safety_stock, 10) THEN 'Low Stock'
                WHEN b.actual_qty < IFNULL(i.reorder_level, 20) THEN 'Reorder'
                ELSE 'OK'
            END as stock_status
        FROM `tabBin` b
        JOIN `tabItem` i ON i.name = b.item_code
        {conditions}
        ORDER BY
            CASE
                WHEN b.actual_qty <= 0 THEN 1
                WHEN b.actual_qty < IFNULL(i.safety_stock, 10) THEN 2
                WHEN b.actual_qty < IFNULL(i.reorder_level, 20) THEN 3
                ELSE 4
            END,
            i.item_name
    """.format(conditions=conditions), params, as_dict=True)

    # Add value calculation
    for item in items:
        item["value"] = flt(item["current_qty"]) * flt(item["valuation_rate"] or 0)

    return {"success": True, "data": items}


@frappe.whitelist()
def get_low_stock_alerts():
    """
    Get items below safety stock or reorder level.
    """
    commissary_warehouse = get_commissary_warehouse()

    alerts = frappe.db.sql("""
        SELECT
            b.item_code,
            i.item_name,
            i.item_group,
            i.stock_uom as uom,
            b.actual_qty as current_qty,
            IFNULL(i.safety_stock, 10) as safety_stock,
            IFNULL(i.reorder_level, 20) as reorder_level,
            CASE
                WHEN b.actual_qty <= 0 THEN 'critical'
                WHEN b.actual_qty < IFNULL(i.safety_stock, 10) THEN 'warning'
                ELSE 'info'
            END as alert_level
        FROM `tabBin` b
        JOIN `tabItem` i ON i.name = b.item_code
        WHERE b.warehouse = %s
        AND i.disabled = 0
        AND i.is_stock_item = 1
        AND (
            b.actual_qty <= 0
            OR b.actual_qty < IFNULL(i.safety_stock, 10)
            OR b.actual_qty < IFNULL(i.reorder_level, 20)
        )
        ORDER BY
            CASE
                WHEN b.actual_qty <= 0 THEN 1
                WHEN b.actual_qty < IFNULL(i.safety_stock, 10) THEN 2
                ELSE 3
            END,
            i.item_name
    """, commissary_warehouse, as_dict=True)

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
