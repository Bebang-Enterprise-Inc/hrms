"""S170 — Employee-facing OT filing API.

Lets crew/supervisor/HR users file `BEI Overtime Request` records via the
`/dashboard/hr/overtime/apply` page. The existing `/dashboard/hr/overtime`
page is approval-only (admins reviewing pending requests); there was no
employee-side filing UI before this sprint, so OT could only be created by
system_detected attendance hooks or manager_validated entries.

Security:
- Employee is resolved server-side from `frappe.session.user` (never trust
  a client-supplied employee id).
- attendance_date must be within the last 7 days (no back-filing older OT).
- overtime_hours must be 0.5..12.
- An existing `Attendance` record on that date is required because the OT
  doctype links to it. If none exists, the API errors with a clear message.
"""
from __future__ import annotations

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

from hrms.utils.sentry import set_backend_observability_context


@frappe.whitelist()
def create_overtime_request(
    attendance_date: str,
    overtime_hours: float,
    reason_category: str,
    overtime_reason: str,
    shift: str | None = None,
) -> dict:
    """Create a BEI Overtime Request for the current user's employee.

    `employee` is resolved server-side from session — never accepted as a
    parameter to prevent spoofing one employee filing OT for another.
    """
    set_backend_observability_context(
        module="overtime",
        action="create_overtime_request",
        mutation_type="create",
    )

    # Permission gate
    frappe.has_permission("BEI Overtime Request", "create", throw=True)

    # Resolve current user → employee
    employee = frappe.db.get_value(
        "Employee", {"user_id": frappe.session.user}, "name"
    )
    if not employee:
        frappe.throw(
            _("No Employee record linked to user {0}").format(frappe.session.user)
        )

    # Validate attendance_date window (within last 7 days, not future)
    parsed_date = getdate(attendance_date)
    today = getdate(nowdate())
    if parsed_date > today:
        frappe.throw(_("Cannot file overtime for a future date."))
    if parsed_date < today - timedelta(days=7):
        frappe.throw(
            _("Overtime can only be filed for the last 7 days. Date {0} is too old.").format(
                attendance_date
            )
        )

    # Validate overtime_hours
    try:
        ot_hours = float(overtime_hours)
    except (TypeError, ValueError):
        frappe.throw(_("overtime_hours must be a number."))
    if ot_hours < 0.5 or ot_hours > 12:
        frappe.throw(_("overtime_hours must be between 0.5 and 12."))

    if not (overtime_reason or "").strip():
        frappe.throw(_("Please provide a reason for the overtime request."))

    # Find the matching Attendance record (BEI Overtime Request requires it)
    attendance_name = frappe.db.get_value(
        "Attendance",
        {
            "employee": employee,
            "attendance_date": attendance_date,
            "docstatus": ["!=", 2],
        },
        "name",
        order_by="modified desc",
    )
    if not attendance_name:
        frappe.throw(
            _(
                "No attendance record found on {0}. Overtime can only be filed for "
                "days you actually worked."
            ).format(attendance_date)
        )

    # Insert the OT request as Pending Review with employee_submitted source
    doc = frappe.get_doc(
        {
            "doctype": "BEI Overtime Request",
            "employee": employee,
            "attendance": attendance_name,
            "attendance_date": attendance_date,
            "shift": shift,
            "overtime_hours": ot_hours,
            "overtime_status": "Pending Review",
            "request_source": "employee_submitted",
            "reason_category": reason_category,
            "employee_explanation": overtime_reason.strip(),
        }
    )
    doc.flags.ignore_permissions = True
    doc.insert()
    frappe.db.commit()

    return {
        "name": doc.name,
        "employee": doc.employee,
        "attendance_date": doc.attendance_date,
        "overtime_hours": float(doc.overtime_hours or 0),
        "overtime_status": doc.overtime_status,
    }
