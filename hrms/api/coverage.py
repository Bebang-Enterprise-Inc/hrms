# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Coverage API
Handles staff coverage requests for relief staffing
"""

import frappe
from frappe import _
from frappe.utils import nowdate
import json


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
    employees = frappe.db.sql("""
        SELECT name, employee_name FROM tabEmployee
        WHERE employee_name LIKE %s
        LIMIT 5
    """, (f"%{employee_name_or_id}%",), as_dict=True)

    if employees:
        if len(employees) == 1:
            return employees[0].name
        suggestions = [f"{e.name} ({e.employee_name})" for e in employees]
        frappe.throw(_("Multiple employees found matching '{0}': {1}").format(
            employee_name_or_id, ", ".join(suggestions)))

    frappe.throw(_("Could not find Employee: {0}").format(employee_name_or_id))


@frappe.whitelist()
def request_coverage(store, coverage_date, shift, reason, absent_employee, notes=None):
    """Request staff coverage."""
    try:
        if not store:
            frappe.throw(_("Store is required"))

        if not absent_employee:
            frappe.throw(_("Absent employee is required"))

        # Resolve store and employee to valid Link values
        warehouse = resolve_warehouse(store)
        employee_id = resolve_employee(absent_employee)

        doc = frappe.new_doc("BEI Staff Coverage Request")
        doc.store = warehouse
        doc.request_date = nowdate()
        doc.coverage_date = coverage_date
        doc.shift = shift
        doc.reason = reason
        doc.absent_employee = employee_id
        doc.requested_by = frappe.session.user
        doc.notes = notes
        doc.insert()

        return {"success": True, "name": doc.name}

    except Exception as e:
        frappe.log_error(
            f"Coverage Request Error for store {store}, employee {absent_employee}: {str(e)}\n\n{frappe.get_traceback()}",
            "Coverage Request Error"
        )
        raise


@frappe.whitelist()
def approve_coverage(request_name, assigned_employee):
    """Approve coverage request and assign replacement."""
    if not assigned_employee:
        frappe.throw(_("Assigned employee is required"))

    doc = frappe.get_doc("BEI Staff Coverage Request", request_name)
    doc.status = "Assigned"
    doc.assigned_employee = assigned_employee
    doc.assigned_by = frappe.session.user
    doc.save()
    return {"success": True}


@frappe.whitelist()
def get_coverage_requests(store=None, status=None, date_from=None, date_to=None, limit=20):
    """Get coverage requests."""
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
            "name", "store", "coverage_date", "shift", "reason",
            "absent_employee", "status", "assigned_employee"
        ],
        order_by="coverage_date desc",
        limit=int(limit)
    )
    return {"requests": requests}
