# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, getdate


class BEIActionPlan(Document):
    def before_save(self):
        """Update status based on dates and completion."""
        if self.status == "Completed":
            return

        if self.due_date and getdate(self.due_date) < getdate(nowdate()):
            if self.status not in ("Completed", "Cancelled"):
                self.status = "Overdue"

    def validate(self):
        """Validate the action plan."""
        if self.completed_date and not self.completed_by:
            self.completed_by = frappe.session.user

        if self.status == "Completed" and not self.completed_date:
            self.completed_date = nowdate()
