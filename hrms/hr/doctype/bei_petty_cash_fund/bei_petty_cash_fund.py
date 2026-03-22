# Copyright (c) 2026, Bebang Enterprise Inc. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class BEIPettyCashFund(Document):
    def validate(self):
        self.validate_threshold()
        self.validate_fund_amount()
        self.validate_custodian()
        self.update_computed_fields()

    def validate_threshold(self):
        """Ensure threshold percentage is between 1 and 100."""
        if self.threshold_percentage < 1 or self.threshold_percentage > 100:
            frappe.throw(_("Threshold percentage must be between 1 and 100"))

    def validate_fund_amount(self):
        """Ensure fund amount is positive."""
        if self.fund_amount <= 0:
            frappe.throw(_("Fund amount must be greater than 0"))

    def validate_custodian(self):
        """Ensure custodian has an Employee record."""
        if self.custodian:
            employee = frappe.db.exists("Employee", {"user_id": self.custodian, "status": "Active"})
            if not employee:
                frappe.msgprint(
                    _("Warning: Custodian {0} does not have an active Employee record").format(
                        self.custodian
                    ),
                    indicator="orange",
                )

    def update_computed_fields(self):
        """Update current_balance and pending_total from actual expenses."""
        # Get pending expenses for this store
        pending = frappe.db.sql(
            """
            SELECT COUNT(*) as count, COALESCE(SUM(manual_amount), 0) as total
            FROM `tabBEI Expense Request`
            WHERE store = %s AND status = 'Pending'
            """,
            self.store,
            as_dict=True,
        )[0]

        self.pending_count = pending.count or 0
        self.pending_total = pending.total or 0
        self.current_balance = self.fund_amount - self.pending_total

    def get_threshold_amount(self):
        """Calculate the threshold amount for auto-submit."""
        return self.fund_amount * self.threshold_percentage / 100

    def is_at_threshold(self):
        """Check if pending total has reached the threshold."""
        return self.pending_total >= self.get_threshold_amount()

    def has_pending_batch(self):
        """Check if there's already a batch under review for this store."""
        return frappe.db.exists(
            "BEI PCF Batch",
            {"store": self.store, "status": ["in", ["Submitted", "Under Review"]]},
        )


def update_pcf_totals(store):
    """
    Update the pending_total and current_balance for a store's PCF fund.
    Called when expenses are added/modified/deleted.
    """
    pcf = frappe.db.get_value("BEI Petty Cash Fund", {"store": store}, "name")
    if pcf:
        doc = frappe.get_doc("BEI Petty Cash Fund", pcf)
        doc.update_computed_fields()
        doc.db_update()
        frappe.db.commit()
        return doc
    return None


def get_pcf_for_store(store):
    """Get the PCF fund document for a store."""
    pcf_name = frappe.db.get_value("BEI Petty Cash Fund", {"store": store, "is_enabled": 1}, "name")
    if pcf_name:
        return frappe.get_doc("BEI Petty Cash Fund", pcf_name)
    return None
