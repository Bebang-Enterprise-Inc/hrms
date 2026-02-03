# Copyright (c) 2026, Bebang Enterprise Inc. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate, now_datetime, getdate


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
        """Ensure no other batch is under review for this store."""
        if self.is_new():
            existing = frappe.db.exists(
                "BEI PCF Batch",
                {
                    "store": self.store,
                    "status": ["in", ["Submitted", "Under Review"]],
                    "name": ["!=", self.name],
                },
            )
            if existing:
                frappe.throw(
                    _(
                        "Store {0} already has a batch under review ({1}). "
                        "Please wait for it to be processed."
                    ).format(self.store, existing)
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
        pcf = frappe.db.get_value("BEI Petty Cash Fund", {"store": self.store}, "name")
        if pcf:
            if self.status in ["Submitted", "Under Review"]:
                # Update last batch date
                frappe.db.set_value("BEI Petty Cash Fund", pcf, "last_batch_date", nowdate())

            if self.status == "Approved":
                # Increment total batches
                frappe.db.sql(
                    """
                    UPDATE `tabBEI Petty Cash Fund`
                    SET total_batches = total_batches + 1,
                        total_expenses_ytd = total_expenses_ytd + %s
                    WHERE name = %s
                    """,
                    (self.total_amount, pcf),
                )

            # Trigger recalculation of pending totals
            from hrms.hr.doctype.bei_petty_cash_fund.bei_petty_cash_fund import update_pcf_totals

            update_pcf_totals(self.store)


def create_batch_from_pending(store, submission_type):
    """
    Create a PCF batch from all pending expenses for a store.

    Args:
        store: Warehouse name
        submission_type: 'Manual', 'Threshold Auto', or 'Month-End Auto'

    Returns:
        BEI PCF Batch document or None if no pending expenses
    """
    # Get all pending expenses for this store
    pending_expenses = frappe.get_all(
        "BEI Expense Request",
        filters={"store": store, "status": "Pending"},
        fields=["name", "employee", "employee_name", "manual_date", "manual_vendor", "manual_description", "manual_amount"],
        order_by="manual_date asc",
    )

    if not pending_expenses:
        return None

    # Check if batch already exists under review
    existing = frappe.db.exists(
        "BEI PCF Batch",
        {"store": store, "status": ["in", ["Submitted", "Under Review"]]},
    )
    if existing:
        frappe.log_error(
            f"Skipping batch creation for {store}: batch {existing} already under review",
            "PCF Auto-Submit",
        )
        return None

    # Create the batch
    batch = frappe.new_doc("BEI PCF Batch")
    batch.store = store
    batch.company = "Bebang Enterprise Inc."
    batch.batch_date = nowdate()
    batch.status = "Submitted"
    batch.submission_type = submission_type

    # Add items
    for exp in pending_expenses:
        batch.append(
            "items",
            {
                "expense_request": exp.name,
                "employee": exp.employee,
                "employee_name": exp.employee_name,
                "expense_date": exp.manual_date,
                "vendor": exp.manual_vendor,
                "description": exp.manual_description,
                "amount": exp.manual_amount,
                "item_status": "Pending",
            },
        )

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
        # Google Chat notifications disabled for now - will be implemented later
        # TODO: Implement proper Google Chat integration
        pass
    except Exception as e:
        # Silently log errors - don't block batch operations
        frappe.log_error(f"Failed to send PCF batch notification: {e}", "PCF Notification")
