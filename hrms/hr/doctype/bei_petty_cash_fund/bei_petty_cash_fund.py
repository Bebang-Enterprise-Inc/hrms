# Copyright (c) 2026, Bebang Enterprise Inc. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class BEIPettyCashFund(Document):
    def validate(self):
        self.validate_fund_type()
        self.validate_threshold()
        self.validate_fund_amount()
        self.validate_custodian()
        self.generate_fund_label()
        self.update_computed_fields()

    def validate_fund_type(self):
        """Enforce exactly one of store/department based on fund_type."""
        if self.fund_type == "Store":
            if not self.store:
                frappe.throw(_("Store is required for Store-type funds"))
            self.department = None
            # Uniqueness: no duplicate store funds
            existing = frappe.db.get_value(
                "BEI Petty Cash Fund",
                {"fund_type": "Store", "store": self.store, "name": ["!=", self.name]},
                "name",
            )
            if existing:
                frappe.throw(_("A PCF fund already exists for store {0} ({1})").format(self.store, existing))
        elif self.fund_type == "Department":
            if not self.department:
                frappe.throw(_("Department is required for Department-type funds"))
            self.store = None
            # Uniqueness: no duplicate department funds
            existing = frappe.db.get_value(
                "BEI Petty Cash Fund",
                {"fund_type": "Department", "department": self.department, "name": ["!=", self.name]},
                "name",
            )
            if existing:
                frappe.throw(_("A PCF fund already exists for department {0} ({1})").format(self.department, existing))

    def generate_fund_label(self):
        """Auto-generate fund_label from store name or department name."""
        if self.fund_type == "Store" and self.store:
            # Strip company suffix like " - BEI" or " - Bebang Enterprise Inc."
            label = self.store
            for suffix in [" - Bebang Enterprise Inc.", " - BEI"]:
                if label.endswith(suffix):
                    label = label[: -len(suffix)]
                    break
            self.fund_label = label
        elif self.fund_type == "Department" and self.department:
            # Strip company suffix from department name too
            label = self.department
            for suffix in [" - Bebang Enterprise Inc.", " - BEI"]:
                if label.endswith(suffix):
                    label = label[: -len(suffix)]
                    break
            self.fund_label = label

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
        # Query by pcf_fund first, fall back to store for pre-migration records
        if self.name and frappe.db.exists("BEI Petty Cash Fund", self.name):
            pending = frappe.db.sql(
                """
                SELECT COUNT(*) as count, COALESCE(SUM(manual_amount), 0) as total
                FROM `tabBEI Expense Request`
                WHERE pcf_fund = %s AND status = 'Pending'
                """,
                self.name,
                as_dict=True,
            )[0]
        elif self.store:
            # Fallback for pre-migration records without pcf_fund
            pending = frappe.db.sql(
                """
                SELECT COUNT(*) as count, COALESCE(SUM(manual_amount), 0) as total
                FROM `tabBEI Expense Request`
                WHERE store = %s AND pcf_fund IS NULL AND status = 'Pending'
                """,
                self.store,
                as_dict=True,
            )[0]
        else:
            pending = {"count": 0, "total": 0}

        # pending is a dict (from frappe.db.sql(..., as_dict=True)) or a plain dict
        # fallback — use key access, not attribute access.
        self.pending_count = pending.get("count") or 0
        self.pending_total = pending.get("total") or 0
        self.current_balance = self.fund_amount - self.pending_total

    def get_threshold_amount(self):
        """Calculate the threshold amount for notification."""
        return self.fund_amount * self.threshold_percentage / 100

    def is_at_threshold(self):
        """Check if pending total has reached the threshold."""
        return self.pending_total >= self.get_threshold_amount()

    def has_pending_batch(self):
        """Check if there's already a batch under review for this fund."""
        # Check by pcf_fund first
        existing = frappe.db.exists(
            "BEI PCF Batch",
            {"pcf_fund": self.name, "status": ["in", ["Submitted", "Under Review"]]},
        )
        if existing:
            return existing
        # Fallback to store for pre-migration batches
        if self.store:
            return frappe.db.exists(
                "BEI PCF Batch",
                {"store": self.store, "pcf_fund": ["is", "not set"], "status": ["in", ["Submitted", "Under Review"]]},
            )
        return None


def update_pcf_totals(store=None, pcf_fund=None):
    """
    Update the pending_total and current_balance for a PCF fund.
    Called when expenses are added/modified/deleted.

    Args:
        store: Warehouse name (legacy compat)
        pcf_fund: PCF fund name (preferred)
    """
    pcf_name = pcf_fund
    if not pcf_name and store:
        pcf_name = frappe.db.get_value("BEI Petty Cash Fund", {"store": store}, "name")

    if pcf_name:
        doc = frappe.get_doc("BEI Petty Cash Fund", pcf_name)
        doc.update_computed_fields()
        doc.db_update()
        frappe.db.commit()
        return doc
    return None


def get_pcf_for_store(store):
    """Get the PCF fund document for a store (backward compat)."""
    pcf_name = frappe.db.get_value("BEI Petty Cash Fund", {"store": store, "is_enabled": 1}, "name")
    if pcf_name:
        return frappe.get_doc("BEI Petty Cash Fund", pcf_name)
    return None


def get_pcf_fund(pcf_fund_name):
    """Get a PCF fund document by name."""
    if pcf_fund_name and frappe.db.exists("BEI Petty Cash Fund", pcf_fund_name):
        return frappe.get_doc("BEI Petty Cash Fund", pcf_fund_name)
    return None
