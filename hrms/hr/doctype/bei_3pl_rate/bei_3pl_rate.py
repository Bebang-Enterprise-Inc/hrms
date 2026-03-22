# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BEI3PLRate(Document):
    def validate(self):
        if self.effective_to and self.effective_from:
            if self.effective_to < self.effective_from:
                frappe.throw(
                    frappe._("Effective To date cannot be before Effective From date")
                )
