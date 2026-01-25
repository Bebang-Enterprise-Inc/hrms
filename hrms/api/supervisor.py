# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Supervisor Tools API
Handles approval queues, store visits, labor planning, and team management
"""

import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, add_days, get_time
import json


# ==============================================================================
# APPROVAL QUEUE
# ==============================================================================


@frappe.whitelist()
def get_pending_approvals(approver=None):
    """Get pending items for an approver."""
    if not approver:
        approver = frappe.session.user

    approvals = frappe.get_all(
        "BEI Approval Queue",
        filters={"assigned_approver": approver, "status": "Pending"},
        fields=[
            "name", "reference_doctype", "reference_name", "store",
            "submitted_by", "submitted_at", "priority"
        ],
        order_by="priority desc, submitted_at asc"
    )
    return {"approvals": approvals}


@frappe.whitelist()
def approve_item(queue_name, notes=None):
    """Approve an item in the queue."""
    doc = frappe.get_doc("BEI Approval Queue", queue_name)
    doc.status = "Approved"
    doc.approved_by = frappe.session.user
    doc.approved_at = now_datetime()
    doc.save()

    # Also update the referenced document if it has status field
    try:
        ref_doc = frappe.get_doc(doc.reference_doctype, doc.reference_name)
        if hasattr(ref_doc, 'status'):
            ref_doc.status = "Approved"
            if hasattr(ref_doc, 'approved_by'):
                ref_doc.approved_by = frappe.session.user
            if hasattr(ref_doc, 'approved_at'):
                ref_doc.approved_at = now_datetime()
            ref_doc.save()
    except Exception:
        pass  # Reference document may not exist

    return {"success": True, "message": f"Approved {queue_name}"}


@frappe.whitelist()
def reject_item(queue_name, reason):
    """Reject an item in the queue."""
    if not reason:
        frappe.throw(_("Rejection reason is required"))

    doc = frappe.get_doc("BEI Approval Queue", queue_name)
    doc.status = "Rejected"
    doc.approved_by = frappe.session.user
    doc.approved_at = now_datetime()
    doc.rejection_reason = reason
    doc.save()
    return {"success": True, "message": f"Rejected {queue_name}"}


@frappe.whitelist()
def escalate_item(queue_name, escalate_to):
    """Escalate an item to another approver."""
    doc = frappe.get_doc("BEI Approval Queue", queue_name)
    doc.status = "Escalated"
    doc.assigned_approver = escalate_to
    doc.save()
    return {"success": True, "message": f"Escalated to {escalate_to}"}


# ==============================================================================
# STORE VISITS
# ==============================================================================


@frappe.whitelist()
def create_store_visit(store, visit_type, audit_items, score_funds=None,
                       score_stocks=None, score_organization=None,
                       score_staffing=None, score_coaching=None,
                       critical_findings=None, action_items=None,
                       follow_up_date=None, photos=None,
                       store_supervisor_present=None):
    """Create a store visit report with 100-point scoring."""
    if not store:
        frappe.throw(_("Store is required"))

    if isinstance(audit_items, str):
        audit_items = json.loads(audit_items)
    if isinstance(photos, str):
        photos = json.loads(photos)

    doc = frappe.new_doc("BEI Store Visit Report")
    doc.store = store
    doc.visit_date = nowdate()
    doc.visit_type = visit_type
    doc.visited_by = frappe.session.user
    doc.store_supervisor_present = store_supervisor_present
    doc.critical_findings = critical_findings
    doc.action_items = action_items
    doc.follow_up_date = follow_up_date

    # Scoring (each max 20, total 100)
    doc.score_funds = int(score_funds) if score_funds else 0
    doc.score_stocks = int(score_stocks) if score_stocks else 0
    doc.score_organization = int(score_organization) if score_organization else 0
    doc.score_staffing = int(score_staffing) if score_staffing else 0
    doc.score_coaching = int(score_coaching) if score_coaching else 0

    for item in audit_items:
        doc.append("audit_items", item)

    if photos:
        for photo in photos:
            doc.append("photos", photo)

    doc.status = "Submitted"
    doc.insert()
    return {"success": True, "name": doc.name, "score": doc.overall_score, "grade": doc.overall_grade}


@frappe.whitelist()
def get_store_visits(store=None, visited_by=None, date_from=None, date_to=None, limit=20):
    """Get store visit history."""
    filters = {}
    if store:
        filters["store"] = store
    if visited_by:
        filters["visited_by"] = visited_by
    if date_from:
        filters["visit_date"] = [">=", date_from]
    if date_to:
        if "visit_date" in filters:
            filters["visit_date"] = ["between", [date_from, date_to]]
        else:
            filters["visit_date"] = ["<=", date_to]

    visits = frappe.get_all(
        "BEI Store Visit Report",
        filters=filters,
        fields=["name", "store", "visit_date", "visit_type", "overall_score", "overall_grade", "status"],
        order_by="visit_date desc",
        limit=int(limit)
    )
    return {"visits": visits}


@frappe.whitelist()
def get_visit_detail(visit_name):
    """Get full details of a store visit."""
    doc = frappe.get_doc("BEI Store Visit Report", visit_name)
    return {"visit": doc.as_dict()}


@frappe.whitelist()
def acknowledge_visit(visit_name):
    """Acknowledge a store visit report."""
    doc = frappe.get_doc("BEI Store Visit Report", visit_name)
    doc.status = "Acknowledged"
    doc.save()
    return {"success": True}


# ==============================================================================
# WEEKLY LABOR PLANNING
# ==============================================================================


@frappe.whitelist()
def create_weekly_plan(store, week_start, shifts, labor_budget=None):
    """Create a weekly labor plan."""
    if not store:
        frappe.throw(_("Store is required"))

    if isinstance(shifts, str):
        shifts = json.loads(shifts)

    doc = frappe.new_doc("BEI Weekly Labor Plan")
    doc.store = store
    doc.week_start_date = week_start
    doc.week_end_date = add_days(week_start, 6)
    doc.planned_by = frappe.session.user
    doc.labor_budget = float(labor_budget) if labor_budget else 0

    total_hours = 0
    for shift in shifts:
        row = doc.append("shifts", shift)
        # Calculate hours
        if shift.get("shift_start") and shift.get("shift_end"):
            start = get_time(shift["shift_start"])
            end = get_time(shift["shift_end"])
            hours = (end.hour * 60 + end.minute - start.hour * 60 - start.minute) / 60
            if hours < 0:
                hours += 24  # Handle overnight shifts
            row.hours = hours
            total_hours += hours

    doc.total_hours = total_hours
    doc.insert()
    return {"success": True, "name": doc.name, "total_hours": total_hours}


@frappe.whitelist()
def get_weekly_plan(store=None, week_start=None):
    """Get weekly labor plan for a store."""
    if not store or not week_start:
        return {"plan": None}
    plans = frappe.get_all(
        "BEI Weekly Labor Plan",
        filters={"store": store, "week_start_date": week_start},
        fields=["name", "status", "total_hours", "planned_by"]
    )

    if plans:
        doc = frappe.get_doc("BEI Weekly Labor Plan", plans[0].name)
        return {"plan": doc.as_dict()}
    return {"plan": None}


@frappe.whitelist()
def update_weekly_plan(plan_name, shifts):
    """Update shifts in a weekly plan."""
    if isinstance(shifts, str):
        shifts = json.loads(shifts)

    doc = frappe.get_doc("BEI Weekly Labor Plan", plan_name)
    doc.shifts = []

    total_hours = 0
    for shift in shifts:
        row = doc.append("shifts", shift)
        if shift.get("shift_start") and shift.get("shift_end"):
            start = get_time(shift["shift_start"])
            end = get_time(shift["shift_end"])
            hours = (end.hour * 60 + end.minute - start.hour * 60 - start.minute) / 60
            if hours < 0:
                hours += 24
            row.hours = hours
            total_hours += hours

    doc.total_hours = total_hours
    doc.save()
    return {"success": True, "total_hours": total_hours}


@frappe.whitelist()
def approve_weekly_plan(plan_name):
    """Approve a weekly labor plan."""
    doc = frappe.get_doc("BEI Weekly Labor Plan", plan_name)
    doc.status = "Approved"
    doc.approved_by = frappe.session.user
    doc.save()
    return {"success": True}


# ==============================================================================
# TEAM MANAGEMENT
# ==============================================================================


@frappe.whitelist()
def get_my_team():
    """Get employees who report to current user."""
    user_employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
    if not user_employee:
        return {"team": []}

    team = frappe.get_all(
        "Employee",
        filters={"reports_to": user_employee, "status": "Active"},
        fields=["name", "employee_name", "designation", "branch", "user_id", "image"]
    )
    return {"team": team}


@frappe.whitelist()
def get_team_attendance(date=None):
    """Get attendance overview for team."""
    if not date:
        date = nowdate()

    user_employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
    if not user_employee:
        return {"attendance": []}

    # Get team members
    team = frappe.get_all(
        "Employee",
        filters={"reports_to": user_employee, "status": "Active"},
        fields=["name", "employee_name"]
    )

    attendance = []
    for member in team:
        # Get latest checkin for the day
        checkins = frappe.get_all(
            "Employee Checkin",
            filters={"employee": member.name, "time": ["like", f"{date}%"]},
            fields=["time", "log_type"],
            order_by="time asc"
        )

        attendance.append({
            "employee": member.name,
            "employee_name": member.employee_name,
            "checkins": checkins,
            "status": "Present" if checkins else "Absent"
        })

    return {"date": date, "attendance": attendance}
