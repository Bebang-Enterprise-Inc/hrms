# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Communication API
Handles CEO complaints, announcements, kudos, and support tickets
"""

import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime
import json


# ==============================================================================
# CEO COMPLAINTS
# ==============================================================================


@frappe.whitelist()
def submit_ceo_complaint(category=None, subject=None, description=None, is_anonymous=False):
    """Submit a complaint to the CEO.

    Bug fix (C12):
    - Employee lookup fallback without status filter
    - insert with ignore_permissions=True
    - Returns user-friendly error instead of raw traceback
    """
    if not category or not subject or not description:
        frappe.throw(_("Category, subject, and description are required"))

    try:
        doc = frappe.new_doc("BEI CEO Complaint")
        doc.submitted_by = frappe.session.user
        employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")
        if not employee:
            # Fallback: try without status filter
            employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
        if not employee:
            frappe.throw(_("No employee record found for your user account"))
        doc.employee = employee
        doc.category = category
        doc.subject = subject
        doc.description = description
        doc.is_anonymous = 1 if is_anonymous else 0
        doc.insert(ignore_permissions=True)
        return {"success": True, "name": doc.name}

    except Exception as e:
        frappe.log_error(
            f"CEO Complaint Error: {str(e)}\n\n{frappe.get_traceback()}",
            "CEO Complaint Submission Error"
        )
        return {"success": False, "error": _("Failed to submit complaint. Please try again or contact support.")}


@frappe.whitelist()
def get_my_complaints(limit=20):
    """Get complaints submitted by current user."""
    complaints = frappe.get_all(
        "BEI CEO Complaint",
        filters={"submitted_by": frappe.session.user},
        fields=["name", "category", "subject", "status", "submission_date"],
        order_by="submission_date desc",
        limit=int(limit)
    )
    return {"complaints": complaints}


@frappe.whitelist()
def get_complaint_status(complaint_name):
    """Get status of a complaint."""
    doc = frappe.get_doc("BEI CEO Complaint", complaint_name)
    return {
        "status": doc.status,
        "response": doc.ceo_response if doc.status in ["Resolved", "Closed"] else None,
        "resolved_date": doc.resolved_date
    }


# ==============================================================================
# ANNOUNCEMENTS
# ==============================================================================


@frappe.whitelist()
def get_announcements(limit=20):
    """Get announcements for current user."""
    filters = [
        ["status", "=", "Published"],
        ["publish_date", "<=", now_datetime()]
    ]

    announcements = frappe.get_all(
        "BEI Announcement",
        filters=filters,
        fields=[
            "name", "title", "announcement_type", "publish_date",
            "priority", "requires_acknowledgment"
        ],
        order_by="priority desc, publish_date desc",
        limit=int(limit)
    )
    return {"announcements": announcements}


@frappe.whitelist()
def get_announcement_detail(announcement_name):
    """Get full announcement content."""
    doc = frappe.get_doc("BEI Announcement", announcement_name)
    return {"announcement": doc.as_dict()}


@frappe.whitelist()
def get_unread_announcements():
    """Get count of unread announcements requiring acknowledgment."""
    count = frappe.db.count(
        "BEI Announcement",
        filters={"status": "Published", "requires_acknowledgment": 1}
    )
    return {"count": count}


# ==============================================================================
# KUDOS
# ==============================================================================


@frappe.whitelist()
def send_kudos(to_employee=None, category=None, message=None, is_public=True):
    """Send kudos to another employee.

    Bug fix (C11):
    - Resolve to_employee from name/email if not an Employee ID
    - insert with ignore_permissions=True (Employee role has create but may fail on save)
    - Returns user-friendly error instead of raw traceback
    """
    if not to_employee or not category or not message:
        frappe.throw(_("Recipient, category, and message are required"))

    try:
        from_employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")
        if not from_employee:
            # Fallback: try without status filter
            from_employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
        if not from_employee:
            frappe.throw(_("You must be an employee to send kudos"))

        # Resolve to_employee - frontend may send employee name or email
        resolved_to = to_employee
        if not frappe.db.exists("Employee", to_employee):
            # Try by employee_name
            emp = frappe.db.get_value("Employee", {"employee_name": to_employee, "status": "Active"}, "name")
            if emp:
                resolved_to = emp
            else:
                # Try by user_id (email)
                emp = frappe.db.get_value("Employee", {"user_id": to_employee, "status": "Active"}, "name")
                if emp:
                    resolved_to = emp

        if from_employee == resolved_to:
            frappe.throw(_("You cannot send kudos to yourself"))

        doc = frappe.new_doc("BEI Kudos")
        doc.from_employee = from_employee
        doc.to_employee = resolved_to
        doc.category = category
        doc.message = message
        doc.is_public = 1 if is_public else 0
        doc.insert(ignore_permissions=True)
        return {"success": True, "name": doc.name}

    except Exception as e:
        frappe.log_error(
            f"Kudos Error: {str(e)}\n\n{frappe.get_traceback()}",
            "Kudos Submission Error"
        )
        return {"success": False, "error": _("Failed to send kudos. Please try again or contact support.")}


@frappe.whitelist()
def get_received_kudos(employee=None, limit=20):
    """Get kudos received by an employee."""
    if not employee:
        employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")

    if not employee:
        return {"kudos": []}

    kudos = frappe.get_all(
        "BEI Kudos",
        filters={"to_employee": employee, "status": ["in", ["Active", "Featured"]]},
        fields=["name", "from_employee", "category", "message", "kudos_date", "points"],
        order_by="kudos_date desc",
        limit=int(limit)
    )

    # Get from_employee names
    for k in kudos:
        k["from_employee_name"] = frappe.db.get_value("Employee", k["from_employee"], "employee_name")

    return {"kudos": kudos}


@frappe.whitelist()
def get_sent_kudos(employee=None, limit=20):
    """Get kudos sent by an employee."""
    if not employee:
        employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")

    if not employee:
        return {"kudos": []}

    kudos = frappe.get_all(
        "BEI Kudos",
        filters={"from_employee": employee},
        fields=["name", "to_employee", "category", "message", "kudos_date"],
        order_by="kudos_date desc",
        limit=int(limit)
    )

    # Get to_employee names
    for k in kudos:
        k["to_employee_name"] = frappe.db.get_value("Employee", k["to_employee"], "employee_name")

    return {"kudos": kudos}


@frappe.whitelist()
def get_kudos_leaderboard(period="month"):
    """Get kudos leaderboard."""
    sql = """
        SELECT to_employee, COUNT(*) as count, SUM(points) as total_points
        FROM `tabBEI Kudos`
        WHERE status IN ('Active', 'Featured')
        GROUP BY to_employee
        ORDER BY total_points DESC
        LIMIT 10
    """
    leaders = frappe.db.sql(sql, as_dict=True)

    # Get employee names
    for leader in leaders:
        leader["employee_name"] = frappe.db.get_value("Employee", leader["to_employee"], "employee_name")

    return {"leaderboard": leaders}


# ==============================================================================
# SUPPORT TICKETS
# ==============================================================================


@frappe.whitelist()
def create_support_ticket(category=None, subject=None, description=None, priority="Medium"):
    """Create a support ticket."""
    if not category or not subject or not description:
        frappe.throw(_("Category, subject, and description are required"))

    doc = frappe.new_doc("BEI Support Ticket")
    doc.submitted_by = frappe.session.user
    doc.category = category
    doc.subject = subject
    doc.description = description
    doc.priority = priority
    doc.insert()
    return {"success": True, "name": doc.name}


@frappe.whitelist()
def get_my_tickets(status=None, limit=20):
    """Get support tickets for current user."""
    filters = {"submitted_by": frappe.session.user}
    if status:
        filters["status"] = status

    tickets = frappe.get_all(
        "BEI Support Ticket",
        filters=filters,
        fields=["name", "category", "subject", "priority", "status", "submission_date"],
        order_by="submission_date desc",
        limit=int(limit)
    )
    return {"tickets": tickets}
