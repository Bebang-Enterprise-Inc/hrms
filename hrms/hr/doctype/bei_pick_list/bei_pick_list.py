# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class BEIPickList(Document):
    def validate(self):
        self.validate_trip()

    def validate_trip(self):
        if self.trip:
            trip_status = frappe.db.get_value("BEI Distribution Trip", self.trip, "status")
            if not trip_status:
                frappe.throw(_("Distribution Trip {0} not found").format(self.trip))
