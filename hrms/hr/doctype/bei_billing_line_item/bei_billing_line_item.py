# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BEIBillingLineItem(Document):
	def validate(self):
		self.calculate_amount()

	def calculate_amount(self):
		self.amount = (self.quantity or 0) * (self.unit_price or 0)
