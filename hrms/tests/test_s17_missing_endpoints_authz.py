from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _load_module(path: Path, alias: str):
	spec = importlib.util.spec_from_file_location(alias, path)
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(module)
	return module


def _install_fake_frappe(allow_access: bool):
	frappe = types.ModuleType("frappe")
	utils = types.ModuleType("frappe.utils")

	class ValidationError(Exception):
		pass

	class PermissionError(Exception):
		pass

	def whitelist(*args, **kwargs):
		def decorator(fn):
			return fn

		return decorator

	def only_for(_roles):
		if not allow_access:
			raise PermissionError("forbidden")

	def throw(message, exc=None):
		err_cls = exc if isinstance(exc, type) else Exception
		raise err_cls(message)

	frappe.whitelist = whitelist
	frappe.only_for = only_for
	frappe.throw = throw
	frappe.ValidationError = ValidationError
	frappe.PermissionError = PermissionError
	frappe._ = lambda value: value
	frappe.db = types.SimpleNamespace(sql=lambda *args, **kwargs: [])
	frappe.get_all = lambda *args, **kwargs: []

	utils.today = lambda: "2026-03-01"

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils

	return frappe


def test_s17_authz_denies_compliance_dashboard_for_non_hr_roles():
	_install_fake_frappe(allow_access=False)
	compliance = _load_module(ROOT / "hrms" / "api" / "compliance.py", "s17_compliance_authz_test")

	with pytest.raises(Exception):
		compliance.get_compliance_dashboard()


def test_s17_authz_denies_team_separation_analytics_for_non_hr_roles():
	_install_fake_frappe(allow_access=False)
	clearance = _load_module(
		ROOT / "hrms" / "api" / "employee_clearance.py",
		"s17_employee_clearance_authz_test",
	)

	with pytest.raises(Exception):
		clearance.get_exit_interview_analytics()

	with pytest.raises(Exception):
		clearance.get_team_separations()


def test_s17_malformed_input_is_rejected_for_compliance_calculators():
	frappe = _install_fake_frappe(allow_access=True)
	compliance = _load_module(
		ROOT / "hrms" / "api" / "compliance.py",
		"s17_compliance_validation_test",
	)

	with pytest.raises(frappe.ValidationError):
		compliance.calculate_13th_month_pay("not-a-year")

	with pytest.raises(frappe.ValidationError):
		compliance.get_holiday_pay_compliance(99, 2026)
