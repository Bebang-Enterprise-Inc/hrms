# Copyright (c) 2026, Bebang Enterprise Inc.
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import flt


class BEIInvoiceItem(Document):
	def validate(self):
		"""Compute derived fields (DM-5: computed in validate, not stored directly)."""
		self.amount = flt(flt(self.qty) * flt(self.rate), 2)
		vat_rate = flt(self.vat_rate) if self.vat_rate is not None else 12
		self.vat_amount = flt(self.amount * vat_rate / 100, 2)
