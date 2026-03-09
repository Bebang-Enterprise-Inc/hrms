from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _ensure_package(name: str) -> types.ModuleType:
	module = sys.modules.get(name)
	if module is None:
		module = types.ModuleType(name)
		module.__path__ = []
		sys.modules[name] = module
		if "." in name:
			parent_name, child_name = name.rsplit(".", 1)
			parent = _ensure_package(parent_name)
			setattr(parent, child_name, module)
	return module


def _register_module(name: str, module: types.ModuleType) -> None:
	sys.modules[name] = module
	if "." in name:
		parent_name, child_name = name.rsplit(".", 1)
		parent = _ensure_package(parent_name)
		setattr(parent, child_name, module)


def _load_module(path: Path, alias: str):
	spec = importlib.util.spec_from_file_location(alias, path)
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(module)
	return module


def _install_fake_frappe(user_roles: list[str] | None = None):
	frappe = types.ModuleType("frappe")
	utils = types.ModuleType("frappe.utils")
	bei_config = types.ModuleType("hrms.utils.bei_config")
	scm_roles = types.ModuleType("hrms.utils.scm_roles")

	class ValidationError(Exception):
		pass

	class PermissionError(Exception):
		pass

	def whitelist(*args, **kwargs):
		if args and callable(args[0]) and len(args) == 1 and not kwargs:
			return args[0]

		def decorator(fn):
			return fn

		return decorator

	def throw(message, exc=None):
		err_cls = exc if isinstance(exc, type) else Exception
		raise err_cls(message)

	frappe.whitelist = whitelist
	frappe.throw = throw
	frappe.ValidationError = ValidationError
	frappe.PermissionError = PermissionError
	frappe._ = lambda value: value
	frappe.session = types.SimpleNamespace(user="pytest@example.com")
	frappe.get_roles = lambda: list(user_roles or [])
	frappe.get_all = lambda *args, **kwargs: []
	frappe.log_error = lambda *args, **kwargs: None
	frappe.db = types.SimpleNamespace(get_value=lambda *args, **kwargs: None)

	utils.nowdate = lambda: "2026-03-10"
	utils.flt = lambda value=0, *args, **kwargs: float(value or 0)
	utils.add_days = lambda value, days=0: value
	utils.now_datetime = lambda: "2026-03-10 00:00:00"

	bei_config.get_company = lambda: "Test Company"
	scm_roles.SCM_INVENTORY_ROLES = set()
	scm_roles.SCM_STOCK_UPDATE_ROLES = set()
	scm_roles.check_scm_permission = lambda *args, **kwargs: None

	_ensure_package("hrms")
	_ensure_package("hrms.utils")
	_register_module("frappe", frappe)
	_register_module("frappe.utils", utils)
	_register_module("hrms.utils.bei_config", bei_config)
	_register_module("hrms.utils.scm_roles", scm_roles)

	return frappe


def test_stock_count_type_mapping_prefers_external_auditor_role():
	_install_fake_frappe(["Store Staff", "External Auditor"])
	inventory = _load_module(ROOT / "hrms" / "api" / "inventory.py", "stock_count_roles_test")

	assert inventory._get_allowed_cycle_count_types() == [inventory.COUNT_TYPE_EXTERNAL_AUDIT]


def test_stock_count_type_mapping_matches_role_groups():
	_install_fake_frappe(["Warehouse User"])
	inventory = _load_module(ROOT / "hrms" / "api" / "inventory.py", "stock_count_warehouse_roles_test")
	assert inventory._get_allowed_cycle_count_types() == [
		inventory.COUNT_TYPE_WAREHOUSE_MONTHLY,
		inventory.COUNT_TYPE_SPOT_CHECK,
	]

	_install_fake_frappe(["Store Supervisor"])
	inventory = _load_module(ROOT / "hrms" / "api" / "inventory.py", "stock_count_supervisor_roles_test")
	assert inventory._get_allowed_cycle_count_types() == [
		inventory.COUNT_TYPE_STORE_MONTHLY,
		inventory.COUNT_TYPE_SPOT_CHECK,
	]

	_install_fake_frappe(["HQ User"])
	inventory = _load_module(ROOT / "hrms" / "api" / "inventory.py", "stock_count_hq_roles_test")
	assert inventory._get_allowed_cycle_count_types() == list(inventory.ALL_CYCLE_COUNT_TYPES)


def test_validate_cycle_count_type_rejects_unknown_and_forbidden_types():
	frappe = _install_fake_frappe(["Store Staff"])
	inventory = _load_module(ROOT / "hrms" / "api" / "inventory.py", "stock_count_validation_test")

	with pytest.raises(frappe.ValidationError):
		inventory._validate_cycle_count_type("Imaginary Count")

	with pytest.raises(frappe.PermissionError):
		inventory._validate_cycle_count_type(inventory.COUNT_TYPE_EXTERNAL_AUDIT)

	assert (
		inventory._validate_cycle_count_type(inventory.COUNT_TYPE_STORE_MONTHLY)
		== inventory.COUNT_TYPE_STORE_MONTHLY
	)


def test_get_assigned_stores_returns_count_type_metadata_for_store_staff():
	_install_fake_frappe(["Store Staff"])
	inventory = _load_module(ROOT / "hrms" / "api" / "inventory.py", "stock_count_assigned_stores_test")

	inventory.frappe.db = types.SimpleNamespace(
		get_value=lambda doctype, filters, fieldname: "TEST-STORE-BGC"
	)
	inventory._resolve_warehouse = lambda branch: f"{branch} - BEI"

	result = inventory.get_assigned_stores()

	assert result["stores"] == [{"store": "TEST-STORE-BGC - BEI", "store_name": "TEST-STORE-BGC"}]
	assert result["allowed_count_types"] == [inventory.COUNT_TYPE_STORE_MONTHLY]
	assert result["default_count_type"] == inventory.COUNT_TYPE_STORE_MONTHLY
