from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


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


def _install_frappe_stub() -> None:
	frappe = types.ModuleType("frappe")

	def _translate(value):
		return value

	def _whitelist(*args, **kwargs):
		if args and callable(args[0]) and len(args) == 1 and not kwargs:
			return args[0]

		def decorator(function):
			return function

		return decorator

	frappe._ = _translate
	frappe.whitelist = _whitelist
	frappe.local = types.SimpleNamespace(
		db=types.SimpleNamespace(),
		session=types.SimpleNamespace(user="pytest@example.com"),
	)
	frappe.get_all = lambda *args, **kwargs: []
	frappe.get_roles = lambda *args, **kwargs: []
	frappe.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(Exception(message))
	frappe.log_error = lambda *args, **kwargs: None
	frappe.logger = lambda: types.SimpleNamespace(warning=lambda *args, **kwargs: None)
	frappe.has_permission = lambda *args, **kwargs: True
	frappe.new_doc = lambda *args, **kwargs: types.SimpleNamespace()
	frappe.get_doc = lambda *args, **kwargs: types.SimpleNamespace()
	frappe.publish_realtime = lambda *args, **kwargs: None
	frappe.get_traceback = lambda: ""

	def _frappe_getattr(name):
		if name == "session":
			return frappe.local.session
		if name == "db":
			return frappe.local.db
		raise AttributeError(name)

	frappe.__getattr__ = _frappe_getattr

	frappe.ValidationError = type("ValidationError", (Exception,), {})
	frappe.PermissionError = type("PermissionError", (Exception,), {})
	frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})

	frappe_utils = types.ModuleType("frappe.utils")
	frappe_utils.flt = lambda value=0, *args, **kwargs: float(value or 0)
	frappe_utils.now_datetime = lambda: None
	frappe_utils.get_first_day = lambda value: value
	frappe_utils.get_last_day = lambda value: value
	frappe_utils.nowdate = lambda: "2026-01-01"
	frappe_utils.getdate = lambda value: value

	frappe_model = types.ModuleType("frappe.model")
	frappe_model_document = types.ModuleType("frappe.model.document")

	class Document:
		pass

	frappe_model_document.Document = Document

	frappe.utils = frappe_utils
	frappe.model = frappe_model
	frappe_model.document = frappe_model_document

	_register_module("frappe", frappe)
	_register_module("frappe.utils", frappe_utils)
	_register_module("frappe.model", frappe_model)
	_register_module("frappe.model.document", frappe_model_document)


def _install_hrms_support_stubs() -> None:
	for package_name in (
		"hrms",
		"hrms.utils",
		"hrms.api",
		"hrms.hr",
		"hrms.hr.doctype",
		"hrms.hr.doctype.bei_store_type",
		"hrms.patches",
		"hrms.patches.v16_0",
	):
		_ensure_package(package_name)

	bei_config = types.ModuleType("hrms.utils.bei_config")
	bei_config.get_company = lambda: "Test Company"
	_register_module("hrms.utils.bei_config", bei_config)

	scm_roles = types.ModuleType("hrms.utils.scm_roles")
	scm_roles.RATE_MANAGEMENT_ROLES = ()
	scm_roles.SCM_BILLING_ROLES = ()
	scm_roles.check_scm_permission = lambda *args, **kwargs: None
	_register_module("hrms.utils.scm_roles", scm_roles)


def _load_module_from_path(module_name: str, relative_path: str):
	module_path = REPO_ROOT / relative_path
	spec = importlib.util.spec_from_file_location(module_name, module_path)
	if spec is None or spec.loader is None:
		raise RuntimeError(f"Unable to load module spec for {module_name} at {module_path}")

	module = importlib.util.module_from_spec(spec)
	_register_module(module_name, module)
	spec.loader.exec_module(module)
	return module


_install_frappe_stub()
_install_hrms_support_stubs()

store_type_module = _load_module_from_path(
	"hrms.hr.doctype.bei_store_type.bei_store_type",
	"hrms/hr/doctype/bei_store_type/bei_store_type.py",
)
billing_api = _load_module_from_path("hrms.api.billing", "hrms/api/billing.py")
store_type_patch = _load_module_from_path(
	"hrms.patches.v16_0.normalize_store_type_category_to_store_type",
	"hrms/patches/v16_0/normalize_store_type_category_to_store_type.py",
)

normalize_store_type = store_type_module.normalize_store_type
resolve_store_type = store_type_module.resolve_store_type


def test_normalize_store_type_contract_aliases():
	assert normalize_store_type("jv") == "JV"
	assert normalize_store_type("Joint Venture") == "JV"
	assert normalize_store_type("managed_franchise") == "Managed Franchise"
	assert normalize_store_type("full-franchise") == "Full Franchise"


def test_resolve_store_type_prefers_canonical_then_legacy():
	assert resolve_store_type("Managed Franchise", "joint venture") == "Managed Franchise"
	assert resolve_store_type("", "joint venture stores") == "JV"
	assert resolve_store_type(None, "full franchise") == "Full Franchise"


def test_billing_store_type_reader_supports_legacy_column(monkeypatch):
	lookup_calls = []

	class FakeDB:
		def get_table_columns(self, table_name):
			lookup_calls.append(table_name)
			assert table_name == "BEI Store Type"
			return ["name", "store", "store_type_category"]

	sample_rows = [
		{"store": "Store A", "store_type_category": "joint venture"},
		{"store": "Store B", "store_type_category": "managed_franchise"},
	]

	monkeypatch.setattr(billing_api.frappe, "db", FakeDB())
	monkeypatch.setattr(
		billing_api.frappe,
		"get_all",
		lambda *args, **kwargs: [dict(row) for row in sample_rows],
	)

	normalized_rows = billing_api._get_store_type_records()

	assert lookup_calls == ["BEI Store Type"]
	assert normalized_rows[0]["store_type"] == "JV"
	assert normalized_rows[1]["store_type"] == "Managed Franchise"


def test_billing_store_type_reader_falls_back_to_tab_table_lookup(monkeypatch):
	lookup_calls = []

	class FakeDB:
		def get_table_columns(self, table_name):
			lookup_calls.append(table_name)
			if table_name == "BEI Store Type":
				raise Exception("doctype signature unsupported")
			if table_name == "tabBEI Store Type":
				return ["name", "store", "store_type_category"]
			return []

	sample_rows = [{"store": "Store A", "store_type_category": "joint venture"}]

	monkeypatch.setattr(billing_api.frappe, "db", FakeDB())
	monkeypatch.setattr(
		billing_api.frappe,
		"get_all",
		lambda *args, **kwargs: [dict(row) for row in sample_rows],
	)

	normalized_rows = billing_api._get_store_type_records()

	assert lookup_calls == ["BEI Store Type", "tabBEI Store Type"]
	assert normalized_rows[0]["store_type"] == "JV"


def test_billing_store_type_reader_returns_empty_on_schema_lookup_failure(monkeypatch):
	class FakeDB:
		def get_table_columns(self, table_name):
			raise Exception(f"missing schema for {table_name}")

	monkeypatch.setattr(billing_api.frappe, "db", FakeDB())
	monkeypatch.setattr(
		billing_api.frappe,
		"get_all",
		lambda *args, **kwargs: (_ for _ in ()).throw(
			AssertionError("get_all must not run when schema lookup fails")
		),
	)

	assert billing_api._get_store_type_records() == []


def test_get_stores_without_rates_degrades_gracefully_on_schema_lookup_failure(monkeypatch):
	class FakeDB:
		def get_table_columns(self, table_name):
			raise Exception(f"missing schema for {table_name}")

		def sql(self, *args, **kwargs):
			return []

	monkeypatch.setattr(billing_api.frappe, "db", FakeDB())
	monkeypatch.setattr(
		billing_api.frappe,
		"get_all",
		lambda *args, **kwargs: (_ for _ in ()).throw(
			AssertionError("get_all must not run when schema lookup fails")
		),
	)

	assert billing_api.get_stores_without_rates() == []


def test_generate_monthly_billing_degrades_gracefully_on_schema_lookup_failure(monkeypatch):
	class FakeDB:
		def get_table_columns(self, table_name):
			raise Exception(f"missing schema for {table_name}")

	monkeypatch.setattr(billing_api.frappe, "db", FakeDB())
	monkeypatch.setattr(
		billing_api.frappe,
		"get_all",
		lambda *args, **kwargs: (_ for _ in ()).throw(
			AssertionError("get_all must not run when schema lookup fails")
		),
	)

	result = billing_api.generate_monthly_billing("2026-02")

	assert result["success"] is True
	assert result["generated"] == 0
	assert result["skipped"] == 0
	assert result["errors"] == []


def test_store_type_patch_is_idempotent_and_schema_safe(monkeypatch):
	class FakePatchDB:
		def __init__(self):
			self.columns = {
				"tabBEI Store Type": ["name", "store", "store_type_category"],
				"tabBEI Billing Schedule": ["name", "store_type"],
			}
			self.rows = {
				"tabBEI Store Type": [
					{"name": "ST-001", "store": "Store A", "store_type_category": "joint venture"},
				],
				"tabBEI Billing Schedule": [
					{"name": "BILL-001", "store_type": "managed-franchise"},
				],
			}
			self.commit_calls = 0

		def table_exists(self, table_name):
			return table_name in self.columns

		def get_table_columns(self, table_name):
			return list(self.columns.get(table_name, []))

		def sql(self, query, as_dict=False):
			table_name = query.split("FROM `", 1)[1].split("`", 1)[0]
			data = self.rows.get(table_name, [])
			if as_dict:
				return [dict(row) for row in data]
			return data

		def set_value(self, doctype, docname, fieldname, value, update_modified=False):
			table_name = f"tab{doctype}"
			for row in self.rows.get(table_name, []):
				if row["name"] == docname:
					row[fieldname] = value
					break

		def commit(self):
			self.commit_calls += 1

	fake_db = FakePatchDB()
	monkeypatch.setattr(store_type_patch.frappe, "db", fake_db)

	first_updates = store_type_patch.execute()
	second_updates = store_type_patch.execute()

	assert first_updates == 2
	assert second_updates == 0
	assert fake_db.commit_calls == 1

	assert fake_db.rows["tabBEI Store Type"][0]["store_type_category"] == "JV"
	assert fake_db.rows["tabBEI Billing Schedule"][0]["store_type"] == "Managed Franchise"
