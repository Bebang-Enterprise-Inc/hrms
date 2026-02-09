"""BEI Employee Transfer API endpoints.

Handles employee transfers between stores/branches.
Uses standard Employee Transfer DocType with transfer_details child table.
"""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import getdate
from hrms.utils.api_helpers import (
    _get_employee_or_throw,
    _check_hr_permission,
    _paginate,
)


@frappe.whitelist()
@rate_limit(limit=10, seconds=60)
def create_transfer(employee, new_branch, transfer_date, reason,
                    new_department=None, new_designation=None, new_reports_to=None):
    """Initiate employee transfer.

    Args:
        employee: Employee ID
        new_branch: New branch/store (Link: Branch)
        transfer_date: Transfer effective date
        reason: Transfer reason
        new_department: New department (optional)
        new_designation: New designation (optional)
        new_reports_to: New reporting manager (optional)

    Returns:
        Created transfer name

    Access: HR only
    """
    _check_hr_permission()

    if not all([employee, new_branch, transfer_date, reason]):
        frappe.throw(_("Required: employee, new_branch, transfer_date, reason"))

    if not frappe.db.exists("Employee", employee):
        frappe.throw(_("Employee not found"), frappe.DoesNotExistError)

    emp_doc = frappe.get_doc("Employee", employee)

    # Build transfer_details rows for each property change
    transfer_details = []

    # Branch change (always included)
    transfer_details.append({
        "property": "Branch",
        "current": emp_doc.branch or "",
        "new": new_branch,
    })

    # Department change (optional)
    if new_department and new_department != emp_doc.department:
        transfer_details.append({
            "property": "Department",
            "current": emp_doc.department or "",
            "new": new_department,
        })

    # Designation change (optional)
    if new_designation and new_designation != emp_doc.designation:
        transfer_details.append({
            "property": "Designation",
            "current": emp_doc.designation or "",
            "new": new_designation,
        })

    # Reports To change (optional)
    if new_reports_to and new_reports_to != emp_doc.reports_to:
        transfer_details.append({
            "property": "Reports To",
            "current": emp_doc.reports_to or "",
            "new": new_reports_to,
        })

    transfer = frappe.get_doc({
        "doctype": "Employee Transfer",
        "employee": employee,
        "transfer_date": getdate(transfer_date),
        "company": emp_doc.company,
        "new_company": emp_doc.company,
        "transfer_details": transfer_details,
    })

    transfer.insert(ignore_permissions=True)

    # Store reason as comment
    transfer.add_comment("Comment", text=f"Transfer Reason: {reason}")

    frappe.db.commit()

    return {
        "message": _("Transfer initiated successfully"),
        "name": transfer.name,
    }


@frappe.whitelist()
def get_transfer_list(status=None, department=None, from_date=None, to_date=None,
                      page=1, page_size=20):
    """List employee transfers.

    Args:
        status: Filter by status (Draft/Submitted/Approved/Cancelled)
        department: Filter by department
        from_date: Filter transfers from this date
        to_date: Filter transfers until this date
        page: Page number
        page_size: Items per page

    Returns:
        Paginated list of transfers

    Access: HR only
    """
    _check_hr_permission()

    page = int(page) if page else 1

    # Build WHERE clauses
    conditions = ["1=1"]
    values = {}

    if status:
        if status == "Draft":
            conditions.append("et.docstatus = 0")
        elif status in ("Submitted", "Approved"):
            conditions.append("et.docstatus = 1")
        elif status == "Cancelled":
            conditions.append("et.docstatus = 2")

    if department:
        conditions.append("e.department = %(department)s")
        values["department"] = department

    if from_date:
        conditions.append("et.transfer_date >= %(from_date)s")
        values["from_date"] = from_date

    if to_date:
        conditions.append("et.transfer_date <= %(to_date)s")
        values["to_date"] = to_date

    where_clause = " AND ".join(conditions)

    transfers = frappe.db.sql("""
        SELECT
            et.name,
            et.employee,
            e.employee_name,
            e.designation,
            e.department,
            e.branch as from_branch,
            et.transfer_date,
            et.docstatus,
            et.creation
        FROM
            `tabEmployee Transfer` et
        INNER JOIN
            `tabEmployee` e ON et.employee = e.name
        WHERE
            {where_clause}
        ORDER BY
            et.creation DESC
    """.format(where_clause=where_clause), values, as_dict=True)

    # Enrich with transfer details (branch changes, reason)
    for transfer in transfers:
        # Get branch change from transfer_details child table
        details = frappe.get_all(
            "Employee Property History",
            filters={"parent": transfer.name, "parenttype": "Employee Transfer"},
            fields=["property", "current", "new"],
        )

        transfer["to_branch"] = transfer.get("from_branch", "")
        transfer["new_branch"] = ""
        transfer["new_department"] = ""
        transfer["new_designation"] = ""
        transfer["reason"] = ""

        for detail in details:
            if detail.property == "Branch":
                transfer["from_branch"] = detail.current
                transfer["to_branch"] = detail.new
                transfer["new_branch"] = detail.new
            elif detail.property == "Department":
                transfer["new_department"] = detail.new
            elif detail.property == "Designation":
                transfer["new_designation"] = detail.new

        # Get reason from comments
        reason_comment = frappe.db.get_value(
            "Comment",
            {"reference_doctype": "Employee Transfer", "reference_name": transfer.name,
             "content": ["like", "%Transfer Reason:%"]},
            "content",
        )
        if reason_comment:
            transfer["reason"] = reason_comment.replace("Transfer Reason: ", "")

        # Map docstatus to readable status
        if transfer.docstatus == 0:
            transfer["status"] = "Draft"
        elif transfer.docstatus == 1:
            transfer["status"] = "Approved"
        elif transfer.docstatus == 2:
            transfer["status"] = "Cancelled"

    return _paginate(transfers, page=page, page_size=int(page_size))


@frappe.whitelist()
@rate_limit(limit=10, seconds=60)
def approve_transfer(transfer_id, action, remarks=None):
    """Approve or reject transfer.

    Args:
        transfer_id: Employee Transfer document name
        action: "approve" or "reject"
        remarks: Approval/rejection notes (optional)

    Returns:
        Success message

    Access: Manager, HR
    """
    if not frappe.db.exists("Employee Transfer", transfer_id):
        frappe.throw(_("Transfer not found"), frappe.DoesNotExistError)

    transfer = frappe.get_doc("Employee Transfer", transfer_id)

    # Permission check
    current_employee = _get_employee_or_throw()
    roles = frappe.get_roles(frappe.session.user)
    is_hr = any(r in roles for r in ["HR Manager", "HR User", "System Manager"])

    # Must be HR to approve/reject
    if not is_hr:
        frappe.throw(_("Permission denied. Only HR can approve transfers."), frappe.PermissionError)

    if action == "approve":
        if transfer.docstatus != 0:
            frappe.throw(_("Only draft transfers can be approved"))

        transfer.submit()

        if remarks:
            transfer.add_comment("Comment", f"Approval Notes: {remarks}")

        frappe.db.commit()

        return {
            "message": _("Transfer approved successfully"),
            "name": transfer.name,
        }

    elif action == "reject":
        if transfer.docstatus == 0:
            # Cancel draft
            transfer.docstatus = 2
            transfer.save()
        elif transfer.docstatus == 1:
            # Amend submitted
            transfer.cancel()

        if remarks:
            transfer.add_comment("Comment", f"Rejection Reason: {remarks}")

        frappe.db.commit()

        return {
            "message": _("Transfer rejected"),
            "name": transfer.name,
        }

    else:
        frappe.throw(_("Invalid action. Use 'approve' or 'reject'."))


@frappe.whitelist()
def get_transfer_detail(transfer_id):
    """Get full transfer details.

    Args:
        transfer_id: Employee Transfer document name

    Returns:
        Full transfer details with timeline

    Access: HR
    """
    _check_hr_permission()

    if not frappe.db.exists("Employee Transfer", transfer_id):
        frappe.throw(_("Transfer not found"), frappe.DoesNotExistError)

    transfer = frappe.get_doc("Employee Transfer", transfer_id)
    emp_doc = frappe.get_doc("Employee", transfer.employee)

    # Extract property changes
    from_branch = emp_doc.branch
    to_branch = emp_doc.branch
    new_department = None
    new_designation = None
    new_reports_to = None

    for detail in transfer.transfer_details:
        if detail.property == "Branch":
            from_branch = detail.current
            to_branch = detail.new
        elif detail.property == "Department":
            new_department = detail.new
        elif detail.property == "Designation":
            new_designation = detail.new
        elif detail.property == "Reports To":
            new_reports_to = detail.new

    # Get reason from comments
    reason = ""
    reason_comment = frappe.db.get_value(
        "Comment",
        {"reference_doctype": "Employee Transfer", "reference_name": transfer.name,
         "content": ["like", "%Transfer Reason:%"]},
        "content",
    )
    if reason_comment:
        reason = reason_comment.replace("Transfer Reason: ", "")

    # Map docstatus
    status_map = {0: "Draft", 1: "Approved", 2: "Cancelled"}
    status = status_map.get(transfer.docstatus, "Unknown")

    # Build timeline from comments and status changes
    timeline = []
    comments = frappe.get_all(
        "Comment",
        filters={
            "reference_doctype": "Employee Transfer",
            "reference_name": transfer.name,
        },
        fields=["comment_type", "content", "creation", "comment_by"],
        order_by="creation asc",
    )

    timeline.append({
        "stage": "Created",
        "date": str(transfer.creation),
        "status": "Draft",
        "user": transfer.owner,
    })

    for comment in comments:
        timeline.append({
            "stage": "Comment",
            "date": str(comment.creation),
            "status": status,
            "user": comment.comment_by,
            "remarks": comment.content,
        })

    if transfer.docstatus == 1:
        timeline.append({
            "stage": "Approved",
            "date": str(transfer.modified),
            "status": "Approved",
            "user": transfer.modified_by,
        })
    elif transfer.docstatus == 2:
        timeline.append({
            "stage": "Cancelled",
            "date": str(transfer.modified),
            "status": "Cancelled",
            "user": transfer.modified_by,
        })

    return {
        "name": transfer.name,
        "employee": transfer.employee,
        "employee_name": emp_doc.employee_name,
        "designation": emp_doc.designation,
        "department": emp_doc.department,
        "from_branch": from_branch,
        "to_branch": to_branch,
        "new_branch": to_branch,
        "new_department": new_department,
        "new_designation": new_designation,
        "new_reports_to": new_reports_to,
        "transfer_date": str(transfer.transfer_date),
        "reason": reason,
        "status": status,
        "docstatus": transfer.docstatus,
        "creation": str(transfer.creation),
        "modified": str(transfer.modified),
        "timeline": timeline,
    }
