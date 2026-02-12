"""
Petty Cash Fund (PCF) APIs
Handles PCF batch submission, threshold monitoring, and auto-submit workflows.

Author: Claude Code
Date: 2026-02-03
"""
import frappe
from frappe import _
from frappe.utils import today, now_datetime, flt, nowdate, getdate
from calendar import monthrange
from datetime import datetime
from hrms.api.store import save_base64_image


# ============================================================
# STORE STAFF ENDPOINTS
# ============================================================


@frappe.whitelist()
def add_expense_to_pending(
    manual_vendor: str,
    manual_description: str,
    manual_amount: float,
    manual_date: str,
    receipt_photo: str,
):
    """
    Add an expense to the pending PCF queue (status='Pending').
    Does NOT submit immediately - waits for batch submission.

    Args:
        manual_vendor: Where they bought it
        manual_description: What they bought (free text)
        manual_amount: How much they paid
        manual_date: When they paid
        receipt_photo: Attached receipt image

    Returns:
        Success response with expense ID and PCF status
    """
    if not manual_vendor or not manual_description or not manual_amount:
        frappe.throw(_("Vendor, description, and amount are required"))

    if not receipt_photo:
        frappe.throw(_("Receipt photo is required"))

    # Get employee from current user
    employee = frappe.db.get_value(
        "Employee",
        {"user_id": frappe.session.user},
        ["name", "employee_name", "branch", "company"],
        as_dict=True,
    )

    if not employee:
        frappe.throw(_("Employee record not found for current user"))

    # Look up warehouse for the employee's branch
    store = _get_store_for_employee(employee)
    if not store:
        frappe.throw(_("Could not find warehouse for your branch. Please contact HR."))

    # Check if store has PCF enabled
    pcf = frappe.db.get_value(
        "BEI Petty Cash Fund",
        {"store": store, "is_enabled": 1},
        ["name", "fund_amount", "pending_total", "threshold_percentage"],
        as_dict=True,
    )

    if not pcf:
        frappe.throw(
            _(
                "PCF is not enabled for this store. Please contact your supervisor or use the regular expense submission."
            )
        )

    # Create expense request with Pending status
    expense = frappe.new_doc("BEI Expense Request")
    expense.employee = employee.name
    expense.store = store
    expense.request_date = today()
    expense.manual_vendor = manual_vendor
    expense.manual_description = manual_description
    expense.manual_amount = flt(manual_amount)
    expense.manual_date = manual_date
    expense.receipt_photo = save_base64_image(receipt_photo, "BEI Expense Request", fieldname="receipt_photo")
    expense.status = "Pending"
    expense.added_to_pending_at = now_datetime()

    expense.insert(ignore_permissions=True)
    frappe.db.commit()

    # Update PCF totals
    from hrms.hr.doctype.bei_petty_cash_fund.bei_petty_cash_fund import update_pcf_totals

    pcf_doc = update_pcf_totals(store)

    # Check if threshold reached
    at_threshold = False
    if pcf_doc and pcf_doc.is_at_threshold():
        at_threshold = True
        # Send notification
        send_threshold_notification(store)

    return {
        "success": True,
        "expense_id": expense.name,
        "message": f"Expense added to PCF pending queue",
        "pcf_status": {
            "fund_amount": pcf_doc.fund_amount if pcf_doc else 0,
            "pending_total": pcf_doc.pending_total if pcf_doc else 0,
            "pending_count": pcf_doc.pending_count if pcf_doc else 0,
            "current_balance": pcf_doc.current_balance if pcf_doc else 0,
            "threshold_percentage": pcf_doc.threshold_percentage if pcf_doc else 50,
            "at_threshold": at_threshold,
        },
    }


@frappe.whitelist()
def get_my_pending_expenses():
    """
    Get current user's pending expenses.

    Returns:
        List of pending expenses for current user
    """
    employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
    if not employee:
        return {"success": True, "expenses": []}

    expenses = frappe.get_all(
        "BEI Expense Request",
        filters={"employee": employee, "status": "Pending"},
        fields=[
            "name",
            "manual_vendor",
            "manual_description",
            "manual_amount",
            "manual_date",
            "added_to_pending_at",
            "receipt_photo",
        ],
        order_by="manual_date asc",
    )

    return {"success": True, "expenses": expenses, "count": len(expenses)}


@frappe.whitelist()
def remove_pending_expense(expense_name: str):
    """
    Cancel a pending expense (only owner can cancel).

    Args:
        expense_name: Name of the BEI Expense Request

    Returns:
        Success response
    """
    expense = frappe.get_doc("BEI Expense Request", expense_name)

    # Check ownership
    employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
    if expense.employee != employee:
        frappe.throw(_("You can only cancel your own expenses"))

    # Check status
    if expense.status != "Pending":
        frappe.throw(_("Only pending expenses can be cancelled"))

    # Delete the expense
    store = expense.store
    expense.delete(ignore_permissions=True)
    frappe.db.commit()

    # Update PCF totals
    from hrms.hr.doctype.bei_petty_cash_fund.bei_petty_cash_fund import update_pcf_totals

    update_pcf_totals(store)

    return {"success": True, "message": "Expense removed from pending queue"}


@frappe.whitelist()
def edit_pending_expense(
    expense_name: str,
    manual_vendor: str = None,
    manual_description: str = None,
    manual_amount: float = None,
    manual_date: str = None,
    receipt_photo: str = None,
):
    """
    Edit a pending expense (only owner can edit, before batch submission).

    Args:
        expense_name: Name of the BEI Expense Request
        Other args: Fields to update (only non-None values are updated)

    Returns:
        Success response with updated expense
    """
    expense = frappe.get_doc("BEI Expense Request", expense_name)

    # Check ownership
    employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
    if expense.employee != employee:
        frappe.throw(_("You can only edit your own expenses"))

    # Check status
    if expense.status != "Pending":
        frappe.throw(_("Only pending expenses can be edited"))

    # Update provided fields
    if manual_vendor is not None:
        expense.manual_vendor = manual_vendor
    if manual_description is not None:
        expense.manual_description = manual_description
    if manual_amount is not None:
        expense.manual_amount = flt(manual_amount)
    if manual_date is not None:
        expense.manual_date = manual_date
    if receipt_photo is not None:
        expense.receipt_photo = save_base64_image(receipt_photo, "BEI Expense Request", fieldname="receipt_photo")

    expense.save(ignore_permissions=True)
    frappe.db.commit()

    # Update PCF totals
    from hrms.hr.doctype.bei_petty_cash_fund.bei_petty_cash_fund import update_pcf_totals

    update_pcf_totals(expense.store)

    return {
        "success": True,
        "message": "Expense updated",
        "expense": {
            "name": expense.name,
            "manual_vendor": expense.manual_vendor,
            "manual_description": expense.manual_description,
            "manual_amount": expense.manual_amount,
            "manual_date": expense.manual_date,
        },
    }


# ============================================================
# PCF STATUS ENDPOINTS
# ============================================================


@frappe.whitelist()
def get_pcf_status(store: str = None):
    """
    Get PCF status for a store.
    If store not provided, uses current user's store.

    Args:
        store: Warehouse name (optional)

    Returns:
        PCF status including balance, pending, threshold
    """
    if not store:
        # Get user's store
        employee = frappe.db.get_value(
            "Employee",
            {"user_id": frappe.session.user},
            ["branch", "company"],
            as_dict=True,
        )
        if employee:
            store = _get_store_for_employee(employee)

    if not store:
        return {"success": False, "error": "Store not found"}

    pcf = frappe.db.get_value(
        "BEI Petty Cash Fund",
        {"store": store},
        [
            "name",
            "store",
            "is_enabled",
            "fund_amount",
            "current_balance",
            "pending_total",
            "pending_count",
            "threshold_percentage",
            "auto_submit_enabled",
            "month_end_auto_submit",
            "custodian",
            "last_batch_date",
        ],
        as_dict=True,
    )

    if not pcf:
        return {"success": False, "error": "PCF not configured for this store"}

    # Calculate threshold info
    threshold_amount = pcf.fund_amount * pcf.threshold_percentage / 100
    at_threshold = (pcf.pending_total or 0) >= threshold_amount
    threshold_progress = (
        ((pcf.pending_total or 0) / pcf.fund_amount * 100) if pcf.fund_amount else 0
    )

    # Check for pending batch
    pending_batch = frappe.db.get_value(
        "BEI PCF Batch",
        {"store": store, "status": ["in", ["Submitted", "Under Review"]]},
        ["name", "status", "total_amount", "expense_count", "batch_date"],
        as_dict=True,
    )

    return {
        "success": True,
        "pcf": {
            "name": pcf.name,
            "store": pcf.store,
            "is_enabled": pcf.is_enabled,
            "fund_amount": pcf.fund_amount,
            "current_balance": pcf.current_balance,
            "pending_total": pcf.pending_total,
            "pending_count": pcf.pending_count,
            "threshold_percentage": pcf.threshold_percentage,
            "threshold_amount": threshold_amount,
            "threshold_progress": round(threshold_progress, 1),
            "at_threshold": at_threshold,
            "auto_submit_enabled": pcf.auto_submit_enabled,
            "month_end_auto_submit": pcf.month_end_auto_submit,
            "custodian": pcf.custodian,
            "last_batch_date": pcf.last_batch_date,
        },
        "pending_batch": pending_batch,
    }


@frappe.whitelist()
def get_store_pending_summary(store: str):
    """
    Get all pending expenses for a store (for custodian view).

    Args:
        store: Warehouse name

    Returns:
        Summary and list of all pending expenses
    """
    # Verify user is custodian or has permission
    pcf = frappe.db.get_value(
        "BEI Petty Cash Fund",
        {"store": store},
        ["name", "custodian", "backup_custodian"],
        as_dict=True,
    )

    if not pcf:
        frappe.throw(_("PCF not configured for this store"))

    user = frappe.session.user
    is_custodian = user in [pcf.custodian, pcf.backup_custodian]
    is_admin = "System Manager" in frappe.get_roles(user) or "Accounts Manager" in frappe.get_roles(user)

    if not is_custodian and not is_admin:
        frappe.throw(_("Only PCF custodians or managers can view store pending summary"))

    # Get all pending expenses
    expenses = frappe.get_all(
        "BEI Expense Request",
        filters={"store": store, "status": "Pending"},
        fields=[
            "name",
            "employee",
            "employee_name",
            "manual_vendor",
            "manual_description",
            "manual_amount",
            "manual_date",
            "added_to_pending_at",
            "receipt_photo",
        ],
        order_by="manual_date asc",
    )

    total_amount = sum(e.manual_amount or 0 for e in expenses)

    return {
        "success": True,
        "store": store,
        "expenses": expenses,
        "count": len(expenses),
        "total_amount": total_amount,
    }


@frappe.whitelist()
def get_pcf_custodians(store=None):
    """
    Get custodians for a store.

    Args:
        store: Warehouse name

    Returns:
        List of custodians
    """
    if not store:
        frappe.throw(_("Store is required"))

    pcf = frappe.db.get_value(
        "BEI Petty Cash Fund",
        {"store": store},
        ["custodian", "backup_custodian"],
        as_dict=True,
    )

    if not pcf:
        return {"success": False, "error": "PCF not configured for this store"}

    custodians = []
    if pcf.custodian:
        user_info = frappe.db.get_value("User", pcf.custodian, ["full_name", "email"], as_dict=True)
        custodians.append(
            {"user": pcf.custodian, "role": "Primary", "name": user_info.full_name if user_info else None}
        )
    if pcf.backup_custodian:
        user_info = frappe.db.get_value("User", pcf.backup_custodian, ["full_name", "email"], as_dict=True)
        custodians.append(
            {"user": pcf.backup_custodian, "role": "Backup", "name": user_info.full_name if user_info else None}
        )

    return {"success": True, "custodians": custodians}


# ============================================================
# BATCH ENDPOINTS
# ============================================================


@frappe.whitelist()
def submit_batch_now(store: str):
    """
    Manually submit a PCF batch for a store.

    Args:
        store: Warehouse name

    Returns:
        Created batch details
    """
    # Verify user is custodian
    pcf = frappe.db.get_value(
        "BEI Petty Cash Fund",
        {"store": store},
        ["name", "custodian", "backup_custodian"],
        as_dict=True,
    )

    if not pcf:
        frappe.throw(_("PCF not configured for this store"))

    user = frappe.session.user
    is_custodian = user in [pcf.custodian, pcf.backup_custodian]
    is_admin = "System Manager" in frappe.get_roles(user) or "Accounts Manager" in frappe.get_roles(user)

    if not is_custodian and not is_admin:
        frappe.throw(_("Only PCF custodians or managers can submit batches"))

    # Create batch
    from hrms.hr.doctype.bei_pcf_batch.bei_pcf_batch import create_batch_from_pending

    batch = create_batch_from_pending(store, "Manual")

    if not batch:
        frappe.throw(_("No pending expenses to submit"))

    return {
        "success": True,
        "batch": {
            "name": batch.name,
            "store": batch.store,
            "batch_date": batch.batch_date,
            "status": batch.status,
            "total_amount": batch.total_amount,
            "expense_count": batch.expense_count,
        },
        "message": f"Batch {batch.name} created with {batch.expense_count} expenses",
    }


@frappe.whitelist()
def get_batch_history(store: str = None, limit: int = 20, offset: int = 0):
    """
    Get batch history for a store.

    Args:
        store: Warehouse name or branch name (will resolve to full warehouse name)
        limit: Number of batches to return
        offset: Pagination offset

    Returns:
        List of past batches
    """
    # Resolve store from branch if needed
    resolved_store = _resolve_store_name(store)
    if not resolved_store:
        return {"success": True, "batches": [], "total": 0, "limit": limit, "offset": offset}

    batches = frappe.get_all(
        "BEI PCF Batch",
        filters={"store": resolved_store},
        fields=[
            "name",
            "batch_date",
            "status",
            "submission_type",
            "total_amount",
            "expense_count",
            "submitted_by",
            "submitted_at",
            "reviewed_by",
            "reviewed_at",
        ],
        order_by="batch_date desc",
        limit_page_length=limit,
        limit_start=offset,
    )

    total = frappe.db.count("BEI PCF Batch", {"store": resolved_store})

    return {
        "success": True,
        "batches": batches,
        "total": total,
        "limit": limit,
        "offset": offset,
        "store": resolved_store,
    }


@frappe.whitelist()
def get_batch_details(batch_name: str):
    """
    Get full batch details including items.

    Args:
        batch_name: Name of the BEI PCF Batch

    Returns:
        Full batch details with items
    """
    batch = frappe.get_doc("BEI PCF Batch", batch_name)

    items = []
    for item in batch.items:
        items.append(
            {
                "expense_request": item.expense_request,
                "employee": item.employee,
                "employee_name": item.employee_name,
                "expense_date": item.expense_date,
                "vendor": item.vendor,
                "description": item.description,
                "amount": item.amount,
                "item_status": item.item_status,
            }
        )

    return {
        "success": True,
        "batch": {
            "name": batch.name,
            "store": batch.store,
            "batch_date": batch.batch_date,
            "status": batch.status,
            "submission_type": batch.submission_type,
            "total_amount": batch.total_amount,
            "expense_count": batch.expense_count,
            "period_start": batch.period_start,
            "period_end": batch.period_end,
            "submitted_by": batch.submitted_by,
            "submitted_at": batch.submitted_at,
            "reviewed_by": batch.reviewed_by,
            "reviewed_at": batch.reviewed_at,
            "review_notes": batch.review_notes,
            "replenishment_requested": batch.replenishment_requested,
            "replenishment_amount": batch.replenishment_amount,
        },
        "items": items,
    }


@frappe.whitelist()
def approve_batch(batch_name: str, notes: str = None):
    """
    Accounting approves a PCF batch.

    Args:
        batch_name: Name of the BEI PCF Batch
        notes: Optional review notes

    Returns:
        Updated batch status
    """
    # Check permissions
    user = frappe.session.user
    is_accounts = "Accounts User" in frappe.get_roles(user) or "Accounts Manager" in frappe.get_roles(user)
    is_admin = "System Manager" in frappe.get_roles(user)

    if not is_accounts and not is_admin:
        frappe.throw(_("Only Accounts users can approve batches"))

    batch = frappe.get_doc("BEI PCF Batch", batch_name)

    if batch.status not in ["Submitted", "Under Review"]:
        frappe.throw(_("Batch is not pending review"))

    batch.status = "Approved"
    batch.reviewed_by = user
    batch.reviewed_at = now_datetime()
    batch.review_notes = notes

    batch.save(ignore_permissions=True)
    frappe.db.commit()

    # Send notification
    from hrms.hr.doctype.bei_pcf_batch.bei_pcf_batch import send_batch_notification

    send_batch_notification(batch, "approved")

    return {
        "success": True,
        "message": f"Batch {batch_name} approved",
        "batch": {
            "name": batch.name,
            "status": batch.status,
            "reviewed_by": batch.reviewed_by,
            "reviewed_at": batch.reviewed_at,
        },
    }


@frappe.whitelist()
def reject_batch(batch_name: str, reason: str):
    """
    Accounting rejects a PCF batch.

    Args:
        batch_name: Name of the BEI PCF Batch
        reason: Rejection reason (required)

    Returns:
        Updated batch status
    """
    if not reason:
        frappe.throw(_("Rejection reason is required"))

    # Check permissions
    user = frappe.session.user
    is_accounts = "Accounts User" in frappe.get_roles(user) or "Accounts Manager" in frappe.get_roles(user)
    is_admin = "System Manager" in frappe.get_roles(user)

    if not is_accounts and not is_admin:
        frappe.throw(_("Only Accounts users can reject batches"))

    batch = frappe.get_doc("BEI PCF Batch", batch_name)

    if batch.status not in ["Submitted", "Under Review"]:
        frappe.throw(_("Batch is not pending review"))

    batch.status = "Rejected"
    batch.reviewed_by = user
    batch.reviewed_at = now_datetime()
    batch.review_notes = reason

    batch.save(ignore_permissions=True)
    frappe.db.commit()

    # Send notification
    from hrms.hr.doctype.bei_pcf_batch.bei_pcf_batch import send_batch_notification

    send_batch_notification(batch, "rejected")

    return {
        "success": True,
        "message": f"Batch {batch_name} rejected",
        "batch": {
            "name": batch.name,
            "status": batch.status,
            "reviewed_by": batch.reviewed_by,
            "reviewed_at": batch.reviewed_at,
            "review_notes": batch.review_notes,
        },
    }


@frappe.whitelist()
def request_replenishment(batch_name: str, amount: float = None):
    """
    Flag a batch for PCF replenishment.

    Args:
        batch_name: Name of the BEI PCF Batch
        amount: Replenishment amount (defaults to batch total)

    Returns:
        Updated batch
    """
    batch = frappe.get_doc("BEI PCF Batch", batch_name)

    if batch.status != "Approved":
        frappe.throw(_("Only approved batches can request replenishment"))

    batch.replenishment_requested = 1
    batch.replenishment_amount = flt(amount) if amount else batch.total_amount
    batch.replenishment_date = nowdate()

    batch.save(ignore_permissions=True)
    frappe.db.commit()

    # Update PCF last replenishment date
    frappe.db.set_value(
        "BEI Petty Cash Fund",
        {"store": batch.store},
        "last_replenishment_date",
        nowdate(),
    )

    return {
        "success": True,
        "message": f"Replenishment requested for PHP {batch.replenishment_amount:,.2f}",
    }


# ============================================================
# ADMIN ENDPOINTS
# ============================================================


@frappe.whitelist()
def create_pcf_fund(
    store: str, fund_amount: float, custodian: str, threshold_percentage: float = 50
):
    """
    Create PCF configuration for a store.

    Args:
        store: Warehouse name
        fund_amount: Total PCF amount
        custodian: User to assign as custodian
        threshold_percentage: Auto-submit threshold (default 50%)

    Returns:
        Created PCF fund details
    """
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only System Managers can create PCF funds"))

    # Check if already exists
    existing = frappe.db.exists("BEI Petty Cash Fund", {"store": store})
    if existing:
        frappe.throw(_("PCF fund already exists for this store"))

    # Create PCF
    pcf = frappe.new_doc("BEI Petty Cash Fund")
    pcf.store = store
    pcf.company = "Bebang Enterprise Inc."
    pcf.fund_amount = flt(fund_amount)
    pcf.threshold_percentage = flt(threshold_percentage)
    pcf.custodian = custodian
    pcf.is_enabled = False  # Start disabled, enable manually
    pcf.auto_submit_enabled = True
    pcf.month_end_auto_submit = True

    pcf.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "success": True,
        "message": f"PCF fund created for {store}",
        "pcf": {"name": pcf.name, "store": pcf.store, "fund_amount": pcf.fund_amount},
    }


@frappe.whitelist()
def update_pcf_settings(
    store: str,
    fund_amount: float = None,
    threshold_percentage: float = None,
    custodian: str = None,
    backup_custodian: str = None,
    is_enabled: int = None,
    auto_submit_enabled: int = None,
    month_end_auto_submit: int = None,
):
    """
    Update PCF settings for a store.

    Args:
        store: Warehouse name
        Other args: Settings to update (only non-None values)

    Returns:
        Updated PCF details
    """
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only System Managers can update PCF settings"))

    pcf = frappe.get_doc("BEI Petty Cash Fund", {"store": store})

    if fund_amount is not None:
        pcf.fund_amount = flt(fund_amount)
    if threshold_percentage is not None:
        pcf.threshold_percentage = flt(threshold_percentage)
    if custodian is not None:
        pcf.custodian = custodian
    if backup_custodian is not None:
        pcf.backup_custodian = backup_custodian
    if is_enabled is not None:
        pcf.is_enabled = int(is_enabled)
    if auto_submit_enabled is not None:
        pcf.auto_submit_enabled = int(auto_submit_enabled)
    if month_end_auto_submit is not None:
        pcf.month_end_auto_submit = int(month_end_auto_submit)

    pcf.save(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True, "message": f"PCF settings updated for {store}"}


@frappe.whitelist()
def assign_pcf_custodian(store: str, user: str, is_backup: bool = False):
    """
    Assign a user as PCF custodian for a store.

    Args:
        store: Warehouse name
        user: User ID to assign
        is_backup: If True, assign as backup custodian

    Returns:
        Success response
    """
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only System Managers can assign custodians"))

    pcf = frappe.get_doc("BEI Petty Cash Fund", {"store": store})

    if is_backup:
        pcf.backup_custodian = user
    else:
        pcf.custodian = user

    pcf.save(ignore_permissions=True)

    # Set user flag
    frappe.db.set_value("User", user, "custom_is_pcf_custodian", 1)
    frappe.db.commit()

    role = "backup custodian" if is_backup else "custodian"
    return {"success": True, "message": f"{user} assigned as {role} for {store}"}


@frappe.whitelist()
def get_all_pcf_funds():
    """
    Get all PCF fund configurations.

    Returns:
        List of all PCF funds
    """
    if "System Manager" not in frappe.get_roles() and "Accounts Manager" not in frappe.get_roles():
        frappe.throw(_("Only System Managers or Accounts Managers can view all PCF funds"))

    funds = frappe.get_all(
        "BEI Petty Cash Fund",
        fields=[
            "name",
            "store",
            "is_enabled",
            "fund_amount",
            "current_balance",
            "pending_total",
            "pending_count",
            "threshold_percentage",
            "custodian",
            "last_batch_date",
        ],
        order_by="store asc",
    )

    return {"success": True, "funds": funds, "count": len(funds)}


# ============================================================
# SCHEDULER JOBS
# ============================================================


def check_threshold_and_auto_submit():
    """
    Hourly job: Check all PCF funds and auto-submit if threshold reached.
    """
    # Guard against concurrent runs
    lock_key = "pcf_threshold_check_running"
    if frappe.cache.get(lock_key):
        frappe.log_error("PCF threshold check already running, skipping", "PCF Auto-Submit")
        return

    frappe.cache.set(lock_key, True, expires_in_sec=3600)

    try:
        funds = frappe.get_all(
            "BEI Petty Cash Fund",
            filters={"is_enabled": 1, "auto_submit_enabled": 1},
            fields=["name", "store", "fund_amount", "threshold_percentage", "pending_total"],
        )

        submitted = 0
        for fund in funds:
            threshold_amount = fund.fund_amount * fund.threshold_percentage / 100
            if (fund.pending_total or 0) >= threshold_amount:
                # Check no batch already under review
                existing = frappe.db.exists(
                    "BEI PCF Batch",
                    {"store": fund.store, "status": ["in", ["Submitted", "Under Review"]]},
                )
                if not existing:
                    from hrms.hr.doctype.bei_pcf_batch.bei_pcf_batch import create_batch_from_pending

                    batch = create_batch_from_pending(fund.store, "Threshold Auto")
                    if batch:
                        submitted += 1
                        frappe.log_error(
                            f"Auto-submitted batch {batch.name} for {fund.store} (threshold)",
                            "PCF Auto-Submit",
                        )

        if submitted:
            frappe.log_error(f"PCF threshold check: {submitted} batches auto-submitted", "PCF Auto-Submit")

    finally:
        frappe.cache.delete(lock_key)


def check_month_end_auto_submit():
    """
    Daily job: On second-to-last day of month, auto-submit all pending.
    """
    today_dt = datetime.now()
    _, last_day = monthrange(today_dt.year, today_dt.month)
    second_to_last = last_day - 1

    if today_dt.day != second_to_last:
        return

    frappe.log_error(f"Month-end PCF auto-submit triggered for day {today_dt.day}", "PCF Month-End")

    funds = frappe.get_all(
        "BEI Petty Cash Fund",
        filters={"is_enabled": 1, "month_end_auto_submit": 1},
        fields=["name", "store", "pending_total"],
    )

    submitted = 0
    for fund in funds:
        if (fund.pending_total or 0) > 0:
            existing = frappe.db.exists(
                "BEI PCF Batch",
                {"store": fund.store, "status": ["in", ["Submitted", "Under Review"]]},
            )
            if not existing:
                from hrms.hr.doctype.bei_pcf_batch.bei_pcf_batch import create_batch_from_pending

                batch = create_batch_from_pending(fund.store, "Month-End Auto")
                if batch:
                    submitted += 1
                    frappe.log_error(
                        f"Auto-submitted batch {batch.name} for {fund.store} (month-end)",
                        "PCF Month-End",
                    )

    frappe.log_error(f"Month-end auto-submit: {submitted} batches created", "PCF Month-End")


# ============================================================
# DOCUMENT EVENT HOOKS
# ============================================================


def on_expense_update(doc, method):
    """
    Called when BEI Expense Request is updated.
    Recalculates PCF totals when status changes.
    """
    if doc.has_value_changed("status") or doc.has_value_changed("manual_amount"):
        if doc.store:
            from hrms.hr.doctype.bei_petty_cash_fund.bei_petty_cash_fund import update_pcf_totals

            update_pcf_totals(doc.store)


def on_expense_delete(doc, method):
    """
    Called when BEI Expense Request is deleted.
    Recalculates PCF totals.
    """
    if doc.store and doc.status == "Pending":
        from hrms.hr.doctype.bei_petty_cash_fund.bei_petty_cash_fund import update_pcf_totals

        update_pcf_totals(doc.store)


def validate_pcf_batch(doc, method):
    """
    Called when BEI PCF Batch is validated.
    Ensures proper computation and validation.
    """
    # Computed in DocType validate method
    pass


def on_batch_update(doc, method):
    """
    Called when BEI PCF Batch is updated.
    Handles status change notifications and expense updates.
    """
    # Handled in DocType on_update method
    pass


# ============================================================
# NOTIFICATION FUNCTIONS
# ============================================================


def send_threshold_notification(store: str):
    """
    Send notification when threshold is reached.
    """
    try:
        pcf = frappe.db.get_value(
            "BEI Petty Cash Fund",
            {"store": store},
            ["custodian", "fund_amount", "pending_total", "threshold_percentage", "pending_count"],
            as_dict=True,
        )

        if not pcf:
            return

        message = f"""*PCF Threshold Reached*

Store: {store}
Pending: PHP {pcf.pending_total:,.2f} ({pcf.pending_count} expenses)
Fund: PHP {pcf.fund_amount:,.2f}
Threshold: {pcf.threshold_percentage}%

Ready for batch submission."""

        from hrms.api.google_chat import send_message_to_space

        send_message_to_space("spaces/AAQA3NVVR6c", message)
    except Exception as e:
        frappe.log_error(f"Failed to send threshold notification: {e}", "PCF Notification")


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def _get_store_for_employee(employee):
    """
    Get the store warehouse for an employee based on their branch.
    """
    if not employee.branch:
        return None

    # Try exact match first
    store = frappe.db.exists("Warehouse", employee.branch)
    if store:
        return store

    # Try with company suffix
    company = employee.company or "Bebang Enterprise Inc."
    store = frappe.db.exists("Warehouse", f"{employee.branch} - {company}")
    if store:
        return store

    # Try partial match
    store = frappe.db.get_value("Warehouse", {"name": ["like", f"{employee.branch}%"]}, "name")
    return store


def _resolve_store_name(store_or_branch: str) -> str:
    """
    Resolve a store name from branch or partial warehouse name.
    Frontend may pass just 'TEST-STORE-BGC' but warehouse is 'TEST-STORE-BGC - BEI'.
    """
    if not store_or_branch:
        return None

    # Try exact match first
    if frappe.db.exists("Warehouse", store_or_branch):
        return store_or_branch

    # Try with common company suffixes
    for suffix in ["Bebang Enterprise Inc.", "BEI"]:
        full_name = f"{store_or_branch} - {suffix}"
        if frappe.db.exists("Warehouse", full_name):
            return full_name

    # Try partial match
    warehouse = frappe.db.get_value(
        "Warehouse", {"name": ["like", f"{store_or_branch}%"]}, "name"
    )
    return warehouse
