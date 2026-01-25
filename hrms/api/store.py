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


def resolve_warehouse(store_or_branch):
    """
    Resolve a branch name or partial warehouse name to the full warehouse name.
    Branch names like 'TEST-STORE-BGC' need to be converted to warehouse names 'TEST-STORE-BGC - BEI'.
    """
    if not store_or_branch:
        return None

    # First check if the exact warehouse exists
    if frappe.db.exists("Warehouse", store_or_branch):
        return store_or_branch

    # Try appending company abbreviation (BEI is the default company)
    warehouse_with_company = f"{store_or_branch} - BEI"
    if frappe.db.exists("Warehouse", warehouse_with_company):
        return warehouse_with_company

    # Try to find warehouse by warehouse_name (without company suffix)
    warehouse = frappe.db.get_value("Warehouse", {"warehouse_name": store_or_branch}, "name")
    if warehouse:
        return warehouse

    frappe.throw(_("Could not find Store: {0}").format(store_or_branch))


@frappe.whitelist()
def get_orderable_items(store):
    """
    Get items available for ordering by this store.
    Returns items filtered by warehouse/store with last order quantity.
    """
    if not store:
        frappe.throw(_("Store is required"))

    # Resolve branch name to warehouse name
    warehouse = resolve_warehouse(store)

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
                    filters={"store": warehouse, "status": ["!=", "Draft"]},
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

    # Resolve branch name to warehouse name
    warehouse = resolve_warehouse(store)

    if isinstance(items, str):
        items = json.loads(items)

    if not items:
        frappe.throw(_("At least one item is required"))

    order = frappe.new_doc("BEI Store Order")
    order.store = warehouse
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
def get_order_history(store=None, limit=20):
    """Get past orders for a store."""
    if not store:
        return {"orders": []}

    # Resolve branch name to warehouse name
    warehouse = resolve_warehouse(store)

    orders = frappe.get_all(
        "BEI Store Order",
        filters={"store": warehouse},
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
def get_expected_deliveries(store=None):
    """
    Get trips expected to deliver to this store today.
    Returns distribution trips with this store as a stop.
    """
    if not store:
        return {"deliveries": []}

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


# ==============================================================================
# STORE OPENING/CLOSING REPORTS
# ==============================================================================


@frappe.whitelist()
def submit_opening_report(store, report_time, checklist_items, notes=None,
                          photo_backup_area=None, photo_frozen_milk=None,
                          photo_toppings_area=None, photo_dispatch_area=None,
                          photo_cold_storage_temp=None):
    """Submit daily opening report with 5 required photos."""
    if not store:
        frappe.throw(_("Store is required"))

    if isinstance(checklist_items, str):
        checklist_items = json.loads(checklist_items)

    doc = frappe.new_doc("BEI Store Opening Report")
    doc.store = store
    doc.report_date = nowdate()
    doc.report_time = report_time
    doc.submitted_by = frappe.session.user
    doc.notes = notes
    doc.photo_backup_area = photo_backup_area
    doc.photo_frozen_milk = photo_frozen_milk
    doc.photo_toppings_area = photo_toppings_area
    doc.photo_dispatch_area = photo_dispatch_area
    doc.photo_cold_storage_temp = photo_cold_storage_temp

    for item in checklist_items:
        doc.append("checklist_items", item)

    doc.insert()
    return {"success": True, "name": doc.name}


@frappe.whitelist()
def get_opening_reports(store=None, date_from=None, date_to=None, limit=20):
    """Get opening report history."""
    filters = {}
    if store:
        filters["store"] = store
    if date_from:
        filters["report_date"] = [">=", date_from]
    if date_to:
        if "report_date" in filters:
            filters["report_date"] = ["between", [date_from, date_to]]
        else:
            filters["report_date"] = ["<=", date_to]

    reports = frappe.get_all(
        "BEI Store Opening Report",
        filters=filters,
        fields=["name", "store", "report_date", "report_time", "status", "submitted_by"],
        order_by="report_date desc",
        limit=int(limit)
    )
    return {"reports": reports}


@frappe.whitelist()
def submit_closing_report(store, report_time, checklist_items, pos_total_sales,
                          actual_cash_count, card_payments, gcash_total,
                          variance_explanation=None, notes=None,
                          photo_xread_opening=None, photo_xread_closing=None,
                          photo_zread=None, photo_closing_reports=None,
                          photo_dashboard_report=None, photo_logo_signage=None,
                          photo_hygrometer=None, photo_water_meter=None,
                          photo_backup_area_clean=None, photo_frozen_milk_clean=None,
                          photo_toppings_clean=None, photo_dispatch_clean=None,
                          photo_cold_storage_close=None, photo_cashier_clean=None,
                          photo_rollup_closed=None):
    """Submit daily closing report with cash reconciliation and 15 required photos."""
    if not store:
        frappe.throw(_("Store is required"))

    if isinstance(checklist_items, str):
        checklist_items = json.loads(checklist_items)

    doc = frappe.new_doc("BEI Store Closing Report")
    doc.store = store
    doc.report_date = nowdate()
    doc.report_time = report_time
    doc.submitted_by = frappe.session.user
    doc.pos_total_sales = float(pos_total_sales)
    doc.actual_cash_count = float(actual_cash_count)
    doc.card_payments = float(card_payments)
    doc.gcash_total = float(gcash_total)
    doc.variance_explanation = variance_explanation
    doc.notes = notes

    # Photos
    doc.photo_xread_opening = photo_xread_opening
    doc.photo_xread_closing = photo_xread_closing
    doc.photo_zread = photo_zread
    doc.photo_closing_reports = photo_closing_reports
    doc.photo_dashboard_report = photo_dashboard_report
    doc.photo_logo_signage = photo_logo_signage
    doc.photo_hygrometer = photo_hygrometer
    doc.photo_water_meter = photo_water_meter
    doc.photo_backup_area_clean = photo_backup_area_clean
    doc.photo_frozen_milk_clean = photo_frozen_milk_clean
    doc.photo_toppings_clean = photo_toppings_clean
    doc.photo_dispatch_clean = photo_dispatch_clean
    doc.photo_cold_storage_close = photo_cold_storage_close
    doc.photo_cashier_clean = photo_cashier_clean
    doc.photo_rollup_closed = photo_rollup_closed

    for item in checklist_items:
        doc.append("checklist_items", item)

    doc.insert()
    return {"success": True, "name": doc.name, "variance": doc.cash_variance}


@frappe.whitelist()
def get_closing_reports(store=None, date_from=None, date_to=None, limit=20):
    """Get closing report history."""
    filters = {}
    if store:
        filters["store"] = store
    if date_from:
        filters["report_date"] = [">=", date_from]
    if date_to:
        if "report_date" in filters:
            filters["report_date"] = ["between", [date_from, date_to]]
        else:
            filters["report_date"] = ["<=", date_to]

    reports = frappe.get_all(
        "BEI Store Closing Report",
        filters=filters,
        fields=["name", "store", "report_date", "status", "cash_variance"],
        order_by="report_date desc",
        limit=int(limit)
    )
    return {"reports": reports}


@frappe.whitelist()
def submit_midshift_check(store, shift, temperature_readings, cleanliness_status,
                          issues_found=None, corrective_action=None, photo_evidence=None):
    """Submit mid-shift temperature and cleanliness check."""
    if not store:
        frappe.throw(_("Store is required"))

    if isinstance(temperature_readings, str):
        temperature_readings = json.loads(temperature_readings)

    doc = frappe.new_doc("BEI Midshift Checklist")
    doc.store = store
    doc.check_datetime = now_datetime()
    doc.submitted_by = frappe.session.user
    doc.shift = shift
    doc.cleanliness_status = cleanliness_status
    doc.issues_found = issues_found
    doc.corrective_action = corrective_action
    doc.photo_evidence = photo_evidence

    for reading in temperature_readings:
        doc.append("temperature_readings", reading)

    doc.insert()
    return {"success": True, "name": doc.name}


@frappe.whitelist()
def get_midshift_checks(store=None, date=None, limit=20):
    """Get mid-shift check history."""
    filters = {}
    if store:
        filters["store"] = store
    if date:
        filters["check_datetime"] = ["like", f"{date}%"]

    checks = frappe.get_all(
        "BEI Midshift Checklist",
        filters=filters,
        fields=["name", "store", "check_datetime", "shift", "cleanliness_status"],
        order_by="check_datetime desc",
        limit=int(limit)
    )
    return {"checks": checks}


@frappe.whitelist()
def upload_pos_data(store, pos_date, pos_system, gross_sales, net_sales,
                    transaction_count, z_reading_file, void_count=None,
                    void_amount=None, discount_amount=None, notes=None):
    """Upload daily POS Z-reading data."""
    if not store:
        frappe.throw(_("Store is required"))

    doc = frappe.new_doc("BEI POS Upload")
    doc.store = store
    doc.pos_date = pos_date
    doc.uploaded_by = frappe.session.user
    doc.pos_system = pos_system
    doc.gross_sales = float(gross_sales)
    doc.net_sales = float(net_sales)
    doc.transaction_count = int(transaction_count)
    doc.void_count = int(void_count) if void_count else 0
    doc.void_amount = float(void_amount) if void_amount else 0
    doc.discount_amount = float(discount_amount) if discount_amount else 0
    doc.z_reading_file = z_reading_file
    doc.notes = notes
    doc.insert()
    return {"success": True, "name": doc.name}


@frappe.whitelist()
def get_pos_uploads(store=None, date_from=None, date_to=None, limit=20):
    """Get POS upload history."""
    filters = {}
    if store:
        filters["store"] = store
    if date_from:
        filters["pos_date"] = [">=", date_from]
    if date_to:
        if "pos_date" in filters:
            filters["pos_date"] = ["between", [date_from, date_to]]
        else:
            filters["pos_date"] = ["<=", date_to]

    uploads = frappe.get_all(
        "BEI POS Upload",
        filters=filters,
        fields=["name", "store", "pos_date", "gross_sales", "net_sales", "status"],
        order_by="pos_date desc",
        limit=int(limit)
    )
    return {"uploads": uploads}
