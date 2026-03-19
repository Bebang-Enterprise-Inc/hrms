import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_frappe():
	frappe = types.ModuleType("frappe")
	sys.modules["frappe"] = frappe

	def whitelist(*args, **kwargs):
		if args and callable(args[0]) and len(args) == 1 and not kwargs:
			return args[0]

		def decorator(fn):
			return fn

		return decorator

	frappe.whitelist = whitelist
	frappe._ = lambda text: text
	frappe.throw = lambda message, exc=None: (_ for _ in ()).throw(Exception(message))
	frappe.log_error = lambda *args, **kwargs: None
	frappe.get_roles = lambda: ["Accounts Manager"]
	frappe.session = types.SimpleNamespace(user="test.hr@bebang.ph")

	class FakeDB:
		def get_value(self, doctype, name, fieldname):
			if doctype == "Employee" and fieldname == "employee_name":
				return "Test Crew"
			return None

		def count(self, *args, **kwargs):
			return 0

		def sql(self, *args, **kwargs):
			return [(0,)]

	captured = {"filters": None}

	def fake_get_all(_doctype, filters=None, fields=None, order_by=None, limit_page_length=None, start=None):
		captured["filters"] = filters
		return [
			{
				"name": "BEI-EXP-TEST-0001",
				"employee": "TEST-CREW-001",
				"store": "TEST-STORE-BGC - BEI",
				"request_date": "2026-03-19",
				"manual_vendor": "Test Vendor",
				"manual_description": "Test expense",
				"manual_amount": 100.0,
				"manual_date": "2026-03-19",
				"internal_ocr_vendor": None,
				"internal_ocr_amount": None,
				"internal_ocr_date": None,
				"internal_match_score": 0,
				"internal_match_status": "",
				"internal_amount_diff": 0,
				"internal_suggested_coa": None,
				"internal_coa_confidence": 0,
				"internal_review_status": "needs_classification",
				"creation": "2026-03-19 00:00:00",
			}
		]

	frappe.db = FakeDB()
	frappe.get_all = fake_get_all
	frappe.get_doc = lambda *args, **kwargs: None
	return captured


class TestExpenseReviewQueueFilters(unittest.TestCase):
	def setUp(self):
		self.captured = _install_fake_frappe()
		if "frappe.utils" not in sys.modules:
			utils = types.ModuleType("frappe.utils")
			utils.now_datetime = lambda: "2026-03-19 00:00:00"
			utils.today = lambda: "2026-03-19"
			utils.flt = lambda value, precision=None: float(value or 0)
			utils.getdate = lambda value=None: value
			sys.modules["frappe.utils"] = utils

		spec = importlib.util.spec_from_file_location(
			"expense_review_under_test",
			ROOT / "hrms" / "api" / "expense_review.py",
		)
		self.module = importlib.util.module_from_spec(spec)
		assert spec and spec.loader
		spec.loader.exec_module(self.module)

	def test_all_queue_only_requests_reviewable_statuses(self):
		result = self.module.get_pending_review(review_type="all", limit=50, offset=0)

		self.assertTrue(result["success"])
		self.assertEqual(result["data"][0]["employee_name"], "Test Crew")
		self.assertEqual(
			self.captured["filters"],
			{
				"status": "Submitted",
				"internal_review_status": [
					"in",
					["pending_review", "mismatch_review", "needs_classification", "ocr_failed"],
				],
			},
		)

	def test_auto_approved_queue_keeps_auto_approved_filter(self):
		self.module.get_pending_review(review_type="auto_approved", limit=50, offset=0)

		self.assertEqual(
			self.captured["filters"],
			{
				"status": "Submitted",
				"internal_review_status": "auto_approved",
			},
		)


if __name__ == "__main__":
	unittest.main()
