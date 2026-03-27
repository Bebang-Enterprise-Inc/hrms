# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BEIProductionTargetLog(Document):
	def before_save(self):
		"""Immutability enforcement: log entries cannot be modified after creation."""
		if not self.is_new():
			frappe.throw("Production Target Log entries are immutable and cannot be modified.")

	def on_trash(self):
		"""Immutability enforcement: log entries cannot be deleted."""
		frappe.throw("Production Target Log entries cannot be deleted.")
