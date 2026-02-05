# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class BEIShiftTemplate(Document):
	def validate(self):
		self.validate_times()
		self.validate_compliance_settings()

	def validate_times(self):
		"""Validate time fields are logical."""
		if self.opening_time and self.closing_time:
			if self.opening_time >= self.closing_time:
				frappe.throw(_("Opening time must be before closing time"))

		if self.midshift_window_start and self.midshift_window_end:
			if self.midshift_window_start >= self.midshift_window_end:
				frappe.throw(_("Midshift window start must be before end"))

		if self.mall_opening and self.mall_closing:
			if self.mall_opening >= self.mall_closing:
				frappe.throw(_("Mall opening must be before closing"))

	def validate_compliance_settings(self):
		"""Validate DOLE compliance settings."""
		if self.max_daily_hours and self.max_daily_hours > 12:
			frappe.msgprint(
				_("Maximum daily hours exceeds 12. Ensure this complies with DOLE regulations."),
				indicator="orange"
			)

		if self.min_break_minutes and self.min_break_minutes < 60:
			frappe.msgprint(
				_("Minimum break is less than 60 minutes. DOLE requires 1 hour break for 8+ hour shifts."),
				indicator="orange"
			)


def get_shift_template_for_store(store):
	"""
	Get the applicable shift template for a store.
	Checks in order: Specific Store → Store Type → All Stores

	Args:
		store: Warehouse name

	Returns:
		BEI Shift Template document or None
	"""
	# Check for specific store template
	template = frappe.db.get_value(
		"BEI Shift Template",
		{"store_type": store, "applies_to": "Specific Store", "is_active": 1},
		"name"
	)
	if template:
		return frappe.get_doc("BEI Shift Template", template)

	# Check store type (mall vs street)
	# Get warehouse parent to determine type
	warehouse_type = frappe.db.get_value("Warehouse", store, "warehouse_type")

	if warehouse_type:
		store_type_map = {
			"Mall Store": "Mall Stores",
			"Street Store": "Street Stores"
		}
		mapped_type = store_type_map.get(warehouse_type)

		if mapped_type:
			template = frappe.db.get_value(
				"BEI Shift Template",
				{"applies_to": mapped_type, "is_active": 1},
				"name"
			)
			if template:
				return frappe.get_doc("BEI Shift Template", template)

	# Fall back to "All Stores" template
	template = frappe.db.get_value(
		"BEI Shift Template",
		{"applies_to": "All Stores", "is_active": 1},
		"name"
	)
	if template:
		return frappe.get_doc("BEI Shift Template", template)

	return None
