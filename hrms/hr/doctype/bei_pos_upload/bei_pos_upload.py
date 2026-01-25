# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BEIPOSUpload(Document):
	def before_insert(self):
		if not self.uploaded_by:
			self.uploaded_by = frappe.session.user
