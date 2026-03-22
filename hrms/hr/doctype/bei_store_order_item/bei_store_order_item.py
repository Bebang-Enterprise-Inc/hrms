# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import flt


class BEIStoreOrderItem(Document):
    def validate(self):
        self.amount = flt(self.qty_requested or 0) * flt(self.unit_price or 0)
