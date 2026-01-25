# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BEIMidshiftChecklist(Document):
	def before_insert(self):
		if not self.submitted_by:
			self.submitted_by = frappe.session.user
