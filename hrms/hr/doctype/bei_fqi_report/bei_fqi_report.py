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
        # TODO: Send notifications to QA, SCM, AS, RM
        pass
