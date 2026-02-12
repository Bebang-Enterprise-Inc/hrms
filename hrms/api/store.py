# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Store Operations API
Handles store ordering, receiving, and FQI reports for my.bebang.ph
"""

import frappe
from frappe import _
from frappe.utils import nowdate, add_days, now_datetime, flt
import json
import base64
import hashlib


def save_base64_image(base64_data, doctype, docname=None, fieldname="photo"):
    """
    Save a base64-encoded image as a Frappe file attachment.
    Returns the file URL that can be stored in Attach Image fields.

    Args:
        base64_data: Base64 string (with or without data:image/... prefix)
        doctype: DocType to attach the file to
        docname: Document name (optional, can attach later)
        fieldname: Field name for the attachment

    Returns:
        str: File URL (e.g., /files/maintenance_photo_abc123.jpg)
    """
    if not base64_data:
        return None

    # Check if it's already a URL (not base64)
    if base64_data.startswith(('/files/', '/private/', 'http://', 'https://')):
        return base64_data

    # Extract the actual base64 content and determine file type
    if ',' in base64_data:
        # Format: data:image/jpeg;base64,/9j/4AAQ...
        header, content = base64_data.split(',', 1)
        if 'png' in header.lower():
            ext = 'png'
        elif 'gif' in header.lower():
            ext = 'gif'
        elif 'webp' in header.lower():
            ext = 'webp'
        else:
            ext = 'jpg'
    else:
        # Raw base64 without header, assume JPEG
        content = base64_data
        ext = 'jpg'

    # Decode base64
    try:
        file_content = base64.b64decode(content)
    except Exception as e:
        frappe.log_error(f"Failed to decode base64 image: {str(e)}", "Base64 Decode Error")
        frappe.throw(_("Invalid image data"))

    # Generate unique filename using hash
    file_hash = hashlib.md5(file_content).hexdigest()[:12]
    filename = f"{doctype.lower().replace(' ', '_')}_{file_hash}.{ext}"

    # Save using Frappe's file handler
    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": filename,
        "content": file_content,
        "attached_to_doctype": doctype if docname else None,
        "attached_to_name": docname,
        "attached_to_field": fieldname,
        "is_private": 0
    })
    file_doc.save(ignore_permissions=True)

    return file_doc.file_url


STORE_OPS_ALLOWED_ROLES = [
    "Store Staff", "Store Supervisor", "Area Supervisor",
    "System Manager", "Administrator"
]


def validate_store_ops_role():
    """Validate that current user has a store operations role.
    Raises PermissionError if user lacks required role."""
    user_roles = frappe.get_roles(frappe.session.user)
    if not any(role in user_roles for role in STORE_OPS_ALLOWED_ROLES):
        frappe.throw(
            _("You do not have permission for store operations"),
            frappe.PermissionError
        )


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


def _get_area_supervisor_for_store(warehouse):
    """Get the area supervisor user for a given warehouse/store."""
    # Check custom_area_supervisor field on Warehouse
    supervisor = frappe.db.get_value("Warehouse", warehouse, "custom_area_supervisor")
    if supervisor:
        return supervisor

    # Fallback: check parent warehouse
    parent = frappe.db.get_value("Warehouse", warehouse, "parent_warehouse")
    if parent:
        supervisor = frappe.db.get_value("Warehouse", parent, "custom_area_supervisor")
        if supervisor:
            return supervisor

    return None


@frappe.whitelist()
def get_user_store():
    """
    Resolve the current user's store(s) based on their role.

    Store Staff / Store Supervisor: Returns store from Employee.branch
    Area Supervisor: Returns all stores where Warehouse.custom_area_supervisor = user

    Returns:
        {
            "stores": [{"name": "Store Name - BEI", "warehouse_name": "Store Name"}],
            "default_store": "Store Name - BEI",
            "is_multi_store": false,
            "role": "Store Staff"
        }
    """
    user = frappe.session.user
    user_roles = frappe.get_roles(user)

    stores = []
    role = None

    if "Area Supervisor" in user_roles:
        # Area supervisors see all stores assigned to them
        role = "Area Supervisor"
        area_stores = frappe.get_all(
            "Warehouse",
            filters={
                "custom_area_supervisor": user,
                "is_group": 0
            },
            fields=["name", "warehouse_name"],
            order_by="warehouse_name"
        )
        stores = area_stores

    if not stores and ("Store Supervisor" in user_roles or "Store Staff" in user_roles
                        or "Employee" in user_roles):
        # Store staff/supervisors get their branch from Employee record
        role = "Store Supervisor" if "Store Supervisor" in user_roles else "Store Staff"
        employee = frappe.db.get_value(
            "Employee",
            {"user_id": user, "status": "Active"},
            ["branch", "employee_name"],
            as_dict=True
        )
        if employee and employee.branch:
            warehouse = resolve_warehouse(employee.branch)
            if warehouse:
                warehouse_name = frappe.db.get_value("Warehouse", warehouse, "warehouse_name") or warehouse
                stores = [{"name": warehouse, "warehouse_name": warehouse_name}]

    # System Manager / HR User fallback - return all stores
    if not stores and ("System Manager" in user_roles or "HR User" in user_roles):
        role = "HR User"
        stores = frappe.get_all(
            "Warehouse",
            filters={"is_group": 0, "disabled": 0},
            fields=["name", "warehouse_name"],
            order_by="warehouse_name",
            limit=50
        )

    default_store = stores[0]["name"] if stores else None

    return {
        "stores": stores,
        "default_store": default_store,
        "is_multi_store": len(stores) > 1,
        "role": role
    }


@frappe.whitelist()
def get_orderable_items(store):
    """
    Get items available for ordering by this store.
    Returns items sorted by order frequency (most ordered first),
    with stock_uom and last order quantity.
    """
    if not store:
        frappe.throw(_("Store is required"))

    # Resolve branch name to warehouse name
    warehouse = resolve_warehouse(store)

    # Get items with order frequency for this store, sorted by most ordered first
    items = frappe.db.sql("""
        SELECT
            i.name, i.item_name, i.item_group, i.stock_uom, i.image,
            COALESCE(freq.order_count, 0) as order_count
        FROM `tabItem` i
        LEFT JOIN (
            SELECT soi.item_code, COUNT(DISTINCT soi.parent) as order_count
            FROM `tabBEI Store Order Item` soi
            JOIN `tabBEI Store Order` so ON so.name = soi.parent
            WHERE so.store = %s AND so.status != 'Draft'
            GROUP BY soi.item_code
        ) freq ON freq.item_code = i.name
        WHERE i.is_stock_item = 1 AND i.disabled = 0
        ORDER BY COALESCE(freq.order_count, 0) DESC, i.item_group, i.item_name
    """, warehouse, as_dict=True)

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

    # Validate quantities - prevent unreasonable orders
    MAX_ORDER_QTY = 10000
    for item_data in items:
        qty = flt(item_data.get("qty_requested", 0))
        if qty <= 0:
            frappe.throw(_("Quantity must be greater than zero for item {0}").format(
                item_data.get("item_code")))
        if qty > MAX_ORDER_QTY:
            frappe.throw(_("Order quantity {0} exceeds maximum allowed ({1}) for item {2}").format(
                qty, MAX_ORDER_QTY, item_data.get("item_code")))

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

    # Bug fix B6: Create approval queue entry routed to area supervisor with required fields
    try:
        approver = _get_area_supervisor_for_store(warehouse)
        if approver:
            queue_entry = frappe.new_doc("BEI Approval Queue")
            queue_entry.reference_doctype = "BEI Store Order"
            queue_entry.reference_name = order.name
            queue_entry.assigned_approver = approver
            queue_entry.status = "Pending"
            # Set required fields
            queue_entry.store = warehouse
            queue_entry.submitted_by = frappe.session.user
            queue_entry.submitted_at = frappe.utils.now()
            queue_entry.insert(ignore_permissions=True)
    except Exception:
        # Don't block order creation if approval queue fails
        frappe.log_error(
            f"Failed to create approval queue for order {order.name}",
            "Approval Queue Error"
        )

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
    Only Area Supervisors can approve orders.

    approved_quantities: {item_code: qty_approved}
    """
    # Verify user has Area Supervisor role
    user_roles = frappe.get_roles(frappe.session.user)
    if "Area Supervisor" not in user_roles and "System Manager" not in user_roles:
        frappe.throw(_("Only Area Supervisors can approve store orders"))

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

    # Resolve store name to valid warehouse (handles branch codes like TEST-STORE-BGC)
    try:
        warehouse = resolve_warehouse(store)
    except Exception:
        # Provide helpful suggestions for common typos
        similar_stores = frappe.db.sql("""
            SELECT name FROM tabWarehouse
            WHERE name LIKE %s OR warehouse_name LIKE %s
            LIMIT 5
        """, (f"%{store[:10]}%", f"%{store[:10]}%"), as_dict=True)

        suggestions = [s.name for s in similar_stores] if similar_stores else []
        msg = _("Store '{0}' not found.").format(store)
        if suggestions:
            msg += _(" Did you mean: {0}?").format(", ".join(suggestions))
        frappe.throw(msg)

    # Convert base64 photo to file URL to avoid DataError (1406) on Attach Image column (C10 fix)
    photo_url = save_base64_image(photo, "BEI FQI Report", fieldname="photo") if photo else None

    fqi = frappe.new_doc("BEI FQI Report")
    fqi.store = warehouse
    fqi.receiving = receiving
    fqi.item_code = item_code
    fqi.issue_type = issue_type
    fqi.description = description
    fqi.photo = photo_url
    fqi.expected_qty = expected_qty
    fqi.actual_qty = actual_qty
    fqi.reported_by = frappe.session.user
    fqi.reported_at = now_datetime()
    fqi.status = "Open"
    fqi.insert(ignore_permissions=True)

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
def submit_opening_report(store, checklist_items, report_time=None, notes=None,
                          photo_backup_area=None, photo_frozen_milk=None,
                          photo_toppings_area=None, photo_dispatch_area=None,
                          photo_cold_storage_temp=None):
    """Submit daily opening report with 5 required photos.

    Bug fixes (C1):
    - report_time made optional (defaults to current time) since frontend may not send it
    - Photos saved via save_base64_image to avoid DataError on Attach Image fields
    - checklist_items can be empty list (allows incomplete submission per REQ-007)
    - Wrapped in try/except returning user-friendly error instead of raw traceback
    """
    try:
        validate_store_ops_role()
        if not store:
            frappe.throw(_("Store is required"))

        # Resolve store name to valid warehouse
        warehouse = resolve_warehouse(store)

        if isinstance(checklist_items, str):
            checklist_items = json.loads(checklist_items)

        doc = frappe.new_doc("BEI Store Opening Report")
        doc.store = warehouse
        doc.report_date = nowdate()
        doc.report_time = report_time or now_datetime().strftime("%H:%M:%S")
        doc.submitted_by = frappe.session.user
        doc.notes = notes

        # Handle photos - convert base64 to file URLs if needed
        # This MUST happen before insert to avoid DataError (1406) on Attach Image columns
        doc.photo_backup_area = save_base64_image(photo_backup_area, "BEI Store Opening Report", fieldname="photo_backup_area")
        doc.photo_frozen_milk = save_base64_image(photo_frozen_milk, "BEI Store Opening Report", fieldname="photo_frozen_milk")
        doc.photo_toppings_area = save_base64_image(photo_toppings_area, "BEI Store Opening Report", fieldname="photo_toppings_area")
        doc.photo_dispatch_area = save_base64_image(photo_dispatch_area, "BEI Store Opening Report", fieldname="photo_dispatch_area")
        doc.photo_cold_storage_temp = save_base64_image(photo_cold_storage_temp, "BEI Store Opening Report", fieldname="photo_cold_storage_temp")

        # Allow empty checklist (incomplete submission per REQ-007)
        if checklist_items:
            for item in checklist_items:
                doc.append("checklist_items", item)

        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        return {"success": True, "name": doc.name}

    except frappe.exceptions.LinkValidationError as e:
        frappe.log_error(f"Opening Report LinkValidation: {str(e)}", "Opening Report Submission Error")
        return {"success": False, "error": str(e)}
    except Exception as e:
        frappe.log_error(
            f"Opening Report Error for store {store}: {str(e)}\n\n{frappe.get_traceback()}",
            "Opening Report Submission Error"
        )
        return {"success": False, "error": _("Failed to submit opening report. Please try again or contact support.")}


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
def submit_closing_report(store, checklist_items=None, report_time=None,
                          pos_total_sales=0, actual_cash_count=0,
                          card_payments=0, gcash_total=0,
                          variance_explanation=None, notes=None,
                          photo_xread_opening=None, photo_xread_closing=None,
                          photo_zread=None, photo_closing_reports=None,
                          photo_dashboard_report=None, photo_logo_signage=None,
                          photo_hygrometer=None, photo_water_meter=None,
                          photo_backup_area_clean=None, photo_frozen_milk_clean=None,
                          photo_toppings_clean=None, photo_dispatch_clean=None,
                          photo_cold_storage_close=None, photo_cashier_clean=None,
                          photo_rollup_closed=None):
    """Submit daily closing report with cash reconciliation and 15 required photos.

    Bug fixes (C2):
    - report_time made optional (defaults to current time)
    - checklist_items made optional (allows partial submission)
    - Cash fields default to 0 to avoid float(None) errors
    - insert with ignore_permissions=True for Employee Self Service role
    - Returns user-friendly error instead of raw traceback
    """
    try:
        if not store:
            frappe.throw(_("Store is required"))

        if isinstance(checklist_items, str):
            checklist_items = json.loads(checklist_items)

        # Resolve branch name to warehouse name
        warehouse = resolve_warehouse(store)

        doc = frappe.new_doc("BEI Store Closing Report")
        doc.store = warehouse
        doc.report_date = nowdate()
        doc.report_time = report_time or now_datetime().strftime("%H:%M:%S")
        doc.submitted_by = frappe.session.user
        doc.pos_total_sales = float(pos_total_sales or 0)
        doc.actual_cash_count = float(actual_cash_count or 0)
        doc.card_payments = float(card_payments or 0)
        doc.gcash_total = float(gcash_total or 0)
        doc.variance_explanation = variance_explanation
        doc.notes = notes

        # Photos - convert base64 to file URLs if needed
        doctype_name = "BEI Store Closing Report"
        doc.photo_xread_opening = save_base64_image(photo_xread_opening, doctype_name, fieldname="photo_xread_opening")
        doc.photo_xread_closing = save_base64_image(photo_xread_closing, doctype_name, fieldname="photo_xread_closing")
        doc.photo_zread = save_base64_image(photo_zread, doctype_name, fieldname="photo_zread")
        doc.photo_closing_reports = save_base64_image(photo_closing_reports, doctype_name, fieldname="photo_closing_reports")
        doc.photo_dashboard_report = save_base64_image(photo_dashboard_report, doctype_name, fieldname="photo_dashboard_report")
        doc.photo_logo_signage = save_base64_image(photo_logo_signage, doctype_name, fieldname="photo_logo_signage")
        doc.photo_hygrometer = save_base64_image(photo_hygrometer, doctype_name, fieldname="photo_hygrometer")
        doc.photo_water_meter = save_base64_image(photo_water_meter, doctype_name, fieldname="photo_water_meter")
        doc.photo_backup_area_clean = save_base64_image(photo_backup_area_clean, doctype_name, fieldname="photo_backup_area_clean")
        doc.photo_frozen_milk_clean = save_base64_image(photo_frozen_milk_clean, doctype_name, fieldname="photo_frozen_milk_clean")
        doc.photo_toppings_clean = save_base64_image(photo_toppings_clean, doctype_name, fieldname="photo_toppings_clean")
        doc.photo_dispatch_clean = save_base64_image(photo_dispatch_clean, doctype_name, fieldname="photo_dispatch_clean")
        doc.photo_cold_storage_close = save_base64_image(photo_cold_storage_close, doctype_name, fieldname="photo_cold_storage_close")
        doc.photo_cashier_clean = save_base64_image(photo_cashier_clean, doctype_name, fieldname="photo_cashier_clean")
        doc.photo_rollup_closed = save_base64_image(photo_rollup_closed, doctype_name, fieldname="photo_rollup_closed")

        if checklist_items:
            for item in checklist_items:
                doc.append("checklist_items", item)

        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        return {"success": True, "name": doc.name, "variance": doc.cash_variance}

    except Exception as e:
        frappe.log_error(
            f"Closing Report Error for store {store}: {str(e)}\n\n{frappe.get_traceback()}",
            "Closing Report Submission Error"
        )
        return {"success": False, "error": _("Failed to submit closing report. Please try again or contact support.")}


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
def submit_midshift_check(store, shift=None, temperature_readings=None,
                          cleanliness_status=None, checklist_items=None,
                          issues_found=None, corrective_action=None, photo_evidence=None,
                          late_reason=None, equipment=None, notes=None):
    """Submit mid-shift temperature and cleanliness check with time window validation.

    Bug fixes (C3):
    - shift defaults to auto-detected based on current time
    - temperature_readings and checklist_items both accepted (frontend may send either)
    - cleanliness_status made optional (defaults to 'Good')
    - photo_evidence saved via save_base64_image to avoid DataError
    - Time window validation relaxed: logs warning but allows submission with auto-populated late_reason
    - insert with ignore_permissions=True for Employee Self Service role
    """
    try:
        validate_store_ops_role()
        if not store:
            frappe.throw(_("Store is required"))

        # Resolve branch name to warehouse name
        warehouse = resolve_warehouse(store)

        if isinstance(temperature_readings, str):
            temperature_readings = json.loads(temperature_readings)
        if isinstance(checklist_items, str):
            checklist_items = json.loads(checklist_items)

        # Auto-detect shift based on current time if not provided
        current_time = now_datetime()
        current_time_str = current_time.strftime("%H:%M:%S")
        if not shift:
            hour = current_time.hour
            if hour < 12:
                shift = "Morning"
            elif hour < 17:
                shift = "Afternoon"
            else:
                shift = "Evening"

        # Normalize shift and cleanliness values to title case (Frappe Select field expects exact match)
        shift_map = {"morning": "Morning", "afternoon": "Afternoon", "evening": "Evening"}
        normalized_shift = shift_map.get(shift.lower(), shift.title()) if shift else "Afternoon"

        cleanliness_map = {"excellent": "Excellent", "good": "Good", "needs attention": "Needs Attention", "critical": "Critical"}
        normalized_cleanliness = cleanliness_map.get((cleanliness_status or "good").lower(), (cleanliness_status or "Good").title()) if cleanliness_status else "Good"

        # Define time windows per shift (can be moved to BEI Shift Template later)
        shift_windows = {
            "Morning": ("10:00:00", "11:00:00"),
            "Afternoon": ("14:00:00", "15:00:00"),
            "Evening": ("18:00:00", "19:00:00")
        }

        # Get time window for this shift
        window_start, window_end = shift_windows.get(normalized_shift, ("00:00:00", "23:59:59"))

        # Check if submission is on time
        is_on_time = window_start <= current_time_str <= window_end

        # Handle photo evidence - convert base64 to file URL
        photo_url = save_base64_image(photo_evidence, "BEI Midshift Checklist", fieldname="photo_evidence") if photo_evidence else None

        doc = frappe.new_doc("BEI Midshift Checklist")
        doc.store = warehouse
        doc.check_datetime = current_time
        doc.submitted_by = frappe.session.user
        doc.shift = normalized_shift
        doc.cleanliness_status = normalized_cleanliness
        doc.issues_found = issues_found
        doc.corrective_action = corrective_action
        doc.photo_evidence = photo_url
        doc.equipment = equipment or "General"

        # Time window fields
        doc.window_start = window_start
        doc.window_end = window_end
        doc.is_on_time = 1 if is_on_time else 0
        # Auto-populate late_reason instead of blocking submission
        if not is_on_time:
            doc.late_reason = late_reason or f"Submitted at {current_time_str} (outside {window_start}-{window_end} window)"

        if temperature_readings:
            for reading in temperature_readings:
                doc.append("temperature_readings", reading)

        # Also accept checklist_items (frontend may send this instead of temperature_readings)
        if checklist_items and hasattr(doc, 'checklist_items'):
            for item in checklist_items:
                doc.append("checklist_items", item)

        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        return {
            "success": True,
            "name": doc.name,
            "is_on_time": is_on_time,
            "window_start": window_start,
            "window_end": window_end
        }

    except Exception as e:
        frappe.log_error(
            f"Midshift Check Error for store {store}: {str(e)}\n\n{frappe.get_traceback()}",
            "Midshift Check Submission Error"
        )
        return {"success": False, "error": _("Failed to submit midshift report. Please try again or contact support.")}


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
def upload_pos_data(store, pos_date, pos_system, discount_report, transaction_report,
                    product_mix, daily_sales_revenue, sales_summary, notes=None,
                    skip_date_validation=False):
    """
    Upload daily POS data with 5 required report files.

    Args:
        store: Store/branch name
        pos_date: Date of POS data
        pos_system: POS system used (MOSAIC)
        discount_report: Discount Report file (base64)
        transaction_report: Transaction Report file (base64)
        product_mix: Product Mix file (base64)
        daily_sales_revenue: Daily Sales Revenue - Summary file (base64)
        sales_summary: Sales Summary file (base64)
        notes: Optional notes
        skip_date_validation: Skip date validation (for back-dated uploads with supervisor approval)
    """
    validate_store_ops_role()

    if not store:
        frappe.throw(_("Store is required"))

    if not all([discount_report, transaction_report, product_mix,
                daily_sales_revenue, sales_summary]):
        frappe.throw(_("All 5 POS report files are required"))

    # Date validation: Extract date from sales_summary and validate it matches pos_date
    date_mismatch_warning = None
    if not skip_date_validation:
        try:
            from hrms.utils.pos_parser import parse_sales_summary
            import base64

            # Decode sales_summary if it's base64
            if isinstance(sales_summary, str) and not sales_summary.startswith('/files/'):
                try:
                    content = base64.b64decode(sales_summary)
                except Exception:
                    content = sales_summary.encode() if isinstance(sales_summary, str) else sales_summary
            else:
                content = None

            if content:
                summary_data = parse_sales_summary(content)
                file_date = summary_data.get("metadata", {}).get("from_date")

                if file_date and str(file_date) != str(pos_date):
                    date_mismatch_warning = _(
                        "Warning: POS file date ({0}) does not match claimed date ({1}). "
                        "Please verify the correct date before submitting."
                    ).format(file_date, pos_date)
                    # Log the mismatch but allow upload (with warning returned)
                    frappe.log_error(
                        f"POS date mismatch - Store: {store}, File date: {file_date}, Claimed date: {pos_date}",
                        "POS Upload Date Mismatch"
                    )
        except Exception as e:
            # Don't block upload if date validation fails, just log it
            frappe.log_error(
                f"POS date validation error: {str(e)}",
                "POS Upload Date Validation Error"
            )

    # Resolve branch name to warehouse name (C6 fix)
    warehouse = resolve_warehouse(store)

    doc = frappe.new_doc("BEI POS Upload")
    doc.store = warehouse
    doc.pos_date = pos_date
    doc.uploaded_by = frappe.session.user
    doc.pos_system = pos_system
    doc.discount_report = discount_report
    doc.transaction_report = transaction_report
    doc.product_mix = product_mix
    doc.daily_sales_revenue = daily_sales_revenue
    doc.sales_summary = sales_summary
    doc.notes = notes
    doc.insert()

    result = {"success": True, "name": doc.name}
    if date_mismatch_warning:
        result["warning"] = date_mismatch_warning
        result["date_mismatch"] = True
    return result


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


# ==============================================================================
# BANK DEPOSIT REPORTS
# ==============================================================================


@frappe.whitelist()
def submit_bank_deposit(store, deposit_date=None, bank=None, deposits=None,
                        total_amount=0, photos=None, notes=None, deposit_type=None):
    """
    Submit bank deposit record with deposit slip photos.

    Bug fixes (C5):
    - Resolve store to warehouse (frontend sends branch code)
    - deposit_date defaults to today
    - bank defaults to empty string (frontend may not send it for Pickup type)
    - Photos converted from base64 via save_base64_image
    - deposit_type accepted (Bank Deposit or Pickup per DocType)
    - insert with ignore_permissions=True for Employee Self Service role
    - Returns user-friendly error instead of raw traceback

    Args:
        store: Store/branch name
        deposit_date: Date of deposit (defaults to today)
        bank: Bank name (BDO, BPI, etc.)
        deposits: List of {dates_covered, amount} for each deposit entry
        total_amount: Total deposit amount
        photos: List of deposit slip photo URLs/base64
        notes: Optional notes
        deposit_type: Bank Deposit or Pickup
    """
    try:
        validate_store_ops_role()

        if not store:
            frappe.throw(_("Store is required"))

        # Resolve branch name to warehouse name
        warehouse = resolve_warehouse(store)

        if isinstance(deposits, str):
            deposits = json.loads(deposits)

        if isinstance(photos, str):
            photos = json.loads(photos)

        if not deposits:
            deposits = []

        if not photos:
            photos = []

        doc = frappe.new_doc("BEI Bank Deposit")
        doc.store = warehouse
        doc.deposit_date = deposit_date or nowdate()
        doc.bank = bank or ""
        doc.total_amount = float(total_amount or 0)
        doc.submitted_by = frappe.session.user
        doc.notes = notes
        if deposit_type:
            doc.deposit_type = deposit_type

        # Add deposit entries
        for entry in deposits:
            doc.append("deposit_entries", {
                "dates_covered": entry.get("dates_covered") or entry.get("date") or nowdate(),
                "amount": float(entry.get("amount", 0))
            })

        # Add photos - convert base64 to file URLs
        for i, photo in enumerate(photos):
            photo_data = photo
            if isinstance(photo, dict):
                photo_data = photo.get("photo") or photo.get("url") or photo.get("data")

            photo_url = save_base64_image(photo_data, "BEI Bank Deposit", fieldname="photo") if photo_data else None
            if photo_url:
                doc.append("deposit_photos", {
                    "photo": photo_url,
                    "photo_number": i + 1
                })

        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        return {"success": True, "name": doc.name}

    except Exception as e:
        frappe.log_error(
            f"Bank Deposit Error for store {store}: {str(e)}\n\n{frappe.get_traceback()}",
            "Bank Deposit Submission Error"
        )
        return {"success": False, "error": _("Failed to submit bank deposit. Please try again or contact support.")}


@frappe.whitelist()
def get_bank_deposits(store=None, date_from=None, date_to=None, limit=20):
    """Get bank deposit history."""
    filters = {}
    if store:
        filters["store"] = store
    if date_from:
        filters["deposit_date"] = [">=", date_from]
    if date_to:
        if "deposit_date" in filters:
            filters["deposit_date"] = ["between", [date_from, date_to]]
        else:
            filters["deposit_date"] = ["<=", date_to]

    deposits = frappe.get_all(
        "BEI Bank Deposit",
        filters=filters,
        fields=["name", "store", "deposit_date", "bank", "total_amount", "submitted_by"],
        order_by="deposit_date desc",
        limit=int(limit)
    )
    return {"deposits": deposits}


# ==============================================================================
# POS DATA EXTRACTION
# ==============================================================================


@frappe.whitelist()
def extract_pos_data(sales_summary=None, transaction_report=None, discount_report=None,
                     daily_sales_revenue=None, product_mix=None):
    """
    Extract and parse data from MOSAIC POS export files.

    Accepts file content in multiple formats:
    - File URL (stored in Frappe File)
    - Base64 encoded string
    - Direct file content

    Args:
        sales_summary: Sales Summary file
        transaction_report: Transaction Report file
        discount_report: Discount Report file
        daily_sales_revenue: Daily Sales Revenue file
        product_mix: Product Mix file

    Returns:
        Consolidated extracted data for frontend display:
        {
            "success": True,
            "data": {
                "date": "2026-01-30",
                "gross_sales": 65474.00,
                "net_sales": 55587.24,
                "vat": 5575.73,
                "beginning_si": 16526,
                "ending_si": 16735,
                "transaction_count": 209,
                "eod_counter": 76,
                "discount_pwd": 1056.85,
                "discount_senior": 1223.28,
                "by_payment_type": {
                    "Cash": 38970.00,
                    "MosaicPay QRPH": 26504.00
                },
                "total_items_sold": 357,
                ...
            }
        }
    """
    from hrms.utils.pos_parser import extract_all_pos_data
    import base64

    def get_file_content(file_input):
        """Get file content from various input formats."""
        if not file_input:
            return None

        # If it's a Frappe file URL
        if isinstance(file_input, str) and file_input.startswith("/files/"):
            file_doc = frappe.get_doc("File", {"file_url": file_input})
            return file_doc.get_content()

        # If it's base64 encoded
        if isinstance(file_input, str):
            try:
                # Try to decode base64
                return base64.b64decode(file_input)
            except Exception:
                pass

        # If it's already bytes
        if isinstance(file_input, bytes):
            return file_input

        return None

    try:
        result = extract_all_pos_data(
            sales_summary_content=get_file_content(sales_summary),
            transaction_report_content=get_file_content(transaction_report),
            discount_report_content=get_file_content(discount_report),
            daily_sales_revenue_content=get_file_content(daily_sales_revenue),
            product_mix_content=get_file_content(product_mix)
        )

        return {
            "success": result.get("success", False),
            "data": result.get("consolidated", {}),
            "sales_summary": result.get("sales_summary"),
            "transaction_report": result.get("transaction_report"),
            "discount_report": result.get("discount_report"),
            "daily_sales_revenue": result.get("daily_sales_revenue"),
            "product_mix": result.get("product_mix"),
            "errors": result.get("errors", [])
        }

    except Exception as e:
        frappe.log_error(f"POS extraction error: {str(e)}", "POS Extraction")
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def get_extracted_pos_data(pos_upload_name):
    """
    Get extracted data for a POS Upload document.

    If extraction hasn't been done yet, perform it now.
    Stores extracted data in the document for caching.

    Args:
        pos_upload_name: Name of BEI POS Upload document

    Returns:
        Extracted POS data
    """
    doc = frappe.get_doc("BEI POS Upload", pos_upload_name)

    # Check if already extracted
    if doc.extracted_data:
        try:
            return {
                "success": True,
                "data": json.loads(doc.extracted_data),
                "cached": True
            }
        except Exception:
            pass

    # Extract data from uploaded files
    result = extract_pos_data(
        sales_summary=doc.sales_summary,
        transaction_report=doc.transaction_report,
        discount_report=doc.discount_report,
        daily_sales_revenue=doc.daily_sales_revenue,
        product_mix=doc.product_mix
    )

    # Cache the result if successful
    if result.get("success") and result.get("data"):
        doc.db_set("extracted_data", json.dumps(result["data"]))
        doc.db_set("gross_sales", result["data"].get("gross_sales", 0))
        doc.db_set("net_sales", result["data"].get("net_sales", 0))
        doc.db_set("status", "Extracted")

    return result


# ==============================================================================
# CLOSING REPORT 3-STAGE FLOW (Enhanced 2026-01-31)
# ==============================================================================


@frappe.whitelist()
def get_or_create_closing_report(store):
    """
    Get existing closing report for today or create a new one.
    Returns the report document with current stage status.
    """
    validate_store_ops_role()
    if not store:
        frappe.throw(_("Store is required"))

    # Resolve store to warehouse (C2 fix for get_or_create_closing_report)
    store = resolve_warehouse(store)

    today = nowdate()

    # Check for existing report
    existing = frappe.db.get_value(
        "BEI Store Closing Report",
        {"store": store, "report_date": today},
        ["name", "stage_completed", "status"],
        as_dict=True
    )

    if existing:
        doc = frappe.get_doc("BEI Store Closing Report", existing.name)
        return {
            "success": True,
            "name": doc.name,
            "is_new": False,
            "stage_completed": doc.stage_completed,
            "status": doc.status,
            "data": doc.as_dict()
        }

    # Create new report
    doc = frappe.new_doc("BEI Store Closing Report")
    doc.store = store
    doc.report_date = today
    doc.submitted_by = frappe.session.user
    # stage_completed is auto-computed by DocType's update_stage_completed() during insert
    doc.insert()

    return {
        "success": True,
        "name": doc.name,
        "is_new": True,
        "stage_completed": "cash",
        "status": "Draft",
        "data": doc.as_dict()
    }


@frappe.whitelist()
def submit_closing_stage1_cash(report_name, petty_cash_fund=0, delivery_fund=0,
                                change_fund=0, cash_notes=None, pos_down=False,
                                pos_down_estimated_sales=None, pos_down_transaction_count=None,
                                pos_down_notes=None, **kwargs):
    """
    Submit Stage 1: Cash Count

    Note: Cash Sales Fund stays in POS only - not entered here.
    Only Petty Cash, Delivery Fund, and Change Fund are entered in this stage.
    Denomination breakdown and voucher amounts are passed via kwargs.
    """
    validate_store_ops_role()
    doc = frappe.get_doc("BEI Store Closing Report", report_name)

    doc.petty_cash_fund = float(petty_cash_fund or 0)
    doc.delivery_fund = float(delivery_fund or 0)
    doc.change_fund = float(change_fund or 0)
    doc.cash_notes = cash_notes

    # POS Down mode
    doc.pos_down = 1 if pos_down else 0
    if pos_down:
        doc.pos_down_estimated_sales = float(pos_down_estimated_sales or 0)
        doc.pos_down_transaction_count = int(pos_down_transaction_count or 0)
        doc.pos_down_notes = pos_down_notes

    # Save denomination breakdown and voucher amounts
    denom_prefixes = ("pcf_denom_", "del_denom_", "chg_denom_")
    voucher_fields = ("pcf_voucher_amount", "delivery_voucher_amount")
    for key, value in kwargs.items():
        if key.startswith(denom_prefixes) or key in voucher_fields:
            if doc.meta.has_field(key):
                doc.set(key, float(value or 0))

    # stage_completed is auto-computed by DocType's update_stage_completed() during save
    doc.save()

    return {
        "success": True,
        "name": doc.name,
        "stage_completed": doc.stage_completed,
        "total_funds": doc.total_funds
    }


@frappe.whitelist()
def submit_closing_stage2_checklist(report_name, inventory_items, checklist_items=None,
                                     cashier_signoff=False, production_signoff=False,
                                     supervisor_signoff=False, equipment_status=None):
    """
    Submit Stage 2: Checklist & Inventory Spot Check

    inventory_items: List of {item_name, expected_count, actual_count}
    - 12 specific items categorized by: Highest Cost, Single Count Variances,
      Shortest Shelf Life, Most Used Items

    checklist_items: General end-of-day tasks
    """
    validate_store_ops_role()
    doc = frappe.get_doc("BEI Store Closing Report", report_name)

    if isinstance(inventory_items, str):
        inventory_items = json.loads(inventory_items)

    if isinstance(checklist_items, str):
        checklist_items = json.loads(checklist_items)

    if isinstance(equipment_status, str):
        equipment_status = json.loads(equipment_status)

    # Clear existing inventory items
    doc.inventory_spot_check = []

    # Add inventory spot check items (12 items)
    for item in inventory_items:
        doc.append("inventory_spot_check", {
            "item_name": item.get("item_name"),
            "category": item.get("category"),
            "expected_count": float(item.get("expected_count", 0)),
            "actual_count": float(item.get("actual_count", 0))
        })

    # Add checklist items if provided
    if checklist_items:
        doc.checklist_items = []
        for item in checklist_items:
            doc.append("checklist_items", item)

    # Equipment status
    if equipment_status:
        doc.freezer_temp = equipment_status.get("freezer_temp")
        doc.chiller_temp = equipment_status.get("chiller_temp")
        doc.pos_closed_properly = equipment_status.get("pos_closed_properly", 0)

    # Staff signoffs
    doc.cashier_signoff = 1 if cashier_signoff else 0
    doc.production_signoff = 1 if production_signoff else 0
    doc.supervisor_signoff = 1 if supervisor_signoff else 0

    # stage_completed is auto-computed by DocType's update_stage_completed() during save
    doc.save()

    return {
        "success": True,
        "name": doc.name,
        "stage_completed": doc.stage_completed,
        "inventory_variance_total": doc.inventory_variance_total,
        "inventory_variance_count": doc.inventory_variance_count
    }


@frappe.whitelist()
def submit_closing_stage3_photos(report_name, x_reading_opening_photo, x_reading_closing_photo,
                                  z_reading_photo, pos_files=None, store_photos=None,
                                  variance_explanation=None, notes=None):
    """
    Submit Stage 3: Photos & Files

    Document Scanner Photos (with edge detection):
    - x_reading_opening_photo: X-Reading from opening shift
    - x_reading_closing_photo: X-Reading from closing shift
    - z_reading_photo: Z-Reading (end of day)

    pos_files: List of 5 POS export files
    store_photos: Dict of store area photos (logo_signage, hygrometer, etc.)
    """
    validate_store_ops_role()
    doc = frappe.get_doc("BEI Store Closing Report", report_name)

    # Document scanner photos (required)
    if not x_reading_opening_photo or not str(x_reading_opening_photo).strip():
        frappe.throw(_("X-Reading Opening photo is required"), title=_("Missing Photo"))
    if not x_reading_closing_photo or not str(x_reading_closing_photo).strip():
        frappe.throw(_("X-Reading Closing photo is required"), title=_("Missing Photo"))
    if not z_reading_photo or not str(z_reading_photo).strip():
        frappe.throw(_("Z-Reading photo is required"), title=_("Missing Photo"))

    doc.photo_xread_opening = str(x_reading_opening_photo).strip()
    doc.photo_xread_closing = str(x_reading_closing_photo).strip()
    doc.photo_zread = str(z_reading_photo).strip()

    # POS files (5 required)
    if pos_files:
        if isinstance(pos_files, str):
            pos_files = json.loads(pos_files)
        doc.pos_discount_report = pos_files.get("discount_report")
        doc.pos_transaction_report = pos_files.get("transaction_report")
        doc.pos_product_mix = pos_files.get("product_mix")
        doc.pos_daily_sales_revenue = pos_files.get("daily_sales_revenue")
        doc.pos_sales_summary = pos_files.get("sales_summary")

    # Store area photos (standard camera)
    if store_photos:
        if isinstance(store_photos, str):
            store_photos = json.loads(store_photos)
        doc.photo_logo_signage = store_photos.get("logo_signage")
        doc.photo_hygrometer = store_photos.get("hygrometer")
        doc.photo_water_meter = store_photos.get("water_meter")
        doc.photo_backup_area_clean = store_photos.get("backup_area")
        doc.photo_frozen_milk_clean = store_photos.get("frozen_milk")
        doc.photo_toppings_clean = store_photos.get("toppings")
        doc.photo_dispatch_clean = store_photos.get("dispatch")
        doc.photo_cold_storage_close = store_photos.get("cold_storage")
        doc.photo_cashier_clean = store_photos.get("cashier")
        doc.photo_rollup_closed = store_photos.get("rollup_door")

    # Variance explanation (required if variance > ±50)
    if variance_explanation:
        doc.variance_explanation = variance_explanation

    doc.notes = notes
    doc.report_time = now_datetime().strftime("%H:%M:%S")
    # stage_completed is auto-computed by DocType's update_stage_completed() during save
    doc.save()

    return {
        "success": True,
        "name": doc.name,
        "stage_completed": doc.stage_completed,
        "status": doc.status,
        "cash_variance": doc.cash_variance
    }


@frappe.whitelist()
def get_closing_report_status(store=None, date=None):
    """
    Get closing report status for a store on a specific date.
    Returns stage progress and completion status.
    """
    if not store:
        frappe.throw(_("Store is required"))
    if not date:
        date = nowdate()

    report = frappe.db.get_value(
        "BEI Store Closing Report",
        {"store": store, "report_date": date},
        ["name", "stage_completed", "status", "pos_down", "cash_variance",
         "inventory_variance_total", "cashier_signoff", "production_signoff"],
        as_dict=True
    )

    if not report:
        return {
            "exists": False,
            "stage_completed": None,
            "status": None
        }

    return {
        "exists": True,
        "name": report.name,
        "stage_completed": report.stage_completed,
        "status": report.status,
        "pos_down": report.pos_down,
        "cash_variance": report.cash_variance,
        "inventory_variance_total": report.inventory_variance_total,
        "cashier_signoff": report.cashier_signoff,
        "production_signoff": report.production_signoff
    }


# ==============================================================================
# MID-SHIFT HANDOVER
# ==============================================================================


@frappe.whitelist()
def submit_mid_shift_handover(store, outgoing_cashier=None, incoming_cashier=None,
                               x_reading_photo=None, cash_count=0, expected_cash=0,
                               variance_explanation=None, x_reading_cash=None,
                               sales_cash_deposit=None):
    """
    Submit mid-shift handover when cashiers switch shifts.
    Identifies shortage/overage per cashier shift.

    Bug fixes (C4):
    - Resolve employee IDs from names/emails (frontend may send either)
    - x_reading_photo converted via save_base64_image
    - cash_count/expected_cash default to 0 to avoid float(None) errors
    - Accept renamed frontend field aliases (x_reading_cash, sales_cash_deposit)
    - Auto-populate outgoing/incoming cashier from session user if not provided
    - insert with ignore_permissions=True for Store Staff role
    """
    try:
        validate_store_ops_role()
        if not store:
            frappe.throw(_("Store is required"))

        # Resolve store
        warehouse = resolve_warehouse(store)

        # Resolve employee references - frontend may send email, name, or employee ID
        def resolve_employee_ref(ref):
            if not ref:
                return None
            # Check if it's already an Employee ID
            if frappe.db.exists("Employee", ref):
                return ref
            # Check by user_id (email)
            emp = frappe.db.get_value("Employee", {"user_id": ref, "status": "Active"}, "name")
            if emp:
                return emp
            # Check by employee_name
            emp = frappe.db.get_value("Employee", {"employee_name": ref, "status": "Active"}, "name")
            if emp:
                return emp
            return ref  # Return as-is, let Frappe validation handle it

        resolved_outgoing = resolve_employee_ref(outgoing_cashier)
        resolved_incoming = resolve_employee_ref(incoming_cashier)

        # Auto-populate from session user if not provided
        if not resolved_outgoing:
            resolved_outgoing = frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")
        if not resolved_incoming:
            resolved_incoming = resolved_outgoing  # Same person if not specified

        # Handle x_reading_photo base64
        photo_url = save_base64_image(x_reading_photo, "BEI Mid-Shift Handover", fieldname="x_reading_photo") if x_reading_photo else None

        # Support renamed fields from frontend
        final_cash_count = float(sales_cash_deposit or cash_count or 0)
        final_expected_cash = float(x_reading_cash or expected_cash or 0)

        doc = frappe.new_doc("BEI Mid-Shift Handover")
        doc.store = warehouse
        doc.report_date = nowdate()
        doc.handover_time = now_datetime().strftime("%H:%M:%S")
        doc.outgoing_cashier = resolved_outgoing
        doc.incoming_cashier = resolved_incoming
        doc.x_reading_photo = photo_url
        doc.cash_count = final_cash_count
        doc.expected_cash = final_expected_cash
        doc.variance_explanation = variance_explanation
        doc.submitted_by = frappe.session.user

        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)

        # Link to closing report if exists
        closing_report = frappe.db.get_value(
            "BEI Store Closing Report",
            {"store": warehouse, "report_date": nowdate()},
            "name"
        )
        if closing_report:
            doc.db_set("closing_report", closing_report)

        return {
            "success": True,
            "name": doc.name,
            "variance": getattr(doc, 'variance', 0),
            "status": getattr(doc, 'status', 'Submitted')
        }

    except Exception as e:
        frappe.log_error(
            f"Handover Error for store {store}: {str(e)}\n\n{frappe.get_traceback()}",
            "Handover Submission Error"
        )
        return {"success": False, "error": _("Failed to submit handover report. Please try again or contact support.")}


@frappe.whitelist()
def get_mid_shift_handovers(store, date=None, limit=10):
    """Get mid-shift handovers for a store on a specific date."""
    validate_store_ops_role()

    if not date:
        date = nowdate()

    handovers = frappe.get_all(
        "BEI Mid-Shift Handover",
        filters={"store": store, "report_date": date},
        fields=["name", "handover_time", "outgoing_cashier", "incoming_cashier",
                "cash_count", "expected_cash", "variance", "status"],
        order_by="handover_time desc",
        limit=int(limit)
    )

    # Get employee names
    for h in handovers:
        h["outgoing_cashier_name"] = frappe.db.get_value(
            "Employee", h["outgoing_cashier"], "employee_name"
        ) or h["outgoing_cashier"]
        h["incoming_cashier_name"] = frappe.db.get_value(
            "Employee", h["incoming_cashier"], "employee_name"
        ) or h["incoming_cashier"]

    return {"handovers": handovers}


# ==============================================================================
# MAINTENANCE REQUESTS
# ==============================================================================


@frappe.whitelist()
def submit_maintenance_request(store, priority, description,
                                issue_category=None, category=None,
                                equipment_area=None, impact_on_operations=None,
                                title=None, before_photos=None, photos=None):
    """
    Submit a maintenance request from store staff.
    Notifies Projects team (Daniel) for assessment and assignment.

    Args:
        store: Store/branch name
        priority: Urgent, High, Normal
        description: Issue description
        issue_category: Category (Equipment, Plumbing, etc.) - backend param name
        category: Category - frontend param name (alias for issue_category)
        equipment_area: Specific equipment/area affected (optional)
        impact_on_operations: Can Operate, Limited Operations, Cannot Operate (optional)
        title: Issue title (optional, prepended to description)
        before_photos: Single photo (deprecated, for backward compatibility)
        photos: JSON array of photo objects [{photo: url, caption: text}, ...]
    """
    validate_store_ops_role()

    import json

    if not store:
        frappe.throw(_("Store is required"))

    # Support both parameter names (frontend sends 'category', backend expects 'issue_category')
    final_category = issue_category or category
    if not final_category:
        frappe.throw(_("Issue category is required"))

    # Resolve branch name to warehouse name
    warehouse = resolve_warehouse(store)

    # Build full description from title + description
    full_description = description
    if title:
        full_description = f"{title}\n\n{description}"

    doc = frappe.new_doc("BEI Maintenance Request")
    doc.store = warehouse
    doc.request_date = nowdate()
    doc.issue_category = final_category
    doc.equipment_area = equipment_area or "Other"
    doc.priority = priority
    doc.description = full_description
    # Normalize impact_on_operations (frontend may send "Partial Impact" for "Limited Operations")
    impact_map = {"Partial Impact": "Limited Operations"}
    normalized_impact = impact_map.get(impact_on_operations, impact_on_operations) or "Can Operate"
    doc.impact_on_operations = normalized_impact
    doc.reported_by = frappe.session.user
    doc.status = "Open"

    # Handle photos - support both old single photo and new array format
    # Also handles base64 data by saving to file system first
    if photos:
        # Parse JSON if string
        if isinstance(photos, str):
            photos = json.loads(photos)

        # Add each photo to the child table
        for photo_data in photos:
            photo_url = None
            caption = ""

            if isinstance(photo_data, str):
                # Simple string - could be URL or base64
                photo_url = save_base64_image(photo_data, "BEI Maintenance Request", fieldname="photo")
            elif isinstance(photo_data, dict):
                # Object with photo and optional caption
                raw_photo = photo_data.get("photo") or photo_data.get("url")
                photo_url = save_base64_image(raw_photo, "BEI Maintenance Request", fieldname="photo")
                caption = photo_data.get("caption", "")

            if photo_url:
                doc.append("photos", {
                    "photo": photo_url,
                    "caption": caption
                })
    elif before_photos:
        # Backward compatibility: convert single photo to child table entry
        photo_url = save_base64_image(before_photos, "BEI Maintenance Request", fieldname="photo")
        if photo_url:
            doc.append("photos", {"photo": photo_url})

    doc.insert(ignore_permissions=True)

    return {
        "success": True,
        "name": doc.name,
        "message": _("Maintenance request {0} submitted. Projects team will be notified.").format(doc.name)
    }


@frappe.whitelist()
def get_maintenance_requests(store=None, status=None, limit=20, my_requests=False):
    """Get maintenance requests optionally filtered by store and status.

    Bug fix (C14): Added my_requests parameter to filter by current user's reported_by.
    This is the fix for "request not visible after submit" - the frontend was calling
    get_maintenance_requests without filtering by user, so it showed requests from
    all stores (or none if store filter didn't match).
    """
    filters = {}

    # C14 fix: When my_requests=True, filter by current user
    if my_requests or (not store and not status):
        filters["reported_by"] = frappe.session.user
    else:
        if store:
            # Resolve store name for consistent matching
            try:
                warehouse = resolve_warehouse(store)
                filters["store"] = warehouse
            except Exception:
                filters["store"] = store
        if status:
            if isinstance(status, str):
                filters["status"] = status
            else:
                filters["status"] = ["in", status]

    requests = frappe.get_all(
        "BEI Maintenance Request",
        filters=filters,
        fields=["name", "store", "store_code", "issue_category", "equipment_area",
                "priority", "status", "scheduled_date", "request_date",
                "reported_by", "description"],
        order_by="request_date desc",
        limit=int(limit)
    )

    return {"requests": requests}


@frappe.whitelist()
def get_my_maintenance_requests(status=None, limit=20):
    """Get maintenance requests submitted by current user.

    Bug fix (C14): Dedicated endpoint for "View My Requests" functionality.
    Filters by reported_by = current user so submitted requests always appear.
    """
    filters = {"reported_by": frappe.session.user}
    if status:
        if isinstance(status, str):
            filters["status"] = status
        else:
            filters["status"] = ["in", status]

    requests = frappe.get_all(
        "BEI Maintenance Request",
        filters=filters,
        fields=["name", "store", "store_code", "issue_category", "equipment_area",
                "priority", "status", "scheduled_date", "request_date",
                "description"],
        order_by="request_date desc",
        limit=int(limit)
    )

    return {"requests": requests}


@frappe.whitelist()
def check_maintenance_for_closing(store, date=None):
    """
    Check if there's maintenance scheduled or completed today that needs verification.
    Used to show dynamic maintenance section in closing report.
    """
    if not date:
        date = nowdate()

    # Get completed maintenance that needs verification
    from hrms.hr.doctype.bei_maintenance_completion.bei_maintenance_completion import (
        check_maintenance_for_closing_report
    )

    return check_maintenance_for_closing_report(store, date)


@frappe.whitelist()
def verify_maintenance_from_closing(maintenance_completion, verified=True,
                                     verification_notes=None):
    """
    Verify or reject maintenance completion from closing report.
    """
    doc = frappe.get_doc("BEI Maintenance Completion", maintenance_completion)

    if verified:
        return doc.verify_completion(notes=verification_notes)
    else:
        if not verification_notes:
            frappe.throw(_("Rejection reason is required"))
        return doc.reject_completion(notes=verification_notes)
