import datetime
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_runtime():
	frappe = types.ModuleType("frappe")
	frappe_utils = types.ModuleType("frappe.utils")
	frappe_rate_limiter = types.ModuleType("frappe.rate_limiter")

	def whitelist(*args, **kwargs):
		if args and callable(args[0]) and len(args) == 1 and not kwargs:
			return args[0]

		def decorator(fn):
			return fn

		return decorator

	def throw(message, exc=None, **kwargs):
		if isinstance(exc, type) and issubclass(exc, Exception):
			raise exc(message)
		raise Exception(message)

	def rate_limit(*args, **kwargs):
		def decorator(fn):
			return fn

		return decorator

	frappe.whitelist = whitelist
	frappe.throw = throw
	frappe._ = lambda text: text
	frappe.PermissionError = type("PermissionError", (Exception,), {})
	frappe.log_error = lambda *args, **kwargs: None
	frappe.parse_json = lambda value: __import__("json").loads(value)
	frappe.get_roles = lambda *args, **kwargs: ["HR User"]
	frappe.session = types.SimpleNamespace(user="test.hr@bebang.ph")
	frappe.db = types.SimpleNamespace(
		sql=lambda *args, **kwargs: [],
		count=lambda *args, **kwargs: 0,
	)

	frappe_utils.flt = lambda value, precision=None: float(value or 0)
	frappe_utils.getdate = (
		lambda value=None: datetime.date.fromisoformat(str(value)) if value else datetime.date(2026, 2, 1)
	)
	frappe_utils.nowdate = lambda: "2026-02-28"
	frappe_utils.add_months = lambda d, m: d
	frappe_utils.get_first_day = lambda d: d
	frappe_utils.get_last_day = lambda d: d
	frappe_utils.add_days = lambda d, n: d
	frappe_utils.date_diff = lambda d1, d2: 0
	frappe_utils.today = lambda: "2026-02-28"

	frappe_rate_limiter.rate_limit = rate_limit

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = frappe_utils
	sys.modules["frappe.rate_limiter"] = frappe_rate_limiter

	hrms_pkg = types.ModuleType("hrms")
	hrms_pkg.__path__ = []
	sys.modules["hrms"] = hrms_pkg

	hrms_utils_pkg = types.ModuleType("hrms.utils")
	hrms_utils_pkg.__path__ = []
	sys.modules["hrms.utils"] = hrms_utils_pkg

	api_helpers = types.ModuleType("hrms.utils.api_helpers")
	api_helpers._check_hr_permission = lambda *args, **kwargs: None
	api_helpers._validate_date_range = lambda *args, **kwargs: None
	api_helpers._paginate = lambda rows, **kwargs: {"data": rows, "total": len(rows)}
	sys.modules["hrms.utils.api_helpers"] = api_helpers

	hrms_payroll_pkg = types.ModuleType("hrms.payroll")
	hrms_payroll_pkg.__path__ = []
	sys.modules["hrms.payroll"] = hrms_payroll_pkg

	ph_statutory = types.ModuleType("hrms.payroll.ph_statutory")
	ph_statutory.get_sss_contribution = lambda *args, **kwargs: {}
	ph_statutory.get_philhealth_contribution = lambda *args, **kwargs: {}
	ph_statutory.get_pagibig_contribution = lambda *args, **kwargs: {}
	sys.modules["hrms.payroll.ph_statutory"] = ph_statutory


def _load_module(name: str, relative_path: str):
	spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


_install_fake_runtime()
payroll = _load_module("payroll_under_test", "hrms/api/payroll.py")
hr_reports = _load_module("hr_reports_under_test", "hrms/api/hr_reports.py")


class TestPayrollComparisonTrainingS09(unittest.TestCase):
	def test_payroll_comparison_returns_frappe_only_mode_without_apex_data(self):
		rows = [
			{
				"employee": "EMP-001",
				"employee_name": "Test One",
				"frappe_gross": 12000,
				"frappe_deductions": 1500,
				"frappe_net": 10500,
			}
		]
		payroll.frappe.db.sql = MagicMock(return_value=rows)

		result = payroll.get_payroll_comparison("2026-02-01", "2026-02-15")

		self.assertEqual(result["mode"], "frappe_only")
		self.assertEqual(result["summary"]["frappe_count"], 1)
		self.assertEqual(result["summary"]["apex_count"], 0)
		self.assertNotIn("not yet implemented", result["note"].lower())

	def test_payroll_comparison_calculates_variance_with_apex_rows(self):
		frappe_rows = [
			{
				"employee": "EMP-001",
				"employee_name": "Test One",
				"frappe_gross": 12000,
				"frappe_deductions": 1500,
				"frappe_net": 10500,
			}
		]
		payroll.frappe.db.sql = MagicMock(return_value=frappe_rows)
		apex_rows = [{"employee_id": "EMP-001", "employee_name": "Test One", "net_pay": 10300}]

		result = payroll.get_payroll_comparison("2026-02-01", "2026-02-15", apex_results=apex_rows)

		self.assertEqual(result["mode"], "with_apex")
		self.assertEqual(result["summary"]["matched_count"], 1)
		self.assertEqual(result["comparison"][0]["variance_net"], 200.0)

	def test_training_completion_returns_live_dashboard_shape(self):
		hr_reports.frappe.db.sql = MagicMock(
			return_value=[
				{"branch": "AYALA EVO - BEI", "completed": 4, "total_active": 5},
				{"branch": "MARKET MARKET - BEI", "completed": 10, "total_active": 10},
			]
		)

		result = hr_reports.get_training_completion_by_store()

		self.assertTrue(result["success"])
		self.assertEqual(result["data"][0]["department"], "AYALA EVO - BEI")
		self.assertEqual(result["data"][0]["required_trainings"], 5)
		self.assertEqual(result["data"][0]["overdue"], 1)
		self.assertEqual(result["data"][0]["compliance_rate"], 80.0)
		self.assertEqual(result["data"][1]["compliance_rate"], 100.0)

		sql_query = hr_reports.frappe.db.sql.call_args[0][0]
		self.assertIn("tabTraining Result Employee", sql_query)
		self.assertIn("COUNT(DISTINCT tre.employee)", sql_query)
		self.assertNotIn("COUNT(DISTINCT tr.employee)", sql_query)


if __name__ == "__main__":
	unittest.main()
