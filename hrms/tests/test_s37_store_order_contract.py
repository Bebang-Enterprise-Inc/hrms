import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


class _FakeFrappe(types.ModuleType):
	def __getattr__(self, name):
		if name == "db":
			return self.local.db
		if name == "session":
			return self.local.session
		raise AttributeError(name)


class _FakeMaterialRequest:
	def __init__(self):
		self.doctype = "Material Request"
		self.name = "MAT-REQ-TEST-0001"
		self.material_request_type = None
		self.company = None
		self.transaction_date = None
		self.schedule_date = None
		self.custom_store_order = None
		self.set_warehouse = None
		self.remarks = None
		self.items = []
		self.insert_called = False
		self.submit_called = False

	def append(self, table, row):
		self.items.append(types.SimpleNamespace(**row))

	def insert(self, ignore_permissions=True):
		self.insert_called = True

	def submit(self):
		self.submit_called = True


_DOCS_CREATED: list[_FakeMaterialRequest] = []


def _install_fake_modules():
	if "frappe" not in sys.modules:
		frappe = _FakeFrappe("frappe")
		utils = types.ModuleType("frappe.utils")

		def whitelist(*args, **kwargs):
			def decorator(fn):
				return fn

			return decorator

		frappe.whitelist = whitelist
		frappe._ = lambda text: text
		frappe.throw = lambda message, exc=None, title=None: (_ for _ in ()).throw(Exception(message))
		frappe.log_error = lambda *args, **kwargs: None
		frappe.local = types.SimpleNamespace(
			db=types.SimpleNamespace(
				exists=lambda doctype, value: False,
				get_value=lambda *args, **kwargs: None,
				has_column=lambda doctype, fieldname: False,
			),
			session=types.SimpleNamespace(user="test.regional@bebang.ph"),
		)

		def _new_doc(doctype):
			doc = _FakeMaterialRequest()
			_DOCS_CREATED.append(doc)
			return doc

		frappe.new_doc = _new_doc
		frappe.get_doc = lambda *args, **kwargs: None
		frappe.get_all = lambda *args, **kwargs: []
		frappe.get_roles = lambda user=None: ["Regional Manager"]
		frappe.utils = utils

		utils.add_days = lambda date, days: "2026-03-13"
		utils.cint = lambda value: int(value or 0)
		utils.flt = lambda value, precision=None: float(value or 0)
		utils.get_datetime = lambda value=None: value
		utils.getdate = lambda value=None: value
		utils.now_datetime = lambda: "2026-03-12 09:00:00"
		utils.nowdate = lambda: "2026-03-12"

		sys.modules["frappe"] = frappe
		sys.modules["frappe.utils"] = utils

	if "hrms" not in sys.modules:
		hrms_pkg = types.ModuleType("hrms")
		hrms_pkg.__path__ = []
		sys.modules["hrms"] = hrms_pkg

	if "hrms.utils" not in sys.modules:
		hrms_utils_pkg = types.ModuleType("hrms.utils")
		hrms_utils_pkg.__path__ = []
		sys.modules["hrms.utils"] = hrms_utils_pkg

	if "hrms.utils.bei_config" not in sys.modules:
		bei_config_mod = types.ModuleType("hrms.utils.bei_config")
		bei_config_mod.SPACE_OPS = "OPS"
		bei_config_mod.get_chat_space = lambda key=None: None
		bei_config_mod.get_company = lambda: "Bebang Enterprise Inc."
		sys.modules["hrms.utils.bei_config"] = bei_config_mod

	if "hrms.utils.scm_roles" not in sys.modules:
		scm_roles_mod = types.ModuleType("hrms.utils.scm_roles")
		scm_roles_mod.SCM_APPROVAL_ROLES = ["Regional Manager"]
		scm_roles_mod.check_scm_permission = lambda roles, action: None
		sys.modules["hrms.utils.scm_roles"] = scm_roles_mod

	if "hrms.utils.supply_chain_contracts" not in sys.modules:
		contracts_spec = importlib.util.spec_from_file_location(
			"hrms.utils.supply_chain_contracts",
			ROOT / "hrms" / "utils" / "supply_chain_contracts.py",
		)
		contracts_mod = importlib.util.module_from_spec(contracts_spec)
		contracts_spec.loader.exec_module(contracts_mod)
		sys.modules["hrms.utils.supply_chain_contracts"] = contracts_mod


_install_fake_modules()

store_spec = importlib.util.spec_from_file_location(
	"store_under_test",
	ROOT / "hrms" / "api" / "store.py",
)
store = importlib.util.module_from_spec(store_spec)
store_spec.loader.exec_module(store)


class TestS37StoreOrderContract(unittest.TestCase):
	def test_create_mr_for_store_order_sets_destination_and_source_warehouse(self):
		_DOCS_CREATED.clear()
		order = types.SimpleNamespace(
			name="BEI-ORD-TEST-0001",
			store="STORE-A - BEI",
			cargo_category="DRY",
			items=[
				types.SimpleNamespace(
					item_code="ITEM-001", item_name="Item 1", qty_requested=3, qty_approved=2, uom="Nos"
				),
				types.SimpleNamespace(
					item_code="ITEM-002", item_name="Item 2", qty_requested=1, qty_approved=1, uom="Nos"
				),
			],
		)

		original_resolver = store._resolve_store_order_source_warehouse
		original_stamper = store.stamp_material_request_contract
		try:
			store._resolve_store_order_source_warehouse = (
				lambda store_warehouse, cargo_category: "DRY-WH - BEI"
			)
			stamp_calls = []

			def _stamp(doc, **kwargs):
				stamp_calls.append(kwargs)

			store.stamp_material_request_contract = _stamp
			mr_name = store._create_mr_for_store_order(order)
		finally:
			store._resolve_store_order_source_warehouse = original_resolver
			store.stamp_material_request_contract = original_stamper

		self.assertEqual(mr_name, "MAT-REQ-TEST-0001")
		self.assertEqual(len(_DOCS_CREATED), 1)
		created = _DOCS_CREATED[0]
		self.assertEqual(created.material_request_type, "Material Transfer")
		self.assertEqual(created.set_warehouse, "STORE-A - BEI")
		self.assertEqual(created.custom_store_order, "BEI-ORD-TEST-0001")
		self.assertTrue(created.insert_called)
		self.assertTrue(created.submit_called)
		self.assertEqual(created.items[0].warehouse, "STORE-A - BEI")
		self.assertEqual(created.items[0].from_warehouse, "DRY-WH - BEI")
		self.assertEqual(stamp_calls[0]["request_source"], "store_order")
		self.assertEqual(stamp_calls[0]["cargo_lane"], "DRY")
		self.assertEqual(stamp_calls[0]["source_warehouse"], "DRY-WH - BEI")
		self.assertEqual(stamp_calls[0]["destination_warehouse"], "STORE-A - BEI")

	def test_create_mr_for_intercompany_store_order_preserves_real_destination_on_request(
		self,
	):
		_DOCS_CREATED.clear()
		order = types.SimpleNamespace(
			name="BEI-ORD-TEST-0002",
			store="STORE-B - BEI",
			cargo_category="DRY",
			items=[
				types.SimpleNamespace(
					item_code="ITEM-010", item_name="Item 10", qty_requested=5, qty_approved=4, uom="Nos"
				),
			],
		)

		original_resolver = store._resolve_store_order_source_warehouse
		original_stamper = store.stamp_material_request_contract
		try:
			store._resolve_store_order_source_warehouse = (
				lambda store_warehouse, cargo_category: "GREENHILLS - BKI"
			)
			stamp_calls = []

			def _stamp(doc, **kwargs):
				stamp_calls.append(kwargs)

			store.stamp_material_request_contract = _stamp
			mr_name = store._create_mr_for_store_order(order)
		finally:
			store._resolve_store_order_source_warehouse = original_resolver
			store.stamp_material_request_contract = original_stamper

		self.assertEqual(mr_name, "MAT-REQ-TEST-0001")
		created = _DOCS_CREATED[0]
		self.assertEqual(created.company, "Bebang Enterprise Inc.")
		self.assertEqual(created.set_warehouse, "STORE-B - BEI")
		self.assertEqual(created.items[0].warehouse, "STORE-B - BEI")
		self.assertEqual(created.items[0].from_warehouse, "GREENHILLS - BKI")
		self.assertEqual(stamp_calls[0]["destination_warehouse"], "STORE-B - BEI")
		self.assertEqual(stamp_calls[0]["source_company"], "Bebang Kitchen Inc.")
		self.assertEqual(stamp_calls[0]["target_company"], "Bebang Enterprise Inc.")
		self.assertEqual(stamp_calls[0]["finance_treatment"], "intercompany")

	def test_create_mr_for_store_order_uses_buyer_register_company_over_warehouse_suffix(self):
		_DOCS_CREATED.clear()
		order = types.SimpleNamespace(
			name="BEI-ORD-TEST-0003",
			store="STORE-C - BEI",
			cargo_category="FC",
			items=[
				types.SimpleNamespace(
					item_code="ITEM-020", item_name="Item 20", qty_requested=2, qty_approved=2, uom="Nos"
				),
			],
		)

		original_resolver = store._resolve_store_order_source_warehouse
		original_stamper = store.stamp_material_request_contract
		original_buyer_resolver = store.resolve_store_buyer_entity
		try:
			store._resolve_store_order_source_warehouse = (
				lambda store_warehouse, cargo_category: "SHAW BLVD - BKI"
			)
			store.resolve_store_buyer_entity = lambda warehouse_docname=None, store_name=None: {
				"buyer_entity_name": "Day Ones Food and Drink Establishments Corp."
			}
			stamp_calls = []

			def _stamp(doc, **kwargs):
				stamp_calls.append(kwargs)

			store.stamp_material_request_contract = _stamp
			mr_name = store._create_mr_for_store_order(order)
		finally:
			store._resolve_store_order_source_warehouse = original_resolver
			store.stamp_material_request_contract = original_stamper
			store.resolve_store_buyer_entity = original_buyer_resolver

		self.assertEqual(mr_name, "MAT-REQ-TEST-0001")
		created = _DOCS_CREATED[0]
		self.assertEqual(created.company, "Bebang Enterprise Inc.")
		self.assertEqual(created.set_warehouse, "STORE-C - BEI")
		self.assertEqual(created.items[0].warehouse, "STORE-C - BEI")
		self.assertEqual(stamp_calls[0]["source_company"], "Bebang Kitchen Inc.")
		self.assertEqual(stamp_calls[0]["target_company"], "Day Ones Food and Drink Establishments Corp.")
		self.assertEqual(stamp_calls[0]["finance_treatment"], "intercompany")

	def test_resolve_store_return_destination_warehouse_uses_trip_route_source(self):
		original_exists = store.frappe.db.exists
		original_get_doc = store.frappe.get_doc
		original_get_value = store.frappe.db.get_value
		try:
			store.frappe.db.exists = lambda doctype, value: (
				(doctype == "BEI Distribution Trip" and value == "TRIP-001")
				or (doctype == "BEI Route" and value == "BEI-ROUTE-0001")
			)
			store.frappe.get_doc = lambda doctype, name=None: (
				types.SimpleNamespace(route="BEI-ROUTE-0001", route_name="North Dry")
				if doctype == "BEI Distribution Trip"
				else None
			)
			store.frappe.db.get_value = lambda doctype, filters, fieldname=None, order_by=None: (
				"DRY-WH - BEI" if doctype == "BEI Route" else None
			)

			destination = store._resolve_store_return_destination_warehouse(
				types.SimpleNamespace(trip="TRIP-001")
			)
		finally:
			store.frappe.db.exists = original_exists
			store.frappe.get_doc = original_get_doc
			store.frappe.db.get_value = original_get_value

		self.assertEqual(destination, "DRY-WH - BEI")


if __name__ == "__main__":
	unittest.main()
