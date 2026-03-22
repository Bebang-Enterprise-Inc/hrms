# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BEIStoreReceiving(Document):
    def validate(self):
        self.validate_items()
        self.update_status()

    def validate_items(self):
        if not self.items:
            frappe.throw("At least one item is required")

    def update_status(self):
        # Check if any items have issues
        has_issues = any(item.has_issue for item in self.items)
        if has_issues:
            self.status = "With Issues"
        elif all(item.received_qty is not None for item in self.items):
            self.status = "Completed"

    def on_submit(self):
        # Create FQI reports for items with issues
        for item in self.items:
            if item.has_issue and not item.fqi_reference:
                self.create_fqi_for_item(item)

    def create_fqi_for_item(self, item):
        fqi = frappe.new_doc("BEI FQI Report")
        fqi.store = self.store
        fqi.receiving = self.name
        fqi.item_code = item.item_code
        fqi.expected_qty = item.expected_qty
        fqi.actual_qty = item.received_qty
        fqi.reported_by = frappe.session.user
        fqi.insert()
        item.fqi_reference = fqi.name
