# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class BEITransferDeviceCommand(Document):
	def validate(self):
		self._validate_command_type()
		self._validate_command_text()
		self._sync_from_transfer_request()

	def _validate_command_type(self):
		allowed = {"UPDATE_USERINFO", "DELETE_USERINFO", "RELIEVER_DELETE_USERINFO"}
		if self.command_type not in allowed:
			frappe.throw(_("Invalid command type: {0}").format(self.command_type))

	def _validate_command_text(self):
		command = (self.command_text or "").strip()
		if not command:
			frappe.throw(_("Command text is required"))

		if command.startswith("C:"):
			frappe.throw(
				_(
					"Command text must not include C:<serial>: prefix. "
					"ADMS receiver adds wire-format prefixes automatically."
				)
			)

		if "USERINFO" in command.upper() and "UPDATE" in command.upper() and "\t" not in command:
			frappe.throw(
				_(
					"USERINFO command must contain real TAB separators "
					"between PIN, Name, and Pri fields."
				)
			)

	def _sync_from_transfer_request(self):
		if not self.transfer_request or not frappe.db.exists("BEI Transfer Request", self.transfer_request):
			return

		transfer = frappe.get_cached_doc("BEI Transfer Request", self.transfer_request)
		self.employee = transfer.employee
		self.employee_name = transfer.employee_name
		self.effective_date = transfer.effective_date

