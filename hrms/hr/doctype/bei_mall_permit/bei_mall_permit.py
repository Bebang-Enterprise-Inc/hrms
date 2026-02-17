# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate, date_diff


class BEIMallPermit(Document):
    def validate(self):
        self.set_status()

    def set_status(self):
        """Auto-compute status based on expiry_date vs today.

        Rules:
        - Expired:      expiry_date < today
        - Expiring Soon: expiry_date <= today + 30 days
        - Active:       expiry_date > today + 30 days
        - Renewal Pending: preserved if manually set (user override)
        """
        if not self.expiry_date:
            return

        # Don't override a manually-set Renewal Pending status
        if self.status == "Renewal Pending":
            return

        today = getdate(nowdate())
        expiry = getdate(self.expiry_date)
        days_remaining = date_diff(expiry, today)

        if days_remaining < 0:
            self.status = "Expired"
        elif days_remaining <= 30:
            self.status = "Expiring Soon"
        else:
            self.status = "Active"
