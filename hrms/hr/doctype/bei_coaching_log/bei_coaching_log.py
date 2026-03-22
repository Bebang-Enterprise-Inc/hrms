# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BEICoachingLog(Document):
    def validate(self):
        """Validate the coaching log."""
        if not self.coached_by:
            self.coached_by = frappe.session.user

        if self.follow_up_required and not self.follow_up_status:
            self.follow_up_status = "Pending"
