"""Sprint 12 tests for discount abuse monitoring backend helpers."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_frappe() -> None:
	if "frappe" not in sys.modules:
		frappe = types.ModuleType("frappe")

		def _module_getattr(name):
			if name in {"session", "conf", "db"} and hasattr(frappe.local, name):
				return getattr(frappe.local, name)
			raise AttributeError(name)

		def whitelist(*args, **kwargs):
			if args and callable(args[0]) and len(args) == 1 and not kwargs:
				return args[0]

			def decorator(fn):
				return fn

			return decorator

		def _throw(message, exc=None):
			if isinstance(exc, type) and issubclass(exc, Exception):
				raise exc(message)
			raise Exception(message)

		frappe.whitelist = whitelist
		frappe._ = lambda text: text
		frappe.throw = _throw
		frappe.log_error = lambda *args, **kwargs: None
		frappe.logger = lambda *args, **kwargs: types.SimpleNamespace(
			info=lambda *a, **k: None,
			warning=lambda *a, **k: None,
			error=lambda *a, **k: None,
		)
		frappe.get_roles = lambda: ["HQ User"]
		frappe.local = types.SimpleNamespace()
		frappe.local.session = types.SimpleNamespace(user="test.audit@bebang.ph")
		frappe.local.conf = {}
		frappe.local.db = types.SimpleNamespace(
			get_single_value=lambda *args, **kwargs: None,
			commit=lambda: None,
		)
		frappe.__getattr__ = _module_getattr
		frappe.get_all = lambda *args, **kwargs: []
		frappe.get_doc = lambda *args, **kwargs: None
		sys.modules["frappe"] = frappe

	if "frappe.utils" not in sys.modules:
		utils = types.ModuleType("frappe.utils")
		utils.now_datetime = lambda: "2026-03-07 12:00:00"
		utils.today = lambda: "2026-03-07"
		sys.modules["frappe.utils"] = utils

	if "hrms" not in sys.modules:
		pkg = types.ModuleType("hrms")
		pkg.__path__ = []
		sys.modules["hrms"] = pkg

	if "hrms.api" not in sys.modules:
		pkg = types.ModuleType("hrms.api")
		pkg.__path__ = []
		sys.modules["hrms.api"] = pkg


def _load_module(module_name: str, relative_path: str):
	spec = importlib.util.spec_from_file_location(module_name, ROOT / relative_path)
	module = importlib.util.module_from_spec(spec)
	sys.modules[module_name] = module
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


_install_fake_frappe()
discount_abuse = _load_module("hrms.api.discount_abuse", "hrms/api/discount_abuse.py")


class TestDiscountAbuseApiS12(unittest.TestCase):
	def test_notifications_use_default_go_live_date_when_config_missing(self):
		with patch.dict(discount_abuse.os.environ, {}, clear=True):
			self.assertEqual(
				discount_abuse._get_notification_go_live_date(),
				date(2026, 3, 10),
			)

	def test_notifications_do_not_fire_before_go_live_date(self):
		with patch.object(discount_abuse, "_get_notification_go_live_date", return_value=date(2026, 3, 10)):
			self.assertFalse(discount_abuse._notifications_enabled_for_day(date(2026, 3, 9)))
			self.assertTrue(discount_abuse._notifications_enabled_for_day(date(2026, 3, 10)))

	def test_build_critical_notification_message_summarizes_rows(self):
		rows = [
			{
				"store_name": "SM North EDSA",
				"detection_type": "same_reference_diff_name_same_day_same_store",
				"identity_key": "25402",
				"order_count": 2,
				"discount_amount_total": "70.72",
			},
			{
				"store_name": "SM Megamall",
				"detection_type": "same_reference_same_day_multi_store",
				"identity_key": "153",
				"order_count": 2,
				"discount_amount_total": "65.36",
			},
		]

		message = discount_abuse._build_critical_notification_message(date(2026, 3, 6), rows)

		self.assertIn("March 06, 2026", message)
		self.assertIn("SM North EDSA", message)
		self.assertIn("SM Megamall", message)
		self.assertIn("2 critical clusters", message)

	def test_build_workbook_contains_expected_tabs(self):
		workbook_bytes = discount_abuse._build_audit_workbook_bytes(
			business_date=date(2026, 3, 6),
			same_day_rows=[
				{
					"severity": "critical",
					"store_name": "SM North EDSA",
					"detection_type": "same_reference_diff_name_same_day_same_store",
					"identity_key": "25402",
					"order_count": 2,
					"discount_amount_total": "70.72",
				}
			],
			rolling_rows=[
				{
					"severity": "high",
					"store_name": "SM Megamall",
					"detection_type": "rolling_30d_name_diff_reference_threshold_same_store",
					"identity_key": "JUDIVINA LAYAG",
					"order_count": 8,
					"distinct_counterparty_count": 3,
				}
			],
			summary={
				"same_day_critical": 1,
				"same_day_high": 0,
				"same_day_medium": 0,
				"rolling_high": 1,
				"rolling_review": 0,
			},
		)

		import io

		import openpyxl

		wb = openpyxl.load_workbook(io.BytesIO(workbook_bytes))
		self.assertEqual(
			wb.sheetnames,
			["Overview", "SameDay_All", "SameDay_Critical", "Rolling30D_All", "Rolling30D_High"],
		)

	def test_query_discount_item_rows_for_orders_uses_order_chunks_without_join(self):
		paid_order_rows = [
			{
				"id": 1001,
				"location_id": 12,
				"store_name": "SM North EDSA",
				"business_date": "2026-02-13",
				"bill_number": "61540",
				"receipt_number": "61540",
				"billed_at": "2026-02-13T11:44:10+08:00",
				"paid_at": "2026-02-13T11:44:20+08:00",
				"original_gross_sales": 1000,
				"gross_sales": 900,
				"net_sales": 800,
				"total_discounts": 70.72,
			}
		]
		item_rows = [
			{
				"order_id": 1001,
				"line_number": 1,
				"product_name": "Combo",
				"quantity": 1,
				"discount_amount": 70.72,
				"discount_name": "Senior Citizen Discount",
				"discount_name_normalized": "SENIOR CITIZEN DISCOUNT",
				"discount_bir_category": "SC",
				"discount_customer_full_name": "Helen Paglingayen",
				"discount_customer_full_name_normalized": "HELEN PAGLINGAYEN",
				"discount_reference_number": "25402",
				"discount_reference_number_normalized": "25402",
			}
		]

		with patch.object(discount_abuse, "_supabase_get_all", return_value=item_rows) as mock_get:
			rows = discount_abuse._query_discount_item_rows_for_orders(paid_order_rows, {"SC"})

		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["store_name"], "SM North EDSA")
		self.assertEqual(rows[0]["bill_number"], "61540")
		self.assertEqual(rows[0]["discount_reference_number_normalized"], "25402")
		call_resource, call_params = mock_get.call_args.args
		self.assertEqual(call_resource, "pos_order_items")
		self.assertIn(("order_id", "in.(1001)"), call_params)
		self.assertIn(("discount_bir_category", "in.(SC)"), call_params)
		self.assertFalse(any(key.startswith("pos_orders.") for key, _ in call_params))

	def test_build_investigation_summary_payload_aggregates_store_metrics(self):
		same_day_rows = [
			{
				"scope": "store",
				"store_name": "SM North EDSA",
				"severity": "critical",
				"detection_type": "same_name_same_day_same_store",
				"rapid_within_4h": True,
			},
			{
				"scope": "store",
				"store_name": "SM North EDSA",
				"severity": "critical",
				"detection_type": "same_reference_diff_name_same_day_same_store",
				"rapid_within_4h": False,
			},
			{
				"scope": "chain",
				"store_name": "SM North EDSA | SM Megamall",
				"severity": "high",
				"detection_type": "same_reference_same_day_multi_store",
				"rapid_within_4h": True,
			},
		]
		item_rows = [
			{
				"location_id": 1,
				"store_name": "SM North EDSA",
				"business_date": "2026-02-13",
				"order_id": 1001,
				"bill_number": "61540",
				"discount_amount": 20.25,
				"discount_bir_category": "SC",
				"discount_customer_full_name_normalized": "HELEN PAGLINGAYEN",
				"discount_reference_number_normalized": "25402",
			},
			{
				"location_id": 1,
				"store_name": "SM North EDSA",
				"business_date": "2026-02-13",
				"order_id": 1001,
				"bill_number": "61540",
				"discount_amount": 25.10,
				"discount_bir_category": "SC",
				"discount_customer_full_name_normalized": "PETRONA REYES",
				"discount_reference_number_normalized": "25402",
			},
			{
				"location_id": 1,
				"store_name": "SM North EDSA",
				"business_date": "2026-02-13",
				"order_id": 1001,
				"bill_number": "61540",
				"discount_amount": 25.37,
				"discount_bir_category": "SC",
				"discount_customer_full_name_normalized": "MARIA VIDAR",
				"discount_reference_number_normalized": "3594",
			},
		]
		paid_order_rows = [
			{
				"id": 1001,
				"location_id": 1,
				"store_name": "SM North EDSA",
				"business_date": "2026-02-13",
				"original_gross_sales": 1000,
				"gross_sales": 900,
				"net_sales": 800,
				"total_discounts": 70.72,
			}
		]

		payload = discount_abuse._build_investigation_summary_payload(
			date(2026, 2, 1),
			date(2026, 2, 28),
			["SM North EDSA"],
			{"SC"},
			same_day_rows,
			item_rows,
			paid_order_rows,
		)

		self.assertEqual(payload["totals"]["same_day_repeat_name_findings"], 1)
		self.assertEqual(payload["totals"]["same_day_same_reference_different_name_findings"], 1)
		self.assertEqual(payload["totals"]["same_day_rapid_repeat_name_findings_4h"], 1)
		self.assertEqual(payload["totals"]["contextual_multi_name_receipts"], 1)
		self.assertEqual(payload["stores"][0]["same_day_metrics"]["repeat_name_findings"], 1)
		self.assertEqual(
			payload["stores"][0]["same_day_metrics"]["same_reference_different_name_findings"],
			1,
		)
		self.assertEqual(payload["stores"][0]["chain_metrics"]["same_day_chain_rows"], 1)
		self.assertEqual(payload["stores"][0]["contextual_metrics"]["multi_name_receipts"], 1)
		self.assertEqual(payload["stores"][0]["rates_per_1000_paid_orders"]["repeat_name_findings"], 1000.0)
		self.assertEqual(
			payload["totals"]["rates_per_1000_paid_orders"]["same_day_repeat_name_findings"],
			1000.0,
		)

	def test_build_investigation_case_rows_includes_alert_and_context_receipt_cases(self):
		same_day_rows = [
			{
				"event_date": "2026-02-13",
				"scope": "store",
				"scope_key": 12,
				"store_name": "SM North EDSA",
				"severity": "critical",
				"detection_type": "same_reference_diff_name_same_day_same_store",
				"identity_key": "25402",
				"customer_names": "HELEN PAGLINGAYEN | PETRONA REYES",
				"reference_numbers": "25402",
				"bill_numbers": "61540 | 61613",
				"business_dates": "2026-02-13",
				"order_count": 2,
				"store_count": 1,
				"discount_amount_total": "70.72",
				"rapid_within_4h": True,
				"min_gap_minutes": 25,
				"details": {},
			}
		]
		item_rows = [
			{
				"location_id": 1,
				"store_name": "SM North EDSA",
				"business_date": "2026-02-20",
				"order_id": 2001,
				"bill_number": "63255",
				"discount_amount": 15,
				"discount_customer_full_name_normalized": "GLORIA FRANCISCO",
				"discount_reference_number_normalized": "1625",
			},
			{
				"location_id": 1,
				"store_name": "SM North EDSA",
				"business_date": "2026-02-20",
				"order_id": 2001,
				"bill_number": "63255",
				"discount_amount": 15,
				"discount_customer_full_name_normalized": "EMILIA VICENTE",
				"discount_reference_number_normalized": "6277",
			},
			{
				"location_id": 1,
				"store_name": "SM North EDSA",
				"business_date": "2026-02-20",
				"order_id": 2001,
				"bill_number": "63255",
				"discount_amount": 15,
				"discount_customer_full_name_normalized": "ROLLIE PIOQUID",
				"discount_reference_number_normalized": "3594",
			},
		]

		rows = discount_abuse._build_investigation_case_rows(
			["SM North EDSA"],
			same_day_rows,
			item_rows,
		)

		self.assertEqual(len(rows), 2)
		self.assertEqual(rows[0]["case_bucket"], "same_day_alert")
		self.assertEqual(rows[0]["names"], ["HELEN PAGLINGAYEN", "PETRONA REYES"])
		self.assertEqual(
			rows[0]["detection_types"],
			["same_reference_diff_name_same_day_same_store"],
		)
		self.assertEqual(rows[1]["case_bucket"], "contextual_receipt")
		self.assertEqual(rows[1]["detection_type"], "context_multi_name_receipt")
		self.assertEqual(rows[1]["bill_numbers"], ["63255"])

	def test_cluster_queue_rows_collapses_duplicate_same_day_alert_rows(self):
		rows = [
			{
				"queue_bucket": "same_day",
				"event_date": "2026-03-08",
				"window_start": "2026-03-08",
				"window_end": "2026-03-08",
				"scope": "chain",
				"scope_key": 0,
				"location_id": 0,
				"store_name": "Robinson Imus | SM North EDSA",
				"discount_bir_category": "SC",
				"identity_type": "reference_number",
				"identity_key": "44228",
				"detection_type": "same_reference_same_day_multi_store",
				"severity": "critical",
				"rapid_within_4h": True,
				"min_gap_minutes": 1.4,
				"order_count": 2,
				"store_count": 2,
				"discount_amount_total": 102.5,
				"details": {
					"order_ids": [47122266, 47122476],
					"store_names": ["Robinson Imus", "SM North EDSA"],
					"customer_names": ["Teresita Romero", "Vilma Ingalla"],
					"reference_numbers": ["44228"],
					"bill_numbers": ["23116", "66897"],
				},
			},
			{
				"queue_bucket": "same_day",
				"event_date": "2026-03-08",
				"window_start": "2026-03-08",
				"window_end": "2026-03-08",
				"scope": "chain",
				"scope_key": 0,
				"location_id": 0,
				"store_name": "Robinson Imus | SM North EDSA",
				"discount_bir_category": "SC",
				"identity_type": "reference_number",
				"identity_key": "44228",
				"detection_type": "same_reference_diff_name_same_day_multi_store",
				"severity": "critical",
				"rapid_within_4h": True,
				"min_gap_minutes": 1.4,
				"order_count": 2,
				"store_count": 2,
				"discount_amount_total": 102.5,
				"details": {
					"order_ids": [47122266, 47122476],
					"store_names": ["Robinson Imus", "SM North EDSA"],
					"customer_names": ["Teresita Romero", "Vilma Ingalla"],
					"reference_numbers": ["44228"],
					"bill_numbers": ["23116", "66897"],
				},
			},
		]

		clusters = discount_abuse._cluster_queue_rows(rows)

		self.assertEqual(len(clusters), 1)
		self.assertEqual(clusters[0]["raw_row_count"], 2)
		self.assertEqual(
			clusters[0]["detection_types"],
			[
				"same_reference_same_day_multi_store",
				"same_reference_diff_name_same_day_multi_store",
			],
		)
		self.assertEqual(len(clusters[0]["resolution_targets"]), 2)
		self.assertEqual(clusters[0]["identity_key"], "44228")

	def test_resolve_discount_audit_incident_updates_all_underlying_targets(self):
		payload = {
			"cluster_id": "same-day::test",
			"resolve_scope_policy": "all_underlying_rows",
			"resolution_targets": [
				{
					"event_date": "2026-03-08",
					"scope": "chain",
					"scope_key": 0,
					"discount_bir_category": "SC",
					"identity_type": "reference_number",
					"identity_key": "44228",
					"detection_type": "same_reference_same_day_multi_store",
				},
				{
					"event_date": "2026-03-08",
					"scope": "chain",
					"scope_key": 0,
					"discount_bir_category": "SC",
					"identity_type": "reference_number",
					"identity_key": "44228",
					"detection_type": "same_reference_diff_name_same_day_multi_store",
				},
			],
		}

		with (
			patch.object(
				discount_abuse,
				"_resolve_discount_alert_payload",
				side_effect=[{"id": 1}, {"id": 2}],
			) as mock_resolve,
			patch.object(discount_abuse, "_check_discount_audit_role", return_value=None),
		):
			result = discount_abuse.resolve_discount_audit_incident(
				payload,
				"under_investigation",
				"cluster review",
			)

		self.assertTrue(result["success"])
		self.assertEqual(result["data"]["resolved_count"], 2)
		self.assertEqual(result["data"]["target_count"], 2)
		self.assertEqual(mock_resolve.call_count, 2)

	def test_build_order_finance_buckets_allocates_statutory_vat_relief_proportionally(self):
		paid_order_rows = [
			{
				"id": 5001,
				"location_id": 10,
				"store_name": "SM North EDSA",
				"business_date": "2026-02-13",
				"original_gross_sales": 1000,
				"gross_sales": 820,
				"total_discounts": 120,
			}
		]
		item_rows = [
			{
				"order_id": 5001,
				"discount_bir_category": "SC",
				"discount_amount": 60,
			},
			{
				"order_id": 5001,
				"discount_bir_category": "PWD",
				"discount_amount": 30,
			},
		]

		buckets = discount_abuse._build_order_finance_buckets(paid_order_rows, item_rows)

		self.assertIn(5001, buckets)
		self.assertAlmostEqual(buckets[5001]["discounts"]["SC"], 60.0)
		self.assertAlmostEqual(buckets[5001]["discounts"]["PWD"], 30.0)
		self.assertAlmostEqual(buckets[5001]["vat_relief"]["SC"], 30.0)
		self.assertAlmostEqual(buckets[5001]["vat_relief"]["PWD"], 15.0)
		self.assertAlmostEqual(buckets[5001]["effective_benefit"]["SC"], 90.0)
		self.assertAlmostEqual(buckets[5001]["effective_benefit"]["PWD"], 45.0)

	def test_build_executive_summary_payload_uses_snapshot_rows_and_ranks_outliers(self):
		snapshot_rows = [
			{
				"scope": "store",
				"location_id": 1,
				"store_name": "SM North EDSA",
				"legal_entity": "BEI",
				"store_type": "mall",
				"peer_group_key": "MALL::BEI",
				"business_date": "2026-02-28",
				"month_start": "2026-02-01",
				"active_days": 28,
				"paid_orders": 6187,
				"pos_original_gross_sales": 2085098,
				"pos_post_discount_gross_sales": 1915330.72,
				"pos_net_sales_without_vat": 1753193.46,
				"pos_total_discounts": 109471.75,
				"all_channel_total_orders": 0,
				"all_channel_gross_sales": 0,
				"sc_recorded_discount_amount": 53159,
				"pwd_recorded_discount_amount": 20018,
				"sc_statutory_vat_relief": 8000,
				"pwd_statutory_vat_relief": 2500,
				"sc_effective_statutory_benefit": 61159,
				"pwd_effective_statutory_benefit": 22518,
				"sc_repeat_name_findings": 10,
				"sc_repeat_reference_findings": 0,
				"sc_same_reference_different_name_findings": 2,
				"sc_same_name_multiple_reference_findings": 2,
				"sc_rapid_repeat_name_findings_4h": 9,
				"sc_rapid_repeat_reference_findings_4h": 0,
				"sc_cross_store_overlap_count": 3,
				"sc_cross_store_overlap_critical": 1,
				"sc_cross_store_overlap_high": 1,
				"sc_same_day_alert_cases": 12,
				"sc_high_confidence_same_day_incidents": 12,
				"sc_same_day_flagged_discount_total": 1327.24,
				"sc_weighted_risk_score": 61.5,
				"sc_weighted_risk_rate": 15.32,
				"pwd_repeat_name_findings": 0,
				"pwd_repeat_reference_findings": 0,
				"pwd_same_reference_different_name_findings": 0,
				"pwd_same_name_multiple_reference_findings": 0,
				"pwd_rapid_repeat_name_findings_4h": 0,
				"pwd_rapid_repeat_reference_findings_4h": 0,
				"pwd_cross_store_overlap_count": 0,
				"pwd_cross_store_overlap_critical": 0,
				"pwd_cross_store_overlap_high": 0,
				"pwd_same_day_alert_cases": 0,
				"pwd_high_confidence_same_day_incidents": 0,
				"pwd_same_day_flagged_discount_total": 0,
				"pwd_weighted_risk_score": 0,
				"pwd_weighted_risk_rate": 0,
			},
			{
				"scope": "store",
				"location_id": 2,
				"store_name": "SM Megamall",
				"legal_entity": "BEI",
				"store_type": "mall",
				"peer_group_key": "MALL::BEI",
				"business_date": "2026-02-28",
				"month_start": "2026-02-01",
				"active_days": 28,
				"paid_orders": 5165,
				"pos_original_gross_sales": 1979070,
				"pos_post_discount_gross_sales": 1832336.57,
				"pos_net_sales_without_vat": 1665716.56,
				"pos_total_discounts": 105000,
				"all_channel_total_orders": 0,
				"all_channel_gross_sales": 0,
				"sc_recorded_discount_amount": 30000,
				"pwd_recorded_discount_amount": 15000,
				"sc_statutory_vat_relief": 5000,
				"pwd_statutory_vat_relief": 1000,
				"sc_effective_statutory_benefit": 35000,
				"pwd_effective_statutory_benefit": 16000,
				"sc_repeat_name_findings": 1,
				"sc_repeat_reference_findings": 0,
				"sc_same_reference_different_name_findings": 0,
				"sc_same_name_multiple_reference_findings": 1,
				"sc_rapid_repeat_name_findings_4h": 1,
				"sc_rapid_repeat_reference_findings_4h": 0,
				"sc_cross_store_overlap_count": 1,
				"sc_cross_store_overlap_critical": 0,
				"sc_cross_store_overlap_high": 1,
				"sc_same_day_alert_cases": 2,
				"sc_high_confidence_same_day_incidents": 1,
				"sc_same_day_flagged_discount_total": 95.12,
				"sc_weighted_risk_score": 7,
				"sc_weighted_risk_rate": 1.19,
				"pwd_repeat_name_findings": 0,
				"pwd_repeat_reference_findings": 0,
				"pwd_same_reference_different_name_findings": 0,
				"pwd_same_name_multiple_reference_findings": 0,
				"pwd_rapid_repeat_name_findings_4h": 0,
				"pwd_rapid_repeat_reference_findings_4h": 0,
				"pwd_cross_store_overlap_count": 0,
				"pwd_cross_store_overlap_critical": 0,
				"pwd_cross_store_overlap_high": 0,
				"pwd_same_day_alert_cases": 0,
				"pwd_high_confidence_same_day_incidents": 0,
				"pwd_same_day_flagged_discount_total": 0,
				"pwd_weighted_risk_score": 0,
				"pwd_weighted_risk_rate": 0,
			},
			{
				"scope": "chain",
				"location_id": 0,
				"store_name": "Chainwide",
				"legal_entity": "CHAINWIDE",
				"store_type": "CHAINWIDE",
				"peer_group_key": "CHAINWIDE",
				"business_date": "2026-02-28",
				"month_start": "2026-02-01",
				"active_days": 28,
				"paid_orders": 11352,
				"pos_original_gross_sales": 4064168,
				"pos_post_discount_gross_sales": 3747667.29,
				"pos_net_sales_without_vat": 3418910.02,
				"pos_total_discounts": 214471.75,
				"all_channel_total_orders": 11352,
				"all_channel_gross_sales": 5500000,
				"sc_recorded_discount_amount": 83159,
				"pwd_recorded_discount_amount": 35018,
				"sc_statutory_vat_relief": 13000,
				"pwd_statutory_vat_relief": 3500,
				"sc_effective_statutory_benefit": 96159,
				"pwd_effective_statutory_benefit": 38518,
				"sc_repeat_name_findings": 11,
				"sc_repeat_reference_findings": 0,
				"sc_same_reference_different_name_findings": 2,
				"sc_same_name_multiple_reference_findings": 3,
				"sc_rapid_repeat_name_findings_4h": 10,
				"sc_rapid_repeat_reference_findings_4h": 0,
				"sc_cross_store_overlap_count": 4,
				"sc_cross_store_overlap_critical": 1,
				"sc_cross_store_overlap_high": 2,
				"sc_same_day_alert_cases": 14,
				"sc_high_confidence_same_day_incidents": 13,
				"sc_same_day_flagged_discount_total": 1422.36,
				"sc_weighted_risk_score": 68.5,
				"sc_weighted_risk_rate": 16.51,
				"pwd_repeat_name_findings": 0,
				"pwd_repeat_reference_findings": 0,
				"pwd_same_reference_different_name_findings": 0,
				"pwd_same_name_multiple_reference_findings": 0,
				"pwd_rapid_repeat_name_findings_4h": 0,
				"pwd_rapid_repeat_reference_findings_4h": 0,
				"pwd_cross_store_overlap_count": 0,
				"pwd_cross_store_overlap_critical": 0,
				"pwd_cross_store_overlap_high": 0,
				"pwd_same_day_alert_cases": 0,
				"pwd_high_confidence_same_day_incidents": 0,
				"pwd_same_day_flagged_discount_total": 0,
				"pwd_weighted_risk_score": 0,
				"pwd_weighted_risk_rate": 0,
			},
		]

		with (
			patch.object(
				discount_abuse,
				"_select_snapshot_rows_for_window",
				return_value=(snapshot_rows, {"snapshot_source": "month", "period_granularity": "month"}),
			),
			patch.object(discount_abuse, "_query_store_day_snapshots", return_value=[]),
		):
			payload = discount_abuse._build_executive_summary_payload(
				date(2026, 2, 1),
				date(2026, 2, 28),
				denominator_scope="pos_original_gross",
				category_scope="BOTH",
				peer_mode="auto",
			)

		self.assertEqual(payload["snapshot_source"], "month")
		self.assertEqual(payload["cards"]["top_outlier_store"]["store_name"], "SM North EDSA")
		self.assertEqual(payload["top_weighted_risk_stores"][0]["store_name"], "SM North EDSA")
		self.assertGreater(payload["cards"]["recorded_sc_pct_of_sales"], 0)
		self.assertGreaterEqual(len(payload["incident_share_vs_sales_share"]), 2)

	def test_build_finance_reconciliation_payload_breaks_out_other_discount_gap(self):
		snapshot_rows = [
			{
				"scope": "chain",
				"location_id": 0,
				"store_name": "Chainwide",
				"business_date": "2026-02-28",
				"month_start": "2026-02-01",
				"paid_orders": 100,
				"pos_original_gross_sales": 1000,
				"pos_post_discount_gross_sales": 820,
				"pos_net_sales_without_vat": 732.14,
				"pos_total_discounts": 120,
				"all_channel_total_orders": 100,
				"all_channel_gross_sales": 1200,
				"sc_recorded_discount_amount": 60,
				"pwd_recorded_discount_amount": 30,
				"sc_statutory_vat_relief": 40,
				"pwd_statutory_vat_relief": 20,
				"sc_effective_statutory_benefit": 100,
				"pwd_effective_statutory_benefit": 50,
				"sc_repeat_name_findings": 0,
				"sc_repeat_reference_findings": 0,
				"sc_same_reference_different_name_findings": 0,
				"sc_same_name_multiple_reference_findings": 0,
				"sc_rapid_repeat_name_findings_4h": 0,
				"sc_rapid_repeat_reference_findings_4h": 0,
				"sc_cross_store_overlap_count": 0,
				"sc_cross_store_overlap_critical": 0,
				"sc_cross_store_overlap_high": 0,
				"sc_same_day_alert_cases": 0,
				"sc_high_confidence_same_day_incidents": 0,
				"sc_same_day_flagged_discount_total": 0,
				"sc_weighted_risk_score": 0,
				"sc_weighted_risk_rate": 0,
				"pwd_repeat_name_findings": 0,
				"pwd_repeat_reference_findings": 0,
				"pwd_same_reference_different_name_findings": 0,
				"pwd_same_name_multiple_reference_findings": 0,
				"pwd_rapid_repeat_name_findings_4h": 0,
				"pwd_rapid_repeat_reference_findings_4h": 0,
				"pwd_cross_store_overlap_count": 0,
				"pwd_cross_store_overlap_critical": 0,
				"pwd_cross_store_overlap_high": 0,
				"pwd_same_day_alert_cases": 0,
				"pwd_high_confidence_same_day_incidents": 0,
				"pwd_same_day_flagged_discount_total": 0,
				"pwd_weighted_risk_score": 0,
				"pwd_weighted_risk_rate": 0,
			}
		]

		with patch.object(
			discount_abuse,
			"_select_snapshot_rows_for_window",
			return_value=(snapshot_rows, {"snapshot_source": "month", "period_granularity": "month"}),
		):
			payload = discount_abuse._build_finance_reconciliation_payload(
				date(2026, 2, 1),
				date(2026, 2, 28),
				denominator_scope="pos_original_gross",
				category_scope="SC",
			)

		self.assertEqual(payload["totals"]["recorded_discount_amount"], 60.0)
		self.assertEqual(payload["totals"]["statutory_vat_relief"], 40.0)
		self.assertEqual(payload["totals"]["effective_statutory_benefit"], 100.0)
		self.assertEqual(payload["totals"]["gross_gap_before_vat"], 180.0)
		self.assertEqual(payload["totals"]["other_discount_gap"], 80.0)
		self.assertEqual(payload["waterfall"][1]["label"], "Recorded statutory discount")

	def test_refresh_discount_benchmark_snapshots_internal_rebuilds_day_and_month_rows(self):
		day_row = {
			"scope": "store",
			"location_id": 1,
			"store_name": "SM North EDSA",
			"business_date": "2026-02-01",
			"month_start": "2026-02-01",
			"paid_orders": 10,
			"active_days": 1,
		}
		chain_row = {
			"scope": "chain",
			"location_id": 0,
			"store_name": "Chainwide",
			"business_date": "2026-02-01",
			"month_start": "2026-02-01",
			"paid_orders": 10,
			"active_days": 1,
		}

		with (
			patch.object(discount_abuse, "_build_store_day_snapshot_rows", return_value=[day_row, chain_row]),
			patch.object(discount_abuse, "_replace_store_day_snapshots", return_value=2) as mock_replace_day,
			patch.object(discount_abuse, "_query_store_day_snapshots", return_value=[day_row, chain_row]),
			patch.object(
				discount_abuse, "_replace_store_month_snapshots", return_value=2
			) as mock_replace_month,
		):
			result = discount_abuse._refresh_discount_benchmark_snapshots_internal(
				date(2026, 2, 1),
				date(2026, 2, 1),
			)

		self.assertTrue(result["success"])
		self.assertEqual(result["store_day_rows_written"], 2)
		self.assertEqual(result["store_month_rows_written"], 2)
		self.assertEqual(result["refreshed_days"], ["2026-02-01"])
		mock_replace_day.assert_called_once()
		mock_replace_month.assert_called_once()


if __name__ == "__main__":
	unittest.main()
