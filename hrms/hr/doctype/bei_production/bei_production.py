# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt
from hrms.api.commissary import resolve_outsourced_item_flag


class BEIProduction(Document):
	def before_save(self):
		if self.qty_planned and self.qty_produced:
			self.yield_pct = flt(self.qty_produced) / flt(self.qty_planned) * 100

		flag = resolve_outsourced_item_flag(
			item_code=getattr(self, "item_code", None),
			item_name=getattr(self, "item_name", None),
		)
		self.is_outsourced_item = 1 if flag["is_outsourced_item"] else 0
		self.outsourced_flag_reason = flag["reason"]

		if flag["is_outsourced_item"]:
			marker = f"[OUTSOURCED:{flag['reason']}]"
			remarks = (self.remarks or "").strip()
			if marker not in remarks:
				self.remarks = f"{remarks} {marker}".strip()
