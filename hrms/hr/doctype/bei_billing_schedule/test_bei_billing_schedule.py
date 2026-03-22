# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from datetime import date


class TestBEIBillingSchedule(FrappeTestCase):
	def setUp(self):
		"""Set up test data."""
		# Create store type masters if they don't exist
		self._create_store_type_if_not_exists("BGC", "Managed Franchise")
		self._create_store_type_if_not_exists("Makati", "Full Franchise")
		self._create_store_type_if_not_exists("Ortigas", "JV")

	def _create_store_type_if_not_exists(self, store_name, store_type):
		"""Helper to create store type master."""
		if not frappe.db.exists("BEI Store Type", store_name):
			frappe.get_doc({
				"doctype": "BEI Store Type",
				"store": store_name,
				"store_type": store_type,
				"royalty_rate": 7,
				"management_fee_rate": 2.5,
				"marketing_fee_rate": 5,
				"price_list_multiplier": 8
			}).insert()

	def tearDown(self):
		"""Clean up test data."""
		frappe.db.rollback()

	def test_managed_franchise_billing(self):
		"""Test billing calculation for Managed Franchise."""
		billing = frappe.get_doc({
			"doctype": "BEI Billing Schedule",
			"billing_period": "2026-02",
			"store": "BGC",
			"store_type": "Managed Franchise",
			"gross_sales": 500000.00,
			"net_sales": 450000.00,
			"online_sales": 50000.00,
			"delivery_cost": 80000.00,
			"logistics_cost": 30000.00
		})
		billing.insert()

		# Managed Franchise formulas from questionnaire:
		# Royalty = 7% gross + 12% VAT
		# Management = 2.5% gross + 12% VAT
		# Marketing = 5% gross
		# eCommerce = 5% online
		# Deliveries = (Cost + 12% VAT) + 8%
		# Logistics = (Cost + 12% VAT) + 8%

		expected_royalty = 500000 * 0.07 * 1.12  # 39,200
		expected_management = 500000 * 0.025 * 1.12  # 14,000
		expected_marketing = 500000 * 0.05  # 25,000
		expected_ecommerce = 50000 * 0.05  # 2,500

		# Delivery: (80000 * 1.12) + 8% = 89,600 * 1.08 = 96,768
		expected_delivery = 80000 * 1.12 * 1.08  # 96,768

		# Logistics: (30000 * 1.12) + 8% = 33,600 * 1.08 = 36,288
		expected_logistics = 30000 * 1.12 * 1.08  # 36,288

		self.assertAlmostEqual(billing.royalty_fee, expected_royalty, places=2)
		self.assertAlmostEqual(billing.management_fee, expected_management, places=2)
		self.assertAlmostEqual(billing.marketing_fee, expected_marketing, places=2)
		self.assertAlmostEqual(billing.ecommerce_fee, expected_ecommerce, places=2)
		self.assertAlmostEqual(billing.delivery_fee, expected_delivery, places=2)
		self.assertAlmostEqual(billing.logistics_fee, expected_logistics, places=2)

	def test_full_franchise_billing(self):
		"""Test billing calculation for Full Franchise."""
		billing = frappe.get_doc({
			"doctype": "BEI Billing Schedule",
			"billing_period": "2026-02",
			"store": "Makati",
			"store_type": "Full Franchise",
			"gross_sales": 400000.00,
			"net_sales": 360000.00,
			"online_sales": 40000.00,
			"delivery_cost": 60000.00,
			"logistics_cost": 20000.00
		})
		billing.insert()

		# Full Franchise formulas:
		# Royalty = 7% gross + 12% VAT
		# Management = N/A (0)
		# Marketing = 5% gross
		# eCommerce = 5% online
		# Deliveries = (Cost + 12% VAT) + 8%
		# Logistics = (Cost + 12% VAT) + 8%

		expected_royalty = 400000 * 0.07 * 1.12  # 31,360
		expected_management = 0  # N/A for Full Franchise
		expected_marketing = 400000 * 0.05  # 20,000
		expected_ecommerce = 40000 * 0.05  # 2,000
		expected_delivery = 60000 * 1.12 * 1.08  # 72,576
		expected_logistics = 20000 * 1.12 * 1.08  # 24,192

		self.assertAlmostEqual(billing.royalty_fee, expected_royalty, places=2)
		self.assertEqual(billing.management_fee, expected_management)
		self.assertAlmostEqual(billing.marketing_fee, expected_marketing, places=2)
		self.assertAlmostEqual(billing.ecommerce_fee, expected_ecommerce, places=2)
		self.assertAlmostEqual(billing.delivery_fee, expected_delivery, places=2)
		self.assertAlmostEqual(billing.logistics_fee, expected_logistics, places=2)

	def test_jv_billing(self):
		"""Test billing calculation for JV stores."""
		billing = frappe.get_doc({
			"doctype": "BEI Billing Schedule",
			"billing_period": "2026-02",
			"store": "Ortigas",
			"store_type": "JV",
			"gross_sales": 600000.00,
			"net_sales": 540000.00,
			"online_sales": 60000.00,
			"delivery_cost": 100000.00,
			"logistics_cost": 40000.00
		})
		billing.insert()

		# JV formulas:
		# Royalty = N/A (0)
		# Management = N/A (0)
		# Marketing = 5% net (not gross!)
		# eCommerce = 5% online
		# Deliveries = Cost + 12% VAT
		# Logistics = Cost + 12% VAT

		expected_royalty = 0
		expected_management = 0
		expected_marketing = 540000 * 0.05  # 27,000 (from net sales!)
		expected_ecommerce = 60000 * 0.05  # 3,000
		expected_delivery = 100000 * 1.12  # 112,000 (no 8% markup)
		expected_logistics = 40000 * 1.12  # 44,800 (no 8% markup)

		self.assertEqual(billing.royalty_fee, expected_royalty)
		self.assertEqual(billing.management_fee, expected_management)
		self.assertAlmostEqual(billing.marketing_fee, expected_marketing, places=2)
		self.assertAlmostEqual(billing.ecommerce_fee, expected_ecommerce, places=2)
		self.assertAlmostEqual(billing.delivery_fee, expected_delivery, places=2)
		self.assertAlmostEqual(billing.logistics_fee, expected_logistics, places=2)

	def test_line_items_calculation(self):
		"""Test that line items are calculated correctly."""
		billing = frappe.get_doc({
			"doctype": "BEI Billing Schedule",
			"billing_period": "2026-02",
			"store": "BGC",
			"store_type": "Managed Franchise",
			"gross_sales": 500000.00,
			"net_sales": 450000.00,
			"line_items": [
				{
					"description": "Plumbing repair",
					"quantity": 2,
					"unit_price": 5000.00,
					"vat_applicable": 1
				},
				{
					"description": "Electrical work",
					"quantity": 1,
					"unit_price": 8000.00,
					"vat_applicable": 1
				}
			]
		})
		billing.insert()

		# Check line item amounts are calculated
		self.assertEqual(billing.line_items[0].amount, 10000.00)
		self.assertEqual(billing.line_items[1].amount, 8000.00)

	def test_totals_calculation(self):
		"""Test that subtotal, VAT, and total are calculated correctly."""
		billing = frappe.get_doc({
			"doctype": "BEI Billing Schedule",
			"billing_period": "2026-02",
			"store": "BGC",
			"store_type": "Managed Franchise",
			"gross_sales": 500000.00,
			"net_sales": 450000.00,
			"online_sales": 50000.00,
			"delivery_cost": 80000.00,
			"logistics_cost": 30000.00,
			"repairs_maintenance": 15000.00,
			"preventive_maintenance": 10000.00,
			"line_items": [
				{
					"description": "Custom charge",
					"quantity": 1,
					"unit_price": 5000.00,
					"vat_applicable": 1
				}
			]
		})
		billing.insert()

		# Sum all fees
		expected_subtotal = (
			billing.royalty_fee +
			billing.management_fee +
			billing.marketing_fee +
			billing.ecommerce_fee +
			billing.delivery_fee +
			billing.logistics_fee +
			15000.00 +  # repairs_maintenance
			10000.00 +  # preventive_maintenance
			5000.00     # line item amount
		)

		# VAT from line items only (other fees already include VAT)
		expected_vat = 5000.00 * 0.12  # 600

		expected_total = expected_subtotal + expected_vat

		self.assertAlmostEqual(billing.subtotal, expected_subtotal, places=2)
		self.assertAlmostEqual(billing.vat_amount, expected_vat, places=2)
		self.assertAlmostEqual(billing.total_amount, expected_total, places=2)

	def test_status_workflow(self):
		"""Test billing status workflow."""
		billing = frappe.get_doc({
			"doctype": "BEI Billing Schedule",
			"billing_period": "2026-02",
			"store": "BGC",
			"store_type": "Managed Franchise",
			"gross_sales": 500000.00,
			"net_sales": 450000.00
		})
		billing.insert()

		# Default status should be Draft
		self.assertEqual(billing.status, "Draft")

		# Test send_to_store method
		billing.send_to_store()
		self.assertEqual(billing.status, "Sent")
		self.assertIsNotNone(billing.sent_on)

	def test_auto_fetch_store_type(self):
		"""Test that store type is auto-fetched from BEI Store Type master."""
		billing = frappe.get_doc({
			"doctype": "BEI Billing Schedule",
			"billing_period": "2026-02",
			"store": "BGC",
			# store_type is intentionally left blank
			"gross_sales": 500000.00,
			"net_sales": 450000.00
		})
		billing.insert()

		# store_type should be auto-fetched from BEI Store Type master
		self.assertEqual(billing.store_type, "Managed Franchise")
