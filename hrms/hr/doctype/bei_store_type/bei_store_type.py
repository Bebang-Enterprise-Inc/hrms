# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

CANONICAL_STORE_TYPE_VALUES = ("JV", "Managed Franchise", "Full Franchise")

STORE_TYPE_ALIASES = {
	"jv": "JV",
	"jv store": "JV",
	"jv stores": "JV",
	"joint venture": "JV",
	"joint venture store": "JV",
	"joint venture stores": "JV",
	"managed franchise": "Managed Franchise",
	"managed-franchise": "Managed Franchise",
	"managed_franchise": "Managed Franchise",
	"full franchise": "Full Franchise",
	"full-franchise": "Full Franchise",
	"full_franchise": "Full Franchise",
}


def normalize_store_type(value):
	"""Normalize any store type variant to its canonical value when possible."""
	if value is None:
		return ""

	raw_value = " ".join(str(value).strip().split())
	if not raw_value:
		return ""

	normalized_key = raw_value.lower().replace("_", " ").replace("-", " ")
	normalized_key = " ".join(normalized_key.split())

	return STORE_TYPE_ALIASES.get(normalized_key, raw_value)


def resolve_store_type(store_type=None, store_type_category=None):
	"""Resolve canonical store type from canonical or legacy field."""
	return normalize_store_type(store_type or store_type_category)


def is_canonical_store_type(value):
	"""Return True if value is one of the canonical store_type values."""
	return normalize_store_type(value) in CANONICAL_STORE_TYPE_VALUES


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
		self.normalize_store_type_fields()
		self.validate_store_type_contract()
		self.validate_store_exists()
		self.validate_store_uniqueness()
		self.set_default_rates()

	def normalize_store_type_fields(self):
		"""Normalize store type values from canonical or legacy fields."""
		self.store_type = resolve_store_type(
			store_type=getattr(self, "store_type", None),
			store_type_category=getattr(self, "store_type_category", None),
		)

	def validate_store_type_contract(self):
		"""Enforce canonical store_type contract."""
		if not self.store_type:
			frappe.throw(_("Store Type is required"))

		if self.store_type not in CANONICAL_STORE_TYPE_VALUES:
			allowed_values = ", ".join(CANONICAL_STORE_TYPE_VALUES)
			frappe.throw(
				_("Invalid store type '{0}'. Allowed values: {1}").format(self.store_type, allowed_values)
			)

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
