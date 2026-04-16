# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Dispatch Tracker API
Handles warehouse dispatch, route tracking, and delivery confirmation for my.bebang.ph
"""

import base64
import hashlib
from typing import Any

import frappe
from frappe import _
from frappe.exceptions import TimestampMismatchError
from frappe.utils import cint, flt, now_datetime, nowdate

from hrms.utils.delivery_billing_policy import (
	DeliveryBillingPolicyError,
	get_pre_delivery_exception_trace,
	should_auto_create_billing_on_delivery,
)

# P0-10: Import centralized RBAC role sets
from hrms.utils.scm_roles import SCM_ADMIN_ROLES, SCM_DISPATCH_ROLES, SCM_STORE_ROLES
from hrms.utils.scm_roles import check_scm_permission as _check_scm_permission
from hrms.utils.sentry import set_backend_observability_context
from hrms.utils.supply_chain_contracts import (
	buyer_entity_requires_billing_hold,
	resolve_markup_percent,
	resolve_store_buyer_entity,
	stamp_billing_schedule_contract,
)


def _has_column(doctype: str, fieldname: str) -> bool:
	"""Return True only when the runtime table really has the column."""
	try:
		return bool(frappe.db.has_column(doctype, fieldname))
	except Exception:
		return False


def _safe_single_value(doctype: str, fieldname: str):
	"""Read singleton field only when the runtime column exists."""
	if not _has_column(doctype, fieldname):
		return None
	try:
		return frappe.db.get_single_value(doctype, fieldname)
	except Exception:
		return None


def _set_if_column(doc: Any, fieldname: str, value: Any):
	"""Set document field only when the backing DB column exists."""
	doctype = getattr(doc, "doctype", None)
	if doctype and _has_column(doctype, fieldname):
		setattr(doc, fieldname, value)


def _get_record_value(record: Any, fieldname: str) -> Any:
	"""Read a field from dict-like or object records."""
	if not fieldname:
		return None
	if isinstance(record, dict):
		return record.get(fieldname)
	return getattr(record, fieldname, None)


def _find_employee_identity(employee_ref: str | None):
	"""Resolve either an Employee ID or employee_name into a canonical Employee record."""
	employee_ref = (employee_ref or "").strip()
	if not employee_ref:
		return None

	employee = frappe.db.get_value("Employee", employee_ref, ["name", "employee_name"], as_dict=True)
	if employee:
		return employee

	return frappe.db.get_value(
		"Employee",
		{"employee_name": employee_ref},
		["name", "employee_name"],
		as_dict=True,
	)


def _infer_vehicle_type(vehicle_label: str | None) -> str:
	"""Choose a safe default BEI Vehicle type from free-text input."""
	text = (vehicle_label or "").strip().lower()
	if "reefer" in text and "van" in text:
		return "Reefer Van"
	if "reefer" in text or "cold" in text:
		return "Reefer Truck"
	if "motor" in text or "bike" in text:
		return "Motorcycle"
	if "l300" in text:
		return "L300"
	if "van" in text:
		return "Van"
	return "Truck"


def _resolve_or_create_departure_vehicle(
	vehicle_label: str | None,
	vehicle_plate: str | None,
) -> tuple[str, str]:
	"""
	Resolve a BEI Vehicle link for trip departure.

	If the submitted vehicle is free text and no master exists yet, create a 3PL vehicle
	record keyed by the plate so dispatch can proceed without pre-seeded master data.
	"""
	vehicle_label = (vehicle_label or "").strip()
	vehicle_plate = (vehicle_plate or "").strip()

	if not vehicle_label and not vehicle_plate:
		return "", ""

	if vehicle_label:
		existing_name = frappe.db.get_value("BEI Vehicle", vehicle_label, "name")
		if existing_name:
			existing_plate = (
				frappe.db.get_value("BEI Vehicle", existing_name, "vehicle_plate") or vehicle_plate
			)
			return str(existing_name), str(existing_plate or "")

	if vehicle_plate:
		existing_by_plate = frappe.db.get_value(
			"BEI Vehicle",
			{"vehicle_plate": vehicle_plate},
			["name", "vehicle_plate"],
			as_dict=True,
		)
		if existing_by_plate:
			return (
				str(_get_record_value(existing_by_plate, "name") or ""),
				str(_get_record_value(existing_by_plate, "vehicle_plate") or vehicle_plate),
			)

	if not vehicle_plate:
		return "", vehicle_label

	try:
		vehicle_doc = frappe.new_doc("BEI Vehicle")
		vehicle_doc.naming_series = "BEI-VEH-.####"
		vehicle_doc.vehicle_plate = vehicle_plate
		vehicle_doc.vehicle_type = _infer_vehicle_type(vehicle_label)
		vehicle_doc.owner_type = "3PL"
		vehicle_doc.status = "Available"
		if hasattr(vehicle_doc, "notes"):
			vehicle_doc.notes = vehicle_label or vehicle_plate
		vehicle_doc.insert(ignore_permissions=True)
		return str(vehicle_doc.name or ""), vehicle_plate
	except Exception:
		frappe.log_error(
			title="Dispatch Vehicle Auto-Create Failed",
			message=f"vehicle_label={vehicle_label!r}, vehicle_plate={vehicle_plate!r}",
		)
		return "", vehicle_plate


def _get_employee_phone_field() -> str | None:
	"""Return the live employee mobile-number column across schema revisions."""
	for fieldname in ("cell_number", "cell_phone"):
		if _has_column("Employee", fieldname):
			return fieldname
	return None


def _get_employee_phone(record: Any) -> str:
	"""Expose the portal contract as cell_phone regardless of backend field name."""
	phone_field = _get_employee_phone_field()
	if not phone_field:
		return ""
	return str(_get_record_value(record, phone_field) or "")


@frappe.whitelist()
def get_trips(date: str | None = None, status: str | None = None):
	"""Get dispatch trips for a date. Defaults to today if no date specified."""
	_check_scm_permission(SCM_DISPATCH_ROLES, "view dispatch trips")

	filters = {"trip_date": date or nowdate()}

	if status:
		filters["status"] = status

	fields = [
		"name",
		"trip_date",
		"route_name",
		"driver",
		"vehicle",
		"vehicle_plate",
		"status",
		"departure_time",
	]
	if _has_column("BEI Distribution Trip", "driver_name"):
		fields.append("driver_name")
	if _has_column("BEI Distribution Trip", "threepl_driver_name"):
		fields.append("threepl_driver_name")

	trips = frappe.get_all(
		"BEI Distribution Trip",
		filters=filters,
		fields=fields,
		order_by="creation",
	)

	# Get stop counts and delivery progress
	for trip in trips:
		stops = frappe.get_all("BEI Trip Stop", filters={"parent": trip.name}, fields=["status"])
		trip["total_stops"] = len(stops)
		trip["delivered_stops"] = sum(1 for s in stops if s.status == "Delivered")
		trip["driver_display"] = (
			trip.get("driver_name") or trip.get("threepl_driver_name") or trip.get("driver") or ""
		)

	return {"trips": trips}


@frappe.whitelist()
def get_trip_detail(trip_name: str):
	"""Get full trip details including all stops."""
	_check_scm_permission(SCM_DISPATCH_ROLES, "view trip details")

	trip = frappe.get_doc("BEI Distribution Trip", trip_name)
	driver_name = getattr(trip, "driver_name", "") or getattr(trip, "threepl_driver_name", "") or ""

	return {
		"trip": {
			"name": trip.name,
			"trip_date": trip.trip_date,
			"route_name": trip.route_name,
			"driver": trip.driver,
			"driver_name": driver_name,
			"threepl_driver_name": getattr(trip, "threepl_driver_name", ""),
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
					"exception_reason": s.exception_reason,
				}
				for s in trip.stops
			],
		}
	}


@frappe.whitelist()
def confirm_departure(
	trip_name: str,
	driver: str | None = None,
	threepl_driver_name: str | None = None,
	vehicle: str | None = None,
	vehicle_plate: str | None = None,
	temperature: float | str | None = None,
	seal_number: str | None = None,
):
	"""
	Confirm trip departure with checklist.
	Updates trip with departure details and sets status to In Transit.
	"""
	_check_scm_permission(SCM_DISPATCH_ROLES, "confirm departure")

	trip = frappe.get_doc("BEI Distribution Trip", trip_name)

	if trip.status != "Preparing":
		frappe.throw(_("Trip is not in Preparing status"))

	if driver:
		employee = _find_employee_identity(driver)
		if employee:
			trip.driver = _get_record_value(employee, "name")
			trip.driver_name = _get_record_value(employee, "employee_name") or trip.driver_name
			_set_if_column(trip, "threepl_driver_name", "")
		else:
			trip.driver = ""
			trip.driver_name = driver.strip()
			_set_if_column(trip, "threepl_driver_name", driver.strip())

	resolved_vehicle, resolved_vehicle_plate = _resolve_or_create_departure_vehicle(vehicle, vehicle_plate)
	if resolved_vehicle:
		trip.vehicle = resolved_vehicle
	elif vehicle:
		trip.vehicle = ""
	if resolved_vehicle_plate:
		trip.vehicle_plate = resolved_vehicle_plate
	if temperature:
		trip.departure_temp = float(temperature)
	if seal_number:
		trip.seal_number = seal_number

	is_threepl_vehicle = False
	if trip.vehicle:
		is_threepl_vehicle = frappe.db.get_value("BEI Vehicle", trip.vehicle, "owner_type") == "3PL"

	external_driver = (threepl_driver_name or getattr(trip, "threepl_driver_name", "") or "").strip()
	if is_threepl_vehicle and external_driver:
		trip.driver = ""
		trip.driver_name = external_driver
		_set_if_column(trip, "threepl_driver_name", external_driver)
	elif not is_threepl_vehicle:
		_set_if_column(trip, "threepl_driver_name", "")

	trip.departure_time = now_datetime()
	trip.status = "In Transit"
	_enable_role_gated_write(trip)
	trip.save(ignore_permissions=True)
	_set_store_orders_in_transit(
		[{"store_order": getattr(stop, "store_order", "")} for stop in getattr(trip, "stops", [])]
	)

	return {"success": True, "message": f"Trip {trip_name} departed at {trip.departure_time}"}


def _get_stop(trip: Any, stop_idx: int | str):
	"""Validate and return a trip stop by 1-based index."""
	stop_idx = int(stop_idx)
	if stop_idx < 1 or stop_idx > len(trip.stops):
		frappe.throw(_("Invalid stop index"))
	return trip.stops[stop_idx - 1]


def _update_trip_status(trip: Any, require_all_processed: bool = False):
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
def confirm_delivery(
	trip_name: str, stop_idx: int | str, signature: str | None = None, signed_by: str | None = None
):
	"""Confirm delivery at a specific stop. stop_idx is 1-based."""
	_check_scm_permission(SCM_DISPATCH_ROLES, "confirm delivery")

	# Auto-generate delivery billing (async, feature-flagged).
	# GAP-092 policy: missing setting defaults to enabled.
	auto_create_setting = frappe.db.get_single_value("BEI Settings", "billing_auto_create_on_delivery")
	auto_create_delivery_billing = should_auto_create_billing_on_delivery(auto_create_setting)

	trip = None
	stop = None
	delivered = 0
	total = 0
	stop_was_updated = False

	for attempt in range(3):
		trip = frappe.get_doc("BEI Distribution Trip", trip_name)
		stop = _get_stop(trip, stop_idx)
		stop_was_updated = False

		if stop.status == "Delivered":
			delivered, total = _update_trip_status(trip)
			break

		if trip.status not in ["In Transit", "Partial"]:
			frappe.throw(_("Trip is not in transit"))

		stop.status = "Delivered"
		stop.arrival_time = now_datetime()
		stop.signature = signature
		stop.signed_by = signed_by
		if auto_create_delivery_billing:
			stop.billing_creation_status = "Pending"

		delivered, total = _update_trip_status(trip)
		_enable_role_gated_write(trip)

		try:
			trip.save(ignore_permissions=True)
			stop_was_updated = True
			break
		except TimestampMismatchError:
			frappe.db.rollback()
			if attempt == 2:
				raise
	else:
		frappe.throw(_("Unable to confirm delivery right now. Please try again."))

	if auto_create_delivery_billing and stop_was_updated:
		frappe.enqueue(
			"hrms.api.dispatch._create_delivery_billing",
			queue="default",
			trip_name=trip.name,
			stop_idx=stop.idx,
			enqueue_after_commit=True,
		)

	# Update linked BEI Store Order status to "Delivered"
	if stop_was_updated and hasattr(stop, "store_order") and stop.store_order:
		_set_store_order_status(stop.store_order, "Delivered")

	# PHASE 1A: Send "1 stop away" notification to next stop
	# This runs AFTER save so delivery is confirmed even if notification fails
	try:
		current_stop_order = int(stop_idx)
		next_stop = None
		if stop_was_updated:
			for s in trip.stops:
				if s.stop_order == current_stop_order + 1 and s.status == "Pending":
					next_stop = s
					break

			if next_stop and trip.departure_time:
				eta_window = _calculate_eta(trip, next_stop.stop_order).get("eta_window") or {}
				eta_range = f"{eta_window.get('min', '')} - {eta_window.get('max', '')}".strip(" -")

				_send_delivery_notification(trip.driver or "Driver", next_stop.store, eta_range)
	except Exception as e:
		# CRITICAL: Notification failures must not block delivery confirmation
		frappe.log_error(
			title="Next Stop Notification Failed",
			message=f"Failed to notify next stop for {trip_name}: {e!s}",
		)

	return {
		"success": True,
		"message": f"Delivery to {stop.store} confirmed",
		"trip_status": trip.status,
		"delivered": delivered,
		"total": total,
	}


@frappe.whitelist()
def report_exception(
	trip_name: str,
	stop_idx: int | str,
	exception_type: str,
	reason: str | None = None,
	photo: str | None = None,
):
	"""Report an exception at a stop (store closed, refused, etc)."""
	_check_scm_permission(SCM_DISPATCH_ROLES, "report exceptions")

	trip = frappe.get_doc("BEI Distribution Trip", trip_name)

	stop = _get_stop(trip, stop_idx)
	stop.status = exception_type
	stop.arrival_time = now_datetime()
	stop.exception_reason = reason
	if photo:
		stop.exception_photo = _save_base64_attachment(
			photo, "BEI Distribution Trip", docname=trip.name, fieldname="exception_photo"
		)

	_update_trip_status(trip, require_all_processed=True)
	_enable_role_gated_write(trip)
	trip.save(ignore_permissions=True)

	return {"success": True, "message": f"Exception reported for {stop.store}: {exception_type}"}


@frappe.whitelist()
def request_pre_delivery_billing_exception(
	trip_name: str, stop_idx: int | str, reason: str, exception_type: str = "Delivery Pre-Billing"
):
	"""
	Create a dual-approval exception request for pre-delivery billing.

	GAP-092: routed through BEI Match Exception with CPO+CFO tier.
	"""
	_check_scm_permission(SCM_DISPATCH_ROLES, "request pre-delivery billing exception")

	if not trip_name:
		frappe.throw(_("Trip name is required"))
	stop_idx = cint(stop_idx)
	if stop_idx <= 0:
		frappe.throw(_("Stop index must be greater than 0"))
	if not reason:
		frappe.throw(_("Reason is required"))

	from hrms.api.procurement import request_match_exception

	payload = {
		"reference_type": "BEI Distribution Trip",
		"reference_name": trip_name,
		"delivery_trip_reference": trip_name,
		"delivery_stop_idx": stop_idx,
		"reason": reason,
		"exception_type": exception_type,
	}
	# Backward-compatible hint for runtimes that still enforce PO context.
	try:
		trip = frappe.get_doc("BEI Distribution Trip", trip_name)
		stop = _get_stop(trip, stop_idx)
		if getattr(stop, "store_order", None):
			payload["purchase_order"] = stop.store_order
	except Exception:
		pass

	return request_match_exception(payload)


@frappe.whitelist()
def get_pre_delivery_billing_exception_status(trip_name: str, stop_idx: int | str):
	"""Return latest pre-delivery billing exception status for one trip stop."""
	_check_scm_permission(SCM_DISPATCH_ROLES, "view pre-delivery billing exception status")

	if not trip_name:
		frappe.throw(_("Trip name is required"))
	stop_idx = cint(stop_idx)
	if stop_idx <= 0:
		frappe.throw(_("Stop index must be greater than 0"))

	fields = ["name", "status", "approval_tier", "approver", "approver_status", "modified"]
	for optional_field in (
		"cpo_approved_by",
		"cpo_approved_at",
		"cfo_approved_by",
		"cfo_approved_at",
		"approval_audit_log",
	):
		if _has_column("BEI Match Exception", optional_field):
			fields.append(optional_field)

	exceptions = frappe.get_all(
		"BEI Match Exception",
		filters={
			"reference_type": "BEI Distribution Trip",
			"delivery_trip_reference": trip_name,
			"delivery_stop_idx": stop_idx,
		},
		fields=fields,
		order_by="modified desc",
		limit_page_length=5,
	)

	return {
		"trip_name": trip_name,
		"stop_idx": stop_idx,
		"latest": exceptions[0] if exceptions else None,
		"exceptions": exceptions,
	}


@frappe.whitelist()
def create_pre_delivery_billing(trip_name: str, stop_idx: int | str, pre_delivery_exception: str):
	"""
	Create delivery billing before stop delivery only when dual approval exists.

	Enforced by BEI Billing Schedule policy + exception trace validation.
	"""
	_check_scm_permission(SCM_ADMIN_ROLES, "create pre-delivery billing")

	if not pre_delivery_exception:
		frappe.throw(_("Pre-delivery billing requires an approved exception (Daymae/CPO + Butch/CFO)."))

	_create_delivery_billing(
		trip_name=trip_name,
		stop_idx=stop_idx,
		pre_delivery_exception=pre_delivery_exception,
		require_pre_delivery_exception=True,
		force_create=True,
	)

	trip = frappe.get_doc("BEI Distribution Trip", trip_name)
	stop = _get_stop(trip, stop_idx)
	if not stop.billing_reference:
		frappe.throw(
			_(
				"Pre-delivery billing did not create a billing reference. Check trip stop status and exception trace."
			)
		)

	return {
		"success": True,
		"trip_name": trip_name,
		"stop_idx": cint(stop_idx),
		"billing_reference": stop.billing_reference,
		"billing_creation_status": stop.billing_creation_status,
		"pre_delivery_exception": pre_delivery_exception,
	}


@frappe.whitelist()
def get_route_progress(trip_name: str):
	"""Get current progress of a trip."""
	_check_scm_permission(SCM_DISPATCH_ROLES, "view route progress")

	trip = frappe.get_doc("BEI Distribution Trip", trip_name)
	scheduled_stops = _get_trip_scheduled_arrivals(trip)

	stops = []
	for stop in trip.stops:
		eta_data = _calculate_eta(trip, cint(getattr(stop, "stop_order", 0) or 0))
		scheduled_arrival = scheduled_stops.get(cint(getattr(stop, "stop_order", 0) or 0))
		stops.append(
			{
				"idx": stop.idx,
				"store": stop.store,
				"stop_order": stop.stop_order,
				"items_count": stop.items_count,
				"status": stop.status,
				"estimated_minutes": _get_trip_stop_estimated_minutes(trip, stop),
				"eta_minutes": eta_data.get("eta_minutes"),
				"eta_window": eta_data.get("eta_window"),
				"eta_timestamp": str(scheduled_arrival) if scheduled_arrival else None,
				"arrival_time": str(stop.arrival_time) if stop.arrival_time else None,
				"signed_by": stop.signed_by,
				"exception_reason": stop.exception_reason,
			}
		)

	total = len(trip.stops)
	delivered = sum(1 for s in trip.stops if s.status == "Delivered")
	exceptions = sum(1 for s in trip.stops if s.status in ["Store Closed", "Refused"])
	progress_pct = round((delivered / total * 100), 1) if total > 0 else 0

	current_stop = None
	next_stop = None
	current_stop_eta = None
	current_stop_eta_window = None
	next_stop_eta = None
	next_stop_eta_window = None
	for i, stop in enumerate(stops):
		if stop.get("status") not in ("Delivered", "Store Closed", "Refused"):
			current_stop = stop.get("store") or stop.get("warehouse")
			current_stop_eta = stop.get("eta_timestamp")
			current_stop_eta_window = stop.get("eta_window")
			if i + 1 < total:
				next_stop = stops[i + 1].get("store") or stops[i + 1].get("warehouse")
				next_stop_eta = stops[i + 1].get("eta_timestamp")
				next_stop_eta_window = stops[i + 1].get("eta_window")
			break

	return {
		"trip_name": trip.name,
		"status": trip.status,
		"departure_time": str(trip.departure_time) if trip.departure_time else None,
		"total_stops": total,
		"delivered": delivered,
		"exceptions": exceptions,
		"pending": total - delivered - exceptions,
		"progress_pct": progress_pct,
		"current_stop": current_stop,
		"current_stop_eta": current_stop_eta,
		"current_stop_eta_window": current_stop_eta_window,
		"next_stop": next_stop,
		"next_stop_eta": next_stop_eta,
		"next_stop_eta_window": next_stop_eta_window,
		"stops": stops,
	}


def _build_trip_doc(trip_date: str | None, route_name: str, stops: list[dict[str, Any]]):
	"""Build a BEI Distribution Trip document with stops (not yet inserted)."""
	trip = frappe.new_doc("BEI Distribution Trip")
	trip.trip_date = trip_date or nowdate()
	trip.route_name = route_name
	trip.status = "Preparing"

	for idx, stop_data in enumerate(stops, 1):
		trip.append(
			"stops",
			{
				"store": stop_data.get("store"),
				"stop_order": idx,
				"items_count": stop_data.get("items_count", 0),
				"status": "Pending",
			},
		)

	return trip


@frappe.whitelist()
def create_trip(trip_date: str | None, route_name: str, stops: list[dict[str, Any]] | str):
	"""Create a new distribution trip. stops: list of {store, items_count}."""
	_check_scm_permission(SCM_DISPATCH_ROLES, "create trips")

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
			(trip.naming_series.replace(".YYYY.", str(nowdate()[:4])).replace(".#####", ""),),
		)
		frappe.db.commit()
		trip = _build_trip_doc(trip_date, route_name, stops)
		trip.insert()

	return {
		"success": True,
		"trip": trip.name,
		"message": f"Trip {trip.name} created with {len(stops)} stops",
	}


def _create_delivery_billing(
	trip_name: str,
	stop_idx: int | str,
	pre_delivery_exception: str | None = None,
	require_pre_delivery_exception: bool = False,
	force_create: bool = False,
):
	"""Create a BEI Billing Schedule for a delivery stop."""
	# G-067: Feature flag — billing is enabled by default.
	# Set BEI Settings.enable_delivery_billing = 0 to disable.
	# Some runtime tenants may not have this field yet; treat missing as enabled.
	billing_setting = _safe_single_value("BEI Settings", "enable_delivery_billing")

	if not force_create and not should_auto_create_billing_on_delivery(billing_setting):
		return

	trip = frappe.get_doc("BEI Distribution Trip", trip_name)
	stop = trip.stops[int(stop_idx) - 1]
	savepoint_name = "delivery_billing"

	try:
		frappe.db.savepoint(savepoint_name)

		# I-04 fix: Duplicate check before creating billing
		existing = frappe.db.get_value(
			"BEI Billing Schedule",
			{
				"trip_reference": trip.name,
				"trip_stop_idx": stop.idx,
				"billing_type": "Delivery",
				"status": ["not in", ["Cancelled"]],
			},
			["name", "goods_value"],
			as_dict=True,
		)
		if existing:
			frappe.db.set_value(
				"BEI Trip Stop",
				stop.name,
				{
					"billing_reference": existing.name,
					"delivery_value": flt(existing.goods_value or 0),
					"billing_creation_status": "Success",
				},
			)
			frappe.db.release_savepoint(savepoint_name)
			return

		exception_trace = None
		if stop.status != "Delivered":
			if not pre_delivery_exception:
				if require_pre_delivery_exception:
					raise DeliveryBillingPolicyError(
						"Pre-delivery billing is blocked without approved dual-approval exception."
					)
				raise DeliveryBillingPolicyError(
					"Trip stop is not delivered. Confirm delivery first or provide approved dual-approval exception."
				)

			exception_doc = frappe.get_doc("BEI Match Exception", pre_delivery_exception)
			exception_trace = get_pre_delivery_exception_trace(
				exception_doc,
				trip_reference=trip.name,
				trip_stop_idx=stop.idx,
			)

		# Resolve store department, store type, and active rate -- bail on missing data
		dept = frappe.db.get_value(
			"BEI Warehouse Department Mapping",
			{"warehouse": stop.store, "is_active": 1},
			"department",
		)
		if not dept:
			_fail_stop(
				trip,
				stop,
				savepoint_name,
				f"No warehouse->department mapping for {stop.store}",
				title="Missing Department Mapping",
			)
			return

		store_type = frappe.db.get_value("BEI Store Type", {"store": dept}, "store_type")
		entity_row = resolve_store_buyer_entity(
			warehouse_docname=stop.store,
			store_name=dept,
		)
		markup_percent = resolve_markup_percent(
			store_type or entity_row.get("store_type"),
			store_name=dept,
			entity_row=entity_row,
		)

		rate = frappe.db.get_value(
			"BEI Delivery Rate",
			{"store": dept, "cargo_type": trip.cargo_type, "status": "Active"},
			["delivery_fee", "logistics_fee"],
			as_dict=True,
		)
		if not rate:
			_fail_stop(trip, stop, savepoint_name, f"No active {trip.cargo_type} rate for {dept}")
			return

		# Calculate goods value from store order
		goods_value = _get_order_goods_value(stop.store_order)
		billing_hold = buyer_entity_requires_billing_hold(entity_row)

		# Create billing record
		billing = frappe.new_doc("BEI Billing Schedule")
		billing.update(
			{
				"billing_type": "Delivery",
				"store": dept,
				"store_type": store_type or "",
				"trip_reference": trip.name,
				"trip_stop_idx": stop.idx,
				"cargo_type": trip.cargo_type,
				"delivery_fee": flt(rate.delivery_fee or 0, 2),
				"logistics_fee": flt(rate.logistics_fee or 0, 2),
				"goods_value": goods_value,
				"handling_fee": flt(goods_value * markup_percent, 2),
				"status": "Draft" if billing_hold else "Pending",
			}
		)
		stamp_billing_schedule_contract(
			billing,
			entity_row=entity_row,
			markup_percent=markup_percent,
			warehouse_docname=stop.store,
		)
		if pre_delivery_exception and _has_column("BEI Billing Schedule", "pre_delivery_exception"):
			billing.pre_delivery_exception = pre_delivery_exception
		if exception_trace:
			_set_if_column(billing, "exception_cpo_approved_by", exception_trace.get("cpo_approved_by"))
			_set_if_column(billing, "exception_cpo_approved_at", exception_trace.get("cpo_approved_at"))
			_set_if_column(billing, "exception_cfo_approved_by", exception_trace.get("cfo_approved_by"))
			_set_if_column(billing, "exception_cfo_approved_at", exception_trace.get("cfo_approved_at"))
			_set_if_column(billing, "exception_approval_audit_log", exception_trace.get("approval_audit_log"))
		billing.insert(ignore_permissions=True)

		# Update stop with billing reference without re-saving the parent trip.
		frappe.db.set_value(
			"BEI Trip Stop",
			stop.name,
			{
				"billing_reference": billing.name,
				"delivery_value": goods_value,
				"billing_creation_status": "Success",
			},
		)

		# C-06 fix: No explicit commit inside enqueued job -- Frappe
		# auto-commits when the enqueued function returns successfully.
		frappe.db.release_savepoint(savepoint_name)

	except Exception as e:
		try:
			frappe.db.rollback(save_point=savepoint_name)
		except Exception:
			pass
		error_title = f"Failed to create billing for {trip_name} stop {stop_idx}: {e!s}"
		if len(error_title) > 140:
			error_title = f"{error_title[:137]}..."
		frappe.log_error(error_title, "Billing Creation Error")
		try:
			frappe.db.set_value("BEI Trip Stop", stop.name, "billing_creation_status", "Failed")
		except Exception:
			pass

		# G-101: Send Chat alert on billing failure
		try:
			from hrms.api.google_chat import send_message_to_space
			from hrms.utils.bei_config import SPACE_NOTIFICATIONS, get_chat_space

			send_message_to_space(
				get_chat_space(SPACE_NOTIFICATIONS),
				f"*Billing Creation Failed*\nTrip: {trip_name}\nStop: {stop_idx}\nError: {str(e)[:200]}",
			)
		except Exception:
			pass  # notification failure must not cascade


def _fail_stop(
	trip: Any, stop: Any, savepoint: Any, error_message: str, title: str = "Missing Delivery Rate"
):
	"""Mark a stop as failed and log the error. Used during billing creation."""
	frappe.log_error(error_message, title)
	frappe.db.set_value("BEI Trip Stop", stop.name, "billing_creation_status", "Failed")
	frappe.db.release_savepoint(savepoint)


def _get_order_goods_value(store_order: str | None):
	"""Calculate the total goods value from a store order's line items."""
	if not store_order:
		return 0

	qty_fields = []
	for fieldname in ("qty", "qty_delivered", "qty_approved", "qty_requested"):
		if _has_column("BEI Store Order Item", fieldname):
			qty_fields.append(fieldname)

	if not qty_fields:
		return 0

	if qty_fields[0] == "qty":
		qty_expr = "qty"
	else:
		non_zero_candidates = [f"NULLIF({fieldname}, 0)" for fieldname in qty_fields[:-1]]
		qty_expr = f"COALESCE({', '.join([*non_zero_candidates, qty_fields[-1], '0'])})"

	result = frappe.db.sql(
		f"""
        SELECT COALESCE(SUM(({qty_expr}) * unit_price), 0)
        FROM `tabBEI Store Order Item`
        WHERE parent = %s
    """,
		store_order,
	)
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
		"Employee", {"user_id": user, "status": "Active"}, ["branch"], as_dict=True
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


def _calculate_eta(trip: Any, my_stop_order: int):
	"""
	Calculate ETA for a delivery stop.

	Returns:
	    dict: {
	        "eta_minutes": int or None,
	        "eta_window": {"min": "HH:MM", "max": "HH:MM"} or None
	    }
	"""
	from frappe.utils import add_to_date, format_time, get_datetime

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

	# G-003/G-073: Use per-stop estimated_minutes if available, fallback to 20 min/stop
	eta_minutes = 0
	cumulative_minutes = 0  # for scheduled arrival calculation
	for stop in sorted(trip.stops, key=lambda s: s.stop_order):
		stop_time = _get_trip_stop_estimated_minutes(trip, stop)
		if stop.stop_order > last_delivered and stop.stop_order <= my_stop_order:
			eta_minutes += stop_time
		if stop.stop_order <= my_stop_order:
			cumulative_minutes += stop_time

	# Calculate arrival window (±15 minutes from scheduled time)
	departure_dt = get_datetime(trip.departure_time)
	scheduled_arrival = add_to_date(departure_dt, minutes=cumulative_minutes)
	window_start = add_to_date(scheduled_arrival, minutes=-15)
	window_end = add_to_date(scheduled_arrival, minutes=15)

	return {
		"eta_minutes": eta_minutes,
		"eta_window": {"min": format_time(window_start), "max": format_time(window_end)},
	}


def _get_route_stop_minutes_by_store(route_name: str | None) -> dict[str, int]:
	"""Resolve route-stop travel minutes keyed by store for ETA calculations."""
	if not route_name:
		return {}
	try:
		route = frappe.get_doc("BEI Route", route_name)
	except Exception:
		return {}

	minutes_by_store: dict[str, int] = {}
	for stop in getattr(route, "stops", []) or []:
		store = getattr(stop, "store", "")
		if not store:
			continue
		minutes_by_store[store] = cint(getattr(stop, "estimated_minutes", 0) or 0) or 20
	return minutes_by_store


def _get_trip_stop_estimated_minutes(trip: Any, stop: Any) -> int:
	"""Get effective stop minutes from trip row or fallback route metadata."""
	runtime_minutes = cint(getattr(stop, "estimated_minutes", 0) or 0)
	if runtime_minutes > 0:
		return runtime_minutes

	cache_name = "_route_stop_minutes_by_store"
	minutes_by_store = getattr(trip, cache_name, None)
	if minutes_by_store is None:
		route_name = getattr(trip, "route", None) or getattr(trip, "route_name", None)
		minutes_by_store = _get_route_stop_minutes_by_store(route_name)
		setattr(trip, cache_name, minutes_by_store)

	return cint(minutes_by_store.get(getattr(stop, "store", ""), 0) or 20)


def _get_trip_scheduled_arrivals(trip: Any) -> dict[int, Any]:
	"""Return scheduled arrival datetimes by stop order using effective route minutes."""
	from frappe.utils import add_to_date, get_datetime

	if not trip.departure_time:
		return {}

	departure_dt = get_datetime(trip.departure_time)
	cumulative_minutes = 0
	scheduled_by_order: dict[int, Any] = {}
	for stop in sorted(trip.stops, key=lambda s: cint(getattr(s, "stop_order", 0) or 0)):
		cumulative_minutes += _get_trip_stop_estimated_minutes(trip, stop)
		scheduled_by_order[cint(getattr(stop, "stop_order", 0) or 0)] = add_to_date(
			departure_dt, minutes=cumulative_minutes
		)
	return scheduled_by_order


def _get_items_preview(store_order: str | None):
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
		limit=11,  # Get 11 to check if there's overflow
	)

	if len(items) > 10:
		overflow_count = len(frappe.get_all("BEI Store Order Item", filters={"parent": store_order})) - 10
		items = items[:10]
		items.append(
			{"item_code": "MORE", "item_name": f"... and {overflow_count} more items", "qty": 0, "uom": ""}
		)

	return items


def _send_delivery_notification(driver: str, store: str, eta_range: str):
	"""
	Send Google Chat notification for "1 stop away" alert.
	G-003: Routes to per-store Chat space first, falls back to global.
	MUST NOT block delivery confirmation if it fails.
	"""
	from hrms.api.google_chat import resolve_store_chat_space, send_message_to_space
	from hrms.utils.bei_config import SPACE_NOTIFICATIONS, get_chat_space

	# G-003: Try per-store Chat space first, fall back to global
	store_space = resolve_store_chat_space(store)
	space = store_space or get_chat_space(SPACE_NOTIFICATIONS)

	message = (
		f"*Delivery Update*\n\n"
		f"Driver *{driver}* is 1 stop away from *{store}*.\n"
		f"ETA: {eta_range}\n\n"
		f"Please prepare receiving area."
	)

	send_message_to_space(space, message)


def _set_store_order_status(store_order_name: str, status: str):
	"""
	Update a single BEI Store Order status. Silently skips if order not found.
	Used to keep store orders in sync with trip/delivery progress.
	"""
	try:
		if frappe.db.exists("BEI Store Order", store_order_name):
			frappe.db.set_value("BEI Store Order", store_order_name, "status", status)
	except Exception as e:
		frappe.log_error(
			title="Store Order Status Update Failed",
			message=f"Failed to set {store_order_name} to {status}: {e!s}",
		)


def _set_store_orders_in_transit(stops: list[dict[str, Any]]):
	"""
	After a trip departs, set all linked BEI Store Orders to "In Transit".
	Only affects orders already allocated to the departing trip.
	"""
	try:
		for stop_data in stops:
			store_order = stop_data.get("store_order")
			if store_order:
				current_status = frappe.db.get_value("BEI Store Order", store_order, "status")
				if current_status in ("Approved", "Ready for Dispatch", "Partially Fulfilled"):
					frappe.db.set_value("BEI Store Order", store_order, "status", "In Transit")
	except Exception as e:
		frappe.log_error(
			title="Store Orders In Transit Update Failed",
			message=f"Failed to set store orders to In Transit: {e!s}",
		)


@frappe.whitelist()
def get_my_delivery(date: str | None = None):
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
		filters={"trip_date": trip_date, "status": ["!=", "Cancelled"]},
		fields=["name"],
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
						"status": my_stop.status,
					},
				},
				"cs_phone": cs_phone,
			}

	return {"ok": False, "message": "No delivery scheduled"}


# ============================================================================
# PHASE 1C: ROUTE MANAGEMENT & TRIP CREATION
# ============================================================================


@frappe.whitelist()
def get_routes(cargo_type: str | None = None, active_only: bool = True):
	"""Get all route masters, optionally filtered."""
	set_backend_observability_context(
		module="warehouse",
		action="get_routes",
		route_action="get_routes",
		mutation_type="load",
		endpoint_or_job="hrms.api.dispatch.get_routes",
		phase="load",
		extras={"cargo_type": cargo_type, "active_only": active_only},
	)
	_check_scm_permission(SCM_DISPATCH_ROLES, "view routes")

	filters = {}
	if cargo_type:
		filters["cargo_type"] = cargo_type
	if active_only:
		filters["active"] = 1

	routes = frappe.get_all(
		"BEI Route",
		filters=filters,
		fields=[
			"name",
			"route_name",
			"cargo_type",
			"source_warehouse",
			"default_vehicle",
			"default_driver",
			"estimated_duration_hrs",
			"active",
		],
		order_by="route_name",
	)

	for route in routes:
		stops = frappe.get_all(
			"BEI Route Stop",
			filters={"parent": route.name},
			fields=["store", "stop_order", "estimated_minutes"],
			order_by="stop_order",
		)
		route["stops"] = stops
		route["stop_count"] = len(stops)

	return {"routes": routes}


@frappe.whitelist()
def get_route_detail(route_name: str):
	"""Get full route details including all stops."""
	set_backend_observability_context(
		module="warehouse",
		action="get_route_detail",
		route_action="get_route_detail",
		mutation_type="load",
		endpoint_or_job="hrms.api.dispatch.get_route_detail",
		phase="load",
		extras={"route_name": route_name},
	)
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
					"mall_permit_required": s.mall_permit_required,
				}
				for s in route.stops
			],
		}
	}


@frappe.whitelist()
def create_route(
	route_name: str,
	cargo_type: str,
	source_warehouse: str,
	stops: list[dict[str, Any]] | str | None = None,
	default_vehicle: str | None = None,
	default_driver: str | None = None,
	notes: str | None = None,
):
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
			route.append(
				"stops",
				{
					"store": stop_data.get("store"),
					"stop_order": idx,
					"estimated_minutes": stop_data.get("estimated_minutes", 20),
					"special_instructions": stop_data.get("special_instructions", ""),
					"mall_permit_required": stop_data.get("mall_permit_required", 0),
				},
			)

	_enable_role_gated_write(route)
	route.insert(ignore_permissions=True)
	return {"success": True, "route": route.name}


@frappe.whitelist()
def update_route(route_name: str, updates: dict[str, Any] | str | None = None):
	"""Update a route master. Accepts partial updates."""
	_check_scm_permission(SCM_ADMIN_ROLES, "update routes")

	if isinstance(updates, str):
		updates = frappe.parse_json(updates)

	route = frappe.get_doc("BEI Route", route_name)

	simple_fields = [
		"route_name",
		"cargo_type",
		"source_warehouse",
		"default_vehicle",
		"default_driver",
		"estimated_duration_hrs",
		"notes",
		"active",
	]
	for field in simple_fields:
		if field in updates:
			setattr(route, field, updates[field])

	if "stops" in updates:
		route.stops = []
		for idx, stop_data in enumerate(updates["stops"], 1):
			route.append(
				"stops",
				{
					"store": stop_data.get("store"),
					"stop_order": idx,
					"estimated_minutes": stop_data.get("estimated_minutes", 20),
					"special_instructions": stop_data.get("special_instructions", ""),
					"mall_permit_required": stop_data.get("mall_permit_required", 0),
				},
			)

	_enable_role_gated_write(route)
	route.save(ignore_permissions=True)
	return {"success": True, "route": route.name}


@frappe.whitelist()
def delete_route(route_name: str):
	"""Soft-delete a route (set active=0)."""
	_check_scm_permission(SCM_ADMIN_ROLES, "delete routes")

	route = frappe.get_doc("BEI Route", route_name)
	route.active = 0
	_enable_role_gated_write(route)
	route.save(ignore_permissions=True)
	return {"success": True, "message": f"Route {route_name} deactivated"}


@frappe.whitelist()
def get_vehicles(status: str | None = None, owner_type: str | None = None):
	"""List vehicles with optional filters."""
	set_backend_observability_context(
		module="warehouse",
		action="get_vehicles",
		route_action="get_vehicles",
		mutation_type="load",
		endpoint_or_job="hrms.api.dispatch.get_vehicles",
		phase="load",
		extras={"status": status, "owner_type": owner_type},
	)
	_check_scm_permission(SCM_DISPATCH_ROLES, "view vehicles")

	filters = {}
	if status:
		filters["status"] = status
	if owner_type:
		filters["owner_type"] = owner_type

	vehicles = frappe.get_all(
		"BEI Vehicle",
		filters=filters,
		fields=[
			"name",
			"vehicle_plate",
			"vehicle_type",
			"capacity_kg",
			"capacity_cbm",
			"owner_type",
			"threepl_partner",
			"status",
		],
		order_by="vehicle_plate",
	)
	# GAP-029 compatibility contract:
	# - Keep legacy object payload (`vehicles`) used by current pages.
	# - Also provide a flat name list to avoid dropdown fallback-to-text
	#   when callers expect a simple string array.
	vehicle_names = [v.get("name") for v in vehicles if v.get("name")]
	return {"vehicles": vehicles, "vehicle_names": vehicle_names, "data": vehicle_names}


def _build_stop_preview(route: Any, trip_date: str):
	"""Shared helper: build stop list with pending order info using bulk queries."""
	store_list = [s.store for s in route.stops]

	orders = frappe.db.get_all(
		"BEI Store Order",
		filters={"store": ["in", store_list], "delivery_date": trip_date, "status": "Approved"},
		fields=["name", "store"],
	)
	order_map = {o.store: o.name for o in orders}

	order_names = [o.name for o in orders]
	item_counts = {}
	if order_names:
		counts = frappe.db.sql(
			"""
            SELECT parent, COUNT(*) as cnt FROM `tabBEI Store Order Item`
            WHERE parent IN %(names)s GROUP BY parent
        """,
			{"names": order_names},
			as_dict=True,
		)
		item_counts = {c.parent: c.cnt for c in counts}

	stops = []
	for s in route.stops:
		order = order_map.get(s.store)
		stops.append(
			{
				"store": s.store,
				"stop_order": getattr(s, "stop_order", 0),
				"estimated_minutes": getattr(s, "estimated_minutes", 0),
				"store_order": order or "",
				"items_count": item_counts.get(order, 0) if order else 0,
			}
		)
	return stops


def _enable_role_gated_write(doc: Any):
	"""Use explicit SCM role checks as the write gate for route/trip mutations."""
	if getattr(doc, "flags", None) is None:
		doc.flags = type("_DispatchDocFlags", (), {})()
	doc.flags.ignore_permissions = True
	doc.flags.ignore_user_permissions = True
	return doc


def _save_base64_attachment(
	base64_data: str | None, doctype: str, docname: str | None = None, fieldname: str = "attachment"
):
	"""Persist a base64/data-url attachment and return a file URL for Attach fields."""
	if not base64_data:
		return None

	if base64_data.startswith(("/files/", "/private/", "http://", "https://")):
		return base64_data

	if "," in base64_data:
		header, content = base64_data.split(",", 1)
		header_lower = header.lower()
		if "png" in header_lower:
			ext = "png"
		elif "gif" in header_lower:
			ext = "gif"
		elif "webp" in header_lower:
			ext = "webp"
		else:
			ext = "jpg"
	else:
		content = base64_data
		ext = "jpg"

	try:
		file_content = base64.b64decode(content)
	except Exception as exc:
		frappe.log_error(f"Failed to decode dispatch attachment: {exc!s}", "Dispatch Attachment Decode")
		frappe.throw(_("Invalid attachment data"))

	file_hash = hashlib.md5(file_content).hexdigest()[:12]
	filename = f"{doctype.lower().replace(' ', '_')}_{fieldname}_{file_hash}.{ext}"
	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": filename,
			"content": file_content,
			"attached_to_doctype": doctype if docname else None,
			"attached_to_name": docname,
			"attached_to_field": fieldname,
			"is_private": 0,
		}
	)
	file_doc.save(ignore_permissions=True)
	return file_doc.file_url


@frappe.whitelist()
def preview_trip_stops(route_name: str, trip_date: str | None = None):
	"""Preview stops and pending store orders for a proposed trip."""
	trip_date = trip_date or nowdate()
	set_backend_observability_context(
		module="warehouse",
		action="preview_trip_stops",
		route_action="preview_trip_stops",
		mutation_type="load",
		endpoint_or_job="hrms.api.dispatch.preview_trip_stops",
		phase="load",
		extras={"route_name": route_name, "trip_date": trip_date},
	)
	_check_scm_permission(SCM_DISPATCH_ROLES, "preview trip stops")
	route = frappe.get_doc("BEI Route", route_name)

	if not route.active:
		frappe.throw(_("Route is not active"))

	stops = _build_stop_preview(route, trip_date)
	return {"route_name": route_name, "trip_date": trip_date, "stops": stops}


@frappe.whitelist()
def create_trip_from_route(
	route_name: str,
	trip_date: str | None = None,
	vehicle: str | None = None,
	driver: str | None = None,
	threepl_driver_name: str | None = None,
	selected_stops: list[dict[str, Any]] | str | None = None,
):
	"""One-click trip creation from a route template.

	1. Loads route + stops
	2. Creates BEI Distribution Trip
	3. Copies stops, links approved store orders
	4. Returns trip name
	"""
	trip_date = trip_date or nowdate()
	set_backend_observability_context(
		module="warehouse",
		action="create_trip_from_route",
		route_action="create_trip_from_route",
		mutation_type="create",
		endpoint_or_job="hrms.api.dispatch.create_trip_from_route",
		phase="mutation",
		extras={
			"route_name": route_name,
			"trip_date": trip_date,
			"vehicle": vehicle,
			"driver": driver,
			"selected_stops_provided": bool(selected_stops),
		},
	)
	_check_scm_permission(SCM_DISPATCH_ROLES, "create trips from routes")

	route = frappe.get_doc("BEI Route", route_name)

	if not route.active:
		frappe.throw(_("Route is not active"))

	# G-069: UX pre-check for duplicate trip (DB constraint is the real guard)
	existing_trip = frappe.db.get_value(
		"BEI Distribution Trip", {"route_name": route_name, "trip_date": trip_date}, "name"
	)
	if existing_trip:
		frappe.throw(
			_("A trip already exists for route '{0}' on {1}: {2}").format(
				route_name, trip_date, existing_trip
			)
		)

	# Resolve vehicle details
	vehicle_plate = None
	if vehicle:
		vehicle_plate = frappe.db.get_value("BEI Vehicle", vehicle, "vehicle_plate")
	elif route.default_vehicle:
		vehicle = route.default_vehicle
		vehicle_plate = frappe.db.get_value("BEI Vehicle", route.default_vehicle, "vehicle_plate")

	if isinstance(selected_stops, str):
		selected_stops = frappe.parse_json(selected_stops)

	if selected_stops:
		# Validate all selected stores exist in route's zone pool
		zone_stores = {s.store for s in route.stops}
		route_stop_map = {s.store: s for s in route.stops}
		for sel in selected_stops:
			if sel.get("store") not in zone_stores:
				frappe.throw(_(f"Store {sel.get('store')} is not in zone {route.route_name}"))

		# Build stops from selection using bulk queries
		sel_stores = [sel.get("store") for sel in selected_stops]
		orders = frappe.db.get_all(
			"BEI Store Order",
			filters={"store": ["in", sel_stores], "delivery_date": trip_date, "status": "Approved"},
			fields=["name", "store"],
		)
		order_map = {o.store: o.name for o in orders}

		order_names = [o.name for o in orders]
		item_counts = {}
		if order_names:
			counts = frappe.db.sql(
				"""
                SELECT parent, COUNT(*) as cnt FROM `tabBEI Store Order Item`
                WHERE parent IN %(names)s GROUP BY parent
            """,
				{"names": order_names},
				as_dict=True,
			)
			item_counts = {c.parent: c.cnt for c in counts}

		stops = []
		for sel in selected_stops:
			store = sel.get("store")
			order = order_map.get(store)
			route_stop = route_stop_map.get(store)
			estimated_minutes = getattr(route_stop, "estimated_minutes", 20) if route_stop else 20
			selected_stop_order = cint(sel.get("stop_order")) or (len(stops) + 1)
			stops.append(
				{
					"store": store,
					"stop_order": selected_stop_order,
					"estimated_minutes": estimated_minutes,
					"items_count": item_counts.get(order, 0) if order else 0,
					"store_order": order or "",
				}
			)
	else:
		# Original behavior: use all route stops (via shared helper)
		stops = _build_stop_preview(route, trip_date)

	# Use existing trip creation logic
	trip = _build_trip_doc(trip_date, route.route_name, stops)
	trip.route = route.name
	trip.driver = driver or route.default_driver
	trip.vehicle = vehicle
	trip.vehicle_plate = vehicle_plate
	trip.cargo_type = route.cargo_type

	if trip.driver:
		trip.driver_name = frappe.db.get_value("Employee", trip.driver, "employee_name") or trip.driver_name

	is_threepl_vehicle = bool(trip.vehicle) and (
		frappe.db.get_value("BEI Vehicle", trip.vehicle, "owner_type") == "3PL"
	)
	external_driver = (threepl_driver_name or "").strip()
	if is_threepl_vehicle and external_driver:
		trip.driver = ""
		trip.driver_name = external_driver
		_set_if_column(trip, "threepl_driver_name", external_driver)
	elif not is_threepl_vehicle:
		_set_if_column(trip, "threepl_driver_name", "")

	# Link store orders to stops
	for idx, stop_data in enumerate(stops):
		if stop_data.get("store_order"):
			trip.stops[idx].store_order = stop_data["store_order"]

	_enable_role_gated_write(trip)
	trip.insert(ignore_permissions=True)

	return {
		"success": True,
		"trip": trip.name,
		"message": f"Trip {trip.name} created from route {route.route_name} with {len(stops)} stops",
	}


@frappe.whitelist()
def duplicate_route(route_name: str, new_name: str):
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
		new_route.append(
			"stops",
			{
				"store": stop.store,
				"stop_order": stop.stop_order,
				"estimated_minutes": stop.estimated_minutes,
				"special_instructions": stop.special_instructions,
				"mall_permit_required": stop.mall_permit_required,
			},
		)

	_enable_role_gated_write(new_route)
	new_route.insert(ignore_permissions=True)
	return {"success": True, "route": new_route.name}


@frappe.whitelist()
def reorder_stops(route_name: str, stop_order_map: dict[str, int] | str):
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

	_enable_role_gated_write(route)
	route.save(ignore_permissions=True)
	return {"success": True, "route": route.name}


@frappe.whitelist()
def get_driver_list():
	"""Get list of available drivers (employees with driver designation)."""
	_check_scm_permission(SCM_DISPATCH_ROLES, "view driver list")
	phone_field = _get_employee_phone_field()
	fields = ["name", "employee_name"]
	if phone_field:
		fields.append(phone_field)

	driver_rows = frappe.get_all(
		"Employee",
		filters={"status": "Active", "designation": ["in", ["Driver", "Delivery Driver", "Truck Driver"]]},
		fields=fields,
		order_by="employee_name",
	)
	drivers = [
		{
			"name": row.name,
			"employee_name": row.employee_name,
			"cell_phone": _get_employee_phone(row),
		}
		for row in driver_rows
	]
	return {"drivers": drivers}


# ============================================================================
# PHASE 3B: DRIVER SCHEDULING ENDPOINTS
# ============================================================================

DRIVER_DESIGNATIONS = ["Driver", "Helper", "Relief Driver", "Delivery Driver", "Truck Driver"]


@frappe.whitelist()
def get_available_drivers(date: str | None = None):
	"""
	Get all drivers with their assignment status for a given date.

	Returns each driver with:
	  - status: "Available" | "Assigned" | "Off-Duty"
	  - trip: trip details if assigned (trip_name, route_name, departure_time, vehicle_plate)

	Args:
	    date: ISO date string (defaults to today)

	Returns:
	    {"drivers": [DriverStatus, ...]}
	"""
	trip_date = date or nowdate()
	set_backend_observability_context(
		module="warehouse",
		action="get_available_drivers",
		route_action="get_available_drivers",
		mutation_type="load",
		endpoint_or_job="hrms.api.dispatch.get_available_drivers",
		phase="load",
		extras={"trip_date": trip_date},
	)
	_check_scm_permission(SCM_DISPATCH_ROLES, "view available drivers")

	phone_field = _get_employee_phone_field()
	driver_fields = ["name", "employee_name", "designation", "status"]
	if phone_field:
		driver_fields.append(phone_field)

	# All active employees with driver designations
	all_drivers = frappe.get_all(
		"Employee",
		filters={"status": "Active", "designation": ["in", DRIVER_DESIGNATIONS]},
		fields=driver_fields,
		order_by="employee_name",
	)

	# Build a map of employee -> trip for the date
	trips_on_date = frappe.get_all(
		"BEI Distribution Trip",
		filters={"trip_date": trip_date},
		fields=["name", "driver", "route_name", "departure_time", "vehicle_plate", "status"],
	)

	assigned_map = {}
	for trip in trips_on_date:
		if trip.driver:
			assigned_map[trip.driver] = trip

	result = []
	for driver in all_drivers:
		assigned_trip = assigned_map.get(driver.name)
		driver_status = "Assigned" if assigned_trip else "Available"

		entry = {
			"employee": driver.name,
			"employee_name": driver.employee_name,
			"designation": driver.designation,
			"cell_phone": _get_employee_phone(driver),
			"status": driver_status,
			"trip": None,
		}

		if assigned_trip:
			entry["trip"] = {
				"name": assigned_trip.name,
				"route_name": assigned_trip.route_name,
				"departure_time": str(assigned_trip.departure_time) if assigned_trip.departure_time else None,
				"vehicle_plate": assigned_trip.vehicle_plate or "",
				"status": assigned_trip.status,
			}

		result.append(entry)

	# Count summary
	available_count = sum(1 for d in result if d["status"] == "Available")
	assigned_count = sum(1 for d in result if d["status"] == "Assigned")

	return {
		"drivers": result,
		"summary": {
			"total": len(result),
			"available": available_count,
			"assigned": assigned_count,
		},
	}


@frappe.whitelist()
def assign_driver(trip_name: str, employee: str, vehicle: str | None = None):
	"""
	Assign a driver (or helper) to an existing trip.
	Only valid for trips in "Preparing" status.

	Args:
	    trip_name: BEI Distribution Trip name
	    employee:  Employee name (Link field)
	    vehicle:   Optional BEI Vehicle name — updates vehicle_plate automatically

	Returns:
	    {"success": True, "trip": trip_name, "driver": employee_name}
	"""
	_check_scm_permission(SCM_DISPATCH_ROLES, "assign drivers to trips")

	# Validate employee exists and has a driver designation
	emp = frappe.db.get_value(
		"Employee",
		{"name": employee, "status": "Active"},
		["name", "employee_name", "designation"],
		as_dict=True,
	)
	if not emp:
		frappe.throw(_("Employee {0} not found or not active").format(employee))

	if emp.designation not in DRIVER_DESIGNATIONS:
		frappe.throw(
			_("Employee {0} does not have a driver designation ({1})").format(
				emp.employee_name, emp.designation
			)
		)

	trip = frappe.get_doc("BEI Distribution Trip", trip_name)

	if trip.status not in ("Preparing", "In Transit"):
		frappe.throw(_("Cannot reassign driver: trip {0} is in status '{1}'").format(trip_name, trip.status))

	trip.driver = employee

	if vehicle:
		vehicle_plate = frappe.db.get_value("BEI Vehicle", vehicle, "vehicle_plate")
		trip.vehicle = vehicle
		trip.vehicle_plate = vehicle_plate or ""

	trip.save()

	return {
		"success": True,
		"trip": trip.name,
		"driver": emp.employee_name,
		"vehicle_plate": trip.vehicle_plate or "",
	}


@frappe.whitelist()
def get_driver_schedule(employee: str, date_from: str | None = None, date_to: str | None = None):
	"""
	Get a specific driver's schedule over a date range.

	Args:
	    employee:  Employee name
	    date_from: Start date (defaults to Monday of current week)
	    date_to:   End date (defaults to Sunday of current week)

	Returns:
	    {
	        "employee": {...},
	        "days": [
	            {
	                "date": "2026-02-17",
	                "status": "Available" | "Assigned" | "Off-Duty",
	                "trip": {...} or null
	            },
	            ...
	        ]
	    }
	"""
	_check_scm_permission(SCM_DISPATCH_ROLES, "view driver schedules")

	from frappe.utils import add_days, get_first_day_of_week, getdate

	today = getdate(nowdate())

	if date_from:
		start = getdate(date_from)
	else:
		# Default to Monday of current week
		weekday = today.weekday()  # Monday=0
		start = add_days(today, -weekday)

	if date_to:
		end = getdate(date_to)
	else:
		# Default to Sunday of current week
		end = add_days(start, 6)
	phone_field = _get_employee_phone_field()
	employee_fields = ["name", "employee_name", "designation", "status"]
	if phone_field:
		employee_fields.append(phone_field)

	# Validate employee
	emp = frappe.db.get_value("Employee", employee, employee_fields, as_dict=True)
	if not emp:
		frappe.throw(_("Employee {0} not found").format(employee))

	# Get all trips assigned to this driver in range
	trips = frappe.get_all(
		"BEI Distribution Trip",
		filters={"driver": employee, "trip_date": ["between", [str(start), str(end)]]},
		fields=["name", "trip_date", "route_name", "departure_time", "vehicle_plate", "status"],
	)

	trip_by_date = {str(t.trip_date): t for t in trips}

	# Build day-by-day schedule
	days = []
	current = start
	while current <= end:
		date_str = str(current)
		trip = trip_by_date.get(date_str)

		if emp.status != "Active":
			day_status = "Off-Duty"
		elif trip:
			day_status = "Assigned"
		else:
			day_status = "Available"

		day_entry = {
			"date": date_str,
			"status": day_status,
			"trip": {
				"name": trip.name,
				"route_name": trip.route_name,
				"departure_time": str(trip.departure_time) if trip.departure_time else None,
				"vehicle_plate": trip.vehicle_plate or "",
				"status": trip.status,
			}
			if trip
			else None,
		}
		days.append(day_entry)
		current = add_days(current, 1)

	return {
		"employee": {
			"name": emp.name,
			"employee_name": emp.employee_name,
			"designation": emp.designation,
			"status": emp.status,
			"cell_phone": _get_employee_phone(emp),
		},
		"date_from": str(start),
		"date_to": str(end),
		"days": days,
	}


@frappe.whitelist()
def get_warehouses():
	"""Get warehouses valid for trip routes/stops.

	Primary source: active `BEI Warehouse Department Mapping`.
	Fallback: leaf warehouses in `Warehouse` when mapping data is incomplete.
	"""
	_check_scm_permission(SCM_DISPATCH_ROLES, "view warehouses")
	mapped = frappe.get_all(
		"BEI Warehouse Department Mapping",
		filters={"is_active": 1},
		fields=["warehouse as name", "warehouse as warehouse_name", "department"],
		order_by="warehouse",
	)

	resolved_mapped = []
	seen = set()
	for row in mapped:
		resolved_name = _resolve_store_to_warehouse_name(row.name)
		if not resolved_name or resolved_name in seen:
			continue
		seen.add(resolved_name)
		resolved_mapped.append(
			{
				"name": resolved_name,
				"warehouse_name": frappe.db.get_value("Warehouse", resolved_name, "warehouse_name")
				or resolved_name,
				"department": row.department,
			}
		)

	if resolved_mapped:
		return resolved_mapped

	fallback = frappe.get_all(
		"Warehouse", filters={"is_group": 0}, fields=["name", "warehouse_name"], order_by="name"
	)
	return [
		{
			"name": row.name,
			"warehouse_name": row.warehouse_name or row.name,
			"department": None,
		}
		for row in fallback
	]


def _canonical_store_key(value: Any):
	"""Normalize store labels for resilient matching across naming variants."""
	if not value:
		return ""
	return "".join(ch for ch in str(value).strip().lower() if ch.isalnum())


def _strip_legacy_company_suffix(store_name: str | None):
	"""Strip company suffixes from store labels.

	S199: handles ALL CAPS store-first names (e.g., "SM TANZA - BEBANG MEGA INC.")
	plus legacy patterns ("SM Tanza - BEI", "SM Tanza - Bebang Enterprise Inc.").
	"""
	import re
	if not store_name:
		return ""
	text = str(store_name).strip()
	upper = text.upper()
	# S199: generic corp suffix — strip " - <ANYTHING INC./CORP./OPC>"
	m = re.search(r"\s+-\s+\S.*(?:INC\.|CORP\.|OPC)$", upper)
	if m:
		return text[: m.start()].strip(" -")
	# Legacy short suffixes
	for suffix in (" - BEI", "- BEI", " - BK", "- BK", " - BKI", "- BKI"):
		if upper.endswith(suffix):
			return text[: len(text) - len(suffix)].strip(" -")
	return text


def _resolve_store_to_warehouse_name(store_name: str | None):
	"""Resolve a store label from BEI Store Type to a valid Warehouse name."""
	if not store_name:
		return None

	raw = str(store_name).strip()

	# 1) exact warehouse docname
	if frappe.db.exists("Warehouse", raw):
		return raw

	# 2) exact docname, case-insensitive
	exact_ci = frappe.db.sql(
		"""
        SELECT name
        FROM `tabWarehouse`
        WHERE LOWER(name) = LOWER(%s)
        LIMIT 1
        """,
		(raw,),
		as_dict=True,
	)
	if exact_ci:
		return exact_ci[0].name

	# 3) common explicit suffix candidates based on stripped base label
	base = _strip_legacy_company_suffix(raw)
	candidates = (
		base,
		f"{base} - BEI" if base else "",
		f"{base} - BK" if base else "",
		f"{base} - Bebang Enterprise Inc." if base else "",
		f"{base} - Bebang Kitchen Inc." if base else "",
	)
	for candidate in candidates:
		if candidate and frappe.db.exists("Warehouse", candidate):
			return candidate

	# 4) warehouse_name exact/case-insensitive match
	by_warehouse_name = frappe.db.sql(
		"""
        SELECT name
        FROM `tabWarehouse`
        WHERE is_group = 0
          AND LOWER(warehouse_name) = LOWER(%s)
        LIMIT 1
        """,
		(base or raw,),
		as_dict=True,
	)
	if by_warehouse_name:
		return by_warehouse_name[0].name

	# 5) canonical fallback (handles punctuation/case/suffix differences)
	target_keys = {k for k in (_canonical_store_key(raw), _canonical_store_key(base)) if k}
	if target_keys:
		for row in frappe.get_all(
			"Warehouse",
			filters={"is_group": 0},
			fields=["name", "warehouse_name"],
			order_by="name",
		):
			if _canonical_store_key(row.name) in target_keys:
				return row.name
			if _canonical_store_key(row.warehouse_name or "") in target_keys:
				return row.name

	# 6) legacy fallback for old behavior
	if frappe.db.exists("Warehouse", store_name):
		return store_name

	# common BEI suffix
	with_bei = f"{store_name} - BEI"
	if frappe.db.exists("Warehouse", with_bei):
		return with_bei

	# warehouse_name match
	return frappe.db.get_value("Warehouse", {"warehouse_name": store_name, "is_group": 0}, "name")


@frappe.whitelist()
def get_stores():
	"""Get route-stop candidates as valid Warehouse link values.

	`BEI Route Stop.store` links to `Warehouse`. `BEI Store Type.store` is a
	Department-style label, so we resolve each entry to an actual warehouse docname.
	"""
	_check_scm_permission(SCM_DISPATCH_ROLES, "view stores")
	rows = frappe.get_all("BEI Store Type", fields=["store", "store_type"], order_by="store")

	stores = []
	seen = set()
	for row in rows:
		warehouse_name = _resolve_store_to_warehouse_name(row.store)
		if not warehouse_name or warehouse_name in seen:
			continue
		seen.add(warehouse_name)
		stores.append(
			{
				"name": warehouse_name,
				"store": warehouse_name,
				"store_type": row.store_type,
				"store_label": row.store,
			}
		)

	if stores:
		return stores

	# Hard fallback to avoid empty selector when Store Type to Warehouse mapping is stale.
	return [
		{
			"name": row["name"],
			"store": row["name"],
			"store_type": "Unknown",
			"store_label": row.get("warehouse_name") or row["name"],
		}
		for row in get_warehouses()
	]
