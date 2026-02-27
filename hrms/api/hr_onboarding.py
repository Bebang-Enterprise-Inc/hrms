# Copyright (c) 2026, Bebang Enterprise Inc.
# For license information, please see license.txt

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, nowdate


HR_ONBOARDING_ALLOWED_ROLES = {"System Manager", "HR Manager", "HR User"}


def _check_hr_permission() -> None:
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection(HR_ONBOARDING_ALLOWED_ROLES):
        frappe.throw(_("You don't have permission to access HR onboarding actions."), frappe.PermissionError)


def _as_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return parsed if parsed > 0 else default


@frappe.whitelist()
def get_job_offers(status=None, department=None, page=1, page_size=20):
    _check_hr_permission()

    page = _as_int(page, 1)
    page_size = min(_as_int(page_size, 20), 100)
    start = (page - 1) * page_size

    where = []
    values: dict[str, Any] = {"start": start, "page_size": page_size}

    if status:
        where.append("jo.status = %(status)s")
        values["status"] = status
    if department:
        where.append("ja.department = %(department)s")
        values["department"] = department

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    total = frappe.db.sql(
        f"""
        SELECT COUNT(*)
        FROM `tabJob Offer` jo
        LEFT JOIN `tabJob Applicant` ja ON ja.name = jo.job_applicant
        {where_sql}
        """,
        values,
    )[0][0]

    rows = frappe.db.sql(
        f"""
        SELECT
            jo.name,
            jo.applicant_name,
            jo.designation,
            jo.company,
            jo.offer_date,
            jo.status,
            jo.job_applicant,
            COALESCE(ja.department, '') AS department
        FROM `tabJob Offer` jo
        LEFT JOIN `tabJob Applicant` ja ON ja.name = jo.job_applicant
        {where_sql}
        ORDER BY jo.creation DESC
        LIMIT %(start)s, %(page_size)s
        """,
        values,
        as_dict=True,
    )

    return {
        "data": rows,
        "total": cint(total),
        "page": page,
        "page_size": page_size,
    }


@frappe.whitelist()
def update_job_offer_status(name: str, status: str, notes: str | None = None):
    _check_hr_permission()

    if not name:
        frappe.throw(_("Job Offer is required."))
    if status not in {"Accepted", "Rejected"}:
        frappe.throw(_("Status must be either Accepted or Rejected."))

    offer = frappe.get_doc("Job Offer", name)
    offer.status = status
    offer.save(ignore_permissions=True)

    if notes:
        offer.add_comment("Comment", _("Offer status note: {0}").format(notes))

    if offer.job_applicant:
        applicant_status = "Accepted" if status == "Accepted" else "Rejected"
        frappe.db.set_value("Job Applicant", offer.job_applicant, "status", applicant_status)

    return {"success": True, "name": offer.name, "status": offer.status}


@frappe.whitelist()
def create_onboarding_from_offer(job_offer: str):
    _check_hr_permission()

    if not job_offer:
        frappe.throw(_("Job Offer is required."))

    offer = frappe.get_doc("Job Offer", job_offer)
    if offer.status != "Accepted":
        frappe.throw(_("Only accepted offers can create onboarding checklists."))

    existing = frappe.db.exists(
        "Employee Onboarding",
        {"job_offer": offer.name, "docstatus": ("!=", 2)},
    )
    if existing:
        return {"success": True, "onboarding_name": existing, "already_exists": True}

    onboarding = frappe.get_doc(
        {
            "doctype": "Employee Onboarding",
            "job_applicant": offer.job_applicant,
            "job_offer": offer.name,
            "employee_name": offer.applicant_name,
            "company": offer.company,
            "designation": offer.designation,
            "date_of_joining": nowdate(),
            "boarding_begins_on": nowdate(),
            "boarding_status": "Pending",
        }
    )
    onboarding.insert(ignore_permissions=True)

    return {"success": True, "onboarding_name": onboarding.name, "already_exists": False}


def _normalize_boarding_status(value: str | None) -> str:
    if value == "In Process":
        return "In Progress"
    return value or "Pending"


def _is_task_completed(task_name: str | None) -> bool:
    if not task_name:
        return False
    status = frappe.db.get_value("Task", task_name, "status")
    return status in {"Completed", "Cancelled"}


@frappe.whitelist()
def get_onboarding_checklist(employee_onboarding: str):
    _check_hr_permission()

    if not employee_onboarding:
        frappe.throw(_("employee_onboarding is required."))

    onboarding = frappe.get_doc("Employee Onboarding", employee_onboarding)
    activities = []
    completed_count = 0

    for row in onboarding.activities or []:
        completed = _is_task_completed(getattr(row, "task", None))
        if completed:
            completed_count += 1
        activities.append(
            {
                "activity_name": getattr(row, "activity_name", ""),
                "required": cint(getattr(row, "required_for_employee_creation", 0)) == 1,
                "completed": completed,
                "task": getattr(row, "task", ""),
                "description": getattr(row, "description", "") or "",
                "assigned_to": getattr(row, "user", "") or getattr(row, "role", "") or "",
            }
        )

    total = len(activities)
    progress = round((completed_count / total) * 100, 2) if total else 0

    return {
        "name": onboarding.name,
        "applicant_name": onboarding.employee_name,
        "designation": onboarding.designation,
        "department": onboarding.department,
        "company": onboarding.company,
        "boarding_status": _normalize_boarding_status(onboarding.boarding_status),
        "job_offer": onboarding.job_offer,
        "progress": progress,
        "total_activities": total,
        "completed_activities": completed_count,
        "activities": activities,
    }

