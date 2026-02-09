"""BEI Performance Management scheduled tasks.

Handles automated probation review creation, regularization triggers,
and appraisal submission hooks.
"""

import frappe
from frappe import _
from frappe.utils import getdate, date_diff, today, add_days


def auto_create_probation_reviews():
    """Daily cron: check probationary employees for 3rd/5th month review milestones.

    Philippine Labor Code: Probationary period cannot exceed 6 months (180 days).
    BEI policy: Conduct reviews at 90 days (3 months) and 150 days (5 months).

    1. Query Employee WHERE status='Active' AND employment_type='Probationary'
    2. For each: check date_diff(today, date_of_joining)
    3. At 90 days: create 3rd Month Appraisal if none exists
    4. At 150 days: create 5th Month Appraisal if none exists
    5. Assign to reports_to supervisor
    """
    today_date = getdate(today())

    # Get all active probationary employees
    probationary_employees = frappe.get_all(
        "Employee",
        filters={
            "status": "Active",
            "employment_type": "Probationary",
        },
        fields=["name", "employee_name", "date_of_joining", "reports_to", "company"],
    )

    for emp in probationary_employees:
        if not emp.date_of_joining:
            continue

        days_employed = date_diff(today_date, getdate(emp.date_of_joining))

        # 3rd month review (90 days)
        if days_employed >= 90 and days_employed < 95:
            _create_appraisal_if_not_exists(
                emp,
                appraisal_type="3rd Month Probation Review",
                review_period_start=emp.date_of_joining,
                review_period_end=today_date,
            )

        # 5th month review (150 days)
        if days_employed >= 150 and days_employed < 155:
            _create_appraisal_if_not_exists(
                emp,
                appraisal_type="5th Month Probation Review",
                review_period_start=add_days(emp.date_of_joining, 90),
                review_period_end=today_date,
            )


def _create_appraisal_if_not_exists(emp_data, appraisal_type, review_period_start, review_period_end):
    """Create appraisal if one doesn't exist for this review period."""
    existing = frappe.db.exists(
        "Appraisal",
        {
            "employee": emp_data.name,
            "bei_appraisal_type": appraisal_type,
            "docstatus": ["<", 2],  # Not cancelled
        }
    )

    if existing:
        return

    appraisal = frappe.get_doc({
        "doctype": "Appraisal",
        "employee": emp_data.name,
        "employee_name": emp_data.employee_name,
        "company": emp_data.company,
        "bei_appraisal_type": appraisal_type,
        "start_date": review_period_start,
        "end_date": review_period_end,
        "status": "Draft",
        "reports_to": emp_data.reports_to,
    })

    try:
        appraisal.insert(ignore_permissions=True)
        frappe.db.commit()

        # Notify supervisor
        if emp_data.reports_to:
            _notify_supervisor_of_review(appraisal, emp_data.reports_to)

        frappe.logger().info(
            f"Auto-created {appraisal_type} for {emp_data.employee_name} ({emp_data.name})"
        )
    except Exception as e:
        frappe.log_error(
            message=f"Failed to create appraisal for {emp_data.name}: {str(e)}",
            title="Auto Appraisal Creation Failed"
        )


def _notify_supervisor_of_review(appraisal, supervisor_id):
    """Send notification to supervisor about pending review."""
    supervisor_email = frappe.db.get_value("Employee", supervisor_id, "user_id")
    if not supervisor_email:
        return

    frappe.sendmail(
        recipients=[supervisor_email],
        subject=_("Probation Review Due: {0}").format(appraisal.employee_name),
        message=_("""
        A probation review has been automatically created for your team member:<br><br>
        <strong>Employee:</strong> {employee_name}<br>
        <strong>Review Type:</strong> {review_type}<br>
        <strong>Review Period:</strong> {start_date} to {end_date}<br><br>
        Please complete the appraisal in my.bebang.ph.
        """).format(
            employee_name=appraisal.employee_name,
            review_type=appraisal.bei_appraisal_type,
            start_date=frappe.format_date(appraisal.start_date),
            end_date=frappe.format_date(appraisal.end_date),
        ),
        reference_doctype="Appraisal",
        reference_name=appraisal.name,
    )


def auto_regularize_overdue():
    """Daily cron: auto-regularize employees past 180 days with no 5th-month review.

    Philippine Labor Code Art. 296: Employees not regularized within 6 months
    are deemed regular by operation of law.

    DOLE Advisory: If no evaluation is made before the end of probation,
    employment is deemed regular from the first day.
    """
    today_date = getdate(today())

    # Get probationary employees past 180 days
    overdue_employees = frappe.db.sql("""
        SELECT
            name, employee_name, date_of_joining, company, reports_to, user_id
        FROM
            tabEmployee
        WHERE
            status = 'Active'
            AND employment_type = 'Probationary'
            AND DATEDIFF(%s, date_of_joining) >= 180
    """, (today_date,), as_dict=True)

    for emp in overdue_employees:
        # Check if 5th month review exists
        fifth_month_review = frappe.db.exists(
            "Appraisal",
            {
                "employee": emp.name,
                "bei_appraisal_type": "5th Month Probation Review",
                "docstatus": 1,  # Submitted
            }
        )

        if fifth_month_review:
            # Has review, regularization should have been triggered by score
            continue

        # No review - auto-regularize by operation of law
        try:
            employee_doc = frappe.get_doc("Employee", emp.name)
            employee_doc.employment_type = "Regular"
            employee_doc.bei_regularization_date = today_date
            employee_doc.bei_regularization_reason = "Auto-regularized by operation of law (180 days)"
            employee_doc.save(ignore_permissions=True)
            frappe.db.commit()

            # Notify HR
            _notify_hr_of_auto_regularization(employee_doc)

            frappe.logger().info(
                f"Auto-regularized {emp.employee_name} ({emp.name}) - 180 days without review"
            )
        except Exception as e:
            frappe.log_error(
                message=f"Failed to auto-regularize {emp.name}: {str(e)}",
                title="Auto Regularization Failed"
            )


def _notify_hr_of_auto_regularization(employee_doc):
    """Notify HR team of automatic regularization."""
    hr_users = frappe.get_all(
        "User",
        filters={"enabled": 1},
        fields=["email"],
    )

    hr_emails = []
    for user in hr_users:
        roles = frappe.get_roles(user.email)
        if "HR Manager" in roles or "HR User" in roles:
            hr_emails.append(user.email)

    if not hr_emails:
        return

    frappe.sendmail(
        recipients=hr_emails,
        subject=_("Auto-Regularization: {0}").format(employee_doc.employee_name),
        message=_("""
        An employee has been automatically regularized due to 180-day probation limit:<br><br>
        <strong>Employee:</strong> {employee_name} ({employee_id})<br>
        <strong>Date of Joining:</strong> {date_of_joining}<br>
        <strong>Regularization Date:</strong> {regularization_date}<br>
        <strong>Reason:</strong> {reason}<br><br>
        Note: Under Philippine Labor Law (Art. 296), employees not evaluated within
        6 months are deemed regular by operation of law. No 5th month review was found.
        """).format(
            employee_name=employee_doc.employee_name,
            employee_id=employee_doc.name,
            date_of_joining=frappe.format_date(employee_doc.date_of_joining),
            regularization_date=frappe.format_date(employee_doc.bei_regularization_date),
            reason=employee_doc.bei_regularization_reason,
        ),
        reference_doctype="Employee",
        reference_name=employee_doc.name,
    )


def on_appraisal_submit(doc, method):
    """Hook on Appraisal submit. If 5th-month review with score >= 3.0:
    - Update Employee.employment_type to 'Regular'
    - Set Employee.regularization_date
    - Log change, notify HR

    If score < 3.0: flag for HR review (don't auto-regularize).

    Args:
        doc: Appraisal document being submitted
        method: Hook method name (unused)
    """
    # Only process 5th month probation reviews
    if doc.bei_appraisal_type != "5th Month Probation Review":
        return

    # Calculate weighted average score from goals
    total_score = 0
    total_weight = 0

    for goal in doc.goals:
        if goal.score and goal.score_earned:
            total_score += goal.score_earned
            total_weight += (goal.score or 5)  # Default weight of 5

    avg_score = (total_score / total_weight) if total_weight > 0 else 0

    # Store calculated score
    doc.db_set("bei_final_score", avg_score, update_modified=False)

    # Check if passing score (3.0 = Meets Expectations)
    if avg_score >= 3.0:
        # Auto-regularize
        employee_doc = frappe.get_doc("Employee", doc.employee)

        if employee_doc.employment_type == "Probationary":
            employee_doc.employment_type = "Regular"
            employee_doc.bei_regularization_date = getdate(today())
            employee_doc.bei_regularization_reason = (
                f"Passed 5th Month Probation Review (Score: {avg_score:.2f}/5.00)"
            )
            employee_doc.save(ignore_permissions=True)
            frappe.db.commit()

            # Notify HR and employee
            _notify_regularization(employee_doc, doc, avg_score)

            frappe.logger().info(
                f"Regularized {employee_doc.employee_name} - Score: {avg_score:.2f}"
            )
    else:
        # Score < 3.0 - Flag for HR review
        doc.db_set("bei_hr_review_required", 1, update_modified=False)
        _notify_hr_review_required(doc, avg_score)


def _notify_regularization(employee_doc, appraisal_doc, score):
    """Notify employee and HR of successful regularization."""
    # Notify employee
    if employee_doc.user_id:
        frappe.sendmail(
            recipients=[employee_doc.user_id],
            subject=_("Congratulations! You have been regularized"),
            message=_("""
            Dear {employee_name},<br><br>
            Congratulations! Based on your excellent performance during the probationary period,
            you have been regularized effective {regularization_date}.<br><br>
            <strong>Appraisal Score:</strong> {score:.2f}/5.00<br>
            <strong>Regularization Date:</strong> {regularization_date}<br><br>
            Welcome to the regular team at Bebang!
            """).format(
                employee_name=employee_doc.employee_name,
                score=score,
                regularization_date=frappe.format_date(employee_doc.bei_regularization_date),
            ),
        )

    # Notify HR
    hr_users = frappe.get_all(
        "User",
        filters={"enabled": 1},
        fields=["email"],
    )

    hr_emails = []
    for user in hr_users:
        roles = frappe.get_roles(user.email)
        if "HR Manager" in roles:
            hr_emails.append(user.email)

    if hr_emails:
        frappe.sendmail(
            recipients=hr_emails,
            subject=_("Employee Regularized: {0}").format(employee_doc.employee_name),
            message=_("""
            An employee has been automatically regularized based on 5th month review:<br><br>
            <strong>Employee:</strong> {employee_name} ({employee_id})<br>
            <strong>Appraisal Score:</strong> {score:.2f}/5.00<br>
            <strong>Regularization Date:</strong> {regularization_date}<br>
            <strong>Appraisal:</strong> {appraisal_id}
            """).format(
                employee_name=employee_doc.employee_name,
                employee_id=employee_doc.name,
                score=score,
                regularization_date=frappe.format_date(employee_doc.bei_regularization_date),
                appraisal_id=appraisal_doc.name,
            ),
            reference_doctype="Employee",
            reference_name=employee_doc.name,
        )


def _notify_hr_review_required(appraisal_doc, score):
    """Notify HR that manual review is needed for below-passing appraisal."""
    hr_users = frappe.get_all(
        "User",
        filters={"enabled": 1},
        fields=["email"],
    )

    hr_emails = []
    for user in hr_users:
        roles = frappe.get_roles(user.email)
        if "HR Manager" in roles:
            hr_emails.append(user.email)

    if hr_emails:
        frappe.sendmail(
            recipients=hr_emails,
            subject=_("HR Review Required: {0}").format(appraisal_doc.employee_name),
            message=_("""
            A 5th month probation review has been submitted with a below-passing score:<br><br>
            <strong>Employee:</strong> {employee_name} ({employee_id})<br>
            <strong>Appraisal Score:</strong> {score:.2f}/5.00 (Passing: 3.00)<br>
            <strong>Appraisal:</strong> {appraisal_id}<br><br>
            <strong>Action Required:</strong> HR review needed to determine next steps
            (extension, PIP, or termination).
            """).format(
                employee_name=appraisal_doc.employee_name,
                employee_id=appraisal_doc.employee,
                score=score,
                appraisal_id=appraisal_doc.name,
            ),
            reference_doctype="Appraisal",
            reference_name=appraisal_doc.name,
        )
