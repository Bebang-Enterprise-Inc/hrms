# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, add_days


class BEIStoreOrder(Document):
    def before_save(self):
        # Auto-set delivery date to next day if not set
        if not self.delivery_date:
            self.delivery_date = add_days(self.order_date or nowdate(), 1)

    def validate(self):
        self.validate_items()

    def validate_items(self):
        if not self.items:
            frappe.throw("At least one item is required")
        for item in self.items:
            if item.qty_requested <= 0:
                frappe.throw(f"Quantity for {item.item_code} must be greater than 0")

    def on_submit(self):
        self.submitted_by = frappe.session.user
        self.status = "Pending Approval"
