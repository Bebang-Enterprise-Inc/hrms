"""BEI Performance Management API endpoints.

Handles probation reviews, appraisals, regularization tracking,
and performance dashboard data.
"""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import getdate, date_diff, today
from hrms.utils.api_helpers import (
    _get_employee_or_throw,
    _get_employee_details,
    _check_hr_permission,
    _check_manager_permission,
    _paginate,
)


@frappe.whitelist()
def get_pending_reviews(page=1):
    """Get employees due for performance reviews.

    Returns:
        For supervisors: Direct reports due for review
        For HR: All employees due for review

    Access: Supervisor (own team), HR (all)
    """
    current_employee = _get_employee_or_throw()
    roles = frappe.get_roles(frappe.session.user)
    is_hr = any(r in roles for r in ["HR Manager", "HR User", "System Manager"])

    page = int(page) if page else 1
    today_date = getdate(today())

    # Build filters
    filters = [
        ["Employee", "status", "=", "Active"],
        ["Employee", "employment_type", "=", "Probationary"],
    ]

    if not is_hr:
        filters.append(["Employee", "reports_to", "=", current_employee])

    # Get probationary employees
    probationary_employees = frappe.get_all(
        "Employee",
        filters=filters,
        fields=["name", "employee_name", "date_of_joining", "company", "branch", "designation"],
    )

    pending_reviews = []

    for emp in probationary_employees:
        if not emp.date_of_joining:
            continue

        days_employed = date_diff(today_date, getdate(emp.date_of_joining))

        # Check if reviews exist
        third_month_exists = frappe.db.exists(
            "Appraisal",
            {
                "employee": emp.name,
                "bei_appraisal_type": "3rd Month Probation Review",
                "docstatus": ["<", 2],
            }
        )

        fifth_month_exists = frappe.db.exists(
            "Appraisal",
            {
                "employee": emp.name,
                "bei_appraisal_type": "5th Month Probation Review",
                "docstatus": ["<", 2],
            }
        )

        # Determine which reviews are due
        review_type = None
        days_until_due = None

        if days_employed >= 90 and not third_month_exists:
            review_type = "3rd Month Probation Review"
            days_until_due = 0 if days_employed >= 90 else 90 - days_employed
        elif days_employed >= 150 and not fifth_month_exists:
            review_type = "5th Month Probation Review"
            days_until_due = 0 if days_employed >= 150 else 150 - days_employed

        if review_type:
            pending_reviews.append({
                "employee": emp.name,
                "employee_name": emp.employee_name,
                "designation": emp.designation,
                "branch": emp.branch,
                "date_of_joining": emp.date_of_joining,
                "days_employed": days_employed,
                "review_type": review_type,
                "days_until_due": days_until_due,
                "is_overdue": days_until_due == 0,
            })

    # Sort by urgency (overdue first, then by days_until_due)
    pending_reviews.sort(key=lambda x: (not x["is_overdue"], x["days_until_due"]))

    return _paginate(pending_reviews, page=page, page_size=20)


@frappe.whitelist()
def get_appraisal_detail(appraisal_id):
    """Get full appraisal details including scores and comments.

    Args:
        appraisal_id: Appraisal document name

    Returns:
        Appraisal document with goals, scores, comments

    Access: Supervisor, HR, Employee (own appraisal only)
    """
    if not frappe.db.exists("Appraisal", appraisal_id):
        frappe.throw(_("Appraisal not found"), frappe.DoesNotExistError)

    appraisal = frappe.get_doc("Appraisal", appraisal_id)

    # Permission check
    current_employee = _get_employee_or_throw()
    roles = frappe.get_roles(frappe.session.user)
    is_hr = any(r in roles for r in ["HR Manager", "HR User", "System Manager"])

    # Allow if: HR, supervisor, or employee themselves
    is_supervisor = appraisal.reports_to == current_employee
    is_employee = appraisal.employee == current_employee

    if not (is_hr or is_supervisor or is_employee):
        frappe.throw(_("Permission denied"), frappe.PermissionError)

    # Get employee details
    employee = frappe.db.get_value(
        "Employee",
        appraisal.employee,
        ["employee_name", "designation", "department", "branch", "date_of_joining"],
        as_dict=True,
    )

    # Calculate final score
    total_score = 0
    total_weight = 0
    goals = []

    for goal in appraisal.goals:
        goals.append({
            "kra": goal.kra,
            "description": goal.description,
            "score": goal.score,
            "score_earned": goal.score_earned,
            "per_weightage": goal.per_weightage,
        })
        if goal.score and goal.score_earned:
            total_score += goal.score_earned
            total_weight += (goal.score or 5)

    final_score = (total_score / total_weight) if total_weight > 0 else 0

    return {
        "name": appraisal.name,
        "employee": appraisal.employee,
        "employee_name": employee.employee_name,
        "designation": employee.designation,
        "department": employee.department,
        "branch": employee.branch,
        "date_of_joining": employee.date_of_joining,
        "appraisal_type": appraisal.bei_appraisal_type,
        "start_date": appraisal.start_date,
        "end_date": appraisal.end_date,
        "status": appraisal.status,
        "docstatus": appraisal.docstatus,
        "final_score": final_score,
        "goals": goals,
        "remarks": appraisal.remarks,
        "supervisor_remarks": appraisal.bei_supervisor_remarks,
        "hr_remarks": appraisal.bei_hr_remarks,
        "created_on": appraisal.creation,
        "modified_on": appraisal.modified,
    }


@frappe.whitelist()
@rate_limit(limit=10, seconds=60)
def submit_appraisal_scores(appraisal_id, scores):
    """Supervisor submits appraisal scores.

    Args:
        appraisal_id: Appraisal document name
        scores: JSON string of list of dicts: [{"kra": "Integrity", "score": 4}, ...]

    Returns:
        Success message with calculated final score

    Access: Supervisor only
    """
    import json

    if not frappe.db.exists("Appraisal", appraisal_id):
        frappe.throw(_("Appraisal not found"), frappe.DoesNotExistError)

    appraisal = frappe.get_doc("Appraisal", appraisal_id)

    # Permission check - must be supervisor
    current_employee = _get_employee_or_throw()
    roles = frappe.get_roles(frappe.session.user)
    is_hr = any(r in roles for r in ["HR Manager", "System Manager"])

    if appraisal.reports_to != current_employee and not is_hr:
        frappe.throw(_("Permission denied. You are not the supervisor for this appraisal."), frappe.PermissionError)

    # Parse scores
    if isinstance(scores, str):
        scores = json.loads(scores)

    if not isinstance(scores, list):
        frappe.throw(_("Scores must be a list of KRA-score pairs"))

    # Update goals with scores
    for score_item in scores:
        kra = score_item.get("kra")
        score = score_item.get("score")

        if not kra or score is None:
            continue

        # Find matching goal
        for goal in appraisal.goals:
            if goal.kra == kra:
                goal.score_earned = float(score)
                break

    # Calculate final score
    total_score = 0
    total_weight = 0

    for goal in appraisal.goals:
        if goal.score and goal.score_earned:
            total_score += goal.score_earned
            total_weight += (goal.score or 5)

    final_score = (total_score / total_weight) if total_weight > 0 else 0

    appraisal.bei_final_score = final_score
    appraisal.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "message": _("Appraisal scores saved successfully"),
        "final_score": final_score,
    }


@frappe.whitelist()
@rate_limit(limit=10, seconds=60)
def submit_self_evaluation(appraisal_id, scores):
    """Employee submits self-evaluation scores.

    Args:
        appraisal_id: Appraisal document name
        scores: JSON string of list of dicts: [{"kra": "Integrity", "score": 4}, ...]

    Returns:
        Success message

    Access: Employee (own appraisal only)
    """
    import json

    if not frappe.db.exists("Appraisal", appraisal_id):
        frappe.throw(_("Appraisal not found"), frappe.DoesNotExistError)

    appraisal = frappe.get_doc("Appraisal", appraisal_id)

    # Permission check - must be the employee
    current_employee = _get_employee_or_throw()

    if appraisal.employee != current_employee:
        frappe.throw(_("Permission denied. This is not your appraisal."), frappe.PermissionError)

    # Parse scores
    if isinstance(scores, str):
        scores = json.loads(scores)

    if not isinstance(scores, list):
        frappe.throw(_("Scores must be a list of KRA-score pairs"))

    # Store self-evaluation in custom field (assumes bei_self_evaluation_json exists)
    appraisal.bei_self_evaluation_json = json.dumps(scores)
    appraisal.bei_self_evaluation_submitted = 1
    appraisal.save(ignore_permissions=True)
    frappe.db.commit()

    # Notify supervisor
    if appraisal.reports_to:
        supervisor_email = frappe.db.get_value("Employee", appraisal.reports_to, "user_id")
        if supervisor_email:
            frappe.sendmail(
                recipients=[supervisor_email],
                subject=_("Self-Evaluation Submitted: {0}").format(appraisal.employee_name),
                message=_("""
                {employee_name} has submitted their self-evaluation for the {appraisal_type}.<br><br>
                Please review and complete the supervisor evaluation in my.bebang.ph.
                """).format(
                    employee_name=appraisal.employee_name,
                    appraisal_type=appraisal.bei_appraisal_type,
                ),
                reference_doctype="Appraisal",
                reference_name=appraisal.name,
            )

    return {
        "message": _("Self-evaluation submitted successfully"),
    }


@frappe.whitelist()
def get_review_summary():
    """Get performance review dashboard statistics.

    Returns:
        Dashboard stats: pending, completed, overdue reviews

    Access: HR only
    """
    _check_hr_permission()

    today_date = getdate(today())

    # Get all active probationary employees
    probationary_employees = frappe.get_all(
        "Employee",
        filters={
            "status": "Active",
            "employment_type": "Probationary",
        },
        fields=["name", "date_of_joining"],
    )

    stats = {
        "total_probationary": len(probationary_employees),
        "pending_3rd_month": 0,
        "pending_5th_month": 0,
        "overdue_3rd_month": 0,
        "overdue_5th_month": 0,
        "completed_this_month": 0,
        "regularization_queue": 0,
    }

    for emp in probationary_employees:
        if not emp.date_of_joining:
            continue

        days_employed = date_diff(today_date, getdate(emp.date_of_joining))

        # Check 3rd month
        if days_employed >= 85:  # Within 5 days of 90
            third_month_exists = frappe.db.exists(
                "Appraisal",
                {
                    "employee": emp.name,
                    "bei_appraisal_type": "3rd Month Probation Review",
                    "docstatus": ["<", 2],
                }
            )
            if not third_month_exists:
                stats["pending_3rd_month"] += 1
                if days_employed >= 90:
                    stats["overdue_3rd_month"] += 1

        # Check 5th month
        if days_employed >= 145:  # Within 5 days of 150
            fifth_month_exists = frappe.db.exists(
                "Appraisal",
                {
                    "employee": emp.name,
                    "bei_appraisal_type": "5th Month Probation Review",
                    "docstatus": ["<", 2],
                }
            )
            if not fifth_month_exists:
                stats["pending_5th_month"] += 1
                if days_employed >= 150:
                    stats["overdue_5th_month"] += 1

        # Regularization queue (170-180 days)
        if days_employed >= 170 and days_employed < 180:
            stats["regularization_queue"] += 1

    # Count completed appraisals this month
    stats["completed_this_month"] = frappe.db.count(
        "Appraisal",
        {
            "docstatus": 1,
            "bei_appraisal_type": ["in", ["3rd Month Probation Review", "5th Month Probation Review"]],
            "modified": [">=", getdate(today()).replace(day=1)],
        }
    )

    return stats


@frappe.whitelist()
def get_regularization_queue(page=1):
    """Get employees approaching 180-day regularization deadline.

    Returns list of probationary employees in days 170-180 range.

    Access: HR only
    """
    _check_hr_permission()

    page = int(page) if page else 1
    today_date = getdate(today())

    # Get probationary employees
    probationary_employees = frappe.get_all(
        "Employee",
        filters={
            "status": "Active",
            "employment_type": "Probationary",
        },
        fields=["name", "employee_name", "designation", "branch", "date_of_joining", "reports_to"],
    )

    queue = []

    for emp in probationary_employees:
        if not emp.date_of_joining:
            continue

        days_employed = date_diff(today_date, getdate(emp.date_of_joining))

        # Only include employees in 170-180 day range
        if days_employed >= 170 and days_employed < 180:
            # Check if 5th month review exists
            fifth_month_review = frappe.db.get_value(
                "Appraisal",
                {
                    "employee": emp.name,
                    "bei_appraisal_type": "5th Month Probation Review",
                    "docstatus": ["<", 2],
                },
                ["name", "status", "bei_final_score"],
                as_dict=True,
            )

            supervisor_name = frappe.db.get_value("Employee", emp.reports_to, "employee_name") if emp.reports_to else None

            queue.append({
                "employee": emp.name,
                "employee_name": emp.employee_name,
                "designation": emp.designation,
                "branch": emp.branch,
                "date_of_joining": emp.date_of_joining,
                "days_employed": days_employed,
                "days_until_deadline": 180 - days_employed,
                "supervisor_name": supervisor_name,
                "has_5th_month_review": bool(fifth_month_review),
                "review_status": fifth_month_review.status if fifth_month_review else None,
                "review_score": fifth_month_review.bei_final_score if fifth_month_review else None,
            })

    # Sort by days_until_deadline (most urgent first)
    queue.sort(key=lambda x: x["days_until_deadline"])

    return _paginate(queue, page=page, page_size=20)
