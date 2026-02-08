# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Dispatch Tracker API
Handles warehouse dispatch, route tracking, and delivery confirmation for my.bebang.ph
"""

import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime
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
