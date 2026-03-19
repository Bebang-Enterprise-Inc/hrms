import importlib.util
import pathlib
import sys
import types

import pytest


def _install_stubs(query_capture, current_user, role_map, fallback_user="edlice@bebang.ph"):
	frappe = types.ModuleType("frappe")

	class _PermissionError(Exception):
		pass

	def _throw(message, exc=None):
		if exc:
			raise exc(message)
		raise Exception(message)

	frappe._ = lambda value: value
	frappe.whitelist = lambda fn=None, **kwargs: fn if fn else (lambda inner: inner)
	frappe.logger = lambda _name: types.SimpleNamespace(warning=lambda *args, **kwargs: None)
	frappe.parse_json = lambda payload: payload
	frappe.throw = _throw
	frappe.PermissionError = _PermissionError
	frappe.session = types.SimpleNamespace(user=current_user)
	frappe.get_roles = lambda user=None: role_map.get(user or current_user, [])

	class _DB:
		@staticmethod
		def sql(query, params=None, as_dict=False):
			query_capture.append(str(query))
			return []

	frappe.local = types.SimpleNamespace(db=_DB())
	frappe.__dict__["db"] = frappe.local.db

	utils = types.ModuleType("frappe.utils")
	utils.today = lambda: "2026-03-16"
	utils.now = lambda: "2026-03-16 09:00:00"
	utils.getdate = lambda value=None: value or "2026-03-16"
	utils.get_time = lambda value=None: value or "09:00:00"
	utils.nowdate = lambda: "2026-03-16"
	utils.now_datetime = lambda: "2026-03-16 09:00:00"

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils

	hrms_pkg = types.ModuleType("hrms")
	hrms_pkg.__path__ = []
	api_pkg = types.ModuleType("hrms.api")
	api_pkg.__path__ = []
	utils_pkg = types.ModuleType("hrms.utils")
	utils_pkg.__path__ = []
	store_mod = types.ModuleType("hrms.api.store")
	store_mod._get_order_approval_fallback_user = lambda: fallback_user
	scm_roles = types.ModuleType("hrms.utils.scm_roles")
	scm_roles.ORDERING_STORE_ROLES = []
	scm_roles.ORDERING_WAREHOUSE_ROLES = [
		"Area Supervisor",
		"Warehouse Manager",
		"System Manager",
		"Administrator",
	]
	scm_roles.ORDERING_APPROVAL_ROLES = [
		"Area Supervisor",
		"Warehouse Manager",
		"System Manager",
		"Administrator",
	]
	scm_roles.check_scm_permission = lambda *args, **kwargs: None

	sys.modules["hrms"] = hrms_pkg
	sys.modules["hrms.api"] = api_pkg
	sys.modules["hrms.api.store"] = store_mod
	sys.modules["hrms.utils"] = utils_pkg
	sys.modules["hrms.utils.scm_roles"] = scm_roles

	return _PermissionError


def _load_module(query_capture, current_user, role_map, fallback_user="edlice@bebang.ph"):
	permission_error = _install_stubs(query_capture, current_user, role_map, fallback_user=fallback_user)
	file_path = pathlib.Path(__file__).resolve().parents[1] / "api" / "ordering.py"
	spec = importlib.util.spec_from_file_location("order_queue_permissions_under_test", file_path)
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(module)
	return module, permission_error


def test_fallback_approver_can_view_order_review_queue():
	queries = []
	ordering, _permission_error = _load_module(
		queries,
		current_user="edlice@bebang.ph",
		role_map={"edlice@bebang.ph": ["Regional Manager"]},
	)

	result = ordering.get_order_review_queue(date="2026-03-16", status="Pending Approval")

	assert queries, "Expected query execution in get_order_review_queue()"
	assert result["total"] == 0


def test_hr_tagged_supervisor_without_approval_role_is_denied():
	queries = []
	ordering, permission_error = _load_module(
		queries,
		current_user="test.supervisor@bebang.ph",
		role_map={"test.supervisor@bebang.ph": ["Store Supervisor", "HR User"]},
	)

	with pytest.raises(permission_error):
		ordering.get_order_review_queue(date="2026-03-16")

	assert not queries, "Permission failures should stop before the query executes"
