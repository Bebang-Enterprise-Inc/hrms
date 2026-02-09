"""Shared API helpers for BEI HR modules.

Common utilities used across payroll, performance, disciplinary,
recruitment, and reports API endpoints.
"""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit


NO_EMPLOYEE_MSG = (
    "Your account is not linked to an employee record. "
    "Please contact HR to set up your employee profile."
)


def _get_employee_or_throw(user=None):
    """Get Employee ID for given user (or current user), or throw a user-friendly error."""
    user = user or frappe.session.user
    employee = frappe.db.get_value(
        "Employee",
        {"user_id": user, "status": "Active"},
        "name",
    )
    if not employee:
        frappe.throw(_(NO_EMPLOYEE_MSG), title=_("Employee Record Not Found"))
    return employee


def _get_employee_details(user=None):
    """Get Employee details dict for given user (or current user)."""
    user = user or frappe.session.user
    employee = frappe.db.get_value(
        "Employee",
        {"user_id": user, "status": "Active"},
        [
            "name",
            "employee_name",
            "designation",
            "department",
            "company",
            "branch",
            "reports_to",
            "user_id",
        ],
        as_dict=True,
    )
    if not employee:
        frappe.throw(_(NO_EMPLOYEE_MSG), title=_("Employee Record Not Found"))
    return employee


def _check_hr_permission():
    """Verify current user has HR Manager or HR User role."""
    roles = frappe.get_roles(frappe.session.user)
    if not any(r in roles for r in ["HR Manager", "HR User", "System Manager"]):
        frappe.throw(_("Permission denied. HR role required."), frappe.PermissionError)


def _check_manager_permission(employee_id):
    """Verify current user is the manager of the given employee."""
    current_employee = _get_employee_or_throw()
    reports_to = frappe.db.get_value("Employee", employee_id, "reports_to")
    if reports_to != current_employee:
        roles = frappe.get_roles(frappe.session.user)
        if not any(r in roles for r in ["HR Manager", "HR User", "System Manager"]):
            frappe.throw(
                _("Permission denied. You are not the reporting manager of this employee."),
                frappe.PermissionError,
            )


def _validate_date_range(from_date, to_date):
    """Validate that from_date <= to_date and range is reasonable."""
    from frappe.utils import getdate, date_diff

    if not from_date or not to_date:
        frappe.throw(_("Both from_date and to_date are required"))

    fd = getdate(from_date)
    td = getdate(to_date)
    if fd > td:
        frappe.throw(_("from_date must be before or equal to to_date"))

    if date_diff(td, fd) > 366:
        frappe.throw(_("Date range cannot exceed 1 year"))


def _paginate(query_results, page=1, page_size=20):
    """Apply pagination to query results.

    Args:
        query_results: List of dicts from frappe.get_all or similar
        page: 1-based page number
        page_size: Number of results per page

    Returns:
        dict with 'data', 'total', 'page', 'page_size', 'total_pages'
    """
    total = len(query_results)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "data": query_results[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }
