"""Employee Data Enrichment API.

Provides API endpoints for the Store Supervisor data verification dashboard
and Data Enrichment V2 with tiered editing and HR approval workflow.
"""
import frappe
from frappe import _
from frappe.utils import today, now_datetime


# ============================================================================
# Data Enrichment V2 - Field Classification
# ============================================================================

# Fields employees can edit without approval
SELF_SERVICE_FIELDS = [
    "custom_nickname",
    "personal_email",
    "cell_number",
    "current_address",
    "permanent_address",
    "emergency_contact_name",
    "emergency_phone_number",
    "bank_name",
    "bank_ac_no",
]

# Fields that require HR approval (via BEI Edit Request)
HR_APPROVAL_FIELDS = [
    "first_name",
    "middle_name",
    "last_name",
    "date_of_birth",
    "marital_status",
    "ctc_sss",
    "ctc_tin",
    "ctc_philhealth",
    "ctc_pagibig",
]

# Human-readable labels for fields
FIELD_LABELS = {
    "first_name": "First Name",
    "middle_name": "Middle Name",
    "last_name": "Last Name",
    "date_of_birth": "Date of Birth",
    "marital_status": "Marital Status",
    "ctc_sss": "SSS Number",
    "ctc_tin": "TIN",
    "ctc_philhealth": "PhilHealth Number",
    "ctc_pagibig": "Pag-IBIG Number",
    "custom_nickname": "Nickname",
    "personal_email": "Personal Email",
    "cell_number": "Mobile Number",
    "current_address": "Current Address",
    "permanent_address": "Permanent Address",
    "emergency_contact_name": "Emergency Contact Name",
    "emergency_phone_number": "Emergency Contact Phone",
    "bank_name": "Bank Name",
    "bank_ac_no": "Bank Account Number",
}


@frappe.whitelist()
def get_enrichment_dashboard(store: str = None) -> dict:
    """Get dashboard data for enrichment campaign.

    Args:
        store: Optional branch/store filter

    Returns:
        Dictionary with stats and employee list
    """
    filters = {"status": "Active"}
    if store:
        filters["branch"] = store

    employees = frappe.get_all(
        "Employee",
        filters=filters,
        fields=[
            "name",
            "employee_name",
            "first_name",
            "last_name",
            "branch",
            "department",
            "designation",
            "attendance_device_id",
            "employee_number",
            "image",
            "cell_number",
            "personal_email",
            "custom_verification_status",
            "custom_verified_by",
            "custom_verified_date",
            "custom_issue_type",
        ],
        order_by="branch asc, employee_name asc",
    )

    # Calculate stats
    total = len(employees)
    verified = len([e for e in employees if e.get("custom_verification_status") == "Verified"])
    pending = len([e for e in employees if e.get("custom_verification_status") in ("Pending", None, "")])
    issues = len([e for e in employees if e.get("custom_verification_status") == "Has Issues"])

    return {
        "stats": {
            "total": total,
            "verified": verified,
            "pending": pending,
            "issues": issues,
            "progress_pct": round(verified / total * 100, 1) if total > 0 else 0,
        },
        "employees": employees,
    }


@frappe.whitelist()
def get_store_progress() -> list[dict]:
    """Get verification progress by store/branch.

    Returns:
        List of dictionaries with branch, total, verified, and progress_pct
    """
    sql = """
        SELECT
            branch,
            COUNT(*) as total,
            SUM(CASE WHEN custom_verification_status = 'Verified' THEN 1 ELSE 0 END) as verified,
            SUM(CASE WHEN custom_verification_status = 'Has Issues' THEN 1 ELSE 0 END) as has_issues
        FROM `tabEmployee`
        WHERE status = 'Active' AND branch IS NOT NULL AND branch != ''
        GROUP BY branch
        ORDER BY branch
    """
    results = frappe.db.sql(sql, as_dict=True)

    for row in results:
        row["pending"] = row["total"] - row["verified"] - row["has_issues"]
        row["progress_pct"] = round(row["verified"] / row["total"] * 100, 1) if row["total"] > 0 else 0

    return results


@frappe.whitelist()
def get_employee_details(employee: str) -> dict:
    """Get full employee details for verification.

    Args:
        employee: Employee name/ID

    Returns:
        Employee document as dictionary
    """
    doc = frappe.get_doc("Employee", employee)
    return doc.as_dict()


@frappe.whitelist()
def mark_employee_verified(employee: str, notes: str = None) -> dict:
    """Mark an employee as verified.

    Args:
        employee: Employee name/ID
        notes: Optional verification notes

    Returns:
        Success status and message
    """
    emp = frappe.get_doc("Employee", employee)
    emp.custom_verification_status = "Verified"
    emp.custom_verified_by = frappe.session.user
    emp.custom_verified_date = today()
    if notes:
        emp.custom_verification_notes = notes
    emp.save(ignore_permissions=True)

    return {"status": "success", "message": _("Employee {0} marked as verified").format(emp.employee_name)}


@frappe.whitelist()
def report_employee_issue(employee: str, issue_type: str, description: str) -> dict:
    """Report an issue with employee data.

    Args:
        employee: Employee name/ID
        issue_type: Type of issue (Wrong Name, Wrong Store, Missing Info, Duplicate, Other)
        description: Description of the issue

    Returns:
        Success status and message
    """
    emp = frappe.get_doc("Employee", employee)
    emp.custom_verification_status = "Has Issues"
    emp.custom_issue_type = issue_type
    emp.custom_issue_description = description
    emp.custom_issue_reported_by = frappe.session.user
    emp.custom_issue_reported_date = today()
    emp.save(ignore_permissions=True)

    # Notify HR via email
    hr_email = frappe.db.get_single_value("HR Settings", "hr_settings_email") or "hr@bebang.ph"
    try:
        frappe.sendmail(
            recipients=[hr_email],
            subject=_("Employee Data Issue: {0}").format(emp.employee_name),
            message=_(
                """
                <p><strong>Issue Reported</strong></p>
                <p><strong>Employee:</strong> {employee_name}</p>
                <p><strong>Branch:</strong> {branch}</p>
                <p><strong>Issue Type:</strong> {issue_type}</p>
                <p><strong>Description:</strong> {description}</p>
                <p><strong>Reported By:</strong> {reported_by}</p>
                """
            ).format(
                employee_name=emp.employee_name,
                branch=emp.branch or "N/A",
                issue_type=issue_type,
                description=description,
                reported_by=frappe.session.user,
            ),
        )
    except Exception:
        # Don't fail if email fails
        pass

    return {"status": "success", "message": _("Issue reported to HR")}


@frappe.whitelist()
def update_employee_field(employee: str, fieldname: str, value: str) -> dict:
    """Update a single field on an employee record.

    Args:
        employee: Employee name/ID
        fieldname: Field to update
        value: New value

    Returns:
        Success status and message
    """
    # Validate allowed fields for update by supervisors
    allowed_fields = [
        "cell_number",
        "personal_email",
        "emergency_phone_number",
        "custom_verification_notes",
    ]

    if fieldname not in allowed_fields:
        frappe.throw(_("You are not allowed to update the field: {0}").format(fieldname))

    emp = frappe.get_doc("Employee", employee)
    emp.set(fieldname, value)
    emp.save(ignore_permissions=True)

    return {"status": "success", "message": _("Field {0} updated successfully").format(fieldname)}


@frappe.whitelist()
def get_user_stores() -> list[str]:
    """Get stores/branches that the current user can manage.

    For HR Managers/System Managers, returns all stores.
    For Store Supervisors, returns only their assigned store(s).

    Returns:
        List of branch names
    """
    user = frappe.session.user
    roles = frappe.get_roles(user)

    # Admin roles see all stores
    if "HR Manager" in roles or "System Manager" in roles or "HR User" in roles:
        stores = frappe.get_all(
            "Employee",
            filters={"status": "Active", "branch": ("is", "set")},
            distinct=True,
            pluck="branch",
        )
        return sorted(set(stores))

    # Find employee record for current user
    employee = frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "branch")

    if employee:
        return [employee]

    return []


@frappe.whitelist()
def get_enrichment_summary() -> dict:
    """Get overall enrichment campaign summary.

    Returns:
        Dictionary with campaign-wide stats
    """
    sql = """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN custom_verification_status = 'Verified' THEN 1 ELSE 0 END) as verified,
            SUM(CASE WHEN custom_verification_status = 'Has Issues' THEN 1 ELSE 0 END) as has_issues,
            SUM(CASE WHEN custom_verification_status IN ('Pending', '', NULL) OR custom_verification_status IS NULL THEN 1 ELSE 0 END) as pending
        FROM `tabEmployee`
        WHERE status = 'Active'
    """
    result = frappe.db.sql(sql, as_dict=True)[0]

    result["progress_pct"] = round(result["verified"] / result["total"] * 100, 1) if result["total"] > 0 else 0

    # Get top stores by completion
    top_stores = frappe.db.sql(
        """
        SELECT
            branch,
            COUNT(*) as total,
            SUM(CASE WHEN custom_verification_status = 'Verified' THEN 1 ELSE 0 END) as verified
        FROM `tabEmployee`
        WHERE status = 'Active' AND branch IS NOT NULL AND branch != ''
        GROUP BY branch
        HAVING COUNT(*) > 0
        ORDER BY (SUM(CASE WHEN custom_verification_status = 'Verified' THEN 1 ELSE 0 END) / COUNT(*)) DESC
        LIMIT 5
    """,
        as_dict=True,
    )

    for store in top_stores:
        store["progress_pct"] = round(store["verified"] / store["total"] * 100, 1) if store["total"] > 0 else 0

    result["top_stores"] = top_stores

    return result


# ============================================================================
# Data Enrichment V2 APIs
# ============================================================================


@frappe.whitelist()
def submit_edit_request(
    employee: str,
    field_name: str,
    requested_value: str,
    reason: str,
    government_id_photo: str = None,
) -> dict:
    """Submit a field change request for HR review.

    Args:
        employee: Employee ID
        field_name: Field to change (must be in HR_APPROVAL_FIELDS)
        requested_value: New value requested
        reason: Reason for the change
        government_id_photo: Optional file path to uploaded government ID

    Returns:
        Success status and edit request ID
    """
    # Validate field is in HR approval list
    if field_name not in HR_APPROVAL_FIELDS:
        frappe.throw(_("Field '{0}' does not require HR approval. Use self-service update.").format(field_name))

    # Validate employee exists
    if not frappe.db.exists("Employee", employee):
        frappe.throw(_("Employee {0} not found").format(employee))

    # Get current value
    current_value = frappe.db.get_value("Employee", employee, field_name) or ""

    # Check for duplicate pending request
    existing = frappe.db.exists(
        "BEI Edit Request",
        {"employee": employee, "field_name": field_name, "status": "Pending"},
    )
    if existing:
        frappe.throw(_("You already have a pending request for this field. Please wait for HR review."))

    # Create edit request
    doc = frappe.get_doc(
        {
            "doctype": "BEI Edit Request",
            "employee": employee,
            "field_name": field_name,
            "field_label": FIELD_LABELS.get(field_name, field_name),
            "current_value": str(current_value),
            "requested_value": requested_value,
            "reason": reason,
            "government_id_photo": government_id_photo,
            "status": "Pending",
        }
    )
    doc.insert(ignore_permissions=True)

    # Update employee enrichment status
    frappe.db.set_value("Employee", employee, "custom_enrichment_status", "In Progress")

    # Notify HR via Google Chat (if configured)
    _notify_hr_new_request(doc)

    return {
        "status": "success",
        "message": _("Edit request submitted. HR will review within 2 business days."),
        "edit_request_id": doc.name,
    }


@frappe.whitelist()
def get_my_edit_requests() -> list:
    """Get all edit requests for current user's employee record.

    Returns:
        List of edit requests with status
    """
    user = frappe.session.user
    employee = frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "name")

    if not employee:
        return []

    requests = frappe.get_all(
        "BEI Edit Request",
        filters={"employee": employee},
        fields=[
            "name",
            "field_name",
            "field_label",
            "current_value",
            "requested_value",
            "reason",
            "status",
            "submission_date",
            "hr_notes",
            "processed_date",
        ],
        order_by="submission_date desc",
    )

    return requests


@frappe.whitelist()
def get_pending_edit_requests(branch: str = None, field_name: str = None) -> list:
    """Get pending edit requests for HR review.

    Args:
        branch: Optional filter by branch
        field_name: Optional filter by field name

    Returns:
        List of pending edit requests
    """
    # Check HR role
    roles = frappe.get_roles()
    if "HR User" not in roles and "HR Manager" not in roles and "System Manager" not in roles:
        frappe.throw(_("You don't have permission to view edit requests"))

    filters = {"status": "Pending"}
    if field_name:
        filters["field_name"] = field_name

    requests = frappe.get_all(
        "BEI Edit Request",
        filters=filters,
        fields=[
            "name",
            "employee",
            "employee_name",
            "branch",
            "field_name",
            "field_label",
            "current_value",
            "requested_value",
            "reason",
            "government_id_photo",
            "submission_date",
        ],
        order_by="submission_date asc",
    )

    # Filter by branch if specified
    if branch:
        requests = [r for r in requests if r.get("branch") == branch]

    return requests


@frappe.whitelist()
def process_edit_request(
    edit_request: str,
    action: str,
    hr_notes: str = None,
) -> dict:
    """Approve, reject, or request more info for an edit request.

    Args:
        edit_request: Edit request name/ID
        action: One of "approve", "reject", "request_info"
        hr_notes: Optional notes from HR

    Returns:
        Success status and message
    """
    # Check HR role
    roles = frappe.get_roles()
    if "HR User" not in roles and "HR Manager" not in roles and "System Manager" not in roles:
        frappe.throw(_("You don't have permission to process edit requests"))

    if action not in ("approve", "reject", "request_info"):
        frappe.throw(_("Invalid action. Must be 'approve', 'reject', or 'request_info'"))

    doc = frappe.get_doc("BEI Edit Request", edit_request)

    if doc.status != "Pending" and doc.status != "More Info Needed":
        frappe.throw(_("This request has already been processed"))

    doc.hr_notes = hr_notes
    doc.processed_by = frappe.session.user
    doc.processed_date = now_datetime()

    if action == "approve":
        doc.status = "Approved"
        # The on_update hook in the DocType will apply the change
    elif action == "reject":
        doc.status = "Rejected"
    else:
        doc.status = "More Info Needed"

    doc.save(ignore_permissions=True)

    action_messages = {
        "approve": _("Edit request approved and employee record updated."),
        "reject": _("Edit request rejected."),
        "request_info": _("Request for more information sent to employee."),
    }

    return {"status": "success", "message": action_messages[action]}


@frappe.whitelist()
def update_self_service_field(employee: str, field_name: str, value: str) -> dict:
    """Update a self-service field without approval.

    Args:
        employee: Employee ID
        field_name: Field to update (must be in SELF_SERVICE_FIELDS)
        value: New value

    Returns:
        Success status and message
    """
    # Validate field is self-service
    if field_name not in SELF_SERVICE_FIELDS:
        frappe.throw(
            _("Field '{0}' requires HR approval. Please submit an edit request.").format(field_name)
        )

    # Validate user can edit this employee (must be own record)
    user = frappe.session.user
    user_employee = frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "name")

    if user_employee != employee:
        # Allow HR to edit any employee
        roles = frappe.get_roles()
        if "HR User" not in roles and "HR Manager" not in roles and "System Manager" not in roles:
            frappe.throw(_("You can only edit your own profile"))

    # Use db.set_value to bypass document validation (some test/legacy employees
    # may have data quality issues like missing naming_series)
    frappe.db.set_value("Employee", employee, field_name, value, update_modified=True)

    # Update enrichment status if not already complete
    current_status = frappe.db.get_value("Employee", employee, "custom_enrichment_status")
    if current_status != "Complete":
        frappe.db.set_value("Employee", employee, "custom_enrichment_status", "In Progress")

    return {
        "status": "success",
        "message": _("Field '{0}' updated successfully").format(FIELD_LABELS.get(field_name, field_name)),
    }


@frappe.whitelist()
def search_employees(query: str, branch: str = None, limit: int = 20) -> list:
    """Search employees by name OR nickname.

    Args:
        query: Search term
        branch: Optional branch filter
        limit: Max results (default 20)

    Returns:
        List of matching employees with match_type indicator
    """
    if not query or len(query) < 2:
        return []

    query = query.strip()
    query_lower = query.lower()

    # Build SQL with nickname search
    sql = """
        SELECT
            name as employee_id,
            employee_name,
            custom_nickname as nickname,
            branch,
            designation,
            image,
            CASE
                WHEN LOWER(COALESCE(custom_nickname, '')) LIKE %(query_like)s THEN 'nickname'
                ELSE 'name'
            END as match_type
        FROM `tabEmployee`
        WHERE status = 'Active'
          AND (
            LOWER(employee_name) LIKE %(query_like)s
            OR LOWER(first_name) LIKE %(query_like)s
            OR LOWER(last_name) LIKE %(query_like)s
            OR LOWER(COALESCE(custom_nickname, '')) LIKE %(query_like)s
          )
    """

    params = {"query_like": f"%{query_lower}%"}

    if branch:
        sql += " AND branch = %(branch)s"
        params["branch"] = branch

    # Order by nickname matches first
    sql += """
        ORDER BY
            CASE WHEN LOWER(COALESCE(custom_nickname, '')) LIKE %(query_like)s THEN 0 ELSE 1 END,
            employee_name
        LIMIT %(limit)s
    """
    params["limit"] = limit

    results = frappe.db.sql(sql, params, as_dict=True)

    return results


@frappe.whitelist()
def get_enrichment_tracker(
    branch: str = None,
    status: str = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Get employees grouped by enrichment status for HR tracking.

    Args:
        branch: Optional branch filter
        status: Optional enrichment status filter
        page: Page number (1-indexed)
        page_size: Results per page

    Returns:
        Summary stats, by-branch breakdown, and paginated employee list
    """
    # Check HR role
    roles = frappe.get_roles()
    if "HR User" not in roles and "HR Manager" not in roles and "System Manager" not in roles:
        frappe.throw(_("You don't have permission to view the enrichment tracker"))

    # Get summary stats
    summary_sql = """
        SELECT
            COUNT(*) as total_employees,
            SUM(CASE WHEN COALESCE(custom_enrichment_status, 'Not Started') = 'Not Started' THEN 1 ELSE 0 END) as not_started,
            SUM(CASE WHEN custom_enrichment_status = 'In Progress' THEN 1 ELSE 0 END) as in_progress,
            SUM(CASE WHEN custom_enrichment_status = 'Submitted' THEN 1 ELSE 0 END) as submitted,
            SUM(CASE WHEN custom_enrichment_status = 'Complete' THEN 1 ELSE 0 END) as complete
        FROM `tabEmployee`
        WHERE status = 'Active'
    """
    summary = frappe.db.sql(summary_sql, as_dict=True)[0]

    # Get by-branch breakdown
    by_branch_sql = """
        SELECT
            branch,
            COUNT(*) as total,
            SUM(CASE WHEN COALESCE(custom_enrichment_status, 'Not Started') = 'Not Started' THEN 1 ELSE 0 END) as not_started,
            SUM(CASE WHEN custom_enrichment_status = 'Complete' THEN 1 ELSE 0 END) as complete
        FROM `tabEmployee`
        WHERE status = 'Active' AND branch IS NOT NULL AND branch != ''
        GROUP BY branch
        ORDER BY branch
    """
    by_branch = frappe.db.sql(by_branch_sql, as_dict=True)

    for row in by_branch:
        row["progress_pct"] = round(row["complete"] / row["total"] * 100, 1) if row["total"] > 0 else 0

    # Get paginated employee list
    filters = {"status": "Active"}
    if branch:
        filters["branch"] = branch
    if status:
        if status == "Not Started":
            filters["custom_enrichment_status"] = ("in", ["Not Started", "", None])
        else:
            filters["custom_enrichment_status"] = status

    offset = (page - 1) * page_size

    employees = frappe.get_all(
        "Employee",
        filters=filters,
        fields=[
            "name as employee_id",
            "employee_name",
            "branch",
            "custom_enrichment_status as enrichment_status",
            "user_id as email",
            "cell_number",
        ],
        order_by="custom_enrichment_status asc, employee_name asc",
        start=offset,
        page_length=page_size,
    )

    # Fix null enrichment status
    for emp in employees:
        if not emp.get("enrichment_status"):
            emp["enrichment_status"] = "Not Started"

    # Get total count for pagination
    total_count = frappe.db.count("Employee", filters)
    total_pages = (total_count + page_size - 1) // page_size

    # Get pending edit requests count
    pending_requests = frappe.db.count("BEI Edit Request", {"status": "Pending"})

    return {
        "summary": summary,
        "by_branch": by_branch,
        "employees": employees,
        "pending_edit_requests": pending_requests,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": total_pages,
        },
    }


@frappe.whitelist()
def send_enrichment_reminders(
    employees: list = None,
    branch: str = None,
    method: str = "email",
) -> dict:
    """Send reminder notifications to employees who haven't completed enrichment.

    Args:
        employees: Optional list of employee IDs. If None, sends to all not_started.
        branch: Optional branch filter (only used if employees is None)
        method: "email", "chat", or "both"

    Returns:
        Success status with sent/failed counts
    """
    # Check HR role
    roles = frappe.get_roles()
    if "HR User" not in roles and "HR Manager" not in roles and "System Manager" not in roles:
        frappe.throw(_("You don't have permission to send reminders"))

    if method not in ("email", "chat", "both"):
        frappe.throw(_("Invalid method. Must be 'email', 'chat', or 'both'"))

    # Get target employees
    if employees:
        if isinstance(employees, str):
            employees = frappe.parse_json(employees)
        targets = frappe.get_all(
            "Employee",
            filters={"name": ("in", employees), "status": "Active"},
            fields=["name", "employee_name", "user_id", "cell_number"],
        )
    else:
        filters = {
            "status": "Active",
            "custom_enrichment_status": ("in", ["Not Started", "", None]),
        }
        if branch:
            filters["branch"] = branch
        targets = frappe.get_all(
            "Employee",
            filters=filters,
            fields=["name", "employee_name", "user_id", "cell_number"],
        )

    sent_count = 0
    failed_count = 0
    failures = []

    for emp in targets:
        try:
            if method in ("email", "both") and emp.get("user_id"):
                frappe.sendmail(
                    recipients=[emp["user_id"]],
                    subject=_("Action Required: Complete Your Profile Data"),
                    message=_(
                        """
                        <p>Hi {name},</p>
                        <p>You haven't completed your data enrichment in my.bebang.ph yet.</p>
                        <p>Please log in and verify/update your information:</p>
                        <ul>
                            <li>Personal contact details</li>
                            <li>Emergency contact</li>
                            <li>Government ID numbers</li>
                            <li>Nickname (so your supervisor can find you!)</li>
                        </ul>
                        <p><a href="https://my.bebang.ph">Login now</a></p>
                        <p>This helps ensure you receive correct payroll, benefits, and communications.</p>
                        <p>Thanks,<br>BEI HR Team</p>
                        """
                    ).format(name=emp["employee_name"]),
                )
                sent_count += 1
            elif not emp.get("user_id"):
                failures.append(f"{emp['name']}: No email address")
                failed_count += 1
        except Exception as e:
            failures.append(f"{emp['name']}: {str(e)}")
            failed_count += 1

    return {
        "status": "success",
        "sent_count": sent_count,
        "failed_count": failed_count,
        "failures": failures[:10],  # Limit failures returned
    }


@frappe.whitelist()
def mark_enrichment_complete(employee: str) -> dict:
    """Mark an employee's enrichment as complete (HR only).

    Args:
        employee: Employee ID

    Returns:
        Success status and message
    """
    # Check HR role
    roles = frappe.get_roles()
    if "HR User" not in roles and "HR Manager" not in roles and "System Manager" not in roles:
        frappe.throw(_("You don't have permission to mark enrichment complete"))

    frappe.db.set_value(
        "Employee",
        employee,
        {
            "custom_enrichment_status": "Complete",
            "custom_enrichment_complete_date": today(),
        },
    )

    emp_name = frappe.db.get_value("Employee", employee, "employee_name")

    return {"status": "success", "message": _("Enrichment marked complete for {0}").format(emp_name)}


def _notify_hr_new_request(doc):
    """Send Google Chat notification to HR about new edit request."""
    try:
        # Import Google Chat notification function if available
        from hrms.api.google_chat import send_message_to_space

        message = _(
            """*Edit Request Submitted*

Employee: {employee_name}
Branch: {branch}
Field: {field_label}
Change: "{current}" → "{requested}"

{photo_note}

Review at: https://my.bebang.ph/dashboard/hr/enrichment-tracker"""
        ).format(
            employee_name=doc.employee_name,
            branch=doc.branch or "N/A",
            field_label=doc.field_label,
            current=doc.current_value or "(empty)",
            requested=doc.requested_value,
            photo_note="Government ID attached" if doc.government_id_photo else "No ID attached",
        )

        # Send to HR space (ERP Automation Committee)
        from hrms.utils.bei_config import get_chat_space, SPACE_ERP_AUTOMATION
        send_message_to_space(get_chat_space(SPACE_ERP_AUTOMATION), message)
    except Exception:
        # Don't fail if chat notification fails
        pass
