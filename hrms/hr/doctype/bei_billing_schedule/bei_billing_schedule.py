# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _


class BEIBillingSchedule(Document):
	def validate(self):
		"""Calculate all fees based on store type."""
		self.calculate_fees()
		self.calculate_line_items()
		self.calculate_totals()

	def calculate_fees(self):
		"""Calculate fees based on store type and sales data."""
		VAT_RATE = 0.12

		# Get store type from BEI Store Type master if not set
		if not self.store_type and self.store:
			store_type_doc = frappe.db.get_value(
				"BEI Store Type",
				{"store": self.store},
				"store_type"
			)
			if store_type_doc:
				self.store_type = store_type_doc

		# Billing matrix by store type
		if self.store_type == "JV":
			# JV Stores
			self.royalty_fee = 0
			self.management_fee = 0

			# Marketing: 5% of NET sales (not gross!)
			self.marketing_fee = self.net_sales * 0.05 if self.net_sales else 0

			# eCommerce: 5% of online sales
			self.ecommerce_fee = self.online_sales * 0.05 if self.online_sales else 0

			# Deliveries: Cost + 12% VAT (no 8% markup for JV)
			if self.delivery_cost:
				self.delivery_fee = self.delivery_cost * (1 + VAT_RATE)

			# Logistics: Cost + 12% VAT (no 8% markup for JV)
			if self.logistics_cost:
				self.logistics_fee = self.logistics_cost * (1 + VAT_RATE)

		elif self.store_type == "Managed Franchise":
			# Managed Franchise
			# Royalty: 7% gross + 12% VAT
			self.royalty_fee = self.gross_sales * 0.07 * (1 + VAT_RATE) if self.gross_sales else 0

			# Management: 2.5% gross + 12% VAT
			self.management_fee = self.gross_sales * 0.025 * (1 + VAT_RATE) if self.gross_sales else 0

			# Marketing: 5% gross
			self.marketing_fee = self.gross_sales * 0.05 if self.gross_sales else 0

			# eCommerce: 5% online
			self.ecommerce_fee = self.online_sales * 0.05 if self.online_sales else 0

			# Deliveries: (Cost + 12% VAT) + 8%
			if self.delivery_cost:
				base_delivery = self.delivery_cost * (1 + VAT_RATE)
				self.delivery_fee = base_delivery * 1.08

			# Logistics: (Cost + 12% VAT) + 8%
			if self.logistics_cost:
				base_logistics = self.logistics_cost * (1 + VAT_RATE)
				self.logistics_fee = base_logistics * 1.08

		elif self.store_type == "Full Franchise":
			# Full Franchise
			# Royalty: 7% gross + 12% VAT
			self.royalty_fee = self.gross_sales * 0.07 * (1 + VAT_RATE) if self.gross_sales else 0

			# Management: N/A
			self.management_fee = 0

			# Marketing: 5% gross
			self.marketing_fee = self.gross_sales * 0.05 if self.gross_sales else 0

			# eCommerce: 5% online
			self.ecommerce_fee = self.online_sales * 0.05 if self.online_sales else 0

			# Deliveries: (Cost + 12% VAT) + 8%
			if self.delivery_cost:
				base_delivery = self.delivery_cost * (1 + VAT_RATE)
				self.delivery_fee = base_delivery * 1.08

			# Logistics: (Cost + 12% VAT) + 8%
			if self.logistics_cost:
				base_logistics = self.logistics_cost * (1 + VAT_RATE)
				self.logistics_fee = base_logistics * 1.08

	def calculate_line_items(self):
		"""Update line item amounts."""
		for item in self.line_items:
			item.amount = (item.quantity or 0) * (item.unit_price or 0)

	def calculate_totals(self):
		"""Calculate subtotal, VAT, and total."""
		# Sum all fees
		fees = [
			self.royalty_fee or 0,
			self.management_fee or 0,
			self.marketing_fee or 0,
			self.ecommerce_fee or 0,
			self.delivery_fee or 0,
			self.logistics_fee or 0,
			self.repairs_maintenance or 0,
			self.preventive_maintenance or 0
		]

		# Add line items
		for item in self.line_items:
			fees.append(item.amount or 0)

		self.subtotal = sum(fees)

		# VAT already included in most fees, but calculate for line items
		vat_amount = 0
		for item in self.line_items:
			if item.vat_applicable:
				vat_amount += (item.amount or 0) * 0.12

		self.vat_amount = vat_amount
		self.total_amount = self.subtotal + self.vat_amount

	def send_to_store(self):
		"""Generate and send Statement of Account to store."""
		self.status = "Sent"
		self.sent_on = frappe.utils.now()
		self.save()

		# TODO: Generate PDF and send via email
		frappe.msgprint(_("Billing statement sent to {0}").format(self.store))
