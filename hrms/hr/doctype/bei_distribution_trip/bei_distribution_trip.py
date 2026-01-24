# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class BEIDistributionTrip(Document):
    def validate(self):
        self.validate_stops()
        self.update_status()

    def validate_stops(self):
        if not self.stops:
            frappe.throw("At least one delivery stop is required")
        # Auto-number stops if not set
        for idx, stop in enumerate(self.stops, 1):
            if not stop.stop_order:
                stop.stop_order = idx

    def update_status(self):
        if not self.stops:
            return

        delivered = sum(1 for s in self.stops if s.status == "Delivered")
        total = len(self.stops)

        if delivered == total:
            self.status = "Completed"
        elif delivered > 0:
            self.status = "Partial"
        elif self.departure_time:
            self.status = "In Transit"

    def confirm_departure(self):
        self.departure_time = now_datetime()
        self.status = "In Transit"
        self.save()

    def confirm_stop_delivery(self, stop_idx, signature, signed_by):
        if stop_idx < len(self.stops):
            stop = self.stops[stop_idx]
            stop.status = "Delivered"
            stop.arrival_time = now_datetime()
            stop.signature = signature
            stop.signed_by = signed_by
            self.update_status()
            self.save()
