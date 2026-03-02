import importlib.util
import pathlib
import sys
import types
from datetime import date, datetime

import pytest


def _install_stubs():
	frappe = types.ModuleType("frappe")

	class _DB:
		@staticmethod
		def exists(doctype, filters=None):
			if doctype == "BEI Store Order":
				return "BEI-ORD-EXISTING"
			return False

		@staticmethod
		def get_single_value(*args, **kwargs):
			return None

	class _OrderDoc:
		def __init__(self):
			self.name = "BEI-ORD-TEST-0001"
			self.status = "Pending Approval"
			self.items = []

		def append(self, table, row):
			assert table == "items"
			self.items.append(row)

		def insert(self, ignore_permissions=False):
			return None

	def _flt(value, precision=None):
		num = float(value or 0)
		return round(num, precision) if precision is not None else num

	def _cint(value):
		return int(value or 0)

	def _getdate(value=None):
		if value in (None, ""):
			return date(2026, 3, 2)
		if isinstance(value, date):
			return value
		return datetime.strptime(str(value), "%Y-%m-%d").date()

	def _new_doc(doctype):
		if doctype == "BEI Store Order":
			return _OrderDoc()
		return types.SimpleNamespace(insert=lambda **kwargs: None)

	def _throw(msg, *args, **kwargs):
		raise RuntimeError(msg)

	frappe.db = _DB()
	frappe.local = types.SimpleNamespace(db=frappe.db)
	frappe.__dict__["db"] = frappe.local.db
	frappe.session = types.SimpleNamespace(user="test.supervisor@bebang.ph")
	frappe.PermissionError = RuntimeError
	frappe.log_error = lambda *args, **kwargs: None
	frappe.get_roles = lambda *args, **kwargs: ["Store Supervisor"]
	frappe.get_all = lambda *args, **kwargs: []
	frappe.get_meta = lambda _doctype: types.SimpleNamespace(has_field=lambda _field: False)
	frappe.new_doc = _new_doc
	frappe.parse_json = lambda payload: payload

	def _whitelist(fn=None, **kwargs):
		if fn is None:
			return lambda inner: inner
		return fn

	frappe.whitelist = _whitelist
	frappe.throw = _throw
	frappe._ = lambda msg: msg
	frappe.utils = types.SimpleNamespace(cint=_cint, now=lambda: "2026-03-02 09:00:00")

	utils = types.ModuleType("frappe.utils")
	utils.nowdate = lambda: "2026-03-02"
	utils.add_days = lambda _d, _n: "2026-03-03"
	utils.now_datetime = lambda: datetime(2026, 3, 2, 10, 0, 0)
	utils.flt = _flt
	utils.cint = _cint
	utils.getdate = _getdate

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils

	hrms_pkg = types.ModuleType("hrms")
	hrms_pkg.__path__ = []
	utils_pkg = types.ModuleType("hrms.utils")
	utils_pkg.__path__ = []
	bei_config = types.ModuleType("hrms.utils.bei_config")
	bei_config.get_company = lambda: "Bebang Enterprise Inc."

	scm_roles = types.ModuleType("hrms.utils.scm_roles")
	scm_roles.SCM_APPROVAL_ROLES = []
	scm_roles.check_scm_permission = lambda *args, **kwargs: None

	sys.modules["hrms"] = hrms_pkg
	sys.modules["hrms.utils"] = utils_pkg
	sys.modules["hrms.utils.bei_config"] = bei_config
	sys.modules["hrms.utils.scm_roles"] = scm_roles


def _load_store_module():
	_install_stubs()
	file_path = pathlib.Path(__file__).resolve().parents[1] / "api" / "store.py"
	spec = importlib.util.spec_from_file_location("s19_store_emergency_under_test", file_path)
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(module)
	module.resolve_warehouse = lambda store: store
	module._get_area_supervisor_for_store = lambda _warehouse: None
	module._notify_store_ops = lambda _msg: None
	return module


def test_non_emergency_duplicate_still_blocked():
	store_mod = _load_store_module()

	with pytest.raises(RuntimeError, match="An order already exists"):
		store_mod.submit_order(
			store="TEST-STORE-BGC",
			items=[{"item_code": "ITEM-001", "qty_requested": 1, "lane": "Dry"}],
			cargo_category="DRY",
			is_emergency=0,
		)


def test_emergency_duplicate_bypasses_duplicate_gate():
	store_mod = _load_store_module()

	result = store_mod.submit_order(
		store="TEST-STORE-BGC",
		items=[{"item_code": "ITEM-001", "qty_requested": 1, "lane": "Dry"}],
		cargo_category="DRY",
		is_emergency=1,
		notes="Emergency replenishment",
	)

	assert result["success"] is True
	assert result["status"] == "Pending Approval"
	assert result["cargo_category"] == "DRY"
