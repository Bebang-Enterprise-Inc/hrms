from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _load_module(path: Path, alias: str):
	spec = importlib.util.spec_from_file_location(alias, path)
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(module)
	return module


def _install_fake_runtime():
	frappe = types.ModuleType("frappe")
	frappe_model = types.ModuleType("frappe.model")
	frappe_workflow = types.ModuleType("frappe.model.workflow")
	frappe_qb = types.ModuleType("frappe.query_builder")
	frappe_rate_limiter = types.ModuleType("frappe.rate_limiter")
	frappe_utils = types.ModuleType("frappe.utils")
	erpnext_employee = types.ModuleType("erpnext.setup.doctype.employee.employee")
	profile_policy = types.ModuleType("hrms.api.profile_policy")
	attendance_correction = types.ModuleType("hrms.api.attendance_correction")
	hrms_pkg = types.ModuleType("hrms")
	hrms_api_pkg = types.ModuleType("hrms.api")
	other_api_modules = [
		"commissary",
		"communication",
		"compliance",
		"coverage",
		"dashboard",
		"disciplinary",
		"employee_clearance",
		"finance",
		"hr_reports",
		"image_utils",
		"inventory",
		"inventory_risk",
		"official_business",
		"payroll",
		"performance",
		"procurement",
		"projects",
		"recruitment",
		"shift_tracking",
		"store",
		"store_dashboard",
		"supervisor",
		"transfer_requests",
		"transfers",
		"warehouse",
	]

	class _Order:
		asc = "asc"
		desc = "desc"

	class ValidationError(Exception):
		pass

	class PermissionError(Exception):
		pass

	class AttrDict(dict):
		__getattr__ = dict.get

		def __setattr__(self, key, value):
			self[key] = value

	state = {
		"current_employee": "EMP-SELF-001",
		"last_get_list": None,
		"last_cached_employee": None,
	}

	def whitelist(*args, **kwargs):
		if args and callable(args[0]) and len(args) == 1 and not kwargs:
			return args[0]

		def decorator(fn):
			return fn

		return decorator

	def throw(message, exc=None):
		err_cls = exc if isinstance(exc, type) else Exception
		raise err_cls(message)

	def get_value(doctype, filters=None, fieldname=None, as_dict=False, cache=False):
		if doctype == "Employee" and isinstance(filters, dict):
			if filters.get("user_id") == "test.crew1@bebang.ph" and filters.get("status") == "Active":
				return state["current_employee"]
			return None
		if doctype == "User" and filters == "approver@example.com" and fieldname == "full_name":
			return "Approver Example"
		return None

	def get_cached_value(doctype, name, fieldname):
		if doctype == "Employee":
			state["last_cached_employee"] = name
			if name == "EMP-SELF-001":
				return ("approver@example.com", "Operations")
		return (None, None)

	def get_list(doctype, fields=None, filters=None, order_by=None, limit=None):
		state["last_get_list"] = {
			"doctype": doctype,
			"fields": fields,
			"filters": dict(filters or {}),
			"order_by": order_by,
			"limit": limit,
		}
		return [
			{
				"name": "SHIFT-REQ-0001",
				"employee": (filters or {}).get("employee"),
				"employee_name": "Test Crew",
				"shift_type": "Opening",
				"from_date": "2026-03-17",
				"to_date": "2026-03-17",
				"status": "Draft",
				"approver": "approver@example.com",
				"docstatus": 0,
				"creation": "2026-03-17 08:00:00",
			}
		]

	frappe.whitelist = whitelist
	frappe.throw = throw
	frappe._ = lambda value: value
	frappe._dict = AttrDict
	frappe.ValidationError = ValidationError
	frappe.PermissionError = PermissionError
	frappe.session = types.SimpleNamespace(user="test.crew1@bebang.ph")
	frappe.db = types.SimpleNamespace(get_value=get_value)
	frappe.get_cached_value = get_cached_value
	frappe.get_list = get_list

	frappe_model.get_permitted_fields = lambda *args, **kwargs: []
	frappe_workflow.get_workflow_name = lambda *args, **kwargs: None
	frappe_qb.Order = _Order
	frappe_rate_limiter.rate_limit = lambda *args, **kwargs: (lambda fn: fn)
	frappe_utils.add_days = lambda value, days: value
	frappe_utils.date_diff = lambda to_date, from_date: 0
	frappe_utils.getdate = lambda value=None: value
	frappe_utils.strip_html = lambda value: value
	frappe_utils.today = lambda: "2026-03-17"

	erpnext_employee.get_holiday_list_for_employee = lambda *args, **kwargs: None
	profile_policy.is_reports_to_candidate = lambda *args, **kwargs: False
	profile_policy.matches_reports_to_query = lambda *args, **kwargs: False
	profile_policy.normalize_text = lambda value: str(value or "").strip().upper()
	profile_policy.resolve_reports_to_display_name = lambda employee_name, full_name: full_name or employee_name

	sys.modules["frappe"] = frappe
	sys.modules["frappe.model"] = frappe_model
	sys.modules["frappe.model.workflow"] = frappe_workflow
	sys.modules["frappe.query_builder"] = frappe_qb
	sys.modules["frappe.rate_limiter"] = frappe_rate_limiter
	sys.modules["frappe.utils"] = frappe_utils
	sys.modules["erpnext.setup.doctype.employee.employee"] = erpnext_employee
	hrms_pkg.__path__ = []
	hrms_api_pkg.__path__ = []
	sys.modules["hrms"] = hrms_pkg
	sys.modules["hrms.api"] = hrms_api_pkg
	sys.modules["hrms.api.profile_policy"] = profile_policy
	sys.modules["hrms.api.attendance_correction"] = attendance_correction
	for module_name in other_api_modules:
		sys.modules[f"hrms.api.{module_name}"] = types.ModuleType(f"hrms.api.{module_name}")

	return state


class TestS055ShiftRequestSelfServiceDefaults(unittest.TestCase):
	def test_get_shift_requests_defaults_to_current_employee(self):
		state = _install_fake_runtime()
		module = _load_module(ROOT / "hrms" / "api" / "__init__.py", "s055_shift_requests_under_test")

		rows = module.get_shift_requests()

		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["employee"], "EMP-SELF-001")
		self.assertEqual(state["last_get_list"]["doctype"], "Shift Request")
		self.assertEqual(state["last_get_list"]["filters"]["employee"], "EMP-SELF-001")

	def test_get_shift_request_approvers_defaults_to_current_employee(self):
		_install_fake_runtime()
		module = _load_module(ROOT / "hrms" / "api" / "__init__.py", "s055_shift_approvers_under_test")

		module.get_department_approvers = lambda department, parentfield: [
			module.frappe._dict(name="approver@example.com", full_name="Approver Example")
		]

		approvers = module.get_shift_request_approvers()

		self.assertEqual(len(approvers), 1)
		self.assertEqual(approvers[0]["name"], "approver@example.com")
		self.assertEqual(approvers[0]["full_name"], "Approver Example")


if __name__ == "__main__":
	unittest.main()
