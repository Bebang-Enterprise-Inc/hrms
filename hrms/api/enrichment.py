"""Employee Data Enrichment API.

Provides API endpoints for the Store Supervisor data verification dashboard.
"""
import frappe
from frappe import _
from frappe.utils import today


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
