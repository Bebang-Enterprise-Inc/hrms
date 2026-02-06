# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class BEIStoreType(Document):
	"""
	Store Type master for franchise billing classification.

	Store Types:
	- JV (Joint Venture): Company-owned stores
	- Managed Franchise: Franchised but managed by company
	- Full Franchise: Independently operated franchises

	Billing rates differ by store type (see BEI Billing Schedule).
	"""

	def validate(self):
		"""Validate store type configuration."""
		self.validate_store_exists()
		self.validate_store_uniqueness()
		self.set_default_rates()

	def validate_store_exists(self):
		"""Ensure store (Department) exists."""
		if not frappe.db.exists("Department", self.store):
			frappe.throw(_("Department {0} does not exist").format(self.store))

	def validate_store_uniqueness(self):
		"""Ensure each store has only one type."""
		if self.is_new():
			existing = frappe.db.exists("BEI Store Type", {"store": self.store})
			if existing and existing != self.name:
				frappe.throw(_("Store {0} already has a type assigned").format(self.store))

	def set_default_rates(self):
		"""Set default billing rates if not specified."""
		if self.store_type == "JV":
			# JV stores: No royalty or management fees
			self.royalty_rate = 0
			self.management_fee_rate = 0
			if not self.marketing_fee_rate:
				self.marketing_fee_rate = 5  # 5% of net sales

		elif self.store_type == "Managed Franchise":
			# Managed Franchise: All fees applicable
			if not self.royalty_rate:
				self.royalty_rate = 7  # 7% of gross sales + VAT
			if not self.management_fee_rate:
				self.management_fee_rate = 2.5  # 2.5% of gross sales + VAT
			if not self.marketing_fee_rate:
				self.marketing_fee_rate = 5  # 5% of gross sales
			if not self.price_list_multiplier:
				self.price_list_multiplier = 8  # 8% markup on deliveries/logistics

		elif self.store_type == "Full Franchise":
			# Full Franchise: No management fee
			if not self.royalty_rate:
				self.royalty_rate = 7  # 7% of gross sales + VAT
			self.management_fee_rate = 0  # No management fee
			if not self.marketing_fee_rate:
				self.marketing_fee_rate = 5  # 5% of gross sales
			if not self.price_list_multiplier:
				self.price_list_multiplier = 8  # 8% markup on deliveries/logistics
