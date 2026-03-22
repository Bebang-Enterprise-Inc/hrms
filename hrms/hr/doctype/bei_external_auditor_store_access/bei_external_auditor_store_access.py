# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BEIExternalAuditorStoreAccess(Document):
	"""
	Defines which warehouses/stores an External Auditor can access.
	Used by inventory.py APIs to filter accessible stores.
	"""
	def validate(self):
		if frappe.db.exists("BEI External Auditor Store Access",
			{"user": self.user, "warehouse": self.warehouse, "name": ["!=", self.name]}):
			frappe.throw(f"Access already granted for {self.user} to {self.warehouse}")
