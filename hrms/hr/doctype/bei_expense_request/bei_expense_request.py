# Copyright (c) 2026, Bebang Enterprise Inc. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today


class BEIExpenseRequest(Document):
    def before_insert(self):
        """Set defaults before first save."""
        # Auto-set employee from session user if not provided
        if not self.employee:
            employee = frappe.db.get_value(
                "Employee",
                {"user_id": frappe.session.user},
                "name"
            )
            if employee:
                self.employee = employee

        # Auto-set employee's store if not provided
        if self.employee and not self.store:
            store = frappe.db.get_value("Employee", self.employee, "custom_store")
            if store:
                self.store = store

    def validate(self):
        """Validation logic."""
        if self.manual_amount and self.manual_amount <= 0:
            frappe.throw("Amount must be greater than 0")

        # Ensure expense date is not in the future
        if self.manual_date:
            if getdate(self.manual_date) > getdate(today()):
                frappe.throw("Expense date cannot be in the future")
