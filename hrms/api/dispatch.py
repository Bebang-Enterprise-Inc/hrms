# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Dispatch Tracker API
Handles warehouse dispatch, route tracking, and delivery confirmation for my.bebang.ph
"""

import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, flt


# RBAC roles for SCM module
SCM_ADMIN_ROLES = {"HR Manager", "Warehouse Manager", "System Manager"}
SCM_DISPATCH_ROLES = {"HR Manager", "Warehouse Manager", "Logistics Coordinator", "System Manager"}
SCM_STORE_ROLES = {"Store Staff", "Store Supervisor", "Area Supervisor", "Warehouse User", "System Manager"}

def _check_scm_permission(allowed_roles, action="access this resource"):
    """Check if current user has any of the allowed roles."""
    user_roles = set(frappe.get_roles(frappe.session.user))
    if not user_roles.intersection(allowed_roles):
        frappe.throw(
            _("You do not have permission to {0}").format(action),
            frappe.PermissionError
        )


@frappe.whitelist()
def get_trips(date=None, status=None):
    """Get dispatch trips for a date. Defaults to today if no date specified."""
    _check_scm_permission(SCM_DISPATCH_ROLES, "view dispatch trips")

    filters = {"trip_date": date or nowdate()}

    if status:
        filters["status"] = status

    trips = frappe.get_all(
        "BEI Distribution Trip",
        filters=filters,
        fields=["name", "trip_date", "route_name", "driver", "vehicle", "vehicle_plate", "status", "departure_time"],
        order_by="creation"
    )

    # Get stop counts and delivery progress
    for trip in trips:
        stops = frappe.get_all(
            "BEI Trip Stop",
            filters={"parent": trip.name},
            fields=["status"]
        )
        trip["total_stops"] = len(stops)
        trip["delivered_stops"] = sum(1 for s in stops if s.status == "Delivered")

    return {"trips": trips}


@frappe.whitelist()
def get_trip_detail(trip_name):
    """Get full trip details including all stops."""
    _check_scm_permission(SCM_DISPATCH_ROLES, "view trip details")

    trip = frappe.get_doc("BEI Distribution Trip", trip_name)

    return {
        "trip": {
            "name": trip.name,
            "trip_date": trip.trip_date,
            "route_name": trip.route_name,
            "driver": trip.driver,
            "vehicle": trip.vehicle,
            "vehicle_plate": trip.vehicle_plate,
            "status": trip.status,
            "departure_time": trip.departure_time,
            "departure_temp": trip.departure_temp,
            "seal_number": trip.seal_number,
            "stops": [
                {
                    "idx": s.idx,
                    "store": s.store,
                    "stop_order": s.stop_order,
                    "items_count": s.items_count,
                    "status": s.status,
                    "arrival_time": s.arrival_time,
                    "signed_by": s.signed_by,
                    "exception_reason": s.exception_reason
                }
                for s in trip.stops
            ]
        }
    }


@frappe.whitelist()
def confirm_departure(trip_name, driver=None, vehicle=None, vehicle_plate=None, temperature=None, seal_number=None):
    """
    Confirm trip departure with checklist.
    Updates trip with departure details and sets status to In Transit.
    """
    _check_scm_permission(SCM_DISPATCH_ROLES, "confirm departure")

    trip = frappe.get_doc("BEI Distribution Trip", trip_name)

    if trip.status != "Preparing":
        frappe.throw(_("Trip is not in Preparing status"))

    if driver:
        trip.driver = driver
    if vehicle:
        trip.vehicle = vehicle
    if vehicle_plate:
        trip.vehicle_plate = vehicle_plate
    if temperature:
        trip.departure_temp = float(temperature)
    if seal_number:
        trip.seal_number = seal_number

    trip.departure_time = now_datetime()
    trip.status = "In Transit"
    trip.save()

    return {
        "success": True,
        "message": f"Trip {trip_name} departed at {trip.departure_time}"
    }


def _get_stop(trip, stop_idx):
    """Validate and return a trip stop by 1-based index."""
    stop_idx = int(stop_idx)
    if stop_idx < 1 or stop_idx > len(trip.stops):
        frappe.throw(_("Invalid stop index"))
    return trip.stops[stop_idx - 1]


def _update_trip_status(trip, require_all_processed=False):
    """Recalculate trip status based on stop statuses.

    Args:
        require_all_processed: If True, only update status when all stops are processed.
            Used by report_exception to preserve "In Transit" until all stops are visited.

    Returns (delivered_count, total_count) for use in response payloads.
    """
    total = len(trip.stops)
    delivered = sum(1 for s in trip.stops if s.status == "Delivered")
    processed = sum(1 for s in trip.stops if s.status != "Pending")

    if processed == total:
        trip.status = "Completed" if delivered == total else "Partial"
    elif not require_all_processed and (delivered > 0 or processed > 0):
        trip.status = "Partial"

    return delivered, total


@frappe.whitelist()
def confirm_delivery(trip_name, stop_idx, signature=None, signed_by=None):
    """Confirm delivery at a specific stop. stop_idx is 1-based."""
    _check_scm_permission(SCM_DISPATCH_ROLES, "confirm delivery")

    trip = frappe.get_doc("BEI Distribution Trip", trip_name)

    if trip.status not in ["In Transit", "Partial"]:
        frappe.throw(_("Trip is not in transit"))

    stop = _get_stop(trip, stop_idx)
    stop.status = "Delivered"
    stop.arrival_time = now_datetime()
    stop.signature = signature
    stop.signed_by = signed_by

    # Auto-generate delivery billing (async, feature-flagged)
    if frappe.db.get_single_value("BEI Settings", "billing_auto_create_on_delivery"):
        stop.billing_creation_status = "Pending"
        frappe.enqueue(
            "hrms.api.dispatch._create_delivery_billing",
            queue="default",
            trip_name=trip.name,
            stop_idx=stop.idx,
            enqueue_after_commit=True
        )

    delivered, total = _update_trip_status(trip)
    trip.save()

    # PHASE 1A: Send "1 stop away" notification to next stop
    # This runs AFTER save so delivery is confirmed even if notification fails
    try:
        current_stop_order = int(stop_idx)
        next_stop = None
        for s in trip.stops:
            if s.stop_order == current_stop_order + 1 and s.status == "Pending":
                next_stop = s
                break

        if next_stop and trip.departure_time:
            from frappe.utils import add_to_date, format_time, get_datetime
            # Calculate ETA for next stop
            departure_dt = get_datetime(trip.departure_time)
            scheduled_arrival = add_to_date(departure_dt, minutes=next_stop.stop_order * 20)
            window_start = add_to_date(scheduled_arrival, minutes=-15)
            window_end = add_to_date(scheduled_arrival, minutes=15)
            eta_range = f"{format_time(window_start)} - {format_time(window_end)}"

            _send_delivery_notification(trip.driver or "Driver", next_stop.store, eta_range)
    except Exception as e:
        # CRITICAL: Notification failures must not block delivery confirmation
        frappe.log_error(
            title="Next Stop Notification Failed",
            message=f"Failed to notify next stop for {trip_name}: {str(e)}"
        )

    return {
        "success": True,
        "message": f"Delivery to {stop.store} confirmed",
        "trip_status": trip.status,
        "delivered": delivered,
        "total": total
    }


@frappe.whitelist()
def report_exception(trip_name, stop_idx, exception_type, reason=None, photo=None):
    """Report an exception at a stop (store closed, refused, etc)."""
    _check_scm_permission(SCM_DISPATCH_ROLES, "report exceptions")

    trip = frappe.get_doc("BEI Distribution Trip", trip_name)

    stop = _get_stop(trip, stop_idx)
    stop.status = exception_type
    stop.arrival_time = now_datetime()
    stop.exception_reason = reason
    if photo:
        stop.exception_photo = photo

    _update_trip_status(trip, require_all_processed=True)
    trip.save()

    return {
        "success": True,
        "message": f"Exception reported for {stop.store}: {exception_type}"
    }


@frappe.whitelist()
def get_route_progress(trip_name):
    """Get current progress of a trip."""
    _check_scm_permission(SCM_DISPATCH_ROLES, "view route progress")

    trip = frappe.get_doc("BEI Distribution Trip", trip_name)

    stops = []
    for stop in trip.stops:
        stops.append({
            "idx": stop.idx,
            "store": stop.store,
            "stop_order": stop.stop_order,
            "items_count": stop.items_count,
            "status": stop.status,
            "arrival_time": str(stop.arrival_time) if stop.arrival_time else None,
            "signed_by": stop.signed_by,
            "exception_reason": stop.exception_reason
        })

    delivered = sum(1 for s in trip.stops if s.status == "Delivered")
    exceptions = sum(1 for s in trip.stops if s.status in ["Store Closed", "Refused"])

    return {
        "trip_name": trip.name,
        "status": trip.status,
        "departure_time": str(trip.departure_time) if trip.departure_time else None,
        "total_stops": len(trip.stops),
        "delivered": delivered,
        "exceptions": exceptions,
        "pending": len(trip.stops) - delivered - exceptions,
        "stops": stops
    }


def _build_trip_doc(trip_date, route_name, stops):
    """Build a BEI Distribution Trip document with stops (not yet inserted)."""
    trip = frappe.new_doc("BEI Distribution Trip")
    trip.trip_date = trip_date or nowdate()
    trip.route_name = route_name
    trip.status = "Preparing"

    for idx, stop_data in enumerate(stops, 1):
        trip.append("stops", {
            "store": stop_data.get("store"),
            "stop_order": idx,
            "items_count": stop_data.get("items_count", 0),
            "status": "Pending"
        })

    return trip


@frappe.whitelist()
def create_trip(trip_date, route_name, stops):
    """Create a new distribution trip. stops: list of {store, items_count}."""
    _check_scm_permission(SCM_ADMIN_ROLES, "create trips")

    if isinstance(stops, str):
        stops = frappe.parse_json(stops)

    if not stops:
        frappe.throw(_("At least one stop is required"))

    trip = _build_trip_doc(trip_date, route_name, stops)

    try:
        trip.insert()
    except frappe.DuplicateEntryError:
        # Naming series counter out of sync - fix and retry with fresh doc
        frappe.db.sql(
            """UPDATE `tabSeries` SET current = (
                SELECT IFNULL(MAX(CAST(SUBSTRING_INDEX(name, '-', -1) AS UNSIGNED)), 0)
                FROM `tabBEI Distribution Trip`
            ) WHERE name = %s""",
            (trip.naming_series.replace('.YYYY.', str(nowdate()[:4])).replace('.#####', ''),)
        )
        frappe.db.commit()
        trip = _build_trip_doc(trip_date, route_name, stops)
        trip.insert()

    return {
        "success": True,
        "trip": trip.name,
        "message": f"Trip {trip.name} created with {len(stops)} stops"
    }


FRANCHISE_STORE_TYPES = ("Full Franchise", "Managed Franchise")
FRANCHISE_MARKUP = 1.08


def _create_delivery_billing(trip_name, stop_idx):
    """Create a BEI Billing Schedule for a delivery stop. Runs async via enqueue."""
    trip = frappe.get_doc("BEI Distribution Trip", trip_name)
    stop = trip.stops[int(stop_idx) - 1]

    try:
        sp = frappe.db.savepoint("delivery_billing")

        # I-04 fix: Duplicate check before creating billing
        existing = frappe.db.exists("BEI Billing Schedule", {
            "trip_reference": trip.name,
            "trip_stop_idx": stop.idx,
            "billing_type": "Delivery",
            "status": ["not in", ["Cancelled"]],
        })
        if existing:
            stop.billing_reference = existing
            stop.billing_creation_status = "Success"
            trip.save(ignore_permissions=True)
            frappe.db.release_savepoint(sp)
            return

        # Resolve store department, store type, and active rate -- bail on missing data
        dept = frappe.db.get_value(
            "BEI Warehouse Department Mapping",
            {"warehouse": stop.store, "is_active": 1},
            "department",
        )
        if not dept:
            _fail_stop(trip, stop, sp, f"No warehouse->department mapping for {stop.store}", title="Missing Department Mapping")
            return

        store_type = frappe.db.get_value("BEI Store Type", {"store": dept}, "store_type")

        rate = frappe.db.get_value(
            "BEI Delivery Rate",
            {"store": dept, "cargo_type": trip.cargo_type, "status": "Active"},
            ["delivery_fee", "logistics_fee"],
            as_dict=True,
        )
        if not rate:
            _fail_stop(trip, stop, sp, f"No active {trip.cargo_type} rate for {dept}")
            return

        # Calculate goods value from store order
        goods_value = _get_order_goods_value(stop.store_order)

        # Apply 8% markup for franchise stores
        is_franchise = store_type in FRANCHISE_STORE_TYPES
        markup = FRANCHISE_MARKUP if is_franchise else 1.0

        # Create billing record
        billing = frappe.new_doc("BEI Billing Schedule")
        billing.update({
            "billing_type": "Delivery",
            "store": dept,
            "store_type": store_type or "",
            "trip_reference": trip.name,
            "trip_stop_idx": stop.idx,
            "cargo_type": trip.cargo_type,
            "delivery_fee": flt(rate.delivery_fee * markup, 2),
            "logistics_fee": flt(rate.logistics_fee * markup, 2),
            "goods_value": goods_value,
            "handling_fee": flt(goods_value * 0.08, 2) if is_franchise else 0,
            "status": "Pending",
        })
        billing.insert(ignore_permissions=True)

        # Update stop with billing reference
        stop.billing_reference = billing.name
        stop.delivery_value = goods_value
        stop.billing_creation_status = "Success"
        trip.save(ignore_permissions=True)

        # C-06 fix: No explicit commit inside enqueued job -- Frappe
        # auto-commits when the enqueued function returns successfully.
        frappe.db.release_savepoint(sp)

    except Exception as e:
        frappe.db.rollback_to_savepoint(sp)
        frappe.log_error(
            f"Failed to create billing for {trip_name} stop {stop_idx}: {str(e)}",
            "Billing Creation Error"
        )
        try:
            trip.reload()
            trip.stops[int(stop_idx) - 1].billing_creation_status = "Failed"
            trip.save(ignore_permissions=True)
        except Exception:
            pass


def _fail_stop(trip, stop, savepoint, error_message, title="Missing Delivery Rate"):
    """Mark a stop as failed and log the error. Used during billing creation."""
    frappe.log_error(error_message, title)
    stop.billing_creation_status = "Failed"
    trip.save(ignore_permissions=True)
    frappe.db.release_savepoint(savepoint)


def _get_order_goods_value(store_order):
    """Calculate the total goods value from a store order's line items."""
    if not store_order:
        return 0
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(qty * unit_price), 0)
        FROM `tabBEI Store Order Item`
        WHERE parent = %s
    """, store_order)
    return result[0][0] if result else 0


# ============================================================================
# PHASE 1A: DELIVERY TRIP TRACKING ENHANCEMENTS
# ============================================================================


def _get_user_warehouse():
    """
    Get the warehouse/store for the current user.
    Returns warehouse name or None if user has no assigned store.
    """
    user = frappe.session.user

    # Get warehouse from Employee.branch
    employee = frappe.db.get_value(
        "Employee",
        {"user_id": user, "status": "Active"},
        ["branch"],
        as_dict=True
    )

    if not employee or not employee.branch:
        return None

    # Resolve branch to full warehouse name
    branch = employee.branch

    # Check if the exact warehouse exists
    if frappe.db.exists("Warehouse", branch):
        return branch

    # Try appending company abbreviation
    warehouse_with_company = f"{branch} - BEI"
    if frappe.db.exists("Warehouse", warehouse_with_company):
        return warehouse_with_company

    # Try to find warehouse by warehouse_name
    warehouse = frappe.db.get_value("Warehouse", {"warehouse_name": branch}, "name")
    return warehouse


def _calculate_eta(trip, my_stop_order):
    """
    Calculate ETA for a delivery stop.

    Returns:
        dict: {
            "eta_minutes": int or None,
            "eta_window": {"min": "HH:MM", "max": "HH:MM"} or None
        }
    """
    from frappe.utils import get_datetime, add_to_date, format_time

    if not trip.departure_time:
        return {"eta_minutes": None, "eta_window": None}

    # Find last delivered stop
    last_delivered = 0
    for stop in trip.stops:
        if stop.status == "Delivered" and stop.stop_order > last_delivered:
            last_delivered = stop.stop_order

    # Calculate stops remaining
    stops_remaining = my_stop_order - last_delivered
    if stops_remaining < 0:
        stops_remaining = 0

    # ETA = 20 minutes per stop
    eta_minutes = stops_remaining * 20

    # Calculate arrival window (±15 minutes from scheduled time)
    departure_dt = get_datetime(trip.departure_time)
    scheduled_arrival = add_to_date(departure_dt, minutes=(my_stop_order - 1) * 20)
    window_start = add_to_date(scheduled_arrival, minutes=-15)
    window_end = add_to_date(scheduled_arrival, minutes=15)

    return {
        "eta_minutes": eta_minutes,
        "eta_window": {
            "min": format_time(window_start),
            "max": format_time(window_end)
        }
    }


def _get_items_preview(store_order):
    """
    Get preview of items from a store order.
    Returns list of up to 10 items, with overflow indicator.
    """
    if not store_order:
        return []

    items = frappe.get_all(
        "BEI Store Order Item",
        filters={"parent": store_order},
        fields=["item_code", "item_name", "qty_requested as qty", "uom"],
        order_by="idx",
        limit=11  # Get 11 to check if there's overflow
    )

    if len(items) > 10:
        overflow_count = len(frappe.get_all(
            "BEI Store Order Item",
            filters={"parent": store_order}
        )) - 10
        items = items[:10]
        items.append({
            "item_code": "MORE",
            "item_name": f"... and {overflow_count} more items",
            "qty": 0,
            "uom": ""
        })

    return items


def _send_delivery_notification(driver, store, eta_range):
    """
    Send Google Chat notification for "1 stop away" alert.
    MUST NOT block delivery confirmation if it fails.
    """
    logger = frappe.logger("dispatch")
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        space = (
            frappe.db.get_single_value("BEI Settings", "delivery_notification_space")
            or "spaces/AAQABiNmpBg"
        )

        message = (
            f"🚚 *Delivery Update*\n\n"
            f"Driver *{driver}* is 1 stop away from *{store}*.\n"
            f"ETA: {eta_range}\n\n"
            f"Please prepare receiving area."
        )

        creds = service_account.Credentials.from_service_account_file(
            "credentials/task-manager-service.json",
            scopes=["https://www.googleapis.com/auth/chat.bot"],
        )
        chat = build("chat", "v1", credentials=creds)
        chat.spaces().messages().create(
            parent=space,
            body={"text": message},
        ).execute()

        logger.info(f"Delivery notification sent for {store} (driver: {driver})")

    except Exception as e:
        # CRITICAL: Never throw - this must not block delivery confirmation
        logger.error(f"Failed to send delivery notification to {store}: {str(e)}")


@frappe.whitelist()
def get_my_delivery(date=None):
    """
    Get delivery trip for the current user's store.

    Args:
        date: Trip date (defaults to today)

    Returns:
        {
            "ok": true,
            "trip": {
                "name": "TRIP-001",
                "driver": "Juan Dela Cruz",
                "vehicle_plate": "ABC 123",
                "departure_time": "2026-02-16 08:00:00",
                "status": "In Transit",
                "my_stop": {
                    "stop_order": 3,
                    "eta_minutes": 40,
                    "eta_window": {"min": "09:25", "max": "09:55"},
                    "items_preview": [...],
                    "status": "Pending"
                }
            },
            "cs_phone": "0917-123-4567"
        }

        OR {"ok": false, "message": "No delivery scheduled"} if no trip found
    """
    from frappe.utils import today

    # RBAC: Only store staff, supervisors, area supervisors, and warehouse users
    allowed_roles = {"Store Staff", "Store Supervisor", "Area Supervisor", "Warehouse User", "System Manager"}
    user_roles = set(frappe.get_roles(frappe.session.user))
    if not user_roles.intersection(allowed_roles):
        frappe.throw("You do not have permission to view delivery information", frappe.PermissionError)

    trip_date = date or today()
    user_warehouse = _get_user_warehouse()

    if not user_warehouse:
        return {"ok": False, "message": "No store assigned to your account"}

    # Find trip with a stop at user's warehouse
    trips = frappe.get_all(
        "BEI Distribution Trip",
        filters={"trip_date": trip_date, "status": ["in", ["Preparing", "In Transit", "Partial"]]},
        fields=["name"]
    )

    for trip_name in trips:
        trip = frappe.get_doc("BEI Distribution Trip", trip_name.name)

        # Find my stop
        my_stop = None
        for stop in trip.stops:
            if stop.store == user_warehouse:
                my_stop = stop
                break

        if my_stop:
            # Calculate ETA
            eta_data = _calculate_eta(trip, my_stop.stop_order)

            # Get items preview
            items_preview = _get_items_preview(my_stop.store_order)

            # Get customer service phone
            cs_phone = frappe.db.get_single_value("BEI Settings", "customer_service_phone") or ""

            return {
                "ok": True,
                "trip": {
                    "name": trip.name,
                    "driver": trip.driver or "TBA",
                    "vehicle_plate": trip.vehicle_plate or "TBA",
                    "departure_time": str(trip.departure_time) if trip.departure_time else None,
                    "status": trip.status,
                    "my_stop": {
                        "stop_order": my_stop.stop_order,
                        "eta_minutes": eta_data["eta_minutes"],
                        "eta_window": eta_data["eta_window"],
                        "items_preview": items_preview,
                        "status": my_stop.status
                    }
                },
                "cs_phone": cs_phone
            }

    return {"ok": False, "message": "No delivery scheduled"}


# ============================================================================
# PHASE 1C: ROUTE MANAGEMENT & TRIP CREATION
# ============================================================================

@frappe.whitelist()
def get_routes(cargo_type=None, active_only=True):
    """Get all route masters, optionally filtered."""
    _check_scm_permission(SCM_DISPATCH_ROLES, "view routes")

    filters = {}
    if cargo_type:
        filters["cargo_type"] = cargo_type
    if active_only:
        filters["active"] = 1

    routes = frappe.get_all(
        "BEI Route",
        filters=filters,
        fields=["name", "route_name", "cargo_type", "source_warehouse", "default_vehicle", "default_driver", "estimated_duration_hrs", "active"],
        order_by="route_name"
    )

    for route in routes:
        stops = frappe.get_all(
            "BEI Route Stop",
            filters={"parent": route.name},
            fields=["store", "stop_order", "estimated_minutes"],
            order_by="stop_order"
        )
        route["stops"] = stops
        route["stop_count"] = len(stops)

    return {"routes": routes}


@frappe.whitelist()
def get_route_detail(route_name):
    """Get full route details including all stops."""
    _check_scm_permission(SCM_DISPATCH_ROLES, "view route details")

    route = frappe.get_doc("BEI Route", route_name)
    return {
        "route": {
            "name": route.name,
            "route_name": route.route_name,
            "cargo_type": route.cargo_type,
            "source_warehouse": route.source_warehouse,
            "default_vehicle": route.default_vehicle,
            "default_driver": route.default_driver,
            "estimated_duration_hrs": route.estimated_duration_hrs,
            "active": route.active,
            "notes": route.notes,
            "stops": [
                {
                    "idx": s.idx,
                    "store": s.store,
                    "stop_order": s.stop_order,
                    "estimated_minutes": s.estimated_minutes,
                    "special_instructions": s.special_instructions,
                    "mall_permit_required": s.mall_permit_required
                }
                for s in route.stops
            ]
        }
    }


@frappe.whitelist()
def create_route(route_name, cargo_type, source_warehouse, stops=None, default_vehicle=None, default_driver=None, notes=None):
    """Create a new route master."""
    _check_scm_permission(SCM_ADMIN_ROLES, "create routes")

    if isinstance(stops, str):
        stops = frappe.parse_json(stops)

    route = frappe.new_doc("BEI Route")
    route.route_name = route_name
    route.cargo_type = cargo_type
    route.source_warehouse = source_warehouse
    route.default_vehicle = default_vehicle
    route.default_driver = default_driver
    route.notes = notes
    route.active = 1

    if stops:
        for idx, stop_data in enumerate(stops, 1):
            route.append("stops", {
                "store": stop_data.get("store"),
                "stop_order": idx,
                "estimated_minutes": stop_data.get("estimated_minutes", 20),
                "special_instructions": stop_data.get("special_instructions", ""),
                "mall_permit_required": stop_data.get("mall_permit_required", 0)
            })

    route.insert()
    return {"success": True, "route": route.name}


@frappe.whitelist()
def update_route(route_name, updates=None):
    """Update a route master. Accepts partial updates."""
    _check_scm_permission(SCM_ADMIN_ROLES, "update routes")

    if isinstance(updates, str):
        updates = frappe.parse_json(updates)

    route = frappe.get_doc("BEI Route", route_name)

    simple_fields = ["route_name", "cargo_type", "source_warehouse", "default_vehicle", "default_driver", "estimated_duration_hrs", "notes", "active"]
    for field in simple_fields:
        if field in updates:
            setattr(route, field, updates[field])

    if "stops" in updates:
        route.stops = []
        for idx, stop_data in enumerate(updates["stops"], 1):
            route.append("stops", {
                "store": stop_data.get("store"),
                "stop_order": idx,
                "estimated_minutes": stop_data.get("estimated_minutes", 20),
                "special_instructions": stop_data.get("special_instructions", ""),
                "mall_permit_required": stop_data.get("mall_permit_required", 0)
            })

    route.save()
    return {"success": True, "route": route.name}


@frappe.whitelist()
def delete_route(route_name):
    """Soft-delete a route (set active=0)."""
    _check_scm_permission(SCM_ADMIN_ROLES, "delete routes")

    route = frappe.get_doc("BEI Route", route_name)
    route.active = 0
    route.save()
    return {"success": True, "message": f"Route {route_name} deactivated"}


@frappe.whitelist()
def get_vehicles(status=None, owner_type=None):
    """List vehicles with optional filters."""
    _check_scm_permission(SCM_DISPATCH_ROLES, "view vehicles")

    filters = {}
    if status:
        filters["status"] = status
    if owner_type:
        filters["owner_type"] = owner_type

    vehicles = frappe.get_all(
        "BEI Vehicle",
        filters=filters,
        fields=["name", "vehicle_plate", "vehicle_type", "capacity_kg", "capacity_cbm", "owner_type", "threepl_partner", "status"],
        order_by="vehicle_plate"
    )
    return {"vehicles": vehicles}


@frappe.whitelist()
def create_trip_from_route(route_name, trip_date=None, vehicle=None, driver=None, selected_stops=None):
    """One-click trip creation from a route template.

    1. Loads route + stops
    2. Creates BEI Distribution Trip
    3. Copies stops, links approved store orders
    4. Returns trip name
    """
    _check_scm_permission(SCM_DISPATCH_ROLES, "create trips from routes")

    route = frappe.get_doc("BEI Route", route_name)

    if not route.active:
        frappe.throw(_("Route is not active"))

    trip_date = trip_date or nowdate()

    # Resolve vehicle details
    vehicle_plate = None
    if vehicle:
        vehicle_plate = frappe.db.get_value("BEI Vehicle", vehicle, "vehicle_plate")
    elif route.default_vehicle:
        vehicle = route.default_vehicle
        vehicle_plate = frappe.db.get_value("BEI Vehicle", route.default_vehicle, "vehicle_plate")

    if selected_stops:
        if isinstance(selected_stops, str):
            selected_stops = frappe.parse_json(selected_stops)

        # Validate all selected stores exist in route's zone pool
        zone_stores = {s.store for s in route.stops}
        for sel in selected_stops:
            if sel.get("store") not in zone_stores:
                frappe.throw(_(f"Store {sel.get('store')} is not in zone {route.route_name}"))

        # Build stops from selection
        stops = []
        for idx, sel in enumerate(selected_stops, 1):
            store = sel.get("store")
            store_order = frappe.db.get_value(
                "BEI Store Order",
                {"store": store, "delivery_date": trip_date, "status": "Approved"},
                "name"
            )
            items_count = 0
            if store_order:
                items_count = frappe.db.count("BEI Store Order Item", {"parent": store_order})
            stops.append({
                "store": store,
                "items_count": items_count,
                "store_order": store_order or ""
            })
    else:
        # Original behavior: use all route stops
        stops = []
        for route_stop in route.stops:
            store_order = frappe.db.get_value(
                "BEI Store Order",
                {"store": route_stop.store, "delivery_date": trip_date, "status": "Approved"},
                "name"
            )
            items_count = 0
            if store_order:
                items_count = frappe.db.count("BEI Store Order Item", {"parent": store_order})
            stops.append({
                "store": route_stop.store,
                "items_count": items_count,
                "store_order": store_order or ""
            })

    # Use existing trip creation logic
    trip = _build_trip_doc(trip_date, route.route_name, stops)
    trip.driver = driver or route.default_driver
    trip.vehicle = vehicle
    trip.vehicle_plate = vehicle_plate
    trip.cargo_type = route.cargo_type

    # Link store orders to stops
    for idx, stop_data in enumerate(stops):
        if stop_data.get("store_order"):
            trip.stops[idx].store_order = stop_data["store_order"]

    trip.insert()

    return {
        "success": True,
        "trip": trip.name,
        "message": f"Trip {trip.name} created from route {route.route_name} with {len(stops)} stops"
    }


@frappe.whitelist()
def duplicate_route(route_name, new_name):
    """Clone a route with a new name."""
    _check_scm_permission(SCM_ADMIN_ROLES, "duplicate routes")

    source = frappe.get_doc("BEI Route", route_name)

    new_route = frappe.new_doc("BEI Route")
    new_route.route_name = new_name
    new_route.cargo_type = source.cargo_type
    new_route.source_warehouse = source.source_warehouse
    new_route.default_vehicle = source.default_vehicle
    new_route.default_driver = source.default_driver
    new_route.estimated_duration_hrs = source.estimated_duration_hrs
    new_route.notes = source.notes
    new_route.active = 1

    for stop in source.stops:
        new_route.append("stops", {
            "store": stop.store,
            "stop_order": stop.stop_order,
            "estimated_minutes": stop.estimated_minutes,
            "special_instructions": stop.special_instructions,
            "mall_permit_required": stop.mall_permit_required
        })

    new_route.insert()
    return {"success": True, "route": new_route.name}


@frappe.whitelist()
def reorder_stops(route_name, stop_order_map):
    """Reorder stops in a route. stop_order_map: {store: new_order}"""
    _check_scm_permission(SCM_ADMIN_ROLES, "reorder stops")

    if isinstance(stop_order_map, str):
        stop_order_map = frappe.parse_json(stop_order_map)

    route = frappe.get_doc("BEI Route", route_name)

    for stop in route.stops:
        if stop.store in stop_order_map:
            stop.stop_order = int(stop_order_map[stop.store])

    # Re-sort stops by new order
    route.stops.sort(key=lambda s: s.stop_order)
    for idx, stop in enumerate(route.stops, 1):
        stop.idx = idx
        stop.stop_order = idx

    route.save()
    return {"success": True, "route": route.name}


@frappe.whitelist()
def get_driver_list():
    """Get list of available drivers (employees with driver designation)."""
    _check_scm_permission(SCM_DISPATCH_ROLES, "view driver list")

    drivers = frappe.get_all(
        "Employee",
        filters={"status": "Active", "designation": ["in", ["Driver", "Delivery Driver", "Truck Driver"]]},
        fields=["name", "employee_name", "cell_phone"],
        order_by="employee_name"
    )
    return {"drivers": drivers}
