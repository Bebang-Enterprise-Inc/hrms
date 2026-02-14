# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Dispatch Tracker API
Handles warehouse dispatch, route tracking, and delivery confirmation for my.bebang.ph
"""

import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, flt


@frappe.whitelist()
def get_trips(date=None, status=None):
    """Get dispatch trips for a date. Defaults to today if no date specified."""
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
