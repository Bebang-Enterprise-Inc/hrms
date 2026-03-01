"""
HR onboarding bridge API for the my.bebang.ph portal.

This module intentionally stays orchestration-focused:
- Recruitment offer queue operations
- Offer status transitions
- Offer -> Employee Onboarding bridge
- Checklist read model for onboarding detail page
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, nowdate


HR_ONBOARDING_ROLES = {"HR Manager", "HR User", "System Manager"}
VALID_OFFER_STATUSES = {"Accepted", "Rejected"}


def _check_hr_onboarding_access():
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection(HR_ONBOARDING_ROLES):
        frappe.throw(_("Only HR users can access recruitment onboarding endpoints."), frappe.PermissionError)


def _normalize_page(page, page_size):
    page = cint(page) if page else 1
    page_size = cint(page_size) if page_size else 20

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 100:
        page_size = 100

    return page, page_size, (page - 1) * page_size


def _resolve_template(company=None, department=None, designation=None):
    if not frappe.db.exists("DocType", "Employee Onboarding Template"):
        return None

    strict_filters = {}
    if company:
        strict_filters["company"] = company
    if department:
        strict_filters["department"] = department
    if designation:
        strict_filters["designation"] = designation

    if strict_filters:
        strict_match = frappe.db.get_value("Employee Onboarding Template", strict_filters, "name")
        if strict_match:
            return strict_match

    if company:
        company_match = frappe.db.get_value(
            "Employee Onboarding Template",
            {"company": company},
            "name",
            order_by="modified desc",
        )
        if company_match:
            return company_match

    return frappe.db.get_value("Employee Onboarding Template", {}, "name", order_by="modified desc")


@frappe.whitelist()
def get_job_offers(status=None, department=None, page=1, page_size=20):
    """Paginated job-offer list for HR recruitment offers page."""
    _check_hr_onboarding_access()
    page, page_size, offset = _normalize_page(page, page_size)

    conditions = ["1=1"]
    params = {"limit": page_size, "offset": offset}

    if status:
        conditions.append("jo.status = %(status)s")
        params["status"] = status

    if department:
        conditions.append("opening.department = %(department)s")
        params["department"] = department

    where = " AND ".join(conditions)

    rows = frappe.db.sql(
        f"""
        SELECT
            jo.name,
            jo.applicant_name,
            jo.designation,
            COALESCE(opening.department, '') AS department,
            jo.company,
            jo.offer_date,
            jo.status,
            jo.job_applicant
        FROM `tabJob Offer` jo
        LEFT JOIN `tabJob Applicant` ja ON ja.name = jo.job_applicant
        LEFT JOIN `tabJob Opening` opening ON opening.name = ja.job_title
        WHERE {where}
        ORDER BY jo.offer_date DESC, jo.creation DESC
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        params,
        as_dict=True,
    )

    total = frappe.db.sql(
        f"""
        SELECT COUNT(jo.name) AS total
        FROM `tabJob Offer` jo
        LEFT JOIN `tabJob Applicant` ja ON ja.name = jo.job_applicant
        LEFT JOIN `tabJob Opening` opening ON opening.name = ja.job_title
        WHERE {where}
        """,
        params,
        as_dict=True,
    )[0].total

    return {
        "data": rows,
        "total": cint(total),
        "page": page,
        "page_size": page_size,
    }


@frappe.whitelist()
def get_onboarding_checklist(employee_onboarding=None, job_offer=None):
    """Return onboarding checklist read model for detail page."""
    _check_hr_onboarding_access()

    onboarding_name = None
    if employee_onboarding:
        onboarding_name = frappe.db.get_value("Employee Onboarding", employee_onboarding, "name")
    elif job_offer:
        onboarding_name = frappe.db.get_value(
            "Employee Onboarding",
            {"job_offer": job_offer, "docstatus": ["!=", 2]},
            "name",
            order_by="creation desc",
        )

    if not onboarding_name:
        frappe.throw(_("Employee onboarding record not found."))

    onboarding_doc = frappe.get_doc("Employee Onboarding", onboarding_name)
    job_offer_name = onboarding_doc.job_offer or job_offer

    offer_meta = {}
    if job_offer_name and frappe.db.exists("Job Offer", job_offer_name):
        offer_meta = frappe.db.get_value(
            "Job Offer",
            job_offer_name,
            ["applicant_name", "designation", "company"],
            as_dict=True,
        ) or {}

    activities = []
    completed_activities = 0
    total_activities = len(onboarding_doc.get("activities", []))

    for row in onboarding_doc.get("activities", []):
        task_name = row.get("task")
        completed = False
        if task_name and frappe.db.exists("Task", task_name):
            completed = frappe.db.get_value("Task", task_name, "status") == "Completed"
        elif onboarding_doc.boarding_status == "Completed":
            completed = True

        if completed:
            completed_activities += 1

        activities.append(
            {
                "activity_name": row.get("activity_name") or "",
                "required": bool(row.get("required_for_employee_creation")),
                "completed": completed,
                "task": task_name or "",
                "description": row.get("description") or "",
                "assigned_to": row.get("user") or row.get("role") or "",
            }
        )

    if total_activities:
        progress = round((completed_activities / total_activities) * 100, 1)
    else:
        progress = 100.0 if onboarding_doc.boarding_status == "Completed" else 0.0

    return {
        "name": onboarding_doc.name,
        "applicant_name": onboarding_doc.employee_name or offer_meta.get("applicant_name") or "",
        "designation": onboarding_doc.designation or offer_meta.get("designation") or "",
        "department": onboarding_doc.department or "",
        "company": onboarding_doc.company or offer_meta.get("company") or "",
        "boarding_status": onboarding_doc.boarding_status or "Pending",
        "job_offer": onboarding_doc.job_offer or "",
        "progress": progress,
        "total_activities": total_activities,
        "completed_activities": completed_activities,
        "activities": activities,
    }


@frappe.whitelist()
def update_job_offer_status(name=None, status=None, notes=None):
    """Update job-offer status and mirror applicant stage."""
    _check_hr_onboarding_access()

    if not name:
        frappe.throw(_("Job Offer name is required."))
    if status not in VALID_OFFER_STATUSES:
        frappe.throw(_("Invalid status. Allowed statuses: Accepted, Rejected."))

    offer = frappe.get_doc("Job Offer", name)
    offer.status = status
    offer.save(ignore_permissions=True)

    applicant_status = "Accepted" if status == "Accepted" else "Rejected"
    if offer.job_applicant and frappe.db.exists("Job Applicant", offer.job_applicant):
        frappe.db.set_value("Job Applicant", offer.job_applicant, "status", applicant_status)

    if notes:
        offer.add_comment("Comment", text=f"{status} by {frappe.session.user}: {notes}")

    return {"success": True, "name": offer.name, "status": offer.status}


@frappe.whitelist()
def create_onboarding_from_offer(job_offer=None):
    """Create Employee Onboarding from an accepted Job Offer (idempotent)."""
    _check_hr_onboarding_access()

    if not job_offer:
        frappe.throw(_("job_offer is required."))
    if not frappe.db.exists("Job Offer", job_offer):
        frappe.throw(_("Job Offer not found."))

    existing = frappe.db.get_value(
        "Employee Onboarding",
        {"job_offer": job_offer, "docstatus": ["!=", 2]},
        "name",
        order_by="creation desc",
    )
    if existing:
        return {"success": True, "onboarding_name": existing, "already_exists": True}

    offer_doc = frappe.get_doc("Job Offer", job_offer)
    if offer_doc.status != "Accepted":
        frappe.throw(_("Only accepted job offers can be converted to onboarding."))

    if not offer_doc.job_applicant:
        frappe.throw(_("Job Offer has no linked Job Applicant."))
    if not frappe.db.exists("Job Applicant", offer_doc.job_applicant):
        frappe.throw(_("Linked Job Applicant does not exist."))

    applicant_doc = frappe.get_doc("Job Applicant", offer_doc.job_applicant)
    opening_meta = {}
    if applicant_doc.job_title and frappe.db.exists("Job Opening", applicant_doc.job_title):
        opening_meta = frappe.db.get_value(
            "Job Opening",
            applicant_doc.job_title,
            ["department", "designation"],
            as_dict=True,
        ) or {}

    designation = offer_doc.designation or opening_meta.get("designation") or applicant_doc.designation or ""
    department = opening_meta.get("department") or ""
    template_name = _resolve_template(
        company=offer_doc.company,
        department=department,
        designation=designation,
    )
    holiday_list = (
        frappe.db.get_value("Employee Onboarding Template", template_name, "holiday_list")
        if template_name
        else None
    )

    start_date = offer_doc.offer_date or nowdate()
    payload = {
        "doctype": "Employee Onboarding",
        "job_applicant": offer_doc.job_applicant,
        "job_offer": offer_doc.name,
        "employee_name": offer_doc.applicant_name or applicant_doc.applicant_name,
        "company": offer_doc.company,
        "department": department,
        "designation": designation,
        "date_of_joining": start_date,
        "boarding_begins_on": start_date,
    }
    if template_name:
        payload["employee_onboarding_template"] = template_name
    if holiday_list:
        payload["holiday_list"] = holiday_list

    onboarding_doc = frappe.get_doc(payload)
    onboarding_doc.insert(ignore_permissions=True)

    return {
        "success": True,
        "onboarding_name": onboarding_doc.name,
        "already_exists": False,
    }
