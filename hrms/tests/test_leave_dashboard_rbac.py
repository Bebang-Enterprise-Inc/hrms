import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _load_leave_dashboard_module():
	module_path = ROOT / "hrms" / "api" / "leave_dashboard.py"
	spec = importlib.util.spec_from_file_location("leave_dashboard_under_test", module_path)
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(module)
	return module


def _install_fake_frappe():
	frappe = types.ModuleType("frappe")
	utils = types.ModuleType("frappe.utils")

	def whitelist(*args, **kwargs):
		def decorator(fn):
			return fn

		return decorator

	tracker = {"roles": None, "sql_calls": []}

	def sql(query, values=None, as_dict=False):
		tracker["sql_calls"].append((query, values, as_dict))
		if "count(name)" in query:
			return [(10,)]
		if "count(la.name)" in query:
			return [(2,)]
		return []

	def only_for(roles):
		tracker["roles"] = roles

	frappe.whitelist = whitelist
	frappe.only_for = only_for
	frappe.throw = lambda message: (_ for _ in ()).throw(Exception(message))
	frappe.db = types.SimpleNamespace(sql=sql, get_value=lambda *a, **k: {})
	frappe._ = lambda value: value

	utils.today = lambda: "2026-02-28"
	utils.add_days = lambda value, days: "2026-03-06"

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils
	return tracker


def test_get_leave_overview_enforces_allowed_roles():
	tracker = _install_fake_frappe()
	leave_dashboard = _load_leave_dashboard_module()

	result = leave_dashboard.get_leave_overview(branch="B1", department="HR")

	assert tracker["roles"] == leave_dashboard.ALLOWED_ROLES
	assert result["total_employees"] == 10
	assert result["on_leave_today"] == 2


def test_get_all_leaves_applies_advanced_filters():
	tracker = _install_fake_frappe()
	leave_dashboard = _load_leave_dashboard_module()

	leave_dashboard.get_all_leaves(
		status="Approved",
		branch="B1",
		department="HR",
		from_date="2026-02-01",
		to_date="2026-02-28",
		employee="EMP-001",
		leave_type="Vacation Leave",
	)

	_query, values, _as_dict = tracker["sql_calls"][-1]
	assert values["status"] == "Approved"
	assert values["branch"] == "B1"
	assert values["department"] == "HR"
	assert values["employee_exact"] == "EMP-001"
	assert values["leave_type"] == "Vacation Leave"
