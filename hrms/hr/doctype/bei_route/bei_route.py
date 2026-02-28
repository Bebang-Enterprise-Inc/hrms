# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


VALID_ARCHITECTURE_MODES = {"hub", "direct"}


class BEIRoute(Document):
	def validate(self):
		self.architecture_mode_resolved = self.resolve_architecture_mode()

	def resolve_architecture_mode(self):
		mode = (getattr(self, "architecture_mode", None) or "").strip().lower()
		if not mode:
			notes = (getattr(self, "notes", None) or "").lower()
			if "mode:direct" in notes or "architecture=direct" in notes:
				mode = "direct"
			elif "mode:hub" in notes or "architecture=hub" in notes:
				mode = "hub"

		mode = mode or "hub"
		if mode not in VALID_ARCHITECTURE_MODES:
			frappe.throw(f"Invalid architecture mode '{mode}'. Use 'hub' or 'direct'.")
		return mode

	def architecture_hint(self):
		mode = self.resolve_architecture_mode()
		if mode == "direct":
			return "Direct store dispatch mode: transfers bypass external hubs."
		return "Hub-and-spoke mode: transfers route through designated hubs."
