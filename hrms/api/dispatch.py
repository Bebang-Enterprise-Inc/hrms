# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Dispatch Tracker API
Handles warehouse dispatch, route tracking, and delivery confirmation for my.bebang.ph
"""

import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, flt
import json


@frappe.whitelist()
def get_trips(date=None, status=None):
    """
    Get dispatch trips for a date.
    Defaults to today if no date specified.
    """
    filters = {}
    if date:
        filters["trip_date"] = date
    else:
        filters["trip_date"] = nowdate()

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


@frappe.whitelist()
def confirm_delivery(trip_name, stop_idx, signature=None, signed_by=None):
    """
    Confirm delivery at a specific stop.
    stop_idx is the row index (1-based) in the stops table.
    """
    trip = frappe.get_doc("BEI Distribution Trip", trip_name)

    if trip.status not in ["In Transit", "Partial"]:
        frappe.throw(_("Trip is not in transit"))

    stop_idx = int(stop_idx)
    if stop_idx < 1 or stop_idx > len(trip.stops):
        frappe.throw(_("Invalid stop index"))

    stop = trip.stops[stop_idx - 1]
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

    # Update trip status
    delivered = sum(1 for s in trip.stops if s.status == "Delivered")
    if delivered == len(trip.stops):
        trip.status = "Completed"
    else:
        trip.status = "Partial"

    trip.save()

    return {
        "success": True,
        "message": f"Delivery to {stop.store} confirmed",
        "trip_status": trip.status,
        "delivered": delivered,
        "total": len(trip.stops)
    }


@frappe.whitelist()
def report_exception(trip_name, stop_idx, exception_type, reason=None, photo=None):
    """
    Report an exception at a stop (store closed, refused, etc).
    exception_type: 'Store Closed' or 'Refused'
    """
    trip = frappe.get_doc("BEI Distribution Trip", trip_name)

    stop_idx = int(stop_idx)
    if stop_idx < 1 or stop_idx > len(trip.stops):
        frappe.throw(_("Invalid stop index"))

    stop = trip.stops[stop_idx - 1]
    stop.status = exception_type
    stop.arrival_time = now_datetime()
    stop.exception_reason = reason
    if photo:
        stop.exception_photo = photo

    # Update trip status
    non_pending = sum(1 for s in trip.stops if s.status != "Pending")
    if non_pending == len(trip.stops):
        # All stops processed (delivered or exception)
        delivered = sum(1 for s in trip.stops if s.status == "Delivered")
        trip.status = "Completed" if delivered == len(trip.stops) else "Partial"

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


@frappe.whitelist()
def create_trip(trip_date, route_name, stops):
    """
    Create a new distribution trip.
    stops: list of {store, items_count}
    """
    if isinstance(stops, str):
        stops = json.loads(stops)

    if not stops:
        frappe.throw(_("At least one stop is required"))

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
        # Rebuild doc from scratch (child rows need fresh parent reference)
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
        trip.insert()

    return {
        "success": True,
        "trip": trip.name,
        "message": f"Trip {trip.name} created with {len(stops)} stops"
    }


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

        # 1. Resolve store department via mapping table
        dept = frappe.db.get_value("BEI Warehouse Department Mapping",
            {"warehouse": stop.store, "is_active": 1}, "department")
        if not dept:
            frappe.log_error(
                f"No warehouse→department mapping for {stop.store}",
                "Billing: Missing Mapping"
            )
            stop.billing_creation_status = "Failed"
            trip.save(ignore_permissions=True)
            frappe.db.release_savepoint(sp)
            return

        # 2. Get store type for markup calculation
        store_type = frappe.db.get_value("BEI Store Type", {"store": dept}, "store_type")

        # 3. Get active delivery rate for store + cargo type
        rate = frappe.db.get_value("BEI Delivery Rate",
            {"store": dept, "cargo_type": trip.cargo_type, "status": "Active"},
            ["delivery_fee", "logistics_fee"], as_dict=True)
        if not rate:
            frappe.log_error(
                f"No active {trip.cargo_type} rate for {dept}",
                "Billing: Missing Rate"
            )
            stop.billing_creation_status = "Failed"
            trip.save(ignore_permissions=True)
            frappe.db.release_savepoint(sp)
            _notify_missing_rate(dept, trip.cargo_type)
            return

        # 4. Calculate goods value from store order
        goods_value = 0
        if stop.store_order:
            result = frappe.db.sql("""
                SELECT COALESCE(SUM(qty * unit_price), 0)
                FROM `tabBEI Store Order Item`
                WHERE parent = %s
            """, stop.store_order)
            goods_value = result[0][0] if result else 0

        # 5. Apply 8% markup for franchise stores
        is_franchise = store_type in ("Full Franchise", "Managed Franchise")
        markup = 1.08 if is_franchise else 1.0

        delivery_fee = flt(rate.delivery_fee * markup, 2)
        logistics_fee = flt(rate.logistics_fee * markup, 2)
        handling_fee = flt(goods_value * 0.08, 2) if is_franchise else 0

        # 6. Create billing record
        billing = frappe.new_doc("BEI Billing Schedule")
        billing.billing_type = "Delivery"
        billing.store = dept
        billing.store_type = store_type or ""
        billing.trip_reference = trip.name
        billing.trip_stop_idx = stop.idx
        billing.cargo_type = trip.cargo_type
        billing.delivery_fee = delivery_fee
        billing.logistics_fee = logistics_fee
        billing.goods_value = goods_value
        billing.handling_fee = handling_fee
        billing.status = "Pending"
        billing.insert(ignore_permissions=True)

        # 7. Update stop with billing reference
        stop.billing_reference = billing.name
        stop.delivery_value = goods_value
        stop.billing_creation_status = "Success"
        trip.save(ignore_permissions=True)

        # C-06 fix: No explicit commit inside enqueued job — Frappe
        # auto-commits when the enqueued function returns successfully.
        frappe.db.release_savepoint(sp)

    except Exception as e:
        frappe.db.rollback_to_savepoint(sp)
        frappe.log_error(
            f"Failed to create billing for {trip_name} stop {stop_idx}: {str(e)}",
            "Billing Creation Error"
        )
        # Mark stop as failed
        try:
            trip.reload()
            stop = trip.stops[int(stop_idx) - 1]
            stop.billing_creation_status = "Failed"
            trip.save(ignore_permissions=True)
        except Exception:
            pass


def _notify_missing_rate(store, cargo_type):
    """Notify Finance and Supply Chain about missing delivery rate."""
    try:
        frappe.log_error(
            f"Billing blocked: No active {cargo_type} rate for store {store}. "
            "Please set rates via the Rate Management Panel.",
            "Missing Delivery Rate"
        )
    except Exception:
        pass
