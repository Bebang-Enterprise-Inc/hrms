# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class BEIWarehouseReceiving(Document):
    def validate(self):
        self.validate_items()
        self.update_status()

    def validate_items(self):
        if not self.items:
            frappe.throw("At least one item is required")

        for item in self.items:
            expected = flt(item.expected_qty or 0)
            received = flt(item.received_qty or 0)
            rejected = flt(item.rejected_qty or 0)
            if received < 0 or rejected < 0:
                frappe.throw("Received and rejected quantities must be non-negative")
            if expected and received > expected:
                frappe.throw(f"Received quantity cannot exceed expected quantity for {item.item_code}")
            if expected and rejected > expected:
                frappe.throw(f"Rejected quantity cannot exceed expected quantity for {item.item_code}")
            item.accepted_qty = max(received - rejected, 0)
            item.has_issue = 1 if rejected > 0 or item.issue_notes else 0

    def update_status(self):
        if self.stock_entry and all(flt(item.accepted_qty or 0) >= 0 for item in self.items):
            has_issues = any(flt(item.rejected_qty or 0) > 0 or item.has_issue for item in self.items)
            self.status = "With Issues" if has_issues else "Completed"
            return
        self.status = "Pending Warehouse Receive"
