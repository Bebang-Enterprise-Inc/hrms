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

    # Resolve branch name to warehouse name
    warehouse = resolve_warehouse(store)

    if isinstance(temperature_readings, str):
        temperature_readings = json.loads(temperature_readings)

    # Normalize shift and cleanliness values to title case (Frappe Select field expects exact match)
    shift_map = {"morning": "Morning", "afternoon": "Afternoon", "evening": "Evening"}
    normalized_shift = shift_map.get(shift.lower(), shift.title()) if shift else shift

    cleanliness_map = {"excellent": "Excellent", "good": "Good", "needs attention": "Needs Attention", "critical": "Critical"}
    normalized_cleanliness = cleanliness_map.get(cleanliness_status.lower(), cleanliness_status.title()) if cleanliness_status else cleanliness_status

    doc = frappe.new_doc("BEI Midshift Checklist")
    doc.store = warehouse
    doc.check_datetime = now_datetime()
    doc.submitted_by = frappe.session.user
    doc.shift = normalized_shift
    doc.cleanliness_status = normalized_cleanliness
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
def upload_pos_data(store, pos_date, pos_system, discount_report, transaction_report,
                    product_mix, daily_sales_revenue, sales_summary, notes=None):
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
    """
    if not store:
        frappe.throw(_("Store is required"))

    if not all([discount_report, transaction_report, product_mix,
                daily_sales_revenue, sales_summary]):
        frappe.throw(_("All 5 POS report files are required"))

    doc = frappe.new_doc("BEI POS Upload")
    doc.store = store
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


# ==============================================================================
# BANK DEPOSIT REPORTS
# ==============================================================================


@frappe.whitelist()
def submit_bank_deposit(store, deposit_date, bank, deposits, total_amount,
                        photos, notes=None):
    """
    Submit bank deposit record with deposit slip photos.

    Args:
        store: Store/branch name
        deposit_date: Date of deposit
        bank: Bank name (BDO, BPI, etc.)
        deposits: List of {dates_covered, amount} for each deposit entry
        total_amount: Total deposit amount
        photos: List of deposit slip photo URLs/base64
        notes: Optional notes
    """
    if not store:
        frappe.throw(_("Store is required"))

    if not bank:
        frappe.throw(_("Bank is required"))

    if isinstance(deposits, str):
        deposits = json.loads(deposits)

    if isinstance(photos, str):
        photos = json.loads(photos)

    if not deposits:
        frappe.throw(_("At least one deposit entry is required"))

    if not photos:
        frappe.throw(_("At least one deposit slip photo is required"))

    doc = frappe.new_doc("BEI Bank Deposit")
    doc.store = store
    doc.deposit_date = deposit_date
    doc.bank = bank
    doc.total_amount = float(total_amount)
    doc.submitted_by = frappe.session.user
    doc.notes = notes

    # Add deposit entries
    for entry in deposits:
        doc.append("deposit_entries", {
            "dates_covered": entry.get("dates_covered"),
            "amount": float(entry.get("amount", 0))
        })

    # Add photos
    for i, photo in enumerate(photos):
        doc.append("deposit_photos", {
            "photo": photo,
            "photo_number": i + 1
        })

    doc.insert()
    return {"success": True, "name": doc.name}


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
    if not store:
        frappe.throw(_("Store is required"))

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
    doc.stage_completed = "Cash"
    doc.insert()

    return {
        "success": True,
        "name": doc.name,
        "is_new": True,
        "stage_completed": "Cash",
        "status": "Draft",
        "data": doc.as_dict()
    }


@frappe.whitelist()
def submit_closing_stage1_cash(report_name, petty_cash_fund=0, delivery_fund=0,
                                change_fund=0, cash_notes=None, pos_down=False,
                                pos_down_estimated_sales=None, pos_down_transaction_count=None,
                                pos_down_notes=None):
    """
    Submit Stage 1: Cash Count

    Note: Cash Sales Fund stays in POS only - not entered here.
    Only Petty Cash, Delivery Fund, and Change Fund are entered in this stage.
    """
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

    doc.stage_completed = "Checklist"
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

    doc.stage_completed = "Photos"
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
    doc = frappe.get_doc("BEI Store Closing Report", report_name)

    # Document scanner photos (required)
    doc.x_reading_opening_photo = x_reading_opening_photo
    doc.x_reading_closing_photo = x_reading_closing_photo
    doc.z_reading_photo = z_reading_photo

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
    doc.stage_completed = "Complete"
    doc.save()

    return {
        "success": True,
        "name": doc.name,
        "stage_completed": doc.stage_completed,
        "status": doc.status,
        "cash_variance": doc.cash_variance
    }


@frappe.whitelist()
def get_closing_report_status(store, date=None):
    """
    Get closing report status for a store on a specific date.
    Returns stage progress and completion status.
    """
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
def submit_mid_shift_handover(store, outgoing_cashier, incoming_cashier,
                               x_reading_photo, cash_count, expected_cash,
                               variance_explanation=None):
    """
    Submit mid-shift handover when cashiers switch shifts.
    Identifies shortage/overage per cashier shift.
    """
    if not store:
        frappe.throw(_("Store is required"))

    if outgoing_cashier == incoming_cashier:
        frappe.throw(_("Outgoing and incoming cashiers must be different"))

    doc = frappe.new_doc("BEI Mid-Shift Handover")
    doc.store = store
    doc.report_date = nowdate()
    doc.handover_time = now_datetime().strftime("%H:%M:%S")
    doc.outgoing_cashier = outgoing_cashier
    doc.incoming_cashier = incoming_cashier
    doc.x_reading_photo = x_reading_photo
    doc.cash_count = float(cash_count)
    doc.expected_cash = float(expected_cash)
    doc.variance_explanation = variance_explanation
    doc.submitted_by = frappe.session.user

    doc.insert()

    # Link to closing report if exists
    closing_report = frappe.db.get_value(
        "BEI Store Closing Report",
        {"store": store, "report_date": nowdate()},
        "name"
    )
    if closing_report:
        doc.db_set("closing_report", closing_report)

    return {
        "success": True,
        "name": doc.name,
        "variance": doc.variance,
        "status": doc.status
    }


@frappe.whitelist()
def get_mid_shift_handovers(store, date=None, limit=10):
    """Get mid-shift handovers for a store on a specific date."""
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
def submit_maintenance_request(store, issue_category, equipment_area, priority,
                                description, impact_on_operations, before_photos=None):
    """
    Submit a maintenance request from store staff.
    Notifies Projects team (Daniel) for assessment and assignment.
    """
    if not store:
        frappe.throw(_("Store is required"))

    # Resolve branch name to warehouse name
    warehouse = resolve_warehouse(store)

    doc = frappe.new_doc("BEI Maintenance Request")
    doc.store = warehouse
    doc.request_date = nowdate()
    doc.issue_category = issue_category
    doc.equipment_area = equipment_area
    doc.priority = priority
    doc.description = description
    doc.impact_on_operations = impact_on_operations
    doc.before_photos = before_photos
    doc.reported_by = frappe.session.user
    doc.status = "Open"

    doc.insert()

    return {
        "success": True,
        "name": doc.name,
        "message": _("Maintenance request {0} submitted. Projects team will be notified.").format(doc.name)
    }


@frappe.whitelist()
def get_maintenance_requests(store=None, status=None, limit=20):
    """Get maintenance requests optionally filtered by store and status."""
    filters = {}
    if store:
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
                "priority", "status", "scheduled_date", "request_date"],
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
