# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class BEIRouteStop(Document):
	HUB_TERMS = ("3MD", "JENTEC", "RCS", "PINNACLE", "HUB")

	def validate(self):
		self.stop_mode = "hub_leg" if self.is_hub_stop() else "direct_leg"

	def is_hub_stop(self):
		store_value = (getattr(self, "store", "") or "").upper()
		return any(term in store_value for term in self.HUB_TERMS)
