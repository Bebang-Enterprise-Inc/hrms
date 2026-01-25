# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class BEIKudos(Document):
	def before_insert(self):
		if not self.from_employee:
			self.from_employee = frappe.db.get_value(
				"Employee", {"user_id": frappe.session.user}, "name"
			)

	def validate(self):
		# Cannot send kudos to yourself
		if self.from_employee == self.to_employee:
			frappe.throw(_("You cannot send kudos to yourself"))
