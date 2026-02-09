"""BEI Employee Transfer API endpoints.

Handles employee transfers between stores/branches with biometric
re-registration tracking.
"""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import getdate, today
from hrms.utils.api_helpers import (
    _get_employee_or_throw,
    _check_hr_permission,
    _paginate,
)


@frappe.whitelist()
@rate_limit(limit=10, seconds=60)
def create_transfer(employee, new_store, new_shift, reason, effective_date, new_supervisor=None):
    """Initiate employee transfer.

    Args:
        employee: Employee ID
        new_store: New warehouse/branch (Link: Warehouse)
        new_shift: New shift type (Link: Shift Type)
        reason: Transfer reason (Performance-based/Operational Need/Employee Request/Promotion)
        effective_date: Transfer effective date
        new_supervisor: New reporting manager (optional)

    Returns:
        Created transfer name

    Access: HR only
    """
    _check_hr_permission()

    # Validate required fields
    if not all([employee, new_store, new_shift, reason, effective_date]):
        frappe.throw(_("All fields are required: employee, new_store, new_shift, reason, effective_date"))

    # Validate employee exists
    if not frappe.db.exists("Employee", employee):
        frappe.throw(_("Employee not found"), frappe.DoesNotExistError)

    # Validate new store exists
    if not frappe.db.exists("Warehouse", new_store):
        frappe.throw(_("Store/branch not found"), frappe.DoesNotExistError)

    # Validate shift exists
    if not frappe.db.exists("Shift Type", new_shift):
        frappe.throw(_("Shift type not found"), frappe.DoesNotExistError)

    # Get employee current details
    emp_doc = frappe.get_doc("Employee", employee)
    old_store = emp_doc.branch
    old_supervisor = emp_doc.reports_to

    # Create Employee Transfer document
    transfer = frappe.get_doc({
        "doctype": "Employee Transfer",
        "employee": employee,
        "transfer_date": getdate(effective_date),
        "company": emp_doc.company,
        # Standard fields
        "new_company": emp_doc.company,  # Internal transfer, same company
        # Custom fields (assumes these exist on Employee Transfer)
        "bei_transfer_reason": reason,
        "bei_new_store": new_store,
        "bei_new_shift": new_shift,
        "bei_effective_date": getdate(effective_date),
        "bei_old_store": old_store,
        "bei_old_supervisor": old_supervisor,
        "bei_new_supervisor": new_supervisor,
        "bei_biometric_reregistered": 0,
    })

    transfer.insert(ignore_permissions=True)
    frappe.db.commit()

    # Notify relevant parties
    _notify_transfer_created(transfer, emp_doc)

    return {
        "message": _("Transfer initiated successfully"),
        "name": transfer.name,
    }


def _notify_transfer_created(transfer, emp_doc):
    """Notify employee, old/new supervisors, and HR of transfer."""
    recipients = []

    # Add employee
    if emp_doc.user_id:
        recipients.append(emp_doc.user_id)

    # Add old supervisor
    if transfer.bei_old_supervisor:
        old_sup_email = frappe.db.get_value("Employee", transfer.bei_old_supervisor, "user_id")
        if old_sup_email:
            recipients.append(old_sup_email)

    # Add new supervisor
    if transfer.bei_new_supervisor:
        new_sup_email = frappe.db.get_value("Employee", transfer.bei_new_supervisor, "user_id")
        if new_sup_email:
            recipients.append(new_sup_email)

    new_store_name = frappe.db.get_value("Warehouse", transfer.bei_new_store, "warehouse_name")

    if recipients:
        frappe.sendmail(
            recipients=list(set(recipients)),  # Deduplicate
            subject=_("Employee Transfer: {0}").format(emp_doc.employee_name),
            message=_("""
            An employee transfer has been initiated:<br><br>
            <strong>Employee:</strong> {employee_name} ({employee})<br>
            <strong>Reason:</strong> {reason}<br>
            <strong>New Store:</strong> {new_store}<br>
            <strong>Effective Date:</strong> {effective_date}<br>
            <strong>Transfer ID:</strong> {transfer_id}<br><br>
            This transfer is pending approval.
            """).format(
                employee_name=emp_doc.employee_name,
                employee=emp_doc.name,
                reason=transfer.bei_transfer_reason,
                new_store=new_store_name,
                effective_date=frappe.format_date(transfer.bei_effective_date),
                transfer_id=transfer.name,
            ),
            reference_doctype="Employee Transfer",
            reference_name=transfer.name,
        )


@frappe.whitelist()
def get_transfer_list(status=None, department=None, page=1):
    """List employee transfers.

    Args:
        status: Filter by status (Draft/Submitted/Approved/Cancelled)
        department: Filter by department
        page: Page number

    Returns:
        Paginated list of transfers

    Access: HR only
    """
    _check_hr_permission()

    page = int(page) if page else 1

    # Build filters
    filters = {}
    if status:
        if status == "Draft":
            filters["docstatus"] = 0
        elif status == "Submitted":
            filters["docstatus"] = 1
        elif status == "Cancelled":
            filters["docstatus"] = 2

    # Get transfers
    transfers = frappe.db.sql("""
        SELECT
            et.name,
            et.employee,
            e.employee_name,
            e.designation,
            e.department,
            et.transfer_date,
            et.bei_transfer_reason as reason,
            et.bei_old_store as old_store,
            et.bei_new_store as new_store,
            et.bei_biometric_reregistered as biometric_done,
            et.docstatus,
            et.creation
        FROM
            `tabEmployee Transfer` et
        INNER JOIN
            `tabEmployee` e ON et.employee = e.name
        WHERE
            1=1
            {department_filter}
            {status_filter}
        ORDER BY
            et.creation DESC
    """.format(
        department_filter="AND e.department = %(department)s" if department else "",
        status_filter="AND et.docstatus = %(docstatus)s" if status else "",
    ), {
        "department": department,
        "docstatus": filters.get("docstatus"),
    }, as_dict=True)

    # Enrich with store names
    for transfer in transfers:
        if transfer.old_store:
            transfer["old_store_name"] = frappe.db.get_value("Warehouse", transfer.old_store, "warehouse_name")
        if transfer.new_store:
            transfer["new_store_name"] = frappe.db.get_value("Warehouse", transfer.new_store, "warehouse_name")

        # Map docstatus to readable status
        if transfer.docstatus == 0:
            transfer["status"] = "Draft"
        elif transfer.docstatus == 1:
            transfer["status"] = "Approved"
        elif transfer.docstatus == 2:
            transfer["status"] = "Cancelled"

    return _paginate(transfers, page=page, page_size=20)


@frappe.whitelist()
@rate_limit(limit=10, seconds=60)
def approve_transfer(transfer_name, action, notes=None):
    """Approve or reject transfer.

    Args:
        transfer_name: Employee Transfer document name
        action: "approve" or "reject"
        notes: Approval/rejection notes (optional)

    Returns:
        Success message

    Access: Manager, HR
    """
    if not frappe.db.exists("Employee Transfer", transfer_name):
        frappe.throw(_("Transfer not found"), frappe.DoesNotExistError)

    transfer = frappe.get_doc("Employee Transfer", transfer_name)

    # Permission check
    current_employee = _get_employee_or_throw()
    roles = frappe.get_roles(frappe.session.user)
    is_hr = any(r in roles for r in ["HR Manager", "System Manager"])

    # Must be HR or old/new supervisor
    is_old_supervisor = transfer.bei_old_supervisor == current_employee
    is_new_supervisor = transfer.bei_new_supervisor == current_employee

    if not (is_hr or is_old_supervisor or is_new_supervisor):
        frappe.throw(_("Permission denied. You are not authorized to approve this transfer."), frappe.PermissionError)

    if action == "approve":
        # Submit the transfer
        transfer.submit()
        frappe.db.commit()

        # Apply transfer changes to Employee record
        _apply_transfer(transfer)

        # Log notes if provided
        if notes:
            transfer.add_comment("Comment", f"Approval Notes: {notes}")

        # Notify parties
        _notify_transfer_approved(transfer)

        return {
            "message": _("Transfer approved successfully"),
        }

    elif action == "reject":
        # Cancel the transfer
        transfer.cancel()
        frappe.db.commit()

        # Log notes
        if notes:
            transfer.add_comment("Comment", f"Rejection Reason: {notes}")

        # Notify parties
        _notify_transfer_rejected(transfer, notes)

        return {
            "message": _("Transfer rejected"),
        }

    else:
        frappe.throw(_("Invalid action. Use 'approve' or 'reject'."))


def _apply_transfer(transfer):
    """Apply approved transfer to Employee record.

    Updates: branch, reports_to, shift assignment
    """
    employee = frappe.get_doc("Employee", transfer.employee)

    # Update branch (store)
    employee.branch = transfer.bei_new_store

    # Update supervisor if provided
    if transfer.bei_new_supervisor:
        employee.reports_to = transfer.bei_new_supervisor

    employee.save(ignore_permissions=True)

    # Create new shift assignment
    if transfer.bei_new_shift:
        # End current shift assignments
        current_shifts = frappe.get_all(
            "Shift Assignment",
            filters={
                "employee": transfer.employee,
                "docstatus": 1,
                "status": "Active",
            },
            fields=["name"],
        )

        for shift in current_shifts:
            shift_doc = frappe.get_doc("Shift Assignment", shift.name)
            shift_doc.status = "Inactive"
            shift_doc.end_date = transfer.bei_effective_date
            shift_doc.save(ignore_permissions=True)

        # Create new shift assignment
        new_shift = frappe.get_doc({
            "doctype": "Shift Assignment",
            "employee": transfer.employee,
            "shift_type": transfer.bei_new_shift,
            "start_date": transfer.bei_effective_date,
            "status": "Active",
            "company": employee.company,
        })
        new_shift.insert(ignore_permissions=True)
        new_shift.submit()

    frappe.db.commit()


def _notify_transfer_approved(transfer):
    """Notify employee and supervisors of approved transfer."""
    emp_doc = frappe.get_doc("Employee", transfer.employee)
    new_store_name = frappe.db.get_value("Warehouse", transfer.bei_new_store, "warehouse_name")

    recipients = []
    if emp_doc.user_id:
        recipients.append(emp_doc.user_id)

    if recipients:
        frappe.sendmail(
            recipients=recipients,
            subject=_("Transfer Approved: {0}").format(emp_doc.employee_name),
            message=_("""
            Your transfer has been approved:<br><br>
            <strong>New Store:</strong> {new_store}<br>
            <strong>Effective Date:</strong> {effective_date}<br>
            <strong>New Shift:</strong> {new_shift}<br><br>
            <strong>Important:</strong> You must re-register your biometric attendance
            at the new location. Contact your new supervisor or HR for assistance.
            """).format(
                new_store=new_store_name,
                effective_date=frappe.format_date(transfer.bei_effective_date),
                new_shift=transfer.bei_new_shift,
            ),
            reference_doctype="Employee Transfer",
            reference_name=transfer.name,
        )


def _notify_transfer_rejected(transfer, notes):
    """Notify employee of rejected transfer."""
    emp_doc = frappe.get_doc("Employee", transfer.employee)

    if emp_doc.user_id:
        frappe.sendmail(
            recipients=[emp_doc.user_id],
            subject=_("Transfer Not Approved"),
            message=_("""
            Your transfer request has been declined.<br><br>
            <strong>Reason:</strong> {notes}<br><br>
            Please contact HR if you have questions.
            """).format(
                notes=notes or "Not specified",
            ),
            reference_doctype="Employee Transfer",
            reference_name=transfer.name,
        )


@frappe.whitelist()
def get_transfer_detail(transfer_name):
    """Get full transfer details.

    Args:
        transfer_name: Employee Transfer document name

    Returns:
        Full transfer details

    Access: HR
    """
    _check_hr_permission()

    if not frappe.db.exists("Employee Transfer", transfer_name):
        frappe.throw(_("Transfer not found"), frappe.DoesNotExistError)

    transfer = frappe.get_doc("Employee Transfer", transfer_name)

    # Get employee details
    emp_doc = frappe.get_doc("Employee", transfer.employee)

    # Get store names
    old_store_name = None
    if transfer.bei_old_store:
        old_store_name = frappe.db.get_value("Warehouse", transfer.bei_old_store, "warehouse_name")

    new_store_name = None
    if transfer.bei_new_store:
        new_store_name = frappe.db.get_value("Warehouse", transfer.bei_new_store, "warehouse_name")

    # Get supervisor names
    old_supervisor_name = None
    if transfer.bei_old_supervisor:
        old_supervisor_name = frappe.db.get_value("Employee", transfer.bei_old_supervisor, "employee_name")

    new_supervisor_name = None
    if transfer.bei_new_supervisor:
        new_supervisor_name = frappe.db.get_value("Employee", transfer.bei_new_supervisor, "employee_name")

    # Map docstatus
    if transfer.docstatus == 0:
        status = "Draft"
    elif transfer.docstatus == 1:
        status = "Approved"
    elif transfer.docstatus == 2:
        status = "Cancelled"

    return {
        "name": transfer.name,
        "employee": transfer.employee,
        "employee_name": emp_doc.employee_name,
        "designation": emp_doc.designation,
        "department": emp_doc.department,
        "transfer_reason": transfer.bei_transfer_reason,
        "effective_date": transfer.bei_effective_date,
        "old_store": transfer.bei_old_store,
        "old_store_name": old_store_name,
        "new_store": transfer.bei_new_store,
        "new_store_name": new_store_name,
        "old_supervisor": transfer.bei_old_supervisor,
        "old_supervisor_name": old_supervisor_name,
        "new_supervisor": transfer.bei_new_supervisor,
        "new_supervisor_name": new_supervisor_name,
        "new_shift": transfer.bei_new_shift,
        "biometric_reregistered": transfer.bei_biometric_reregistered,
        "status": status,
        "docstatus": transfer.docstatus,
        "creation": transfer.creation,
        "modified": transfer.modified,
    }
