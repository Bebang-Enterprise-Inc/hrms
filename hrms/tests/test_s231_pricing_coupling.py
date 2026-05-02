"""S231 D-3 + D-4 unit tests — pricing coupling (rate sourcing, recipient
routing, BFC precondition, e-com base, Vista Mall carveout).

Covers TM-6 items that don't require post-sweep production state. The 14th
test (`test_post_sweep_44_companies_have_valid_defaults`) lives in a
separate file because it needs production after Phase B has run.

Run via:
    bench --site hq.bebang.ph run-tests --module hrms.tests.test_s231_pricing_coupling --verbose

Plan: docs/plans/2026-05-02-sprint-231-pricing-coupling-and-defaults-defense.md
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import frappe

from hrms.api.billing import (
	_assert_bfc_billing_ready,
	_resolve_fee_recipient_company,
)
from hrms.hr.doctype.bei_billing_schedule.bei_billing_schedule import VAT_RATE


class _FakeBilling:
	"""Stand-in for a BEI Billing Schedule doc usable by calculate_fees.

	Implements just the surface calculate_fees touches: get / set /
	billing_type / store_type / sales fields. No DB I/O.
	"""

	def __init__(
		self,
		store_type: str,
		gross_sales: float = 0,
		net_sales: float = 0,
		website_sales: float = 0,
		online_sales: float = 0,
		store: str = "TEST-STORE",
		billing_type: str = "Monthly Fees",
	) -> None:
		self.billing_type = billing_type
		self.store_type = store_type
		self.gross_sales = gross_sales
		self.net_sales = net_sales
		self.website_sales = website_sales
		self.online_sales = online_sales
		self.store = store
		self.royalty_fee = 0.0
		self.marketing_fee = 0.0
		self.management_fee = 0.0
		self.ecommerce_fee = 0.0
		self.delivery_fee = 0.0
		self.logistics_fee = 0.0
		self.goods_value = 0.0
		self.handling_fee = 0.0

	def get(self, key, default=None):
		return getattr(self, key, default)

	def set(self, key, value):
		setattr(self, key, value)


def _run_calculate_fees(
	billing: _FakeBilling,
	schedule_rows: list[dict],
	carveouts: dict[tuple[str, str], float] | None = None,
) -> _FakeBilling:
	"""Drive BEIBillingSchedule.calculate_fees against a fake billing doc.

	`schedule_rows` is the list `frappe.get_all('BEI Fee Schedule', ...)` would
	return. `carveouts` maps (store, fee_type) → override rate.
	"""
	from hrms.hr.doctype.bei_billing_schedule.bei_billing_schedule import BEIBillingSchedule

	carveouts = carveouts or {}

	def _carveout_lookup(doctype, filters, field):
		if doctype != "BEI Fee Carveout" or field != "rate_override":
			return None
		key = (filters.get("store"), filters.get("fee_type"))
		return carveouts.get(key)

	with (
		patch("frappe.get_all", return_value=schedule_rows) as mock_get_all,
		patch("frappe.db.get_value", side_effect=_carveout_lookup),
	):
		BEIBillingSchedule.calculate_fees(billing)
		mock_get_all.assert_called()
	return billing


# ============================================================================
# Mystery 0.04 + e-com base regression tests
# ============================================================================


class TestS231Mystery004(unittest.TestCase):
	"""Confirms the fix for the 0.04 vs 0.05 e-commerce rate inconsistency."""

	def test_ecom_fee_uses_website_sales_only(self):
		"""TM-6 #13: e-commerce rate applies to website_sales, NOT online_sales
		(which includes FoodPanda + Grab) per CEO 2026-05-02.
		"""
		schedules = [
			{"fee_type": "E-commerce", "rate": 0.05, "base_field": "website_sales"},
		]
		# Set online_sales much higher than website_sales to detect mis-rooting.
		billing = _FakeBilling(
			store_type="JV", website_sales=10_000.00, online_sales=999_999.00
		)
		_run_calculate_fees(billing, schedules)
		# 5% of 10,000 = 500. If online_sales were used, fee would be ~50,000.
		self.assertAlmostEqual(billing.ecommerce_fee, 500.00, places=2)

	def test_mystery_004_replaced_by_seed_005(self):
		"""TM-6 #6 (variant): JV E-com fee is 5% per BEI Fee Schedule seed,
		not the legacy hardcoded 4% (`mystery_004_investigation.md`).
		"""
		schedules = [
			{"fee_type": "E-commerce", "rate": 0.05, "base_field": "website_sales"},
		]
		billing = _FakeBilling(store_type="JV", website_sales=100_000.00)
		_run_calculate_fees(billing, schedules)
		# 5% of 100,000 = 5,000 (vs broken 4,000 under the old constant).
		self.assertAlmostEqual(billing.ecommerce_fee, 5_000.00, places=2)


# ============================================================================
# Per-ownership-type fee math tests
# ============================================================================


class TestS231MonthlyFeeMath(unittest.TestCase):

	def test_monthly_billing_jv_marketing_5pct(self):
		"""TM-6 #6: JV gets Marketing 5% gross + E-com 5% website. No royalty,
		no management.
		"""
		schedules = [
			{"fee_type": "Marketing", "rate": 0.05, "base_field": "gross_sales"},
			{"fee_type": "E-commerce", "rate": 0.05, "base_field": "website_sales"},
		]
		billing = _FakeBilling(
			store_type="JV", gross_sales=2_000_000.00, website_sales=100_000.00
		)
		_run_calculate_fees(billing, schedules)
		self.assertAlmostEqual(billing.marketing_fee, 100_000.00, places=2)
		self.assertAlmostEqual(billing.ecommerce_fee, 5_000.00, places=2)
		self.assertEqual(billing.royalty_fee, 0)
		self.assertEqual(billing.management_fee, 0)

	def test_monthly_billing_mf_full_fee_set(self):
		"""TM-6 #7: Managed Franchise gets full quartet (Royalty + Marketing
		+ Management + E-com).
		"""
		schedules = [
			{"fee_type": "Royalty", "rate": 0.07, "base_field": "net_sales_ex_vat"},
			{"fee_type": "Marketing", "rate": 0.05, "base_field": "net_sales_ex_vat"},
			{"fee_type": "Management", "rate": 0.025, "base_field": "gross_sales"},
			{"fee_type": "E-commerce", "rate": 0.05, "base_field": "website_sales"},
		]
		# Pick gross 1,571,252.40 + the matching net (incl. VAT) per plan S5.
		gross = 1_571_252.40
		net = gross  # plan S5 input — net sales = gross sales for the test row
		website = 49_310.00
		billing = _FakeBilling(
			store_type="Managed Franchise",
			gross_sales=gross,
			net_sales=net,
			website_sales=website,
		)
		_run_calculate_fees(billing, schedules)
		# Royalty: 7% × (net / 1.12) = 0.07 * 1,402,903.93 ≈ 98,203.27
		expected_royalty = round((net / (1 + VAT_RATE)) * 0.07, 2)
		self.assertAlmostEqual(billing.royalty_fee, expected_royalty, places=2)
		expected_marketing = round((net / (1 + VAT_RATE)) * 0.05, 2)
		self.assertAlmostEqual(billing.marketing_fee, expected_marketing, places=2)
		expected_mgmt = round(gross * 0.025, 2)
		self.assertAlmostEqual(billing.management_fee, expected_mgmt, places=2)
		expected_ecom = round(website * 0.05, 2)
		self.assertAlmostEqual(billing.ecommerce_fee, expected_ecom, places=2)

	def test_monthly_billing_ff_no_management_fee(self):
		"""TM-6 #8: Full Franchise gets Royalty + Marketing + E-com but NO
		Management Fee (FF stores manage themselves).
		"""
		schedules = [
			{"fee_type": "Royalty", "rate": 0.07, "base_field": "net_sales_ex_vat"},
			{"fee_type": "Marketing", "rate": 0.05, "base_field": "net_sales_ex_vat"},
			{"fee_type": "E-commerce", "rate": 0.05, "base_field": "website_sales"},
		]
		billing = _FakeBilling(
			store_type="Full Franchise",
			gross_sales=1_000_000,
			net_sales=1_000_000,
			website_sales=50_000,
		)
		_run_calculate_fees(billing, schedules)
		self.assertGreater(billing.royalty_fee, 0)
		self.assertGreater(billing.marketing_fee, 0)
		self.assertGreater(billing.ecommerce_fee, 0)
		self.assertEqual(billing.management_fee, 0)

	def test_monthly_billing_co_owned_skipped(self):
		"""TM-6 #9: Company Owned stores get NO franchise fees — markup is
		applied via BKI intercompany SI instead.
		"""
		# Even if the (impossible) seeder somehow returned schedules for
		# Co-Owned, calculate_fees must early-return BEFORE consulting them.
		schedules = [
			{"fee_type": "Royalty", "rate": 0.07, "base_field": "net_sales_ex_vat"},
		]
		billing = _FakeBilling(
			store_type="Company Owned", gross_sales=500_000, net_sales=500_000
		)
		_run_calculate_fees(billing, schedules)
		self.assertEqual(billing.royalty_fee, 0)
		self.assertEqual(billing.marketing_fee, 0)
		self.assertEqual(billing.management_fee, 0)
		self.assertEqual(billing.ecommerce_fee, 0)


# ============================================================================
# Carveout test
# ============================================================================


class TestS231Carveouts(unittest.TestCase):

	def test_vista_mall_carveout_2pct_management(self):
		"""TM-6 #14: Vista Mall Management Fee = 2.0% (carveout) overrides
		the standard MF 2.5% rate per CEO 2026-05-02.
		"""
		schedules = [
			{"fee_type": "Management", "rate": 0.025, "base_field": "gross_sales"},
		]
		# Carveout for Vista Mall reduces Management to 2.0%.
		carveouts = {("Vista Mall", "Management"): 0.02}
		gross = 1_000_000.00
		billing = _FakeBilling(
			store_type="Managed Franchise", gross_sales=gross, store="Vista Mall"
		)
		_run_calculate_fees(billing, schedules, carveouts=carveouts)
		# 2% of 1,000,000 = 20,000 (not 25,000 from the schedule rate)
		self.assertAlmostEqual(billing.management_fee, 20_000.00, places=2)

	def test_no_carveout_uses_schedule_rate(self):
		"""Defensive: when no carveout exists for (store, fee_type), the
		schedule rate must apply unchanged.
		"""
		schedules = [
			{"fee_type": "Management", "rate": 0.025, "base_field": "gross_sales"},
		]
		gross = 1_000_000.00
		# OTHER store has no carveout
		billing = _FakeBilling(
			store_type="Managed Franchise", gross_sales=gross, store="OTHER STORE"
		)
		_run_calculate_fees(billing, schedules, carveouts={})
		self.assertAlmostEqual(billing.management_fee, 25_000.00, places=2)


# ============================================================================
# Recipient routing tests (D-4)
# ============================================================================


class TestS231RecipientRouting(unittest.TestCase):

	def test_recipient_routing_jv_to_bei(self):
		"""TM-6 #11: JV fees route to BEI revenue (NOT BFC). Per CEO
		2026-05-02 + Collection Agent Letter §"What this letter does NOT
		cover" item 4.
		"""

		def _settings(_dt, field):
			return {
				"jv_revenue_company": "Bebang Enterprise Inc.",
				"bfc_revenue_company": "BEBANG FRANCHISE CORP.",
			}.get(field)

		with patch("frappe.db.get_single_value", side_effect=_settings):
			recipient = _resolve_fee_recipient_company("JV")
		self.assertEqual(recipient, "Bebang Enterprise Inc.")

	def test_recipient_routing_mf_to_bfc(self):
		"""TM-6 #12: MF + FF fees route to BFC revenue (collected by BEI as
		agent during interim per Collection Agent Letter §1-3).
		"""

		def _settings(_dt, field):
			return {
				"jv_revenue_company": "Bebang Enterprise Inc.",
				"bfc_revenue_company": "BEBANG FRANCHISE CORP.",
			}.get(field)

		with patch("frappe.db.get_single_value", side_effect=_settings):
			self.assertEqual(
				_resolve_fee_recipient_company("Managed Franchise"),
				"BEBANG FRANCHISE CORP.",
			)
			self.assertEqual(
				_resolve_fee_recipient_company("Full Franchise"),
				"BEBANG FRANCHISE CORP.",
			)

	def test_recipient_routing_company_owned_returns_none(self):
		"""Co-Owned has no franchise fees → recipient is None and the SI
		path is skipped entirely (no exception).
		"""
		# Should not call get_single_value at all
		with patch("frappe.db.get_single_value") as mock_settings:
			recipient = _resolve_fee_recipient_company("Company Owned")
		self.assertIsNone(recipient)
		mock_settings.assert_not_called()

	def test_recipient_routing_unknown_type_raises(self):
		"""Defensive: unknown ownership_type raises ValueError so a typo
		can't silently send fees to the wrong company.
		"""
		with self.assertRaises(ValueError):
			_resolve_fee_recipient_company("InvalidType")


# ============================================================================
# BFC precondition test
# ============================================================================


class TestS231BfcBillingReady(unittest.TestCase):

	def test_bfc_billing_ready_passes_when_all_set(self):
		"""All three preconditions met → no exception."""

		def _settings(_dt, field):
			return {
				"bfc_or_active": 1,
				"bfc_vat_registration_active": 1,
				"bfc_sales_naming_series": "BFC-SI-.YYYY.-.####",
			}.get(field, 0)

		with patch("frappe.db.get_single_value", side_effect=_settings):
			# Should not raise
			_assert_bfc_billing_ready()

	def test_bfc_billing_ready_throws_when_or_inactive(self):
		"""bfc_or_active=0 → throws."""

		def _settings(_dt, field):
			return {
				"bfc_or_active": 0,
				"bfc_vat_registration_active": 1,
				"bfc_sales_naming_series": "BFC-SI-.YYYY.-.####",
			}.get(field, 0)

		with patch("frappe.db.get_single_value", side_effect=_settings):
			with self.assertRaises(Exception) as ctx:
				_assert_bfc_billing_ready()
			self.assertIn("OR booklet", str(ctx.exception))

	def test_bfc_billing_ready_throws_when_vat_inactive(self):
		"""bfc_vat_registration_active=0 → throws."""

		def _settings(_dt, field):
			return {
				"bfc_or_active": 1,
				"bfc_vat_registration_active": 0,
				"bfc_sales_naming_series": "BFC-SI-.YYYY.-.####",
			}.get(field, 0)

		with patch("frappe.db.get_single_value", side_effect=_settings):
			with self.assertRaises(Exception) as ctx:
				_assert_bfc_billing_ready()
			self.assertIn("VAT registration", str(ctx.exception))

	def test_bfc_billing_ready_throws_when_naming_series_missing(self):
		"""bfc_sales_naming_series unset → throws."""

		def _settings(_dt, field):
			return {
				"bfc_or_active": 1,
				"bfc_vat_registration_active": 1,
				"bfc_sales_naming_series": None,
			}.get(field, 0)

		with patch("frappe.db.get_single_value", side_effect=_settings):
			with self.assertRaises(Exception) as ctx:
				_assert_bfc_billing_ready()
			self.assertIn("naming series", str(ctx.exception))


# ============================================================================
# Idempotency / regeneration test (smoke)
# ============================================================================


class TestS231Idempotency(unittest.TestCase):

	def test_monthly_billing_idempotent_per_period(self):
		"""TM-6 #10: re-running calculate_fees on the same input produces
		the SAME fee amounts (no carry-over, no drift).
		"""
		schedules = [
			{"fee_type": "Marketing", "rate": 0.05, "base_field": "gross_sales"},
			{"fee_type": "E-commerce", "rate": 0.05, "base_field": "website_sales"},
		]
		billing = _FakeBilling(
			store_type="JV", gross_sales=2_000_000, website_sales=100_000
		)

		_run_calculate_fees(billing, schedules)
		first_marketing = billing.marketing_fee
		first_ecom = billing.ecommerce_fee

		# Pollute with stale Royalty (simulates an ownership flip MF→JV)
		billing.royalty_fee = 999_999.99

		_run_calculate_fees(billing, schedules)
		self.assertAlmostEqual(billing.marketing_fee, first_marketing, places=2)
		self.assertAlmostEqual(billing.ecommerce_fee, first_ecom, places=2)
		# Stale Royalty must be zeroed by the up-front zeroing block.
		self.assertEqual(billing.royalty_fee, 0)
