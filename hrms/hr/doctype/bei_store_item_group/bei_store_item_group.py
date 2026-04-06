# Copyright (c) 2026, BEI and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class BEIStoreItemGroup(Document):
	def validate(self):
		if not self.members:
			frappe.throw(_("BEI Store Item Group must have at least one member."))
		seen = set()
		for member in self.members:
			if member.item_code in seen:
				frappe.throw(_("Member item {0} is listed more than once.").format(member.item_code))
			seen.add(member.item_code)
			if member.priority is None:
				member.priority = 100
			if not member.conversion_to_display:
				member.conversion_to_display = 1.0
