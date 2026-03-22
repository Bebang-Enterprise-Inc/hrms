# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BEIExternalHub(Document):
    def validate(self):
        """Validate hub data before saving."""
        if self.contact_email:
            if "@" not in self.contact_email:
                frappe.throw("Please enter a valid email address")

    def before_save(self):
        """Convert hub_code to uppercase."""
        if self.hub_code:
            self.hub_code = self.hub_code.upper()
