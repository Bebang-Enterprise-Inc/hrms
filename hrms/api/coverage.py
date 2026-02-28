# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Coverage API
Handles staff coverage requests for relief staffing
"""

import json

import frappe
from frappe import _
from frappe.utils import nowdate


def resolve_warehouse(store_or_branch):
	"""Resolve a branch name or partial warehouse name to the full warehouse name."""
	if not store_or_branch:
		return None

	# First check if the exact warehouse exists
	if frappe.db.exists("Warehouse", store_or_branch):
		return store_or_branch

	# Try appending company abbreviation
	warehouse_with_company = f"{store_or_branch} - BEI"
	if frappe.db.exists("Warehouse", warehouse_with_company):
		return warehouse_with_company

	# Try to find warehouse by warehouse_name
	warehouse = frappe.db.get_value("Warehouse", {"warehouse_name": store_or_branch}, "name")
	if warehouse:
		return warehouse

	frappe.throw(_("Could not find Store: {0}").format(store_or_branch))


def resolve_employee(employee_name_or_id):
	"""Resolve an employee name or ID to employee ID."""
	if not employee_name_or_id:
		return None

	# First check if it's already an employee ID
	if frappe.db.exists("Employee", employee_name_or_id):
		return employee_name_or_id

	# Search by employee_name
	employee = frappe.db.get_value("Employee", {"employee_name": employee_name_or_id}, "name")
	if employee:
		return employee

	# Search by partial match
	employees = frappe.db.sql(
		"""
        SELECT name, employee_name FROM tabEmployee
        WHERE employee_name LIKE %s
        LIMIT 5
    """,
		(f"%{employee_name_or_id}%",),
		as_dict=True,
	)

	if employees:
		if len(employees) == 1:
			return employees[0].name
		suggestions = [f"{e.name} ({e.employee_name})" for e in employees]
		frappe.throw(
			_("Multiple employees found matching '{0}': {1}").format(
				employee_name_or_id, ", ".join(suggestions)
			)
		)

	frappe.throw(_("Could not find Employee: {0}").format(employee_name_or_id))


@frappe.whitelist()
def request_coverage(
	store=None, coverage_date=None, shift=None, reason=None, absent_employee=None, notes=None
):
	"""Request staff coverage.

	Bug fix (C13):
	- Status set to "Pending" (not "Open" which is not in DocType allowed values)
	- DocType allows: Pending, Assigned, Cancelled
	- Shift normalized to match DocType options: Opening, Mid, Closing
	- insert with ignore_permissions=True
	- Returns user-friendly error instead of raw traceback
	"""
	try:
		if not store:
			frappe.throw(_("Store is required"))

		if not absent_employee:
			frappe.throw(_("Absent employee is required"))

		# Resolve store and employee to valid Link values
		warehouse = resolve_warehouse(store)
		employee_id = resolve_employee(absent_employee)

		# Normalize shift to match DocType options: Opening, Mid, Closing
		shift_map = {
			"morning": "Opening",
			"opening": "Opening",
			"mid": "Mid",
			"midshift": "Mid",
			"afternoon": "Mid",
			"closing": "Closing",
			"evening": "Closing",
		}
		normalized_shift = shift_map.get((shift or "").lower(), shift.title() if shift else "Opening")
		# Validate against allowed options
		if normalized_shift not in ("Opening", "Mid", "Closing"):
			normalized_shift = "Opening"

		doc = frappe.new_doc("BEI Staff Coverage Request")
		doc.store = warehouse
		doc.request_date = nowdate()
		doc.coverage_date = coverage_date or nowdate()
		doc.shift = normalized_shift
		doc.reason = reason
		doc.absent_employee = employee_id
		doc.requested_by = frappe.session.user
		doc.notes = notes
		# C13 fix: "Open" is not a valid status. DocType allows: Pending, Assigned, Cancelled
		doc.status = "Pending"
		doc.insert(ignore_permissions=True)

		return {"success": True, "name": doc.name}

	except Exception as e:
		frappe.log_error(
			f"Coverage Request Error for store {store}, employee {absent_employee}: {e!s}\n\n{frappe.get_traceback()}",
			"Coverage Request Error",
		)
		return {
			"success": False,
			"error": _("Failed to submit coverage request. Please try again or contact support."),
		}


@frappe.whitelist()
def approve_coverage(request_name, assigned_employee):
	"""Approve coverage request and assign replacement."""
	allowed_roles = ["Area Supervisor", "Store Supervisor", "HR Manager", "System Manager"]
	if not any(r in frappe.get_roles(frappe.session.user) for r in allowed_roles):
		frappe.throw(_("Not authorized to approve coverage requests"), frappe.PermissionError)

	if not assigned_employee:
		frappe.throw(_("Assigned employee is required"))

	doc = frappe.get_doc("BEI Staff Coverage Request", request_name)
	if doc.status not in ("Pending", "Open"):
		frappe.throw(_("Only pending coverage requests can be assigned"))

	assigned_employee_id = resolve_employee(assigned_employee)
	doc.status = "Assigned"
	doc.assigned_employee = assigned_employee_id
	doc.assigned_by = frappe.session.user
	doc.save(ignore_permissions=True)
	return {"success": True, "assigned_employee": assigned_employee_id}


@frappe.whitelist()
def get_coverage_requests(store=None, status=None, date_from=None, date_to=None, limit=20):
	"""Get coverage requests."""
	limit = min(int(limit or 20), 500)
	filters = {}
	if store:
		filters["store"] = store
	if status:
		filters["status"] = status
	if date_from:
		filters["coverage_date"] = [">=", date_from]
	if date_to:
		if "coverage_date" in filters:
			filters["coverage_date"] = ["between", [date_from, date_to]]
		else:
			filters["coverage_date"] = ["<=", date_to]

	requests = frappe.get_all(
		"BEI Staff Coverage Request",
		filters=filters,
		fields=[
			"name",
			"store",
			"coverage_date",
			"shift",
			"reason",
			"absent_employee",
			"status",
			"assigned_employee",
		],
		order_by="coverage_date desc",
		limit=int(limit),
	)
	return {"requests": requests}
