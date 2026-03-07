from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _load_hr_reports_module():
	frappe = types.ModuleType("frappe")
	utils = types.ModuleType("frappe.utils")
	rate_limiter = types.ModuleType("frappe.rate_limiter")
	leave_dashboard = types.ModuleType("hrms.api.leave_dashboard")

	def whitelist(*_args, **_kwargs):
		def decorator(fn):
			return fn

		return decorator

	class _DB:
		@staticmethod
		def escape(value):
			return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"

	frappe.whitelist = whitelist
	frappe.db = _DB()
	frappe._ = lambda text: text

	utils.add_days = lambda value, _days: value
	utils.date_diff = lambda *_args, **_kwargs: 0
	utils.flt = float
	utils.getdate = lambda value=None: value
	utils.today = lambda: "2026-03-07"

	rate_limiter.rate_limit = lambda *args, **kwargs: (lambda fn: fn)

	leave_dashboard.get_dashboard_data = lambda **kwargs: kwargs
	leave_dashboard.get_leave_overview = lambda **kwargs: kwargs
	leave_dashboard.get_all_leaves = lambda **kwargs: kwargs
	leave_dashboard.check_leave_conflicts = lambda **kwargs: kwargs
	leave_dashboard.bulk_action = lambda **kwargs: kwargs

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils
	sys.modules["frappe.rate_limiter"] = rate_limiter
	sys.modules["hrms.api.leave_dashboard"] = leave_dashboard

	spec = importlib.util.spec_from_file_location(
		"hr_reports_under_test",
		ROOT / "hrms" / "api" / "hr_reports.py",
	)
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(module)
	return module


def test_employee_permission_query_keeps_general_test_employees_hidden():
	hr_reports = _load_hr_reports_module()

	assert (
		hr_reports.get_employee_permission_query_conditions("Guest")
		== "(`tabEmployee`.name NOT LIKE 'TEST-%')"
	)


def test_employee_permission_query_allows_current_user_to_resolve_own_test_employee():
	hr_reports = _load_hr_reports_module()

	query = hr_reports.get_employee_permission_query_conditions("test.area@bebang.ph")

	assert "(`tabEmployee`.name NOT LIKE 'TEST-%')" in query
	assert "`tabEmployee`.user_id = 'test.area@bebang.ph'" in query
