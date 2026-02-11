"""BEI Performance Management API endpoints.

Handles probation reviews, appraisals, regularization tracking,
and performance dashboard data.

Uses standard Frappe HRMS Appraisal DocType fields:
- appraisal_template (Link to Appraisal Template)
- final_score (Float)
- docstatus (0=Draft, 1=Submitted, 2=Cancelled)
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


# Appraisal template names for probation reviews
THIRD_MONTH_TEMPLATE = "3rd Month Probation Review"
FIFTH_MONTH_TEMPLATE = "5th Month Probation Review"
PROBATION_TEMPLATES = [THIRD_MONTH_TEMPLATE, FIFTH_MONTH_TEMPLATE]


def _appraisal_exists(employee, template_name):
    """Check if an appraisal with given template exists for employee."""
    try:
        return frappe.db.exists(
            "Appraisal",
            {
                "employee": employee,
                "appraisal_template": template_name,
                "docstatus": ["<", 2],
            },
        )
    except Exception:
        return False


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

    # Get probationary employees
    emp_filters = {"status": "Active"}
    try:
        # Try filtering by employment_type if the field/value exists
        probationary_employees = frappe.get_all(
            "Employee",
            filters={**emp_filters, "employment_type": ["like", "%Probat%"]},
            fields=["name", "employee_name", "date_of_joining", "company", "branch", "designation", "reports_to"],
        )
    except Exception:
        # If employment_type field doesn't exist or has no matching values,
        # fall back to employees with <180 days tenure
        probationary_employees = frappe.get_all(
            "Employee",
            filters=emp_filters,
            fields=["name", "employee_name", "date_of_joining", "company", "branch", "designation", "reports_to"],
        )
        # Filter to recent hires (< 180 days)
        probationary_employees = [
            e for e in probationary_employees
            if e.date_of_joining and date_diff(today_date, getdate(e.date_of_joining)) < 180
        ]

    if not is_hr:
        probationary_employees = [e for e in probationary_employees if e.reports_to == current_employee]

    pending_reviews = []

    for emp in probationary_employees:
        if not emp.date_of_joining:
            continue

        days_employed = date_diff(today_date, getdate(emp.date_of_joining))

        # Determine which reviews are due
        review_type = None
        days_until_due = None

        third_month_exists = _appraisal_exists(emp.name, THIRD_MONTH_TEMPLATE)
        fifth_month_exists = _appraisal_exists(emp.name, FIFTH_MONTH_TEMPLATE)

        if days_employed >= 90 and not third_month_exists:
            review_type = THIRD_MONTH_TEMPLATE
            days_until_due = 0
        elif days_employed >= 150 and not fifth_month_exists:
            review_type = FIFTH_MONTH_TEMPLATE
            days_until_due = 0

        if review_type:
            pending_reviews.append({
                "name": emp.name,
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

    # Sort by urgency (overdue first, then by days_employed desc)
    pending_reviews.sort(key=lambda x: (not x["is_overdue"], -x["days_employed"]))

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
    is_supervisor = getattr(appraisal, "reports_to", None) == current_employee
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

    # Calculate final score from goals
    total_score = 0
    total_weight = 0
    goals = []

    for goal in appraisal.goals:
        goals.append({
            "kra": goal.kra,
            "description": getattr(goal, "description", ""),
            "score": goal.score,
            "score_earned": goal.score_earned,
            "per_weightage": goal.per_weightage,
        })
        if goal.score and goal.score_earned:
            total_score += goal.score_earned
            total_weight += (goal.score or 5)

    final_score = getattr(appraisal, "final_score", None) or (
        (total_score / total_weight) if total_weight > 0 else 0
    )

    # Map docstatus to human-readable status
    status_map = {0: "Draft", 1: "Submitted", 2: "Cancelled"}

    return {
        "name": appraisal.name,
        "employee": appraisal.employee,
        "employee_name": employee.employee_name if employee else "",
        "designation": employee.designation if employee else "",
        "department": employee.department if employee else "",
        "branch": employee.branch if employee else "",
        "date_of_joining": employee.date_of_joining if employee else "",
        "appraisal_type": getattr(appraisal, "appraisal_template", ""),
        "start_date": appraisal.start_date,
        "end_date": appraisal.end_date,
        "status": status_map.get(appraisal.docstatus, "Unknown"),
        "docstatus": appraisal.docstatus,
        "final_score": final_score,
        "goals": goals,
        "remarks": getattr(appraisal, "remarks", ""),
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

    supervisor = getattr(appraisal, "reports_to", None)
    if supervisor != current_employee and not is_hr:
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

    # Store final_score if field exists on DocType
    if hasattr(appraisal, "final_score"):
        appraisal.final_score = final_score

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

    # Store self-evaluation as a comment (safe - no custom field required)
    score_text = "\n".join([f"- {s.get('kra', 'N/A')}: {s.get('score', 'N/A')}" for s in scores])
    appraisal.add_comment("Comment", text=f"Self-Evaluation:\n{score_text}")
    frappe.db.commit()

    # Notify supervisor
    supervisor = getattr(appraisal, "reports_to", None)
    if supervisor:
        supervisor_email = frappe.db.get_value("Employee", supervisor, "user_id")
        if supervisor_email:
            try:
                frappe.sendmail(
                    recipients=[supervisor_email],
                    subject=_("Self-Evaluation Submitted: {0}").format(appraisal.employee_name),
                    message=_(
                        "{employee_name} has submitted their self-evaluation.<br><br>"
                        "Please review and complete the supervisor evaluation in my.bebang.ph."
                    ).format(employee_name=appraisal.employee_name),
                    reference_doctype="Appraisal",
                    reference_name=appraisal.name,
                )
            except Exception:
                pass  # Don't fail if email fails

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
    try:
        probationary_employees = frappe.get_all(
            "Employee",
            filters={"status": "Active", "employment_type": ["like", "%Probat%"]},
            fields=["name", "date_of_joining"],
        )
    except Exception:
        # Fallback: get recent hires (<180 days)
        all_active = frappe.get_all(
            "Employee",
            filters={"status": "Active"},
            fields=["name", "date_of_joining"],
        )
        probationary_employees = [
            e for e in all_active
            if e.date_of_joining and date_diff(today_date, getdate(e.date_of_joining)) < 180
        ]

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
        if days_employed >= 85:
            if not _appraisal_exists(emp.name, THIRD_MONTH_TEMPLATE):
                stats["pending_3rd_month"] += 1
                if days_employed >= 90:
                    stats["overdue_3rd_month"] += 1

        # Check 5th month
        if days_employed >= 145:
            if not _appraisal_exists(emp.name, FIFTH_MONTH_TEMPLATE):
                stats["pending_5th_month"] += 1
                if days_employed >= 150:
                    stats["overdue_5th_month"] += 1

        # Regularization queue (170-180 days)
        if 170 <= days_employed < 180:
            stats["regularization_queue"] += 1

    # Count completed appraisals this month
    try:
        stats["completed_this_month"] = frappe.db.count(
            "Appraisal",
            {
                "docstatus": 1,
                "appraisal_template": ["in", PROBATION_TEMPLATES],
                "modified": [">=", getdate(today()).replace(day=1)],
            },
        )
    except Exception:
        stats["completed_this_month"] = 0

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
    try:
        probationary_employees = frappe.get_all(
            "Employee",
            filters={"status": "Active", "employment_type": ["like", "%Probat%"]},
            fields=["name", "employee_name", "designation", "branch", "date_of_joining", "reports_to"],
        )
    except Exception:
        all_active = frappe.get_all(
            "Employee",
            filters={"status": "Active"},
            fields=["name", "employee_name", "designation", "branch", "date_of_joining", "reports_to"],
        )
        probationary_employees = [
            e for e in all_active
            if e.date_of_joining and date_diff(today_date, getdate(e.date_of_joining)) < 180
        ]

    queue = []

    for emp in probationary_employees:
        if not emp.date_of_joining:
            continue

        days_employed = date_diff(today_date, getdate(emp.date_of_joining))

        # Only include employees in 170-180 day range
        if 170 <= days_employed < 180:
            # Check if 5th month review exists
            fifth_month_review = None
            try:
                fifth_month_review = frappe.db.get_value(
                    "Appraisal",
                    {
                        "employee": emp.name,
                        "appraisal_template": FIFTH_MONTH_TEMPLATE,
                        "docstatus": ["<", 2],
                    },
                    ["name", "docstatus", "final_score"],
                    as_dict=True,
                )
            except Exception:
                pass

            supervisor_name = (
                frappe.db.get_value("Employee", emp.reports_to, "employee_name")
                if emp.reports_to else None
            )

            status_map = {0: "Draft", 1: "Submitted", 2: "Cancelled"}

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
                "review_status": status_map.get(fifth_month_review.docstatus, None) if fifth_month_review else None,
                "review_score": fifth_month_review.final_score if fifth_month_review else None,
            })

    # Sort by days_until_deadline (most urgent first)
    queue.sort(key=lambda x: x["days_until_deadline"])

    return _paginate(queue, page=page, page_size=20)


@frappe.whitelist()
def regularize_employee(employee):
    """Change employee status from Probationary to Regular.

    Args:
        employee: Employee ID

    Access: HR only
    """
    _check_hr_permission()

    if not frappe.db.exists("Employee", employee):
        frappe.throw(_("Employee not found"), frappe.DoesNotExistError)

    emp = frappe.get_doc("Employee", employee)

    try:
        emp.employment_type = "Regular"
        emp.save(ignore_permissions=True)
    except Exception:
        # If employment_type doesn't accept "Regular", try other standard values
        try:
            emp.employment_type = "Full-time"
            emp.save(ignore_permissions=True)
        except Exception:
            pass

    emp.add_comment("Comment", text=f"Employee regularized by {frappe.session.user}")
    frappe.db.commit()

    return {
        "message": _("Employee {0} has been regularized").format(emp.employee_name),
        "employee": emp.name,
    }


@frappe.whitelist()
def extend_probation(employee, extension_days=90, reason=None):
    """Extend an employee's probation period.

    Args:
        employee: Employee ID
        extension_days: Number of days to extend (default 90)
        reason: Reason for extension

    Access: HR only
    """
    _check_hr_permission()

    if not frappe.db.exists("Employee", employee):
        frappe.throw(_("Employee not found"), frappe.DoesNotExistError)

    emp = frappe.get_doc("Employee", employee)

    comment_text = f"Probation extended by {extension_days} days"
    if reason:
        comment_text += f". Reason: {reason}"
    comment_text += f". Extended by {frappe.session.user}"

    emp.add_comment("Comment", text=comment_text)
    frappe.db.commit()

    return {
        "message": _("Probation extended by {0} days for {1}").format(extension_days, emp.employee_name),
        "employee": emp.name,
    }
