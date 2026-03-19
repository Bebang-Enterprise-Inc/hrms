# Copyright (c) 2026, Frappe Technologies Pvt. Ltd.
# For license information, please see license.txt

"""Sprint 07 checks for expense fallback signaling and review-path stability."""

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_frappe():
	if "frappe" not in sys.modules:
		frappe = types.ModuleType("frappe")

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
		frappe.get_roles = lambda: ["Accounts Manager"]
		frappe.session = types.SimpleNamespace(user="test.accounting@bebang.ph")
		frappe.conf = {}
		frappe.db = types.SimpleNamespace(
			count=lambda *args, **kwargs: 0,
			sql=lambda *args, **kwargs: [(0,)],
			get_value=lambda *args, **kwargs: None,
			get_single_value=lambda *args, **kwargs: None,
			commit=lambda: None,
		)
		frappe.get_all = lambda *args, **kwargs: []
		frappe.get_doc = lambda *args, **kwargs: None
		sys.modules["frappe"] = frappe

	if "frappe.utils" not in sys.modules:
		utils = types.ModuleType("frappe.utils")
		utils.today = lambda: "2026-02-27"
		utils.now_datetime = lambda: "2026-02-27 00:00:00"
		utils.flt = lambda value, precision=None: float(value or 0)
		utils.getdate = lambda value=None: value
		sys.modules["frappe.utils"] = utils

	frappe = sys.modules["frappe"]
	utils = sys.modules["frappe.utils"]
	if not hasattr(frappe, "conf"):
		frappe.conf = {}
	if not hasattr(utils, "getdate"):
		utils.getdate = lambda value=None: value

	if "hrms" not in sys.modules:
		hrms_pkg = types.ModuleType("hrms")
		hrms_pkg.__path__ = []
		sys.modules["hrms"] = hrms_pkg

	if "hrms.api" not in sys.modules:
		hrms_api_pkg = types.ModuleType("hrms.api")
		hrms_api_pkg.__path__ = []
		sys.modules["hrms.api"] = hrms_api_pkg


def _load_module(module_name: str, relative_path: str):
	spec = importlib.util.spec_from_file_location(module_name, ROOT / relative_path)
	module = importlib.util.module_from_spec(spec)
	sys.modules[module_name] = module
	spec.loader.exec_module(module)
	return module


_install_fake_frappe()
expense_classifier = _load_module("hrms.api.expense_classifier", "hrms/api/expense_classifier.py")
expense_review = _load_module("hrms.api.expense_review", "hrms/api/expense_review.py")


class _ExpenseDoc:
	def __init__(self):
		self.name = "EXP-0001"
		self.employee = "EMP-0001"
		self.store = "TEST STORE - BEI"
		self.status = "Submitted"
		self.manual_amount = 120.0
		self.internal_suggested_coa = None
		self.internal_final_coa = None
		self.internal_approved_amount = None
		self.internal_approval_source = None
		self.internal_reviewed_by = None
		self.internal_review_date = None
		self.internal_review_notes = None
		self.pcf_batch = None

	def save(self, **kwargs):
		return None


class TestExpenseModelFallbackS07(unittest.TestCase):
	def test_classifier_returns_explicit_degraded_fallback_when_runtime_is_missing(self):
		with (
			patch.object(expense_classifier, "JOBLIB_AVAILABLE", False),
			patch.object(expense_classifier, "REQUESTS_AVAILABLE", False),
			patch.object(expense_classifier.os.path, "exists", return_value=False),
		):
			result = expense_classifier.classify_expense("zzqv unmatched token", "unknown vendor")

		self.assertEqual(result["method"], "fallback_degraded")
		self.assertEqual(result["fallback_reason"], "ml_model_missing_and_openai_unavailable")
		self.assertIn("runtime_health", result)
		self.assertFalse(result["runtime_health"]["ml_model_available"])
		self.assertFalse(result["runtime_health"]["openai_available"])

	def test_create_pcf_jv_returns_structured_skip_when_batch_is_missing(self):
		expense = _ExpenseDoc()
		result = expense_review._create_pcf_jv(expense)

		self.assertFalse(result["created"])
		self.assertEqual(result["reason"], "missing_pcf_batch")
		self.assertIsNone(result["journal_entry"])

	def test_approve_expense_does_not_fail_on_missing_pcf_jv_hook(self):
		expense = _ExpenseDoc()
		with (
			patch.object(expense_review.frappe, "get_doc", return_value=expense),
			patch.object(expense_review, "_notify_employee", return_value=None),
		):
			result = expense_review.approve_expense(
				expense_name=expense.name,
				final_coa="6006003",
				approved_amount=120.0,
				approval_source="manual",
			)

		self.assertTrue(result["success"])
		self.assertEqual(result["data"]["status"], "Approved")
		self.assertEqual(expense.internal_final_coa, "6006003")
		self.assertEqual(expense.status, "Approved")

	def test_notify_employee_swallow_import_and_logging_failures(self):
		expense = _ExpenseDoc()

		with (
			patch.object(
				expense_review.frappe.db,
				"get_value",
				return_value="test.accounting@bebang.ph",
			),
			patch.object(expense_review.frappe, "log_error", side_effect=Exception("log failed")),
		):
			result = expense_review._notify_employee(expense, "rejected")

		self.assertIsNone(result)


if __name__ == "__main__":
	unittest.main()
