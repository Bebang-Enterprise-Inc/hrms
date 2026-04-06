# Copyright (c) 2026, Bebang Enterprise Inc. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate, now_datetime, getdate, flt
from hrms.utils.bei_config import get_company


class BEIPCFBatch(Document):
    def validate(self):
        self.validate_items()
        self.validate_no_duplicate_batch()
        self.compute_totals()

    def validate_items(self):
        """Ensure batch has at least one item."""
        if not self.items or len(self.items) == 0:
            frappe.throw(_("Cannot create batch with no expense items"))

    def validate_no_duplicate_batch(self):
        """Ensure no other batch is under review for this fund/store."""
        if self.is_new():
            # Check by pcf_fund first
            if self.pcf_fund:
                existing = frappe.db.exists(
                    "BEI PCF Batch",
                    {
                        "pcf_fund": self.pcf_fund,
                        "status": ["in", ["Submitted", "Under Review"]],
                        "name": ["!=", self.name],
                    },
                )
            elif self.store:
                existing = frappe.db.exists(
                    "BEI PCF Batch",
                    {
                        "store": self.store,
                        "status": ["in", ["Submitted", "Under Review"]],
                        "name": ["!=", self.name],
                    },
                )
            else:
                existing = None

            if existing:
                label = self.pcf_fund or self.store
                frappe.throw(
                    _(
                        "{0} already has a batch under review ({1}). "
                        "Please wait for it to be processed."
                    ).format(label, existing)
                )

    def compute_totals(self):
        """Compute total_amount, expense_count, period_start, period_end from items."""
        if not self.items:
            return

        self.expense_count = len(self.items)
        self.total_amount = sum(item.amount or 0 for item in self.items)

        dates = [getdate(item.expense_date) for item in self.items if item.expense_date]
        if dates:
            self.period_start = min(dates)
            self.period_end = max(dates)

    def before_insert(self):
        """Set submission details."""
        self.submitted_by = frappe.session.user
        self.submitted_at = now_datetime()

    def on_update(self):
        """Update linked expenses when batch status changes."""
        if self.has_value_changed("status"):
            self.update_expense_statuses()
            self.update_pcf_fund()

    def update_expense_statuses(self):
        """Update status of all expenses in this batch based on batch status."""
        status_map = {
            "Submitted": "Submitted",
            "Under Review": "Submitted",
            "Approved": "Approved",
            "Rejected": "Rejected",
        }

        new_status = status_map.get(self.status)
        if new_status:
            for item in self.items:
                if item.expense_request:
                    frappe.db.set_value(
                        "BEI Expense Request",
                        item.expense_request,
                        "status",
                        new_status,
                    )

    def update_pcf_fund(self):
        """Update PCF fund history fields."""
        pcf_name = self.pcf_fund
        if not pcf_name and self.store:
            pcf_name = frappe.db.get_value("BEI Petty Cash Fund", {"store": self.store}, "name")

        if pcf_name:
            if self.status in ["Submitted", "Under Review"]:
                frappe.db.set_value("BEI Petty Cash Fund", pcf_name, "last_batch_date", nowdate())

            if self.status == "Approved":
                frappe.db.sql(
                    """
                    UPDATE `tabBEI Petty Cash Fund`
                    SET total_batches = total_batches + 1,
                        total_expenses_ytd = total_expenses_ytd + %s
                    WHERE name = %s
                    """,
                    (self.total_amount, pcf_name),
                )

            # Trigger recalculation of pending totals
            from hrms.hr.doctype.bei_petty_cash_fund.bei_petty_cash_fund import update_pcf_totals

            update_pcf_totals(pcf_fund=pcf_name)


def create_batch_from_pending(store=None, submission_type="Manual", pcf_fund=None):
    """
    Create a PCF batch from all pending expenses for a fund.

    Args:
        store: Warehouse name (legacy, used if pcf_fund not set)
        submission_type: 'Manual', 'Threshold Auto', or 'Month-End Auto'
        pcf_fund: PCF fund name (preferred)

    Returns:
        BEI PCF Batch document or None if no pending expenses
    """
    from hrms.api.expense_classifier import COA_LABELS

    # Get all pending expenses
    if pcf_fund:
        filters = {"pcf_fund": pcf_fund, "status": "Pending"}
    elif store:
        filters = {"store": store, "status": "Pending"}
    else:
        return None

    pending_expenses = frappe.get_all(
        "BEI Expense Request",
        filters=filters,
        fields=[
            "name", "employee", "employee_name", "manual_date",
            "manual_vendor", "manual_description", "manual_amount",
            "internal_suggested_coa", "internal_coa_confidence",
        ],
        order_by="manual_date asc",
    )

    if not pending_expenses:
        return None

    # Check if batch already exists under review
    if pcf_fund:
        existing = frappe.db.exists(
            "BEI PCF Batch",
            {"pcf_fund": pcf_fund, "status": ["in", ["Submitted", "Under Review"]]},
        )
    else:
        existing = frappe.db.exists(
            "BEI PCF Batch",
            {"store": store, "status": ["in", ["Submitted", "Under Review"]]},
        )

    if existing:
        label = pcf_fund or store
        frappe.log_error(
            f"Skipping batch creation for {label}: batch {existing} already under review",
            "PCF Auto-Submit",
        )
        return None

    # Create the batch
    batch = frappe.new_doc("BEI PCF Batch")
    batch.store = store
    batch.pcf_fund = pcf_fund
    batch.company = get_company()
    batch.batch_date = nowdate()
    batch.status = "Submitted"
    batch.submission_type = submission_type

    # Add items with COA data
    for exp in pending_expenses:
        item_data = {
            "expense_request": exp.name,
            "employee": exp.employee,
            "employee_name": exp.employee_name,
            "expense_date": exp.manual_date,
            "vendor": exp.manual_vendor,
            "description": exp.manual_description,
            "amount": exp.manual_amount,
            "item_status": "Pending",
            "approved_amount": exp.manual_amount,  # Default to original amount
        }

        # Copy COA fields from expense if available
        if exp.internal_suggested_coa:
            item_data["suggested_coa"] = exp.internal_suggested_coa
            item_data["suggested_coa_label"] = COA_LABELS.get(exp.internal_suggested_coa, "")
            item_data["coa_confidence"] = flt(exp.internal_coa_confidence)

        batch.append("items", item_data)

    batch.insert(ignore_permissions=True)

    # Update expense statuses to Submitted and link to batch
    for exp in pending_expenses:
        frappe.db.set_value(
            "BEI Expense Request",
            exp.name,
            {"status": "Submitted", "pcf_batch": batch.name},
        )

    frappe.db.commit()

    # Send notification
    send_batch_notification(batch, "created")

    return batch


def send_batch_notification(batch, event):
    """
    Send Google Chat notification for batch events.

    Args:
        batch: BEI PCF Batch document
        event: 'created', 'approved', or 'rejected'
    """
    try:
        from hrms.api.google_chat import send_message_to_space

        # Use fund_label for display, fall back to store
        fund_label = ""
        if batch.pcf_fund:
            fund_label = frappe.db.get_value("BEI Petty Cash Fund", batch.pcf_fund, "fund_label") or batch.pcf_fund
        else:
            fund_label = batch.store or "Unknown"

        messages = {
            "created": f"*PCF Batch Created*\n\nFund: {fund_label}\nBatch: {batch.name}\nType: {batch.submission_type}\nExpenses: {batch.expense_count}\nTotal: PHP {batch.total_amount:,.2f}\n\nReady for accounting review.",
            "approved": f"*PCF Batch Approved*\n\nFund: {fund_label}\nBatch: {batch.name}\nTotal: PHP {batch.total_amount:,.2f}\nReviewed by: {batch.reviewed_by}",
            "rejected": f"*PCF Batch Rejected*\n\nFund: {fund_label}\nBatch: {batch.name}\nTotal: PHP {batch.total_amount:,.2f}\nReason: {batch.review_notes or 'Not specified'}",
        }

        message = messages.get(event)
        if message:
            from hrms.utils.bei_config import get_chat_space, SPACE_ERP_AUTOMATION
            send_message_to_space(get_chat_space(SPACE_ERP_AUTOMATION), message)
    except Exception as e:
        frappe.log_error(f"Failed to send PCF batch notification: {e}", "PCF Notification")
