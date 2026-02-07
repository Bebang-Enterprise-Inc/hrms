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
def submit_ceo_complaint(category, subject, description, is_anonymous=False):
    """Submit a complaint to the CEO."""
    doc = frappe.new_doc("BEI CEO Complaint")
    doc.submitted_by = frappe.session.user
    employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
    if not employee:
        frappe.throw(_("No employee record found for your user account"))
    doc.employee = employee
    doc.category = category
    doc.subject = subject
    doc.description = description
    doc.is_anonymous = 1 if is_anonymous else 0
    doc.insert()
    return {"success": True, "name": doc.name}


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
def send_kudos(to_employee, category, message, is_public=True):
    """Send kudos to another employee."""
    from_employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
    if not from_employee:
        frappe.throw(_("You must be an employee to send kudos"))
    if from_employee == to_employee:
        frappe.throw(_("You cannot send kudos to yourself"))

    doc = frappe.new_doc("BEI Kudos")
    doc.from_employee = from_employee
    doc.to_employee = to_employee
    doc.category = category
    doc.message = message
    doc.is_public = 1 if is_public else 0
    doc.insert()
    return {"success": True, "name": doc.name}


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
def create_support_ticket(category, subject, description, priority="Medium"):
    """Create a support ticket."""
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
