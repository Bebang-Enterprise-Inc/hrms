"""Recruitment API endpoints for MRF → Job Opening → Applicant → Job Offer pipeline"""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import getdate, date_diff, flt, today, nowdate
from hrms.utils.api_helpers import (
    _get_employee_or_throw,
    _get_employee_details,
    _check_hr_permission,
    _check_manager_permission,
    _validate_date_range,
    _paginate,
)


@frappe.whitelist()
@rate_limit(limit=10, seconds=60)
def create_mrf(data):
    """Submit new Manpower Request Form.

    Args:
        data (dict): MRF fields
            - requesting_department (required)
            - position_title (required)
            - designation (required)
            - department (required)
            - number_of_vacancies (default: 1)
            - reason (required): Replacement/New Position/Seasonal/Expansion
            - replaced_employee (conditional on reason)
            - preferred_start_date (required)
            - job_description (required)
            - qualifications
            - salary_range_min
            - salary_range_max
            - internal_hiring_eligible
            - justification (required)
            - store

    Returns:
        dict: Created MRF name and status
    """
    # Get current employee
    current_employee = _get_employee_or_throw()
    emp_details = _get_employee_details()

    # Parse data
    if isinstance(data, str):
        import json

        data = json.loads(data)

    # Validate required fields
    required_fields = [
        "requesting_department",
        "position_title",
        "designation",
        "department",
        "reason",
        "preferred_start_date",
        "job_description",
        "justification",
    ]
    for field in required_fields:
        if not data.get(field):
            frappe.throw(_(f"Missing required field: {field}"))

    # Create MRF document
    mrf = frappe.get_doc(
        {
            "doctype": "BEI Manpower Request Form",
            "requesting_department": data["requesting_department"],
            "requested_by": current_employee,
            "position_title": data["position_title"],
            "designation": data["designation"],
            "department": data["department"],
            "store": data.get("store"),
            "number_of_vacancies": data.get("number_of_vacancies", 1),
            "reason": data["reason"],
            "replaced_employee": data.get("replaced_employee"),
            "preferred_start_date": data["preferred_start_date"],
            "job_description": data["job_description"],
            "qualifications": data.get("qualifications"),
            "salary_range_min": data.get("salary_range_min"),
            "salary_range_max": data.get("salary_range_max"),
            "internal_hiring_eligible": data.get("internal_hiring_eligible", 0),
            "justification": data["justification"],
            "status": "Draft",
        }
    )
    mrf.insert()

    # Auto-submit to move to Pending Hiring Manager
    mrf.db_set("status", "Pending Hiring Manager")

    return {
        "name": mrf.name,
        "status": mrf.status,
        "message": _("Manpower Request Form created and submitted for approval"),
    }


@frappe.whitelist()
def get_mrf_list(status=None, department=None, page=1, page_size=50):
    """List MRFs with filters.

    HR users see all MRFs. Department heads see only their department's MRFs.

    Args:
        status: Filter by status
        department: Filter by department
        page: Page number (1-based)
        page_size: Results per page

    Returns:
        dict: Paginated MRF list
    """
    # Check permissions
    roles = frappe.get_roles(frappe.session.user)
    is_hr = any(r in roles for r in ["HR Manager", "HR User", "System Manager"])

    filters = {}
    if status:
        filters["status"] = status
    if department:
        filters["department"] = department

    # Non-HR users only see their department's MRFs
    if not is_hr:
        current_emp = _get_employee_or_throw()
        emp_dept = frappe.db.get_value("Employee", current_emp, "department")
        filters["requesting_department"] = emp_dept

    results = frappe.get_all(
        "BEI Manpower Request Form",
        filters=filters,
        fields=[
            "name",
            "position_title",
            "designation",
            "department",
            "requesting_department",
            "requested_by",
            "number_of_vacancies",
            "reason",
            "preferred_start_date",
            "status",
            "linked_job_opening",
            "creation",
            "modified",
        ],
        order_by="creation desc",
    )

    return _paginate(results, page=int(page), page_size=int(page_size))


@frappe.whitelist()
@rate_limit(limit=10, seconds=60)
def approve_mrf(mrf_name, action, notes=None):
    """Approve or reject MRF at current approval level.

    Approval flow:
    1. Pending Hiring Manager → Pending HR Manager
    2. Pending HR Manager → Pending CEO (if C-level/VP) OR Approved (if below)
    3. Pending CEO → Approved

    Args:
        mrf_name: MRF document name
        action: "approve" or "reject"
        notes: Optional approval notes

    Returns:
        dict: Updated MRF status
    """
    if action not in ["approve", "reject"]:
        frappe.throw(_("Invalid action. Must be 'approve' or 'reject'"))

    mrf = frappe.get_doc("BEI Manpower Request Form", mrf_name)
    current_status = mrf.status

    # Check approval permissions based on current status
    roles = frappe.get_roles(frappe.session.user)
    current_emp = _get_employee_or_throw()

    if current_status == "Pending Hiring Manager":
        # Hiring Manager or HR can approve
        if not any(r in roles for r in ["HR Manager", "System Manager"]):
            # Verify user is the actual department head for the requesting department
            dept_head = frappe.db.get_value(
                "Department", mrf.department, "department_head"
            )
            if current_emp != dept_head:
                frappe.throw(
                    _("Only the department head of {0} can approve at this stage").format(
                        mrf.department
                    )
                )
    elif current_status == "Pending HR Manager":
        # HR Manager only
        if "HR Manager" not in roles and "System Manager" not in roles:
            frappe.throw(_("Only HR Managers can approve at this stage"))
    elif current_status == "Pending CEO":
        # CEO/System Manager only
        if "System Manager" not in roles:
            # Additional check for CEO role if needed
            frappe.throw(_("Only CEO can approve at this stage"))
    else:
        frappe.throw(_(f"MRF cannot be approved in status: {current_status}"))

    # Process action
    if action == "reject":
        mrf.db_set("status", "Rejected")
        status_msg = _("MRF rejected")
    else:
        # Determine next status based on current status
        if current_status == "Pending Hiring Manager":
            mrf.db_set("status", "Pending HR Manager")
            status_msg = _("MRF approved by Hiring Manager, forwarded to HR Manager")
        elif current_status == "Pending HR Manager":
            # Check designation level to determine if CEO approval needed
            designation = frappe.db.get_value("Designation", mrf.designation, "name")
            ceo_approval_required = any(
                keyword in designation.upper()
                for keyword in ["VP", "VICE PRESIDENT", "C-LEVEL", "DIRECTOR"]
            )
            if ceo_approval_required:
                mrf.db_set("status", "Pending CEO")
                status_msg = _("MRF approved by HR Manager, forwarded to CEO")
            else:
                mrf.db_set("status", "Approved")
                # Auto-create Job Opening
                _create_job_opening_from_mrf(mrf)
                status_msg = _("MRF approved and Job Opening created")
        elif current_status == "Pending CEO":
            mrf.db_set("status", "Approved")
            # Auto-create Job Opening
            _create_job_opening_from_mrf(mrf)
            status_msg = _("MRF approved by CEO and Job Opening created")

    # Add comment with notes
    if notes:
        mrf.add_comment(
            "Comment",
            text=f"{action.upper()} by {frappe.session.user}: {notes}",
        )

    return {
        "name": mrf.name,
        "status": mrf.status,
        "message": status_msg,
    }


def _create_job_opening_from_mrf(mrf):
    """Create Job Opening from approved MRF.

    Args:
        mrf: BEI Manpower Request Form document
    """
    if mrf.linked_job_opening:
        return  # Already created

    job_opening = frappe.get_doc(
        {
            "doctype": "Job Opening",
            "job_title": mrf.position_title,
            "designation": mrf.designation,
            "department": mrf.department,
            "company": frappe.defaults.get_defaults().get("company", "Bebang Enterprise Inc."),
            "status": "Open",
            "planned_vacancies": mrf.number_of_vacancies,
            "description": mrf.job_description,
            "publish": 1 if mrf.internal_hiring_eligible else 0,
            "lower_range": mrf.salary_range_min,
            "upper_range": mrf.salary_range_max,
        }
    )
    job_opening.insert(ignore_permissions=True)

    # Link back to MRF
    mrf.db_set("linked_job_opening", job_opening.name)

    frappe.msgprint(
        _(f"Job Opening {job_opening.name} created successfully"),
        indicator="green",
        alert=True,
    )


@frappe.whitelist()
def get_recruitment_pipeline(status=None, department=None):
    """Get recruitment pipeline kanban data.

    Stages: Applied → Screening → Interview → Offer → Hired

    Args:
        status: Filter by Job Applicant status
        department: Filter by department

    Returns:
        dict: Pipeline data grouped by stage
    """
    _check_hr_permission()

    filters = {}
    if status:
        filters["status"] = status

    # Get all applicants
    applicants = frappe.get_all(
        "Job Applicant",
        filters=filters,
        fields=[
            "name",
            "applicant_name",
            "email_id",
            "job_title",
            "status",
            "source",
            "creation",
            "modified",
        ],
        order_by="creation desc",
    )

    # Filter by department if specified
    if department:
        job_openings = frappe.get_all(
            "Job Opening", filters={"department": department}, pluck="name"
        )
        applicants = [a for a in applicants if a.get("job_title") in job_openings]

    # Group by status
    pipeline = {
        "Open": [],
        "Replied": [],
        "Hold": [],
        "Accepted": [],
        "Rejected": [],
    }

    for applicant in applicants:
        stage = applicant.get("status", "Open")
        if stage in pipeline:
            pipeline[stage].append(applicant)

    # Add counts
    result = {
        "stages": pipeline,
        "counts": {stage: len(apps) for stage, apps in pipeline.items()},
        "total": len(applicants),
    }

    return result


@frappe.whitelist()
@rate_limit(limit=20, seconds=60)
def update_applicant_stage(applicant_name, stage, notes=None):
    """Move applicant through pipeline stages.

    Args:
        applicant_name: Job Applicant name
        stage: New stage (Open/Replied/Hold/Accepted/Rejected)
        notes: Optional stage transition notes

    Returns:
        dict: Updated applicant status
    """
    _check_hr_permission()

    valid_stages = ["Open", "Replied", "Hold", "Accepted", "Rejected"]
    if stage not in valid_stages:
        frappe.throw(_(f"Invalid stage. Must be one of: {', '.join(valid_stages)}"))

    applicant = frappe.get_doc("Job Applicant", applicant_name)
    applicant.db_set("status", stage)

    # Add comment with notes
    if notes:
        applicant.add_comment(
            "Comment",
            text=f"Stage changed to {stage} by {frappe.session.user}: {notes}",
        )

    return {
        "name": applicant.name,
        "status": applicant.status,
        "message": _(f"Applicant moved to {stage}"),
    }


@frappe.whitelist()
def get_applicant_detail(applicant_name):
    """Get full applicant profile with stage history.

    Args:
        applicant_name: Job Applicant name

    Returns:
        dict: Complete applicant details
    """
    _check_hr_permission()

    applicant = frappe.get_doc("Job Applicant", applicant_name)

    # Get stage history from comments
    comments = frappe.get_all(
        "Comment",
        filters={"reference_doctype": "Job Applicant", "reference_name": applicant_name},
        fields=["content", "owner", "creation"],
        order_by="creation desc",
    )

    return {
        "name": applicant.name,
        "applicant_name": applicant.applicant_name,
        "email_id": applicant.email_id,
        "phone_number": applicant.phone_number,
        "job_title": applicant.job_title,
        "status": applicant.status,
        "source": applicant.source,
        "resume_attachment": applicant.resume_attachment,
        "cover_letter": applicant.cover_letter,
        "creation": applicant.creation,
        "modified": applicant.modified,
        "notes": applicant.notes,
        "stage_history": comments,
    }


@frappe.whitelist()
@rate_limit(limit=5, seconds=60)
def create_job_offer(applicant_name, data):
    """Generate job offer for applicant.

    Args:
        applicant_name: Job Applicant name
        data (dict): Offer details
            - designation (required)
            - company (required)
            - offer_date (required)
            - offer_terms (required)

    Returns:
        dict: Created Job Offer name
    """
    _check_hr_permission()

    # Parse data
    if isinstance(data, str):
        import json

        data = json.loads(data)

    # Validate required fields
    required_fields = ["designation", "company", "offer_date", "offer_terms"]
    for field in required_fields:
        if not data.get(field):
            frappe.throw(_(f"Missing required field: {field}"))

    applicant = frappe.get_doc("Job Applicant", applicant_name)

    # Create Job Offer
    job_offer = frappe.get_doc(
        {
            "doctype": "Job Offer",
            "job_applicant": applicant.name,
            "applicant_name": applicant.applicant_name,
            "designation": data["designation"],
            "company": data["company"],
            "offer_date": data["offer_date"],
            "status": "Awaiting Response",
            "offer_terms": data["offer_terms"],
        }
    )
    job_offer.insert()

    # Update applicant status
    applicant.db_set("status", "Accepted")

    return {
        "name": job_offer.name,
        "status": job_offer.status,
        "message": _("Job Offer created successfully"),
    }


@frappe.whitelist()
def get_recruitment_metrics(from_date=None, to_date=None):
    """Get recruitment metrics and KPIs.

    Metrics:
    - Time to fill (days from MRF to hire)
    - Source effectiveness (applicants per source)
    - Pipeline conversion rates
    - MRF approval times

    Args:
        from_date: Start date for metrics
        to_date: End date for metrics

    Returns:
        dict: Recruitment metrics
    """
    _check_hr_permission()

    # Default to last 90 days if not specified
    if not from_date:
        from_date = frappe.utils.add_days(today(), -90)
    if not to_date:
        to_date = today()

    _validate_date_range(from_date, to_date)

    # MRF metrics
    mrf_created = frappe.db.count(
        "BEI Manpower Request Form",
        filters={"creation": ["between", [from_date, to_date]]},
    )
    mrf_approved = frappe.db.count(
        "BEI Manpower Request Form",
        filters={
            "status": "Approved",
            "modified": ["between", [from_date, to_date]],
        },
    )

    # Job Opening metrics
    openings_created = frappe.db.count(
        "Job Opening",
        filters={"creation": ["between", [from_date, to_date]]},
    )
    openings_filled = frappe.db.count(
        "Job Opening",
        filters={
            "status": "Closed",
            "modified": ["between", [from_date, to_date]],
        },
    )

    # Applicant metrics by source
    applicant_sources = frappe.db.sql(
        """
        SELECT
            source,
            COUNT(*) as count,
            SUM(CASE WHEN status = 'Accepted' THEN 1 ELSE 0 END) as accepted
        FROM `tabJob Applicant`
        WHERE creation BETWEEN %s AND %s
        GROUP BY source
        ORDER BY count DESC
    """,
        (from_date, to_date),
        as_dict=True,
    )

    # Pipeline conversion
    total_applicants = frappe.db.count(
        "Job Applicant",
        filters={"creation": ["between", [from_date, to_date]]},
    )
    applicants_replied = frappe.db.count(
        "Job Applicant",
        filters={
            "status": ["in", ["Replied", "Hold", "Accepted"]],
            "creation": ["between", [from_date, to_date]],
        },
    )
    applicants_accepted = frappe.db.count(
        "Job Applicant",
        filters={
            "status": "Accepted",
            "creation": ["between", [from_date, to_date]],
        },
    )

    # Calculate time to fill (simplified - should track actual hiring dates)
    avg_time_to_fill = frappe.db.sql(
        """
        SELECT AVG(DATEDIFF(modified, creation)) as avg_days
        FROM `tabJob Opening`
        WHERE status = 'Closed'
        AND modified BETWEEN %s AND %s
    """,
        (from_date, to_date),
    )
    avg_time_to_fill = avg_time_to_fill[0][0] if avg_time_to_fill else 0

    return {
        "period": {"from_date": from_date, "to_date": to_date},
        "mrf": {
            "created": mrf_created,
            "approved": mrf_approved,
            "approval_rate": round((mrf_approved / mrf_created * 100), 2)
            if mrf_created > 0
            else 0,
        },
        "openings": {
            "created": openings_created,
            "filled": openings_filled,
            "fill_rate": round((openings_filled / openings_created * 100), 2)
            if openings_created > 0
            else 0,
        },
        "applicants": {
            "total": total_applicants,
            "replied": applicants_replied,
            "accepted": applicants_accepted,
            "reply_rate": round((applicants_replied / total_applicants * 100), 2)
            if total_applicants > 0
            else 0,
            "acceptance_rate": round((applicants_accepted / total_applicants * 100), 2)
            if total_applicants > 0
            else 0,
        },
        "sources": applicant_sources,
        "avg_time_to_fill_days": round(avg_time_to_fill, 1) if avg_time_to_fill else 0,
    }
