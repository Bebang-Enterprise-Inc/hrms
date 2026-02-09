"""BEI Attendance Correction API endpoints.

Handles attendance correction requests and approvals.
Uses the built-in Frappe Attendance Request DocType.
"""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import getdate, today
from hrms.utils.api_helpers import (
    _get_employee_or_throw,
    _get_employee_details,
    _check_hr_permission,
    _check_manager_permission,
    _paginate,
)


@frappe.whitelist()
@rate_limit(limit=10, seconds=60)
def get_corrections(status=None, employee=None, page=1):
    """Get attendance correction requests.

    Args:
        status: Filter by status (Pending/Approved/Rejected)
        employee: Filter by employee ID
        page: Page number

    Returns:
        Paginated list of attendance corrections

    Access: Own requests (all), team requests (supervisor), all (HR)
    """
    current_employee = _get_employee_or_throw()
    roles = frappe.get_roles(frappe.session.user)
    is_hr = any(r in roles for r in ["HR Manager", "HR User", "System Manager"])

    page = int(page) if page else 1

    filters = {}
    if status:
        if status == "Pending":
            filters["docstatus"] = 0
        elif status == "Approved":
            filters["docstatus"] = 1
        elif status == "Rejected":
            filters["docstatus"] = 2

    if employee:
        filters["employee"] = employee
    elif not is_hr:
        # Non-HR users only see their own
        filters["employee"] = current_employee

    corrections = frappe.get_all(
        "Attendance Request",
        filters=filters,
        fields=[
            "name", "employee", "employee_name", "department",
            "from_date", "to_date", "reason", "explanation",
            "docstatus", "creation",
        ],
        order_by="creation desc",
    )

    return _paginate(corrections, page=page)


@frappe.whitelist()
@rate_limit(limit=5, seconds=60)
def submit_correction(attendance_date, correction_type, actual_time=None, reason=None):
    """Submit an attendance correction request.

    Args:
        attendance_date: Date to correct
        correction_type: Type of correction (Missing Punch, Wrong Time, etc.)
        actual_time: The correct time (optional)
        reason: Reason for correction

    Returns:
        Created request name
    """
    employee = _get_employee_or_throw()

    if not attendance_date:
        frappe.throw(_("Attendance date is required"))
    if not reason:
        frappe.throw(_("Reason is required"))

    att_date = getdate(attendance_date)
    explanation = f"Type: {correction_type or 'General'}"
    if actual_time:
        explanation += f"\nActual Time: {actual_time}"
    explanation += f"\nReason: {reason}"

    doc = frappe.get_doc({
        "doctype": "Attendance Request",
        "employee": employee,
        "from_date": att_date,
        "to_date": att_date,
        "reason": "Work From Home" if correction_type == "Remote Work" else "On Duty",
        "explanation": explanation,
    })

    doc.insert()
    frappe.db.commit()

    return {
        "message": _("Correction request submitted successfully"),
        "name": doc.name,
    }


@frappe.whitelist()
@rate_limit(limit=10, seconds=60)
def approve_correction(correction_id):
    """Approve an attendance correction request.

    Args:
        correction_id: Attendance Request name

    Returns:
        Success message

    Access: Supervisor of employee or HR
    """
    _check_hr_permission()

    if not correction_id:
        frappe.throw(_("Correction ID is required"))

    doc = frappe.get_doc("Attendance Request", correction_id)

    if doc.docstatus != 0:
        frappe.throw(_("This request has already been processed"))

    doc.submit()
    frappe.db.commit()

    return {
        "message": _("Correction request approved"),
        "name": doc.name,
    }


@frappe.whitelist()
@rate_limit(limit=10, seconds=60)
def reject_correction(correction_id, reason=None):
    """Reject an attendance correction request.

    Args:
        correction_id: Attendance Request name
        reason: Rejection reason

    Returns:
        Success message

    Access: Supervisor of employee or HR
    """
    _check_hr_permission()

    if not correction_id:
        frappe.throw(_("Correction ID is required"))

    doc = frappe.get_doc("Attendance Request", correction_id)

    if doc.docstatus != 0:
        frappe.throw(_("This request has already been processed"))

    # Add rejection reason as comment
    if reason:
        doc.add_comment("Comment", text=f"Rejected: {reason}")

    doc.add_comment("Comment", text=f"Status: Rejected by {frappe.session.user}")
    frappe.delete_doc("Attendance Request", correction_id, force=True)
    frappe.db.commit()

    return {
        "message": _("Correction request rejected"),
        "name": doc.name,
    }
