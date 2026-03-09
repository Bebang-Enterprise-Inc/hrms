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
		self.assertEqual(rows[1]["case_bucket"], "contextual_receipt")
		self.assertEqual(rows[1]["detection_type"], "context_multi_name_receipt")
		self.assertEqual(rows[1]["bill_numbers"], ["63255"])


if __name__ == "__main__":
	unittest.main()
