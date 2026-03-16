import importlib.util
import pathlib
import sys
import types
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_stubs():
	frappe = types.ModuleType("frappe")

	class _DB:
		@staticmethod
		def exists(*args, **kwargs):
			return None

		@staticmethod
		def get_value(*args, **kwargs):
			return None

		@staticmethod
		def get_single_value(*args, **kwargs):
			return None

	def _flt(value, precision=None):
		num = float(value or 0)
		return round(num, precision) if precision is not None else num

	def _cint(value):
		return int(value or 0)

	def _getdate(value=None):
		if value in (None, ""):
			return date(2026, 3, 13)
		if isinstance(value, date):
			return value
		return datetime.strptime(str(value), "%Y-%m-%d").date()

	def _get_datetime(value=None):
		if value in (None, ""):
			return datetime(2026, 3, 13, 10, 0, 0)
		if isinstance(value, datetime):
			return value
		return datetime.fromisoformat(str(value).replace("Z", "+00:00"))

	def _throw(msg, *args, **kwargs):
		raise RuntimeError(msg)

	def _whitelist(fn=None, **kwargs):
		if fn is None:
			return lambda inner: inner
		return fn

	frappe.local = types.SimpleNamespace(
		db=_DB(),
		session=types.SimpleNamespace(user="test.area@bebang.ph"),
	)
	frappe.__dict__["db"] = frappe.local.db
	frappe.__dict__["session"] = frappe.local.session
	frappe.PermissionError = RuntimeError
	frappe.log_error = lambda *args, **kwargs: None
	frappe.get_roles = lambda *args, **kwargs: ["Store Supervisor"]
	frappe.get_all = lambda *args, **kwargs: []
	frappe.get_meta = lambda _doctype: types.SimpleNamespace(has_field=lambda _field: False)
	frappe.new_doc = lambda doctype: None
	frappe.get_doc = lambda *args, **kwargs: None
	frappe.parse_json = lambda payload: payload
	frappe.throw = _throw
	frappe.whitelist = _whitelist
	frappe._ = lambda msg: msg
	frappe.utils = types.SimpleNamespace(cint=_cint, now=lambda: "2026-03-13 10:00:00")

	utils = types.ModuleType("frappe.utils")
	utils.nowdate = lambda: "2026-03-13"
	utils.add_days = lambda _d, _n: "2026-03-14"
	utils.now_datetime = lambda: datetime(2026, 3, 13, 10, 0, 0)
	utils.flt = _flt
	utils.cint = _cint
	utils.getdate = _getdate
	utils.get_datetime = _get_datetime

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils

	hrms_pkg = types.ModuleType("hrms")
	hrms_pkg.__path__ = []
	utils_pkg = types.ModuleType("hrms.utils")
	utils_pkg.__path__ = []
	bei_config = types.ModuleType("hrms.utils.bei_config")
	bei_config.SPACE_OPS = "OPS"
	bei_config.get_chat_space = lambda _space: "spaces/AAAAvDZdY-o"
	bei_config.get_company = lambda: "Bebang Enterprise Inc."

	scm_roles = types.ModuleType("hrms.utils.scm_roles")
	scm_roles.SCM_APPROVAL_ROLES = []
	scm_roles.check_scm_permission = lambda *args, **kwargs: None

	supply_chain_contracts = types.ModuleType("hrms.utils.supply_chain_contracts")
	supply_chain_contracts.FINANCE_TREATMENT_INTERCOMPANY = "intercompany"
	supply_chain_contracts.FINANCE_TREATMENT_SAME_COMPANY = "same_company"
	supply_chain_contracts.REQUEST_SOURCE_STORE_DISPOSAL = "store_disposal"
	supply_chain_contracts.REQUEST_SOURCE_STORE_ORDER = "store_order"
	supply_chain_contracts.REQUEST_SOURCE_STORE_RETURN = "store_return"
	supply_chain_contracts.infer_finance_treatment = lambda *args, **kwargs: None
	supply_chain_contracts.resolve_material_request_contract = lambda *args, **kwargs: {}
	supply_chain_contracts.resolve_route_source_warehouse = lambda *args, **kwargs: None
	supply_chain_contracts.resolve_store_buyer_entity = lambda *args, **kwargs: None
	supply_chain_contracts.resolve_warehouse_company = lambda *args, **kwargs: "Bebang Enterprise Inc."
	supply_chain_contracts.stamp_material_request_contract = lambda *args, **kwargs: None
	supply_chain_contracts.stamp_stock_entry_contract = lambda *args, **kwargs: None

	sys.modules["hrms"] = hrms_pkg
	sys.modules["hrms.utils"] = utils_pkg
	sys.modules["hrms.utils.bei_config"] = bei_config
	sys.modules["hrms.utils.scm_roles"] = scm_roles
	sys.modules["hrms.utils.supply_chain_contracts"] = supply_chain_contracts


def _load_store_module():
	_install_stubs()
	file_path = ROOT / "hrms" / "api" / "store.py"
	spec = importlib.util.spec_from_file_location("store_order_approval_under_test", file_path)
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(module)
	return module


class _FakeOrder:
	def __init__(
		self,
		name="BEI-ORD-TEST-0001",
		status="Pending Approval",
		is_emergency=1,
		store_name="TEST-STORE - BEI",
		creation="2026-03-03 12:30:00",
	):
		self.name = name
		self.status = status
		self.is_emergency = is_emergency
		self.store = store_name
		self.creation = creation
		self.approved_by = None
		self.approved_at = None
		self.items = [
			SimpleNamespace(item_code="ITEM-001", qty_requested=3, qty_approved=0),
			SimpleNamespace(item_code="ITEM-002", qty_requested=5, qty_approved=0),
		]
		self._save_count = 0

	def save(self, ignore_permissions=True):
		self._save_count += 1


class _FakeQueueDoc:
	def __init__(self, name):
		self.name = name
		self.status = "Pending"
		self.approved_by = None
		self.approved_at = None
		self._save_count = 0

	def save(self, ignore_permissions=True):
		self._save_count += 1


def test_resolve_routing_prefers_area_supervisor():
	store_mod = _load_store_module()
	with patch.object(store_mod, "_get_area_supervisor_for_store", return_value="test.area@bebang.ph"), patch.object(
		store_mod, "_get_order_approval_fallback_user", return_value="edlice@bebang.ph"
	):
		routing = store_mod._resolve_order_approval_routing(
			warehouse="TEST-STORE - BEI",
			is_emergency=1,
			submitted_after_cutoff=True,
		)

	assert routing["first_source"] == "area_supervisor"
	assert routing["first_approver"] == "test.area@bebang.ph"


def test_resolve_routing_falls_back_when_area_is_unmapped():
	store_mod = _load_store_module()
	with patch.object(store_mod, "_get_area_supervisor_for_store", return_value=None), patch.object(
		store_mod, "_get_order_approval_fallback_user", return_value="edlice@bebang.ph"
	):
		routing = store_mod._resolve_order_approval_routing(
			warehouse="TEST-STORE - BEI",
			is_emergency=1,
			submitted_after_cutoff=True,
		)

	assert routing["first_source"] == "fallback_approver"
	assert routing["first_approver"] == "edlice@bebang.ph"


def test_approve_order_area_supervisor_finalizes_order():
	store_mod = _load_store_module()
	fake_order = _FakeOrder()
	fake_queue_doc = _FakeQueueDoc("BEI-APQ-AREA-0001")
	store_mod.frappe.session.user = "test.area@bebang.ph"

	def fake_get_doc(doctype, name):
		if doctype == "BEI Store Order":
			return fake_order
		if doctype == "BEI Approval Queue":
			return fake_queue_doc
		raise AssertionError(f"Unexpected get_doc call: {doctype} / {name}")

	with patch.object(store_mod.frappe, "get_doc", side_effect=fake_get_doc), patch.object(
		store_mod,
		"_get_pending_approval_entries",
		return_value=[
			{
				"name": "BEI-APQ-AREA-0001",
				"assigned_approver": "test.area@bebang.ph",
			}
		],
	), patch.object(store_mod, "_is_system_approver", return_value=False), patch.object(
		store_mod, "_get_area_supervisor_for_store", return_value="test.area@bebang.ph"
	), patch.object(
		store_mod, "_get_order_approval_fallback_user", return_value="edlice@bebang.ph"
	), patch.object(
		store_mod, "_notify_store_ops"
	), patch.object(
		store_mod, "_close_order_assignments"
	), patch.object(
		store_mod, "_append_order_comment"
	) as append_comment, patch.object(
		store_mod, "_create_mr_for_store_order", return_value="MAT-MR-0001"
	) as create_mr:
		result = store_mod.approve_order(
			order_name=fake_order.name,
			approved_quantities=[{"item_code": "ITEM-001", "qty_approved": 2}],
		)

	assert result["success"] is True
	assert result["stage"] == "area_supervisor"
	assert result["status"] == "Approved"
	assert result["material_request"] == "MAT-MR-0001"
	assert result["fallback_override"] is False
	assert fake_order.status == "Approved"
	assert fake_order.approved_by == "test.area@bebang.ph"
	assert fake_queue_doc.status == "Approved"
	assert fake_queue_doc.approved_by == "test.area@bebang.ph"
	assert create_mr.call_count == 1
	assert append_comment.called is False


def test_approve_order_fallback_override_finalizes_order():
	store_mod = _load_store_module()
	fake_order = _FakeOrder()
	fake_queue_doc = _FakeQueueDoc("BEI-APQ-AREA-0001")
	store_mod.frappe.session.user = "edlice@bebang.ph"

	def fake_get_doc(doctype, name):
		if doctype == "BEI Store Order":
			return fake_order
		if doctype == "BEI Approval Queue":
			return fake_queue_doc
		raise AssertionError(f"Unexpected get_doc call: {doctype} / {name}")

	with patch.object(store_mod.frappe, "get_doc", side_effect=fake_get_doc), patch.object(
		store_mod,
		"_get_pending_approval_entries",
		return_value=[
			{
				"name": "BEI-APQ-AREA-0001",
				"assigned_approver": "test.area@bebang.ph",
			}
		],
	), patch.object(store_mod, "_is_system_approver", return_value=False), patch.object(
		store_mod, "_get_area_supervisor_for_store", return_value="test.area@bebang.ph"
	), patch.object(
		store_mod, "_get_order_approval_fallback_user", return_value="edlice@bebang.ph"
	), patch.object(
		store_mod, "_notify_store_ops"
	), patch.object(
		store_mod, "_close_order_assignments"
	), patch.object(
		store_mod, "_append_order_comment"
	) as append_comment, patch.object(
		store_mod, "_create_mr_for_store_order", return_value="MAT-MR-0001"
	) as create_mr:
		result = store_mod.approve_order(
			order_name=fake_order.name,
			approved_quantities=[{"item_code": "ITEM-001", "qty_approved": 2}],
		)

	assert result["success"] is True
	assert result["stage"] == "fallback_approver"
	assert result["status"] == "Approved"
	assert result["fallback_override"] is True
	assert fake_order.status == "Approved"
	assert fake_order.approved_by == "edlice@bebang.ph"
	assert fake_queue_doc.status == "Approved"
	assert fake_queue_doc.approved_by == "edlice@bebang.ph"
	assert create_mr.call_count == 1
	assert append_comment.call_count == 1
