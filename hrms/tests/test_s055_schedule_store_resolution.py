import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_dependencies():
	frappe = sys.modules.get("frappe") or types.ModuleType("frappe")
	utils = sys.modules.get("frappe.utils") or types.ModuleType("frappe.utils")

	def whitelist(*args, **kwargs):
		def decorator(fn):
			return fn

		return decorator

	frappe.whitelist = getattr(frappe, "whitelist", whitelist)
	frappe._ = getattr(frappe, "_", lambda text: text)
	frappe.throw = getattr(
		frappe, "throw", lambda message, exc=None: (_ for _ in ()).throw(Exception(message))
	)
	frappe.PermissionError = getattr(
		frappe, "PermissionError", type("PermissionError", (Exception,), {})
	)
	frappe.ValidationError = getattr(
		frappe, "ValidationError", type("ValidationError", (Exception,), {})
	)
	frappe.__dict__.setdefault("local", types.SimpleNamespace())
	if not getattr(frappe.local, "db", None):
		frappe.local.db = types.SimpleNamespace(
			get_value=lambda *args, **kwargs: None,
			exists=lambda *args, **kwargs: False,
			table_exists=lambda *args, **kwargs: False,
			sql=lambda *args, **kwargs: [],
			has_column=lambda *args, **kwargs: False,
		)
	if not getattr(frappe.local, "session", None):
		frappe.local.session = types.SimpleNamespace(user="test.supervisor@bebang.ph")
	frappe.__dict__.setdefault("db", frappe.local.db)
	frappe.__dict__.setdefault("session", frappe.local.session)
	frappe.get_doc = getattr(frappe, "get_doc", lambda *args, **kwargs: None)
	frappe.delete_doc = getattr(frappe, "delete_doc", lambda *args, **kwargs: None)
	frappe.get_all = getattr(frappe, "get_all", lambda *args, **kwargs: [])
	frappe.get_roles = getattr(frappe, "get_roles", lambda *args, **kwargs: [])

	utils.add_days = getattr(utils, "add_days", lambda value, days: value)
	utils.cint = getattr(utils, "cint", lambda value: int(float(value or 0)))
	utils.flt = getattr(utils, "flt", lambda value: float(value or 0))
	utils.get_datetime = getattr(utils, "get_datetime", lambda value=None: value)
	utils.getdate = getattr(utils, "getdate", lambda value=None: value)
	utils.now_datetime = getattr(utils, "now_datetime", lambda: "2026-03-17 12:00:00")
	utils.nowdate = getattr(utils, "nowdate", lambda: "2026-03-17")

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils

	if "hrms" not in sys.modules:
		hrms_pkg = types.ModuleType("hrms")
		hrms_pkg.__path__ = []
		sys.modules["hrms"] = hrms_pkg

	if "hrms.api" not in sys.modules:
		hrms_api_pkg = types.ModuleType("hrms.api")
		hrms_api_pkg.__path__ = [str(ROOT / "hrms" / "api")]
		sys.modules["hrms.api"] = hrms_api_pkg

	if "hrms.utils" not in sys.modules:
		hrms_utils_pkg = types.ModuleType("hrms.utils")
		hrms_utils_pkg.__path__ = [str(ROOT / "hrms" / "utils")]
		sys.modules["hrms.utils"] = hrms_utils_pkg

	if "hrms.utils.bei_config" not in sys.modules:
		config_mod = types.ModuleType("hrms.utils.bei_config")
		config_mod.SPACE_OPS = "ops"
		config_mod.get_chat_space = lambda *args, **kwargs: "space"
		config_mod.get_company = lambda *args, **kwargs: "Bebang Enterprise Inc."
		sys.modules["hrms.utils.bei_config"] = config_mod

	if "hrms.utils.scm_roles" not in sys.modules:
		scm_mod = types.ModuleType("hrms.utils.scm_roles")
		scm_mod.SCM_APPROVAL_ROLES = set()
		scm_mod.check_scm_permission = lambda *args, **kwargs: True
		sys.modules["hrms.utils.scm_roles"] = scm_mod

	if "hrms.utils.supply_chain_contracts" not in sys.modules:
		contracts_mod = types.ModuleType("hrms.utils.supply_chain_contracts")
		contracts_mod.FINANCE_TREATMENT_INTERCOMPANY = "intercompany"
		contracts_mod.FINANCE_TREATMENT_SAME_COMPANY = "same_company"
		contracts_mod.REQUEST_SOURCE_STORE_DISPOSAL = "store_disposal"
		contracts_mod.REQUEST_SOURCE_STORE_ORDER = "store_order"
		contracts_mod.REQUEST_SOURCE_STORE_RETURN = "store_return"
		contracts_mod.get_preferred_commissary_warehouses = lambda *args, **kwargs: []
		contracts_mod.infer_finance_treatment = lambda *args, **kwargs: "same_company"
		contracts_mod.resolve_material_request_contract = lambda *args, **kwargs: {}
		contracts_mod.resolve_route_source_warehouse = lambda *args, **kwargs: None
		contracts_mod.resolve_store_buyer_entity = lambda *args, **kwargs: {}
		contracts_mod.resolve_warehouse_company = lambda *args, **kwargs: "Bebang Enterprise Inc."
		contracts_mod.stamp_material_request_contract = lambda *args, **kwargs: None
		contracts_mod.stamp_stock_entry_contract = lambda *args, **kwargs: None
		sys.modules["hrms.utils.supply_chain_contracts"] = contracts_mod


_install_fake_dependencies()
spec = importlib.util.spec_from_file_location(
	"store_under_test_s055",
	ROOT / "hrms" / "api" / "store.py",
)
store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(store)


class TestS055ScheduleStoreResolution(unittest.TestCase):
	def setUp(self):
		store.frappe.session.user = "test.supervisor@bebang.ph"
		store.frappe.get_all = MagicMock(return_value=[])
		store.frappe.get_roles = MagicMock(return_value=[])
		store.frappe.db.exists = MagicMock(return_value=False)
		store.frappe.db.get_value = MagicMock(return_value=None)

	def test_resolve_warehouse_maps_commissary_shaw_alias(self):
		store.frappe.db.exists = MagicMock(
			side_effect=lambda doctype, name=None: doctype == "Warehouse" and name == "Shaw BLVD - BKI"
		)
		store.frappe.db.get_value = MagicMock(return_value=None)

		self.assertEqual(store.resolve_warehouse("COMMISSARY SHAW"), "Shaw BLVD - BKI")

	def test_get_commissary_schedule_locations_avoids_department_field(self):
		warehouse_fields = {}

		def fake_get_all(doctype, **kwargs):
			if doctype == "Warehouse":
				warehouse_fields["fields"] = list(kwargs.get("fields") or [])
				return [
					{
						"name": "Shaw BLVD - BKI",
						"warehouse_name": "Shaw BLVD",
						"company": "Bebang Kitchen Inc.",
					}
				]
			return []

		store.frappe.get_all = MagicMock(side_effect=fake_get_all)
		with patch.object(
			store,
			"get_preferred_commissary_warehouses",
			return_value=("Shaw BLVD - BKI",),
		):
			result = store._get_commissary_schedule_locations()

		self.assertEqual(warehouse_fields["fields"], ["name", "warehouse_name", "company"])
		self.assertEqual(result[0]["department"], None)

	def test_get_user_store_store_schedule_uses_employee_context_for_hr_store_lead(self):
		active_employee = {
			"name": "TEST-SUPERVISOR-001",
			"branch": "TEST-STORE-BGC",
			"employee_name": "Test Supervisor",
			"reports_to": None,
			"designation": "Store Supervisor",
		}

		def fake_db_get_value(doctype, filters=None, fieldname=None, as_dict=False):
			if doctype == "Employee" and isinstance(filters, dict):
				return dict(active_employee)
			return None

		store.frappe.db.get_value = MagicMock(side_effect=fake_db_get_value)
		store.frappe.get_roles = MagicMock(return_value=["HR User"])

		with (
			patch.object(store, "_get_store_schedule_locations", return_value=[]),
			patch.object(
				store,
				"resolve_employee_store_context",
				return_value={
					"warehouse": "TEST-STORE-BGC - BEI",
					"warehouse_name": "TEST-STORE-BGC",
					"branch": "TEST-STORE-BGC",
				},
			),
		):
			result = store.get_user_store(surface="store_schedule")

		self.assertEqual(result["role"], "Store Supervisor")
		self.assertEqual(result["default_store"], "TEST-STORE-BGC - BEI")
		self.assertEqual(
			result["stores"],
			[{"name": "TEST-STORE-BGC - BEI", "warehouse_name": "TEST-STORE-BGC"}],
		)

	def test_get_store_schedule_locations_filters_polluted_mapping_and_unions_canonical_stores(self):
		def fake_table_exists(table_name):
			return table_name in {"tabBEI Warehouse Department Mapping", "tabBEI Store Type"}

		def fake_get_all(doctype, **kwargs):
			if doctype == "BEI Warehouse Department Mapping":
				return [
					{"warehouse": "3MD Logistics - Camangyanan", "department": "3MD Logistics", "store_type": ""},
					{"warehouse": "TEST-COMMISSARY - BKI", "department": "COMMISSARY SHAW", "store_type": ""},
					{"warehouse": "SM Bicutan - BEI", "department": "SM Bicutan", "store_type": "JV"},
				]
			if doctype == "BEI Store Type":
				return [
					{"store": "SM Bicutan", "store_type": "JV"},
					{"store": "TEST-STORE-BGC", "store_type": "Full Franchise"},
				]
			if doctype == "Warehouse":
				filters = kwargs.get("filters") or {}
				if "name" in filters:
					return [
						{
							"name": "3MD Logistics - Camangyanan",
							"warehouse_name": "3MD Logistics",
							"department": "3MD Logistics",
							"custom_area_supervisor": None,
						},
						{
							"name": "TEST-COMMISSARY - BKI",
							"warehouse_name": "TEST-COMMISSARY",
							"department": "COMMISSARY SHAW",
							"custom_area_supervisor": None,
						},
						{
							"name": "SM Bicutan - BEI",
							"warehouse_name": "SM Bicutan",
							"department": "SM Bicutan",
							"custom_area_supervisor": "test.area@bebang.ph",
						},
					]
				if "department" in filters:
					return [
						{
							"name": "SM Bicutan - BEI",
							"warehouse_name": "SM Bicutan",
							"department": "SM Bicutan",
							"custom_area_supervisor": "test.area@bebang.ph",
						},
						{
							"name": "TEST-STORE-BGC - BEI",
							"warehouse_name": "TEST-STORE-BGC",
							"department": "TEST-STORE-BGC",
							"custom_area_supervisor": "test.area@bebang.ph",
						},
					]
			return []

		store.frappe.db.table_exists = MagicMock(side_effect=fake_table_exists)
		store.frappe.get_all = MagicMock(side_effect=fake_get_all)

		result = store._get_store_schedule_locations()

		self.assertEqual(
			result,
			[
				{
					"name": "SM Bicutan - BEI",
					"warehouse_name": "SM Bicutan",
					"department": "SM Bicutan",
					"store_type": "JV",
					"custom_area_supervisor": "test.area@bebang.ph",
				},
				{
					"name": "TEST-STORE-BGC - BEI",
					"warehouse_name": "TEST-STORE-BGC",
					"department": "TEST-STORE-BGC",
					"store_type": "Full Franchise",
					"custom_area_supervisor": "test.area@bebang.ph",
				},
			],
		)

	def test_get_user_store_store_schedule_system_user_uses_filtered_schedule_rows(self):
		store.frappe.session.user = "sam@bebang.ph"
		store.frappe.get_roles = MagicMock(return_value=["System Manager"])
		store.frappe.db.get_value = MagicMock(return_value=None)

		with patch.object(
			store,
			"_get_store_schedule_locations",
			return_value=[
				{"name": "SM Bicutan - BEI", "warehouse_name": "SM Bicutan"},
				{"name": "TEST-STORE-BGC - BEI", "warehouse_name": "TEST-STORE-BGC"},
			],
		):
			result = store.get_user_store(surface="store_schedule")

		self.assertEqual(result["role"], "HR User")
		self.assertEqual(result["default_store"], "SM Bicutan - BEI")
		self.assertEqual(
			result["stores"],
			[
				{"name": "SM Bicutan - BEI", "warehouse_name": "SM Bicutan"},
				{"name": "TEST-STORE-BGC - BEI", "warehouse_name": "TEST-STORE-BGC"},
			],
		)

	def test_get_user_store_area_designation_filters_to_schedule_locations(self):
		active_employee = {
			"name": "TEST-AREA-001",
			"branch": "TEST-STORE-BGC",
			"employee_name": "Test Area Supervisor",
			"reports_to": None,
			"designation": "Area Supervisor",
		}

		def fake_db_get_value(doctype, filters=None, fieldname=None, as_dict=False):
			if doctype == "Employee" and isinstance(filters, dict):
				return dict(active_employee)
			return None

		def fake_get_all(doctype, **kwargs):
			if doctype == "Warehouse":
				return [
					{"name": "3MD Logistics - Camangyanan", "warehouse_name": "3MD Logistics"},
					{"name": "TEST-STORE-BGC - BEI", "warehouse_name": "TEST-STORE-BGC"},
					{"name": "TEST-STORE-MOA - BEI", "warehouse_name": "TEST-STORE-MOA"},
				]
			return []

		store.frappe.db.get_value = MagicMock(side_effect=fake_db_get_value)
		store.frappe.get_all = MagicMock(side_effect=fake_get_all)
		store.frappe.get_roles = MagicMock(return_value=["HR User"])

		with patch.object(
			store,
			"_get_store_schedule_locations",
			return_value=[
				{"name": "TEST-STORE-BGC - BEI", "warehouse_name": "TEST-STORE-BGC"},
				{"name": "TEST-STORE-MOA - BEI", "warehouse_name": "TEST-STORE-MOA"},
			],
		):
			result = store.get_user_store(surface="store_schedule")

		self.assertEqual(result["role"], "Area Supervisor")
		self.assertEqual(
			result["stores"],
			[
				{"name": "TEST-STORE-BGC - BEI", "warehouse_name": "TEST-STORE-BGC"},
				{"name": "TEST-STORE-MOA - BEI", "warehouse_name": "TEST-STORE-MOA"},
			],
		)

	def test_get_user_store_hybrid_area_and_system_user_unions_schedule_rows(self):
		active_employee = {
			"name": "TEST-AREA-001",
			"branch": "Araneta Gateway",
			"employee_name": "Sam Tester",
			"reports_to": None,
			"designation": "Area Supervisor",
		}

		def fake_db_get_value(doctype, filters=None, fieldname=None, as_dict=False):
			if doctype == "Employee" and isinstance(filters, dict):
				return dict(active_employee)
			return None

		def fake_get_all(doctype, **kwargs):
			if doctype == "Warehouse":
				return [{"name": "Araneta Gateway - Bebang Enterprise Inc.", "warehouse_name": "Araneta Gateway"}]
			return []

		store.frappe.session.user = "sam@bebang.ph"
		store.frappe.db.get_value = MagicMock(side_effect=fake_db_get_value)
		store.frappe.get_all = MagicMock(side_effect=fake_get_all)
		store.frappe.get_roles = MagicMock(return_value=["Area Supervisor", "System Manager", "HR User"])

		with patch.object(
			store,
			"_get_store_schedule_locations",
			return_value=[
				{"name": "Araneta Gateway - Bebang Enterprise Inc.", "warehouse_name": "Araneta Gateway"},
				{"name": "TEST-STORE-BGC - BEI", "warehouse_name": "TEST-STORE-BGC"},
			],
		):
			result = store.get_user_store(surface="store_schedule")

		self.assertEqual(result["role"], "Area Supervisor")
		self.assertEqual(
			result["stores"],
			[
				{"name": "Araneta Gateway - Bebang Enterprise Inc.", "warehouse_name": "Araneta Gateway"},
				{"name": "TEST-STORE-BGC - BEI", "warehouse_name": "TEST-STORE-BGC"},
			],
		)

	def test_get_user_store_commissary_schedule_uses_employee_context_with_warehouse_role(self):
		active_employee = {
			"name": "TEST-COMMISSARY-001",
			"branch": "COMMISSARY SHAW",
			"employee_name": "Test Commissary Supervisor",
			"reports_to": None,
			"designation": "Commissary Supervisor",
		}

		def fake_db_get_value(doctype, filters=None, fieldname=None, as_dict=False):
			if doctype == "Employee" and isinstance(filters, dict):
				return dict(active_employee)
			return None

		store.frappe.session.user = "test.commissary@bebang.ph"
		store.frappe.db.get_value = MagicMock(side_effect=fake_db_get_value)
		store.frappe.get_roles = MagicMock(return_value=["Warehouse User"])

		with (
			patch.object(store, "_get_commissary_schedule_locations", return_value=[]),
			patch.object(
				store,
				"resolve_employee_store_context",
				return_value={
					"warehouse": "Shaw BLVD - BKI",
					"warehouse_name": "Shaw BLVD",
					"branch": "COMMISSARY SHAW",
				},
			),
		):
			result = store.get_user_store(surface="commissary_schedule")

		self.assertEqual(result["role"], "Warehouse User")
		self.assertEqual(result["default_store"], "Shaw BLVD - BKI")
		self.assertEqual(result["stores"], [{"name": "Shaw BLVD - BKI", "warehouse_name": "Shaw BLVD"}])


if __name__ == "__main__":
	unittest.main()
