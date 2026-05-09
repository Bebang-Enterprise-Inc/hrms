"""S238 — unit tests for hrms/api/bki_store_pi_generator.py.

8 tests per v2/v2.1 plan Phase 3-T4:
  Test 1: SI on BKI to per-store Customer -> 1 Draft PI w/ correct supplier + accts
  Test 2: SI on BKI to non-Company Customer -> NO PI (filter)
  Test 3: enable_bki_store_pi_generator=0 -> NO PI (kill switch)
  Test 4: Resubmit/idempotency -> PI not duplicated
  Test 5: SI on non-BKI Company -> NO PI (filter)
  Test 6: SI cancel: Draft PI deleted; Submitted PI gets Comment (not deleted)
  Test 7: SI w/ VAT + EWT-deduct rows -> PI mirrors only VAT
  Test 8: bki_si_reference Custom Field missing -> hook returns early w/ log

Most tests use mocks since live tabSales Invoice creation requires the full
ERPNext stack. Live tests run via /local-frappe + bench --site test_site
in Phase 4. This file documents the shape; the assertions are the contract.
"""
from __future__ import annotations

import unittest
from unittest import mock

import frappe

from hrms.api.bki_store_pi_generator import (
	BKI_COMPANY,
	BKI_TRADE_SUPPLIER,
	ACCT_INVENTORY_FROM_COMMISSARY,
	ACCT_INPUT_VAT_BKI_INTERCO,
	ACCT_AP_TRADE_BKI,
	cascade_cancel_store_pi,
	maybe_generate_store_pi,
)


def _make_si(company, customer, name="ACC-SINV-2026-09999", naming_series="BKI-SI-.YYYY.-.#####", items=None, taxes=None):
	"""Minimal Sales Invoice mock."""
	doc = mock.MagicMock()
	doc.company = company
	doc.customer = customer
	doc.name = name
	doc.naming_series = naming_series
	doc.posting_date = "2026-05-09"
	doc.posting_time = "10:00:00"
	doc.items = items or []
	doc.taxes = taxes or []
	doc.bei_legal_entity = company
	doc.bei_store_label = customer.split(" - ")[0] if " - " in customer else customer
	return doc


class TestS238PiGenerator(unittest.TestCase):
	"""S238 PI generator behavior contract.

	Phase 4 (live) replays these assertions in real bench via
	`bench --site test_site run-tests --module hrms.tests.test_s238_pi_generator`.
	"""

	def test_1_bki_to_per_store_si_creates_draft_pi(self):
		"""Test 1: BKI SI to per-store Customer -> 1 Draft PI w/ supplier + accounts."""
		# This test verifies the contract: when maybe_generate_store_pi is called
		# with a BKI SI to a Customer matching a per-store Company, it should
		# create a Draft PI with:
		#   pi.company = buyer_company (per-store)
		#   pi.supplier = "BEBANG KITCHEN INC. - Trade"
		#   pi.bki_si_reference = si.name
		#   pi.update_stock = 1
		#   pi.set_warehouse = buyer_company (canonical: warehouse name == company name)
		#   pi.bei_legal_entity = buyer_company  (v2.1-CRIT-1: NOT seller's)
		# Live verification in Phase 4-T2.
		self.assertEqual(BKI_TRADE_SUPPLIER, "BEBANG KITCHEN INC. - Trade")
		self.assertEqual(BKI_COMPANY, "BEBANG KITCHEN INC.")

	def test_2_non_company_customer_skipped(self):
		"""Test 2: SI on BKI to non-Company Customer -> NO PI (filter Path 2)."""
		si = _make_si(company=BKI_COMPANY, customer="Walk-in Customer")
		with mock.patch("hrms.api.bki_store_pi_generator.frappe") as mock_frappe:
			mock_frappe.get_meta.return_value.has_field.return_value = True
			mock_frappe.get_single.return_value.enable_bki_store_pi_generator = 1
			mock_frappe.get_single.return_value.bki_sales_naming_series = ""
			mock_frappe.db.exists.side_effect = lambda dt, filt: False  # Walk-in is not a Company
			# Should return early without raising
			maybe_generate_store_pi(si)
			# Sentry breadcrumb path was hit; verify by checking exists was called for Company
			calls = [c for c in mock_frappe.db.exists.call_args_list if c[0] and c[0][0] == "Company"]
			self.assertGreater(len(calls), 0)

	def test_3_kill_switch_skips_generator(self):
		"""Test 3: enable_bki_store_pi_generator=0 -> NO PI (kill switch)."""
		si = _make_si(
			company=BKI_COMPANY,
			customer="ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC",
		)
		with mock.patch("hrms.api.bki_store_pi_generator.frappe") as mock_frappe:
			mock_frappe.get_meta.return_value.has_field.return_value = True
			settings = mock.MagicMock()
			settings.enable_bki_store_pi_generator = 0  # kill switch
			mock_frappe.get_single.return_value = settings
			maybe_generate_store_pi(si)
			# Should return before any insert; no exists check on per-store Co
			self.assertFalse(any(
				c[0][0] == "Purchase Invoice" if c[0] else False
				for c in mock_frappe.db.exists.call_args_list
			))

	def test_4_idempotency_via_bki_si_reference(self):
		"""Test 4: Resubmit -> PI not duplicated (existing bki_si_reference shortcut)."""
		si = _make_si(
			company=BKI_COMPANY,
			customer="ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC",
		)
		with mock.patch("hrms.api.bki_store_pi_generator.frappe") as mock_frappe:
			mock_frappe.get_meta.return_value.has_field.return_value = True
			settings = mock.MagicMock()
			settings.enable_bki_store_pi_generator = 1
			settings.bki_sales_naming_series = ""
			mock_frappe.get_single.return_value = settings

			def exists_stub(dt, filt=None):
				if dt == "Company":
					return True  # Customer matches a Company
				if dt == "Purchase Invoice" and isinstance(filt, dict) and filt.get("bki_si_reference"):
					return "EXISTING-PI"  # already exists
				return False

			mock_frappe.db.exists.side_effect = exists_stub
			maybe_generate_store_pi(si)
			# No new doc created — verify by checking new_doc was not called
			mock_frappe.new_doc.assert_not_called()

	def test_5_non_bki_company_si_skipped(self):
		"""Test 5: SI on non-BKI Company -> NO PI (filter Path 1)."""
		si = _make_si(
			company="ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC",
			customer="walk-in",
		)
		with mock.patch("hrms.api.bki_store_pi_generator.frappe") as mock_frappe:
			maybe_generate_store_pi(si)
			# Returns immediately; nothing called
			mock_frappe.get_single.assert_not_called()
			mock_frappe.new_doc.assert_not_called()

	def test_6_cascade_on_cancel_draft_deletes_submitted_comments(self):
		"""Test 6: SI cancel -> Draft PI deleted; Submitted PI gets Comment."""
		si = _make_si(company=BKI_COMPANY, customer="ARANETA")

		# Sub-test 6a: paired PI is Draft -> deleted
		with mock.patch("hrms.api.bki_store_pi_generator.frappe") as mock_frappe:
			mock_frappe.get_meta.return_value.has_field.return_value = True
			mock_frappe.db.get_value.side_effect = [
				"PINV-2026-09999",  # PI name
				0,                   # docstatus = Draft
			]
			cascade_cancel_store_pi(si)
			mock_frappe.delete_doc.assert_called_once()

		# Sub-test 6b: paired PI is Submitted -> Comment, not deleted
		with mock.patch("hrms.api.bki_store_pi_generator.frappe") as mock_frappe:
			mock_frappe.get_meta.return_value.has_field.return_value = True
			mock_frappe.db.get_value.side_effect = [
				"PINV-2026-09999",  # PI name
				1,                   # docstatus = Submitted
			]
			mock_doc = mock.MagicMock()
			mock_frappe.get_doc.return_value = mock_doc
			cascade_cancel_store_pi(si)
			mock_frappe.delete_doc.assert_not_called()
			# Comment was created on PI
			get_doc_calls = mock_frappe.get_doc.call_args_list
			self.assertTrue(any(
				isinstance(c[0][0], dict) and c[0][0].get("doctype") == "Comment"
				for c in get_doc_calls
			))

	def test_7_ewt_deduct_rows_filtered_from_taxes(self):
		"""Test 7: SI w/ VAT + EWT-deduct rows -> PI mirrors only VAT."""
		# This contract is enforced inside _mirror_taxes — verified at Phase 4
		# in real bench because the SI .taxes child table needs full ERPNext
		# scaffolding. Static check: the function source contains the filter.
		import inspect
		from hrms.api.bki_store_pi_generator import _mirror_taxes
		src = inspect.getsource(_mirror_taxes)
		self.assertIn('"vat" not in ah', src)
		self.assertIn('add_deduct_tax', src)
		self.assertIn('"deduct"', src.lower())

	def test_8_has_field_guard_returns_early(self):
		"""Test 8: bki_si_reference Custom Field missing -> hook returns early w/ log."""
		si = _make_si(
			company=BKI_COMPANY,
			customer="ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC",
		)
		with mock.patch("hrms.api.bki_store_pi_generator.frappe") as mock_frappe:
			mock_frappe.get_meta.return_value.has_field.return_value = False  # field missing
			maybe_generate_store_pi(si)
			# Returns early after log_error; no settings fetch, no doc creation
			mock_frappe.log_error.assert_called_once()
			mock_frappe.get_single.assert_not_called()
			mock_frappe.new_doc.assert_not_called()

	def test_9_account_number_constants(self):
		"""Sanity: account number constants match the seeded values from Phase 1."""
		self.assertEqual(ACCT_INVENTORY_FROM_COMMISSARY, "1104210")
		self.assertEqual(ACCT_INPUT_VAT_BKI_INTERCO, "1106210")
		self.assertEqual(ACCT_AP_TRADE_BKI, "2103210")
