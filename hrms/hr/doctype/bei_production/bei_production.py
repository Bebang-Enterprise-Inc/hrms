# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class BEIProduction(Document):
	def before_save(self):
		if self.qty_planned and self.qty_produced:
			self.yield_pct = flt(self.qty_produced) / flt(self.qty_planned) * 100
