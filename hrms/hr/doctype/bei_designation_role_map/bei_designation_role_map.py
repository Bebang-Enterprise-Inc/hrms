# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document


def _split_roles(raw_roles: str | None) -> list[str]:
	if not raw_roles:
		return []
	parts = re.split(r"[\n,]+", raw_roles)
	return [part.strip() for part in parts if part and part.strip()]


class BEIDesignationRoleMap(Document):
	def validate(self):
		self._validate_roles(self.roles_to_add, "Roles To Add")
		self._validate_roles(self.roles_to_remove, "Roles To Remove")

	def _validate_roles(self, raw_roles: str | None, label: str):
		for role in _split_roles(raw_roles):
			if not frappe.db.exists("Role", role):
				frappe.throw(_("{0} has invalid role: {1}").format(label, role))

