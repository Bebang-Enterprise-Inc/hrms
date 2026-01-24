# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Store Operations API
Handles store ordering, receiving, and FQI reports for my.bebang.ph
"""

import frappe
from frappe import _
from frappe.utils import nowdate, add_days, now_datetime
import json


@frappe.whitelist()
def get_orderable_items(store):
    """
    Get items available for ordering by this store.
    Returns items filtered by warehouse/store with last order quantity.
    """
    if not store:
        frappe.throw(_("Store is required"))

    # Get items that can be ordered by this store
    # For now, return all stock items - can be filtered later by store config
    items = frappe.get_all(
        "Item",
        filters={
            "is_stock_item": 1,
            "disabled": 0
        },
        fields=["name", "item_name", "item_group", "stock_uom", "image"],
        order_by="item_group, item_name"
    )

    # Get last order quantities for each item
    for item in items:
        last_order = frappe.get_all(
            "BEI Store Order Item",
            filters={
                "item_code": item.name,
                "parent": ["in", frappe.get_all(
                    "BEI Store Order",
                    filters={"store": store, "status": ["!=", "Draft"]},
                    pluck="name",
                    limit=1
                )]
            },
            fields=["qty_requested"],
            order_by="creation desc",
            limit=1
        )
        item["last_order_qty"] = last_order[0].qty_requested if last_order else 0

    return {"items": items}


@frappe.whitelist()
def submit_order(store, items):
    """
    Submit a new store order.
    Items should be a list of {item_code, qty_requested}
    """
    if not store:
        frappe.throw(_("Store is required"))

    if isinstance(items, str):
        items = json.loads(items)

    if not items:
        frappe.throw(_("At least one item is required"))

    order = frappe.new_doc("BEI Store Order")
    order.store = store
    order.order_date = nowdate()
    order.delivery_date = add_days(nowdate(), 1)
    order.status = "Pending Approval"
    order.submitted_by = frappe.session.user

    for item_data in items:
        order.append("items", {
            "item_code": item_data.get("item_code"),
            "qty_requested": item_data.get("qty_requested", 0)
        })

    order.insert()

    return {
        "success": True,
        "order": order.name,
        "message": f"Order {order.name} submitted successfully"
    }


@frappe.whitelist()
def get_order_history(store, limit=20):
    """Get past orders for a store."""
    if not store:
        frappe.throw(_("Store is required"))

    orders = frappe.get_all(
        "BEI Store Order",
        filters={"store": store},
        fields=["name", "order_date", "delivery_date", "status", "submitted_by", "approved_by"],
        order_by="creation desc",
        limit=int(limit)
    )

    # Get item counts for each order
    for order in orders:
        order["item_count"] = frappe.db.count(
            "BEI Store Order Item",
            {"parent": order.name}
        )

    return {"orders": orders}


@frappe.whitelist()
def approve_order(order_name, approved_quantities=None):
    """
    Approve a store order. Optionally adjust quantities.
    approved_quantities: {item_code: qty_approved}
    """
    order = frappe.get_doc("BEI Store Order", order_name)

    if order.status != "Pending Approval":
        frappe.throw(_("Order is not pending approval"))

    if approved_quantities:
        if isinstance(approved_quantities, str):
            approved_quantities = json.loads(approved_quantities)
        for item in order.items:
            if item.item_code in approved_quantities:
                item.qty_approved = approved_quantities[item.item_code]
            else:
                item.qty_approved = item.qty_requested
    else:
        for item in order.items:
            item.qty_approved = item.qty_requested

    order.status = "Approved"
    order.approved_by = frappe.session.user
    order.approved_at = now_datetime()
    order.save()

    return {
        "success": True,
        "message": f"Order {order_name} approved"
    }


@frappe.whitelist()
def get_expected_deliveries(store):
    """
    Get trips expected to deliver to this store today.
    Returns distribution trips with this store as a stop.
    """
    if not store:
        frappe.throw(_("Store is required"))

    today = nowdate()

    # Find trips with this store as a stop
    trips = frappe.db.sql("""
        SELECT DISTINCT
            t.name, t.trip_date, t.route_name, t.driver, t.vehicle,
            t.status, t.departure_time,
            s.stop_order, s.items_count, s.status as stop_status
        FROM `tabBEI Distribution Trip` t
        JOIN `tabBEI Trip Stop` s ON s.parent = t.name
        WHERE s.store = %s
        AND t.trip_date = %s
        AND t.status IN ('Preparing', 'In Transit')
        ORDER BY t.trip_date, s.stop_order
    """, (store, today), as_dict=True)

    return {"deliveries": trips}


@frappe.whitelist()
def complete_receiving(store, trip, items, receiver_1_signature=None, receiver_2_signature=None, driver_signature=None):
    """
    Complete receiving for a delivery.
    Items: list of {item_code, expected_qty, received_qty, checks, has_issue}
    """
    if not store:
        frappe.throw(_("Store is required"))

    if isinstance(items, str):
        items = json.loads(items)

    receiving = frappe.new_doc("BEI Store Receiving")
    receiving.store = store
    receiving.trip = trip
    receiving.receiving_date = now_datetime()
    receiving.receiver_1 = frappe.session.user
    receiving.receiver_1_signature = receiver_1_signature
    receiving.receiver_2_signature = receiver_2_signature
    receiving.driver_signature = driver_signature

    has_issues = False
    for item_data in items:
        row = receiving.append("items", {
            "item_code": item_data.get("item_code"),
            "expected_qty": item_data.get("expected_qty"),
            "received_qty": item_data.get("received_qty"),
            "check_condition": item_data.get("check_condition", 0),
            "check_packaging": item_data.get("check_packaging", 0),
            "check_expiry": item_data.get("check_expiry", 0),
            "check_temperature": item_data.get("check_temperature", 0),
            "check_food_quality": item_data.get("check_food_quality", 0),
            "expiry_date": item_data.get("expiry_date"),
            "temperature_reading": item_data.get("temperature_reading"),
            "has_issue": item_data.get("has_issue", 0)
        })
        if row.has_issue:
            has_issues = True

    receiving.status = "With Issues" if has_issues else "Completed"
    receiving.insert()

    return {
        "success": True,
        "receiving": receiving.name,
        "message": f"Receiving {receiving.name} completed"
    }


@frappe.whitelist()
def create_fqi_report(store, receiving=None, item_code=None, issue_type=None, description=None, photo=None, expected_qty=None, actual_qty=None):
    """
    Create a Food Quality Incident report.
    """
    if not store:
        frappe.throw(_("Store is required"))

    if not issue_type:
        frappe.throw(_("Issue type is required"))

    fqi = frappe.new_doc("BEI FQI Report")
    fqi.store = store
    fqi.receiving = receiving
    fqi.item_code = item_code
    fqi.issue_type = issue_type
    fqi.description = description
    fqi.photo = photo
    fqi.expected_qty = expected_qty
    fqi.actual_qty = actual_qty
    fqi.reported_by = frappe.session.user
    fqi.reported_at = now_datetime()
    fqi.status = "Open"
    fqi.insert()

    return {
        "success": True,
        "fqi": fqi.name,
        "message": f"FQI Report {fqi.name} created"
    }


@frappe.whitelist()
def get_fqi_reports(store=None, status=None, limit=20):
    """Get FQI reports optionally filtered by store and status."""
    filters = {}
    if store:
        filters["store"] = store
    if status:
        filters["status"] = status

    reports = frappe.get_all(
        "BEI FQI Report",
        filters=filters,
        fields=["name", "store", "item_code", "issue_type", "status", "reported_by", "reported_at", "resolved_at"],
        order_by="creation desc",
        limit=int(limit)
    )

    return {"reports": reports}
