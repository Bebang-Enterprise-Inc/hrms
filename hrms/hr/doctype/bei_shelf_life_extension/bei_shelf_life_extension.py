# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BEIShelfLifeExtension(Document):
	def before_insert(self):
		if not self.requested_by:
			self.requested_by = frappe.session.user
