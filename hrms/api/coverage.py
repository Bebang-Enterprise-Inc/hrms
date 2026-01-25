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


@frappe.whitelist()
def request_coverage(store, coverage_date, shift, reason, absent_employee, notes=None):
    """Request staff coverage."""
    if not store:
        frappe.throw(_("Store is required"))

    doc = frappe.new_doc("BEI Staff Coverage Request")
    doc.store = store
    doc.request_date = nowdate()
    doc.coverage_date = coverage_date
    doc.shift = shift
    doc.reason = reason
    doc.absent_employee = absent_employee
    doc.requested_by = frappe.session.user
    doc.notes = notes
    doc.insert()

    return {"success": True, "name": doc.name}


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
