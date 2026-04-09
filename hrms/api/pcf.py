"""
Petty Cash Fund (PCF) APIs
Handles PCF batch submission, threshold monitoring, and notification workflows.

Supports both store-based and department-based PCF funds.

Author: Claude Code
Date: 2026-02-03
Updated: 2026-04-06 (S157 — department funds, COA surface, notify-only threshold)
"""
import frappe
from frappe import _
from frappe.utils import today, now_datetime, flt, nowdate, getdate
from hrms.utils.bei_config import get_company
from calendar import monthrange
from datetime import datetime
from hrms.api.store import resolve_employee_store_context, save_base64_image


# ============================================================
# FUND RESOLUTION
# ============================================================


def _get_pcf_fund_for_user(user=None):
    """
    Resolve the PCF fund for a user.
    Checks store first (via branch→warehouse), then department.

    Returns:
        dict with keys: pcf_fund (name), fund_type, store, department
        or None if no fund found
    """
    user = user or frappe.session.user
    employee = frappe.db.get_value(
        "Employee",
        {"user_id": user, "status": "Active"},
        ["name", "employee_name", "branch", "department", "company"],
        as_dict=True,
    )

    if not employee:
        return None

    # Try store-based fund first
    store = _get_store_for_employee(employee)
    if store:
        pcf_name = frappe.db.get_value(
            "BEI Petty Cash Fund",
            {"store": store, "is_enabled": 1},
            "name",
        )
        if pcf_name:
            return {
                "pcf_fund": pcf_name,
                "fund_type": "Store",
                "store": store,
                "department": None,
                "employee": employee,
            }

    # Try department-based fund
    if employee.department:
        pcf_name = frappe.db.get_value(
            "BEI Petty Cash Fund",
            {"fund_type": "Department", "department": employee.department, "is_enabled": 1},
            "name",
        )
        if pcf_name:
            return {
                "pcf_fund": pcf_name,
                "fund_type": "Department",
                "store": None,
                "department": employee.department,
                "employee": employee,
            }

    return None


def _resolve_pcf_fund(pcf_fund=None, store=None):
    """
    Resolve a PCF fund name from either pcf_fund or store.

    Args:
        pcf_fund: Direct PCF fund name (preferred)
        store: Warehouse name (legacy compat)

    Returns:
        PCF fund name or None
    """
    if pcf_fund:
        if frappe.db.exists("BEI Petty Cash Fund", pcf_fund):
            return pcf_fund
        return None

    if store:
        return frappe.db.get_value("BEI Petty Cash Fund", {"store": store}, "name")

    return None


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
    pcf_fund: str = None,
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
        pcf_fund: Optional PCF fund name (for department users)

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

    # Resolve PCF fund
    if pcf_fund:
        fund_doc = frappe.get_doc("BEI Petty Cash Fund", pcf_fund)
        if not fund_doc.is_enabled:
            frappe.throw(_("This PCF fund is not enabled"))
        store = fund_doc.store  # Will be None for department funds
    else:
        # Legacy path: resolve via employee's store
        fund_context = _get_pcf_fund_for_user()
        if not fund_context:
            frappe.throw(
                _("No PCF fund found for your store or department. Please contact your supervisor.")
            )
        pcf_fund = fund_context["pcf_fund"]
        store = fund_context.get("store")

    # Create expense request with Pending status
    expense = frappe.new_doc("BEI Expense Request")
    expense.employee = employee.name
    expense.store = store
    expense.pcf_fund = pcf_fund
    expense.expense_type = "PCF"
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

    pcf_doc = update_pcf_totals(store=store, pcf_fund=pcf_fund)

    # Check if threshold reached
    at_threshold = False
    if pcf_doc and pcf_doc.is_at_threshold():
        at_threshold = True
        send_threshold_notification(pcf_fund=pcf_fund, store=store)

    return {
        "success": True,
        "expense_id": expense.name,
        "message": "Expense added to PCF pending queue",
        "pcf_status": {
            "fund_amount": pcf_doc.fund_amount if pcf_doc else 0,
            "pending_total": pcf_doc.pending_total if pcf_doc else 0,
            "pending_count": pcf_doc.pending_count if pcf_doc else 0,
            "current_balance": pcf_doc.current_balance if pcf_doc else 0,
            "threshold_percentage": pcf_doc.threshold_percentage if pcf_doc else 60,
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
            "pcf_fund",
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

    # Capture references before deletion
    store = expense.store
    pcf_fund = expense.pcf_fund
    expense.delete(ignore_permissions=True)
    frappe.db.commit()

    # Update PCF totals
    from hrms.hr.doctype.bei_petty_cash_fund.bei_petty_cash_fund import update_pcf_totals

    update_pcf_totals(store=store, pcf_fund=pcf_fund)

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

    # Permission check — S167 DEFECT-022 fix: allow the owner, the fund
    # custodian/backup custodian, or an admin. Without custodian access,
    # the custodian has no way to correct a row before submitting the
    # batch (plan S167 scenario 1.3 requires this).
    user = frappe.session.user
    employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
    is_owner = employee and expense.employee == employee

    is_custodian = False
    if expense.pcf_fund:
        fund = frappe.db.get_value(
            "BEI Petty Cash Fund",
            expense.pcf_fund,
            ["custodian", "backup_custodian"],
            as_dict=True,
        )
        if fund:
            is_custodian = user in [fund.custodian, fund.backup_custodian]

    is_admin = "System Manager" in frappe.get_roles(user) or "Accounts Manager" in frappe.get_roles(user)

    if not (is_owner or is_custodian or is_admin):
        frappe.throw(_("You can only edit your own expenses, or expenses on a fund you are custodian of"))

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

    update_pcf_totals(store=expense.store, pcf_fund=expense.pcf_fund)

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
def get_pcf_status(store: str = None, pcf_fund: str = None):
    """
    Get PCF status for a fund.
    If neither store nor pcf_fund provided, uses current user's fund.

    Args:
        store: Warehouse name (optional, legacy)
        pcf_fund: PCF fund name (optional, preferred)

    Returns:
        PCF status including balance, pending, threshold
    """
    pcf_name = _resolve_pcf_fund(pcf_fund=pcf_fund, store=store)

    if not pcf_name:
        # Try to resolve from user
        fund_context = _get_pcf_fund_for_user()
        if fund_context:
            pcf_name = fund_context["pcf_fund"]

    if not pcf_name:
        return {"success": False, "error": "PCF fund not found"}

    pcf = frappe.db.get_value(
        "BEI Petty Cash Fund",
        pcf_name,
        [
            "name",
            "store",
            "fund_type",
            "department",
            "fund_label",
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
        return {"success": False, "error": "PCF not configured"}

    # Calculate threshold info
    threshold_amount = pcf.fund_amount * pcf.threshold_percentage / 100
    at_threshold = (pcf.pending_total or 0) >= threshold_amount
    threshold_progress = (
        ((pcf.pending_total or 0) / pcf.fund_amount * 100) if pcf.fund_amount else 0
    )

    # Check for pending batch
    pending_batch = frappe.db.get_value(
        "BEI PCF Batch",
        {"pcf_fund": pcf_name, "status": ["in", ["Submitted", "Under Review"]]},
        ["name", "status", "total_amount", "expense_count", "batch_date"],
        as_dict=True,
    )
    # Fallback to store-based batch for pre-migration
    if not pending_batch and pcf.store:
        pending_batch = frappe.db.get_value(
            "BEI PCF Batch",
            {"store": pcf.store, "pcf_fund": ["is", "not set"], "status": ["in", ["Submitted", "Under Review"]]},
            ["name", "status", "total_amount", "expense_count", "batch_date"],
            as_dict=True,
        )

    return {
        "success": True,
        "pcf": {
            "name": pcf.name,
            "store": pcf.store,
            "fund_type": pcf.fund_type,
            "department": pcf.department,
            "fund_label": pcf.fund_label,
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
def get_fund_pending_summary(pcf_fund: str = None, store: str = None):
    """
    Get all pending expenses for a fund (for custodian view).

    Args:
        pcf_fund: PCF fund name (preferred)
        store: Warehouse name (legacy compat)

    Returns:
        Summary and list of all pending expenses
    """
    pcf_name = _resolve_pcf_fund(pcf_fund=pcf_fund, store=store)
    if not pcf_name:
        frappe.throw(_("PCF fund not found"))

    # Verify user is custodian or has permission
    pcf = frappe.db.get_value(
        "BEI Petty Cash Fund",
        pcf_name,
        ["name", "fund_label", "custodian", "backup_custodian", "store"],
        as_dict=True,
    )

    if not pcf:
        frappe.throw(_("PCF not configured"))

    user = frappe.session.user
    is_custodian = user in [pcf.custodian, pcf.backup_custodian]
    is_admin = "System Manager" in frappe.get_roles(user) or "Accounts Manager" in frappe.get_roles(user)

    if not is_custodian and not is_admin:
        frappe.throw(_("Only PCF custodians or managers can view fund pending summary"))

    # Get all pending expenses for this fund
    filters = {"pcf_fund": pcf_name, "status": "Pending"}
    expenses = frappe.get_all(
        "BEI Expense Request",
        filters=filters,
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

    # If no results, try store fallback for pre-migration data
    if not expenses and pcf.store:
        expenses = frappe.get_all(
            "BEI Expense Request",
            filters={"store": pcf.store, "pcf_fund": ["is", "not set"], "status": "Pending"},
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
        "pcf_fund": pcf_name,
        "fund_label": pcf.fund_label,
        "store": pcf.store,
        "expenses": expenses,
        "count": len(expenses),
        "total_amount": total_amount,
    }


# Keep old name as alias for backward compatibility
@frappe.whitelist()
def get_store_pending_summary(store: str):
    """Backward-compatible alias for get_fund_pending_summary."""
    return get_fund_pending_summary(store=store)


@frappe.whitelist()
def get_pcf_custodians(store=None, pcf_fund=None):
    """
    Get custodians for a fund.

    Args:
        store: Warehouse name (legacy)
        pcf_fund: PCF fund name (preferred)

    Returns:
        List of custodians
    """
    pcf_name = _resolve_pcf_fund(pcf_fund=pcf_fund, store=store)
    if not pcf_name:
        return {"success": False, "error": "PCF not configured"}

    pcf = frappe.db.get_value(
        "BEI Petty Cash Fund",
        pcf_name,
        ["custodian", "backup_custodian"],
        as_dict=True,
    )

    if not pcf:
        return {"success": False, "error": "PCF not configured"}

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
def submit_batch_now(store: str = None, pcf_fund: str = None):
    """
    Manually submit a PCF batch for a fund.

    Args:
        store: Warehouse name (legacy)
        pcf_fund: PCF fund name (preferred)

    Returns:
        Created batch details
    """
    pcf_name = _resolve_pcf_fund(pcf_fund=pcf_fund, store=store)
    if not pcf_name:
        frappe.throw(_("PCF fund not found"))

    pcf = frappe.db.get_value(
        "BEI Petty Cash Fund",
        pcf_name,
        ["name", "custodian", "backup_custodian", "store", "fund_label"],
        as_dict=True,
    )

    if not pcf:
        frappe.throw(_("PCF not configured"))

    user = frappe.session.user
    is_custodian = user in [pcf.custodian, pcf.backup_custodian]
    is_admin = "System Manager" in frappe.get_roles(user) or "Accounts Manager" in frappe.get_roles(user)

    if not is_custodian and not is_admin:
        frappe.throw(_("Only PCF custodians or managers can submit batches"))

    # Create batch
    from hrms.hr.doctype.bei_pcf_batch.bei_pcf_batch import create_batch_from_pending

    batch = create_batch_from_pending(store=pcf.store, submission_type="Manual", pcf_fund=pcf_name)

    if not batch:
        frappe.throw(_("No pending expenses to submit"))

    return {
        "success": True,
        "batch": {
            "name": batch.name,
            "store": batch.store,
            "pcf_fund": batch.pcf_fund,
            "fund_label": pcf.fund_label,
            "batch_date": batch.batch_date,
            "status": batch.status,
            "total_amount": batch.total_amount,
            "expense_count": batch.expense_count,
        },
        "message": f"Batch {batch.name} created with {batch.expense_count} expenses",
    }


@frappe.whitelist()
def get_batch_history(store: str = None, pcf_fund: str = None, limit: int = 20, offset: int = 0):
    """
    Get batch history for a fund.

    Args:
        store: Warehouse name (legacy)
        pcf_fund: PCF fund name (preferred)
        limit: Number of batches to return
        offset: Pagination offset

    Returns:
        List of past batches
    """
    pcf_name = _resolve_pcf_fund(pcf_fund=pcf_fund, store=store)

    # If store was passed but not resolved to a fund, try resolving store name
    if not pcf_name and store:
        resolved_store = _resolve_store_name(store)
        if resolved_store:
            pcf_name = frappe.db.get_value("BEI Petty Cash Fund", {"store": resolved_store}, "name")

    if not pcf_name:
        return {"success": True, "batches": [], "total": 0, "limit": limit, "offset": offset}

    # Get batches by pcf_fund
    batches = frappe.get_all(
        "BEI PCF Batch",
        filters={"pcf_fund": pcf_name},
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
            "pcf_fund",
        ],
        order_by="batch_date desc",
        limit_page_length=limit,
        limit_start=offset,
    )

    total = frappe.db.count("BEI PCF Batch", {"pcf_fund": pcf_name})

    return {
        "success": True,
        "batches": batches,
        "total": total,
        "limit": limit,
        "offset": offset,
        "pcf_fund": pcf_name,
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
                "name": item.name,
                "expense_request": item.expense_request,
                "employee": item.employee,
                "employee_name": item.employee_name,
                "expense_date": item.expense_date,
                "vendor": item.vendor,
                "description": item.description,
                "amount": item.amount,
                "item_status": item.item_status,
                "suggested_coa": item.suggested_coa,
                "suggested_coa_label": item.suggested_coa_label,
                "coa_confidence": item.coa_confidence,
                "final_coa": item.final_coa,
                "approved_amount": item.approved_amount,
            }
        )

    return {
        "success": True,
        "batch": {
            "name": batch.name,
            "store": batch.store,
            "pcf_fund": batch.pcf_fund,
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

    replenishment_amount = flt(amount) if amount else batch.total_amount
    batch.replenishment_requested = 1
    batch.replenishment_amount = replenishment_amount
    batch.replenishment_date = nowdate()

    journal_entry_name, journal_entry_error = _create_replenishment_journal_entry(
        batch=batch, replenishment_amount=replenishment_amount
    )

    if journal_entry_name:
        line = f"[{nowdate()}] Replenishment JE: {journal_entry_name}"
        batch.review_notes = f"{(batch.review_notes or '').strip()}\n{line}".strip()
    elif journal_entry_error:
        line = f"[{nowdate()}] Replenishment JE skipped: {journal_entry_error}"
        batch.review_notes = f"{(batch.review_notes or '').strip()}\n{line}".strip()

    batch.save(ignore_permissions=True)
    frappe.db.commit()

    # Update PCF last replenishment date
    pcf_name = batch.pcf_fund or frappe.db.get_value("BEI Petty Cash Fund", {"store": batch.store}, "name")
    if pcf_name:
        frappe.db.set_value("BEI Petty Cash Fund", pcf_name, "last_replenishment_date", nowdate())

    return {
        "success": True,
        "message": f"Replenishment requested for PHP {batch.replenishment_amount:,.2f}",
        "journal_entry": journal_entry_name,
        "journal_entry_status": "created" if journal_entry_name else "skipped",
        "journal_entry_error": journal_entry_error,
    }


def _create_replenishment_journal_entry(batch, replenishment_amount: float):
    """Create replenishment ledger entry when accounts are available.

    Accounting contract:
    - Dr PCF cash account (1113000 if mapped in chart)
    - Cr replenishment source account (BEI setting override, else company default cash account)
    """
    company = get_company()
    pcf_account = _get_account_by_number(company, "1113000")
    source_account = _get_replenishment_source_account(company)

    if not pcf_account or not source_account:
        missing = []
        if not pcf_account:
            missing.append("pcf_account_1113000")
        if not source_account:
            missing.append("source_account")
        return None, f"missing_account_mapping:{','.join(missing)}"

    if pcf_account == source_account:
        return None, "invalid_mapping_same_account"

    cost_center = None
    if batch.store:
        cost_center = frappe.db.get_value("Warehouse", batch.store, "cost_center")

    je = frappe.new_doc("Journal Entry")
    je.company = company
    je.posting_date = nowdate()
    je.voucher_type = "Journal Entry"

    fund_label = ""
    if batch.pcf_fund:
        fund_label = frappe.db.get_value("BEI Petty Cash Fund", batch.pcf_fund, "fund_label") or batch.pcf_fund
    else:
        fund_label = batch.store or ""
    je.user_remark = f"PCF replenishment request for {batch.name} ({fund_label})"

    je.append(
        "accounts",
        {
            "account": pcf_account,
            "debit_in_account_currency": flt(replenishment_amount),
            "cost_center": cost_center,
            "reference_type": "BEI PCF Batch",
            "reference_name": batch.name,
        },
    )
    je.append(
        "accounts",
        {
            "account": source_account,
            "credit_in_account_currency": flt(replenishment_amount),
            "cost_center": cost_center,
            "reference_type": "BEI PCF Batch",
            "reference_name": batch.name,
        },
    )

    je.insert(ignore_permissions=True)
    je.flags.ignore_permissions = True
    je.submit()
    return je.name, None


def _get_account_by_number(company: str, account_number: str):
    account = frappe.db.get_value(
        "Account",
        {"company": company, "account_number": account_number, "is_group": 0},
        "name",
    )
    if account:
        return account

    # Fallback for charts without account_number populated consistently.
    return frappe.db.get_value(
        "Account",
        {"company": company, "name": ["like", f"{account_number} -%"], "is_group": 0},
        "name",
    )


def _get_replenishment_source_account(company: str):
    if frappe.db.has_column("tabBEI Settings", "pcf_replenishment_source_account"):
        source = frappe.db.get_single_value("BEI Settings", "pcf_replenishment_source_account")
        if source:
            return source

    if frappe.db.has_column("tabCompany", "default_cash_account"):
        source = frappe.db.get_value("Company", company, "default_cash_account")
        if source:
            return source

    return None


# ============================================================
# COA CLASSIFICATION ENDPOINTS
# ============================================================


def _resolve_coa_code_to_account(code: str, company: str) -> str | None:
    """
    DEFECT-009 fix: Map a naked GL code (e.g. "6010100") to a full Account
    DocType name (e.g. "6010100 - Representation & Entertainment - BEI") for
    the given company. Returns None if no match.

    The classifier returns naked codes from Liezel's training data; the
    batch approve flow validates against tabAccount link, which fails on
    a bare code. Resolve once at classify-time so approve always succeeds.
    """
    if not code or not company:
        return None
    # Prefer non-group leaf accounts whose name starts with the code + " - "
    rows = frappe.db.sql(
        """
        SELECT name FROM `tabAccount`
        WHERE company=%s AND is_group=0 AND name LIKE %s
        ORDER BY name LIMIT 1
        """,
        (company, f"{code} - %"),
        as_dict=False,
    )
    return rows[0][0] if rows else None


@frappe.whitelist()
def classify_batch_items(batch_name: str):
    """
    Run AI classification on all items in a batch.
    Populates suggested_coa, suggested_coa_label, coa_confidence.

    Args:
        batch_name: Name of the BEI PCF Batch

    Returns:
        Classification results per item
    """
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(
        module="pcf",
        action="classify_batch_items",
        mutation_type="update",
        extras={"batch_name": batch_name},
    )

    batch = frappe.get_doc("BEI PCF Batch", batch_name)
    from hrms.api.expense_classifier import classify_expense, COA_LABELS

    results = []
    for item in batch.items:
        try:
            classification = classify_expense(
                description=item.description or "",
                vendor=item.vendor or "",
                amount=flt(item.amount),
            )

            suggested_code = classification.get("coa")
            suggested_label = COA_LABELS.get(suggested_code, "") if suggested_code else ""
            confidence = flt(classification.get("confidence", 0))

            # DEFECT-009: classifier returns naked GL codes like "6010100";
            # resolve to the full Account DocType name so later approve
            # calls don't hit LinkValidationError. Store the resolved name
            # in suggested_coa (Link field), and keep the raw code on the
            # label for diagnostics if resolution fails.
            suggested_coa = _resolve_coa_code_to_account(suggested_code, batch.company) if suggested_code else None
            if suggested_code and not suggested_coa:
                # Lookup failed - leave suggested_coa empty, surface via label
                suggested_label = f"{suggested_label} (unresolved: {suggested_code})" if suggested_label else f"Unresolved: {suggested_code}"

            # Update batch item
            frappe.db.set_value(
                "BEI PCF Batch Item",
                item.name,
                {
                    "suggested_coa": suggested_coa,
                    "suggested_coa_label": suggested_label,
                    "coa_confidence": confidence,
                },
            )

            # Also backfill onto the linked expense
            if item.expense_request:
                frappe.db.set_value(
                    "BEI Expense Request",
                    item.expense_request,
                    {
                        "internal_suggested_coa": suggested_coa,
                        "internal_coa_confidence": confidence,
                        "internal_classification_method": classification.get("method", ""),
                    },
                )

            results.append({
                "item": item.name,
                "expense_request": item.expense_request,
                "suggested_coa": suggested_coa,
                "suggested_coa_label": suggested_label,
                "coa_confidence": confidence,
                "method": classification.get("method", ""),
            })
        except Exception as e:
            frappe.log_error(f"Classification failed for item {item.name}: {e}", "PCF COA Classification")
            results.append({
                "item": item.name,
                "expense_request": item.expense_request,
                "error": str(e),
            })

    frappe.db.commit()
    return {"success": True, "results": results, "classified": len([r for r in results if "error" not in r])}


@frappe.whitelist()
def approve_batch_with_coa(batch_name: str, items: str = None, notes: str = None):
    """
    Approve a batch with COA decisions per item.

    Args:
        batch_name: Name of the BEI PCF Batch
        items: JSON list of {name, final_coa, approved_amount} dicts
        notes: Optional review notes

    Returns:
        Updated batch status
    """
    import json as json_lib

    # Check permissions
    user = frappe.session.user
    is_accounts = "Accounts User" in frappe.get_roles(user) or "Accounts Manager" in frappe.get_roles(user)
    is_admin = "System Manager" in frappe.get_roles(user)

    if not is_accounts and not is_admin:
        frappe.throw(_("Only Accounts users can approve batches"))

    batch = frappe.get_doc("BEI PCF Batch", batch_name)

    if batch.status not in ["Submitted", "Under Review"]:
        frappe.throw(_("Batch is not pending review"))

    # Apply COA decisions to items
    if items:
        if isinstance(items, str):
            items = json_lib.loads(items)

        for item_decision in items:
            item_name = item_decision.get("name")
            if not item_name:
                continue

            updates = {}
            if item_decision.get("final_coa"):
                updates["final_coa"] = item_decision["final_coa"]
            if item_decision.get("approved_amount") is not None:
                updates["approved_amount"] = flt(item_decision["approved_amount"])

            if updates:
                frappe.db.set_value("BEI PCF Batch Item", item_name, updates)

                # Also set on linked expense
                expense_name = frappe.db.get_value("BEI PCF Batch Item", item_name, "expense_request")
                if expense_name:
                    exp_updates = {}
                    if "final_coa" in updates:
                        exp_updates["internal_final_coa"] = updates["final_coa"]
                    if "approved_amount" in updates:
                        exp_updates["internal_approved_amount"] = updates["approved_amount"]
                    if exp_updates:
                        frappe.db.set_value("BEI Expense Request", expense_name, exp_updates)

    # Approve the batch
    batch.status = "Approved"
    batch.reviewed_by = user
    batch.reviewed_at = now_datetime()
    batch.review_notes = notes

    batch.save(ignore_permissions=True)
    frappe.db.commit()

    from hrms.hr.doctype.bei_pcf_batch.bei_pcf_batch import send_batch_notification

    send_batch_notification(batch, "approved")

    return {
        "success": True,
        "message": f"Batch {batch_name} approved with COA classifications",
        "batch": {
            "name": batch.name,
            "status": batch.status,
            "reviewed_by": batch.reviewed_by,
            "reviewed_at": batch.reviewed_at,
        },
    }


# ============================================================
# ADMIN ENDPOINTS
# ============================================================


@frappe.whitelist()
def create_pcf_fund(
    store: str = None,
    fund_amount: float = 10000,
    custodian: str = None,
    threshold_percentage: float = 60,
    fund_type: str = "Store",
    department: str = None,
):
    """
    Create PCF configuration for a store or department.

    Args:
        store: Warehouse name (for store-type funds)
        fund_amount: Total PCF amount
        custodian: User to assign as custodian
        threshold_percentage: Notification threshold (default 60%)
        fund_type: "Store" or "Department"
        department: Department name (for department-type funds)

    Returns:
        Created PCF fund details
    """
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only System Managers can create PCF funds"))

    # Validate based on fund type
    if fund_type == "Store":
        if not store:
            frappe.throw(_("Store is required for Store-type funds"))
        existing = frappe.db.exists("BEI Petty Cash Fund", {"fund_type": "Store", "store": store})
        if existing:
            frappe.throw(_("PCF fund already exists for this store"))
    elif fund_type == "Department":
        if not department:
            frappe.throw(_("Department is required for Department-type funds"))
        existing = frappe.db.exists("BEI Petty Cash Fund", {"fund_type": "Department", "department": department})
        if existing:
            frappe.throw(_("PCF fund already exists for this department"))
    else:
        frappe.throw(_("Invalid fund type. Must be 'Store' or 'Department'"))

    # Create PCF
    pcf = frappe.new_doc("BEI Petty Cash Fund")
    pcf.fund_type = fund_type
    pcf.store = store if fund_type == "Store" else None
    pcf.department = department if fund_type == "Department" else None
    pcf.company = get_company()
    pcf.fund_amount = flt(fund_amount)
    pcf.threshold_percentage = flt(threshold_percentage)
    pcf.custodian = custodian
    pcf.is_enabled = False  # Start disabled, enable manually
    pcf.auto_submit_enabled = True
    pcf.month_end_auto_submit = True

    pcf.insert(ignore_permissions=True)
    frappe.db.commit()

    # DEFECT-017: flatten fund fields at the top level so the frontend
    # normalizer (which reads message.name / message.fund_type) sees real
    # values. The nested `pcf` block is retained for any older consumers.
    payload = {
        "name": pcf.name,
        "fund_type": pcf.fund_type,
        "fund_label": pcf.fund_label,
        "store": pcf.store,
        "department": pcf.department,
        "fund_amount": pcf.fund_amount,
        "threshold_percentage": pcf.threshold_percentage,
        "custodian": pcf.custodian,
        "is_enabled": pcf.is_enabled,
    }
    return {
        "success": True,
        "message": f"PCF fund created: {pcf.fund_label}",
        "pcf": payload,
        **payload,
    }


@frappe.whitelist()
def update_pcf_settings(
    store: str = None,
    pcf_fund: str = None,
    fund_amount: float = None,
    threshold_percentage: float = None,
    custodian: str = None,
    backup_custodian: str = None,
    is_enabled: int = None,
    auto_submit_enabled: int = None,
    month_end_auto_submit: int = None,
):
    """
    Update PCF settings for a fund.

    Args:
        store: Warehouse name (legacy)
        pcf_fund: PCF fund name (preferred)
        Other args: Settings to update (only non-None values)

    Returns:
        Updated PCF details
    """
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only System Managers can update PCF settings"))

    pcf_name = _resolve_pcf_fund(pcf_fund=pcf_fund, store=store)
    if not pcf_name:
        frappe.throw(_("PCF fund not found"))

    pcf = frappe.get_doc("BEI Petty Cash Fund", pcf_name)

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

    return {"success": True, "message": f"PCF settings updated for {pcf.fund_label}"}


@frappe.whitelist()
def assign_pcf_custodian(store: str = None, pcf_fund: str = None, user: str = None, is_backup: bool = False):
    """
    Assign a user as PCF custodian for a fund.

    Args:
        store: Warehouse name (legacy)
        pcf_fund: PCF fund name (preferred)
        user: User ID to assign
        is_backup: If True, assign as backup custodian

    Returns:
        Success response
    """
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only System Managers can assign custodians"))

    pcf_name = _resolve_pcf_fund(pcf_fund=pcf_fund, store=store)
    if not pcf_name:
        frappe.throw(_("PCF fund not found"))

    pcf = frappe.get_doc("BEI Petty Cash Fund", pcf_name)

    if is_backup:
        pcf.backup_custodian = user
    else:
        pcf.custodian = user

    pcf.save(ignore_permissions=True)

    # Set user flag
    frappe.db.set_value("User", user, "custom_is_pcf_custodian", 1)
    frappe.db.commit()

    role = "backup custodian" if is_backup else "custodian"
    return {"success": True, "message": f"{user} assigned as {role} for {pcf.fund_label}"}


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
            "fund_type",
            "store",
            "department",
            "fund_label",
            "is_enabled",
            "fund_amount",
            "current_balance",
            "pending_total",
            "pending_count",
            "threshold_percentage",
            "custodian",
            "last_batch_date",
        ],
        order_by="fund_type asc, fund_label asc",
    )

    return {"success": True, "funds": funds, "count": len(funds)}


# ============================================================
# SCHEDULER JOBS
# ============================================================


def check_threshold_and_notify():
    """
    Hourly job: Check all PCF funds and send notification if threshold reached.
    Does NOT auto-create batches — custodian decides when to submit.
    """
    # Guard against concurrent runs
    lock_key = "pcf_threshold_check_running"
    if frappe.cache.get(lock_key):
        frappe.log_error("PCF threshold check already running, skipping", "PCF Threshold")
        return

    frappe.cache.set(lock_key, True, expires_in_sec=3600)

    try:
        funds = frappe.get_all(
            "BEI Petty Cash Fund",
            filters={"is_enabled": 1, "auto_submit_enabled": 1},
            fields=["name", "store", "fund_type", "fund_label", "fund_amount", "threshold_percentage", "pending_total"],
        )

        notified = 0
        for fund in funds:
            threshold_amount = fund.fund_amount * fund.threshold_percentage / 100
            if (fund.pending_total or 0) >= threshold_amount:
                # Check no batch already under review
                existing = frappe.db.exists(
                    "BEI PCF Batch",
                    {"pcf_fund": fund.name, "status": ["in", ["Submitted", "Under Review"]]},
                )
                if not existing:
                    send_threshold_notification(pcf_fund=fund.name)
                    notified += 1
                    frappe.log_error(
                        f"Threshold notification sent for {fund.fund_label} ({fund.name})",
                        "PCF Threshold",
                    )

        if notified:
            frappe.log_error(f"PCF threshold check: {notified} notifications sent", "PCF Threshold")

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
        fields=["name", "store", "fund_label", "pending_total"],
    )

    submitted = 0
    for fund in funds:
        if (fund.pending_total or 0) > 0:
            existing = frappe.db.exists(
                "BEI PCF Batch",
                {"pcf_fund": fund.name, "status": ["in", ["Submitted", "Under Review"]]},
            )
            if not existing:
                from hrms.hr.doctype.bei_pcf_batch.bei_pcf_batch import create_batch_from_pending

                batch = create_batch_from_pending(
                    store=fund.store, submission_type="Month-End Auto", pcf_fund=fund.name
                )
                if batch:
                    submitted += 1
                    frappe.log_error(
                        f"Auto-submitted batch {batch.name} for {fund.fund_label} (month-end)",
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
        from hrms.hr.doctype.bei_petty_cash_fund.bei_petty_cash_fund import update_pcf_totals

        if doc.pcf_fund:
            update_pcf_totals(pcf_fund=doc.pcf_fund)
        elif doc.store:
            update_pcf_totals(store=doc.store)


def on_expense_delete(doc, method):
    """
    Called when BEI Expense Request is deleted.
    Recalculates PCF totals.
    """
    if doc.status == "Pending":
        from hrms.hr.doctype.bei_petty_cash_fund.bei_petty_cash_fund import update_pcf_totals

        if doc.pcf_fund:
            update_pcf_totals(pcf_fund=doc.pcf_fund)
        elif doc.store:
            update_pcf_totals(store=doc.store)


def validate_pcf_batch(doc, method):
    """
    Called when BEI PCF Batch is validated.
    Ensures proper computation and validation.
    """
    if not getattr(doc, "items", None):
        frappe.throw(_("Cannot create batch with no expense items"), frappe.ValidationError)

    # Keep batch aggregates in sync even when batch records are touched outside
    # the standard doctype flow.
    valid_items = [item for item in doc.items if getattr(item, "expense_request", None)]
    doc.expense_count = len(valid_items)
    doc.total_amount = sum(flt(getattr(item, "amount", 0)) for item in valid_items)

    dates = [getdate(item.expense_date) for item in valid_items if getattr(item, "expense_date", None)]
    if dates:
        doc.period_start = min(dates)
        doc.period_end = max(dates)


def on_batch_update(doc, method):
    """
    Called when BEI PCF Batch is updated.
    Handles status change notifications and expense updates.
    """
    status_map = {
        "Submitted": "Submitted",
        "Under Review": "Submitted",
        "Approved": "Approved",
        "Rejected": "Rejected",
    }
    target_status = status_map.get(getattr(doc, "status", None))
    if not target_status:
        return

    # Idempotent status sync for linked expenses. Safe to run multiple times.
    for item in getattr(doc, "items", []) or []:
        expense_request = getattr(item, "expense_request", None)
        if not expense_request:
            continue
        frappe.db.set_value("BEI Expense Request", expense_request, "status", target_status)

    # Keep PCF aggregates fresh for dashboard and threshold logic.
    try:
        from hrms.hr.doctype.bei_petty_cash_fund.bei_petty_cash_fund import update_pcf_totals

        if getattr(doc, "pcf_fund", None):
            update_pcf_totals(pcf_fund=doc.pcf_fund)
        elif getattr(doc, "store", None):
            update_pcf_totals(store=doc.store)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "PCF Hook Update Totals Failed")


# ============================================================
# NOTIFICATION FUNCTIONS
# ============================================================


def send_threshold_notification(pcf_fund: str = None, store: str = None):
    """
    Send notification when threshold is reached.

    Args:
        pcf_fund: PCF fund name (preferred)
        store: Warehouse name (legacy)
    """
    try:
        pcf_name = _resolve_pcf_fund(pcf_fund=pcf_fund, store=store)
        if not pcf_name:
            return

        pcf = frappe.db.get_value(
            "BEI Petty Cash Fund",
            pcf_name,
            ["custodian", "fund_amount", "pending_total", "threshold_percentage", "pending_count", "fund_label"],
            as_dict=True,
        )

        if not pcf:
            return

        message = f"""*PCF at {pcf.threshold_percentage:.0f}% — ready for batch submission*

Fund: {pcf.fund_label}
Pending: PHP {pcf.pending_total:,.2f} ({pcf.pending_count} expenses)
Fund Amount: PHP {pcf.fund_amount:,.2f}
Threshold: {pcf.threshold_percentage}%

Custodian can submit a batch when ready."""

        from hrms.api.google_chat import send_message_to_space
        from hrms.utils.bei_config import get_chat_space, SPACE_ERP_AUTOMATION

        send_message_to_space(get_chat_space(SPACE_ERP_AUTOMATION), message)
    except Exception as e:
        frappe.log_error(f"Failed to send threshold notification: {e}", "PCF Notification")


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def _get_store_for_employee(employee):
    """
    Get the store warehouse for an employee based on their branch.
    """
    store_context = resolve_employee_store_context(employee)
    return store_context.get("warehouse")


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
    for suffix in [get_company(), "BEI"]:
        full_name = f"{store_or_branch} - {suffix}"
        if frappe.db.exists("Warehouse", full_name):
            return full_name

    # Try partial match
    warehouse = frappe.db.get_value(
        "Warehouse", {"name": ["like", f"{store_or_branch}%"]}, "name"
    )
    return warehouse
