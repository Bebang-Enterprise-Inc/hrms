# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class BEIFQIReport(Document):
    def validate(self):
        if not self.reported_by:
            self.reported_by = frappe.session.user
        if not self.reported_at:
            self.reported_at = now_datetime()

    def resolve(self, resolution_notes, resolved_by=None):
        self.status = "Resolved"
        self.resolution = resolution_notes
        self.resolved_by = resolved_by or frappe.session.user
        self.resolved_at = now_datetime()
        self.save()

    def on_update(self):
        # Notify relevant parties when FQI is created
        if self.is_new():
            self.notify_stakeholders()

    def notify_stakeholders(self):
        """Send Google Chat notification when a new FQI report is created."""
        try:
            from hrms.api.google_chat import send_message_to_space
            from hrms.utils.bei_config import get_chat_space, SPACE_NOTIFICATIONS

            message = (
                f"*FQI Report #{self.name}*\n"
                f"Issue: {self.issue_type or 'Not specified'}\n"
                f"Store: {self.store or 'N/A'}\n"
                f"Item: {self.item_code or 'N/A'}\n"
                f"Status: {self.status}\n"
                f"Reported by: {self.reported_by or frappe.session.user}"
            )
            send_message_to_space(get_chat_space(SPACE_NOTIFICATIONS), message)
        except Exception:
            frappe.log_error("FQI notification failed", "BEI FQI Report")
