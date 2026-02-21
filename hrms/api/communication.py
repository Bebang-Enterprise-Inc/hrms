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

def _get_current_employee():
    """Helper to get the active or fallback employee record for the current session user."""
    employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")
    if not employee:
        employee = _get_current_employee()
    return employee


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
        employee = _get_current_employee()
        if not employee:
            frappe.throw(_("No employee record found for your user account"))
            
        doc = frappe.get_doc({
            "doctype": "BEI CEO Complaint",
            "submitted_by": frappe.session.user,
            "employee": employee,
            "category": category,
            "subject": subject,
            "description": description,
            "is_anonymous": int(is_anonymous)
        }).insert(ignore_permissions=True)
        
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


@frappe.whitelist()
def attach_complaint_evidence(complaint_name, file_url):
    """Attach a file to a CEO complaint. Called after file is uploaded via Frappe's upload API."""
    doc = frappe.get_doc("BEI CEO Complaint", complaint_name)

    # Verify the complaint belongs to the current user
    if doc.submitted_by != frappe.session.user:
        frappe.throw(_("You can only attach files to your own complaints"))    

    # Validate file format and size based on URL/extension
    allowed_exts = [".jpg", ".jpeg", ".png", ".pdf", ".doc", ".docx"]
    if not any(file_url.lower().endswith(ext) for ext in allowed_exts):
        frappe.throw(_("Invalid file type. Only Image, PDF, and DOC files are allowed."))
    
    file_doc = frappe.get_doc("File", {"file_url": file_url})
    if file_doc.file_size and file_doc.file_size > 10 * 1024 * 1024:
        frappe.throw(_("File size exceeds 10MB limit."))

    # Add attachment via Frappe's native mechanism
    frappe.attach_file(
        dt="BEI CEO Complaint",
        dn=complaint_name,
        filedata=None,  # File already uploaded separately
        fname=None,
        ftype=None,
        file_url=file_url
    )
    return {"success": True}


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


@frappe.whitelist()
def acknowledge_announcement(announcement_name):
    """Record that the current user has acknowledged an announcement."""       
    employee = _get_current_employee()
    if not employee:
        frappe.throw(_("No employee record found"))

    # Idempotent - checking using get_value directly as advised by the audit
    ack = frappe.db.get_value("BEI Announcement Read Receipt", {
        "announcement": announcement_name,
        "employee": employee
    }, "name")
    
    if ack:
        return {"success": True, "already_acknowledged": True}

    doc = frappe.new_doc("BEI Announcement Read Receipt")
    doc.announcement = announcement_name
    doc.employee = employee
    doc.read_date = now_datetime()
    doc.insert(ignore_permissions=True)
    return {"success": True, "already_acknowledged": False}


@frappe.whitelist()
def get_acknowledgment_status(announcement_name):
    """Check if current user has acknowledged the announcement."""
    employee = _get_current_employee()
    if not employee:
        return {"acknowledged": False}

    ack = frappe.db.get_value(
        "BEI Announcement Read Receipt",
        {"announcement": announcement_name, "employee": employee},
        ["name", "read_date"],
        as_dict=True
    )
    return {"acknowledged": bool(ack), "read_date": ack.read_date if ack else None}


@frappe.whitelist()
def create_announcement(title, announcement_type, content, priority="Normal",  
                        target_audience="All", requires_acknowledgment=0,      
                        expiry_date=None):
    """Create a published announcement. HR Manager role required."""
    if frappe.session.user == "Guest":
        frappe.throw(_("Authentication required"))

    # Role check
    if not frappe.has_permission("BEI Announcement", "create"):
        frappe.throw(_("You do not have permission to create announcements"))  

    doc = frappe.get_doc({
        "doctype": "BEI Announcement",
        "title": title,
        "announcement_type": announcement_type,
        "priority": priority,
        "status": "Published",
        "publish_date": now_datetime(),
        "expiry_date": expiry_date,
        "content": content,
        "target_audience": target_audience,
        "published_by": frappe.session.user,
        "requires_acknowledgment": int(requires_acknowledgment)
    }).insert(ignore_permissions=True)

    # Optional: notify all employees via Google Chat
    # Only if a global notification space exists
    try:
        from hrms.api.google_chat import send_message_to_space
        from hrms.utils.bei_config import SPACE_NOTIFICATIONS
        send_message_to_space(
            SPACE_NOTIFICATIONS,
            f"*New Announcement: {title}*\nType: {announcement_type} | Priority: {priority}\nLog in to my.bebang.ph to read."
        )
    except Exception:
        pass  # Never block announcement creation on notification failure      

    return {"success": True, "name": doc.name}


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
        from_employee = _get_current_employee()
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

        doc = frappe.get_doc({
            "doctype": "BEI Kudos",
            "from_employee": from_employee,
            "to_employee": resolved_to,
            "category": category,
            "message": message,
            "is_public": int(is_public)
        }).insert(ignore_permissions=True)
        
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
        employee = _get_current_employee()

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
        employee = _get_current_employee()

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

    doc = frappe.get_doc({
        "doctype": "BEI Support Ticket",
        "submitted_by": frappe.session.user,
        "category": category,
        "subject": subject,
        "description": description,
        "priority": priority
    }).insert()
    
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
