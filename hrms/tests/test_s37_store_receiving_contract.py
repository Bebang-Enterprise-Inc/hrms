import importlib.util
import json
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


class _FakeStoreReceiving:
	def __init__(self):
		self.doctype = "BEI Store Receiving"
		self.name = "BEI-RCV-TEST-0001"
		self.store = None
		self.trip = None
		self.receiving_date = None
		self.receiver_1 = None
		self.receiver_1_signature = None
		self.receiver_2_signature = None
		self.driver_signature = None
		self.status = "In Progress"
		self.stock_entry = None
		self.items = []
		self.insert_called = False
		self.save_called = False

	def append(self, table, row):
		item = types.SimpleNamespace(**row)
		self.items.append(item)
		return item

	def insert(self, ignore_permissions=True):
		self.insert_called = True
		return self

	def save(self, ignore_permissions=True):
		self.save_called = True
		return self


class _FakeStockEntry:
	def __init__(self):
		self.doctype = "Stock Entry"
		self.name = "MAT-STE-STORE-0001"
		self.stock_entry_type = None
		self.company = None
		self.posting_date = None
		self.posting_time = None
		self.to_warehouse = None
		self.remarks = None
		self.items = []
		self.insert_called = False
		self.submit_called = False
		self.custom_request_source = None
		self.custom_cargo_lane = None
		self.custom_destination_warehouse = None
		self.custom_source_company = None
		self.custom_target_company = None
		self.custom_finance_treatment = None

	def append(self, table, row):
		self.items.append(types.SimpleNamespace(**row))

	def insert(self, ignore_permissions=True):
		self.insert_called = True
		return self

	def submit(self):
		self.submit_called = True
		return self


_DOCS_CREATED: list[object] = []
_WAREHOUSE_COMPANIES = {
	"Greenhills Ortigas - BKI": "Bebang Kitchen Inc.",
	"TEST-STORE-BGC - BEI": "Bebang Enterprise Inc.",
	"TEST-STORE-MAKATI - BEI": "Bebang Enterprise Inc.",
}


def _material_request_factory(finance_treatment: str):
	target_company = (
		"Bebang Enterprise Inc." if finance_treatment == "intercompany" else "Bebang Kitchen Inc."
	)
	destination_warehouse = (
		"TEST-STORE-BGC - BEI" if finance_treatment == "intercompany" else "Greenhills Ortigas - BKI"
	)
	return types.SimpleNamespace(
		custom_request_source="store_order",
		custom_cargo_lane="DRY",
		custom_source_warehouse="Greenhills Ortigas - BKI",
		custom_destination_warehouse=destination_warehouse,
		custom_source_company="Bebang Kitchen Inc.",
		custom_target_company=target_company,
		custom_finance_treatment=finance_treatment,
		custom_store_order="BEI-ORD-TEST-0001",
		set_warehouse=destination_warehouse,
		items=[],
	)


def _install_fake_modules():
	if "frappe" not in sys.modules:
		frappe = _FakeFrappe("frappe")
		utils = types.ModuleType("frappe.utils")

		def whitelist(*args, **kwargs):
			def decorator(fn):
				return fn

			return decorator

		def _throw(message, exc=None, title=None):
			raise Exception(message)

		frappe.whitelist = whitelist
		frappe._ = lambda text: text
		frappe.throw = _throw
		frappe.PermissionError = type("PermissionError", (Exception,), {})
		frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
		frappe.log_error = lambda *args, **kwargs: None
		frappe.get_traceback = lambda: "traceback"
		frappe.parse_json = json.loads
		frappe.local = types.SimpleNamespace(session=types.SimpleNamespace(user="test.staff@bebang.ph"))
		frappe.get_roles = lambda user=None: ["Store Staff"]

		def _exists(doctype, value):
			if doctype == "Warehouse":
				return value in _WAREHOUSE_COMPANIES
			if doctype == "BEI Distribution Trip":
				return value in {"TRIP-INTER", "TRIP-SAME"}
			if doctype == "BEI Route":
				return value == "BEI-ROUTE-0001"
			if doctype == "DocType":
				return value in {"BEI Trip Stop"}
			return False

		def _get_value(doctype, filters, fieldname=None, order_by=None, as_dict=False):
			if doctype == "Warehouse" and isinstance(filters, str):
				return _WAREHOUSE_COMPANIES.get(filters)
			if doctype == "BEI Trip Stop":
				return "BEI-ORD-TEST-0001"
			if doctype == "BEI Store Order":
				return "DRY"
			if doctype == "Material Request":
				return "MAT-REQ-TEST-0001"
			if doctype == "BEI Route":
				return "Greenhills Ortigas - BKI"
			return None

		frappe.local.db = types.SimpleNamespace(
			exists=_exists,
			get_value=_get_value,
			has_column=lambda doctype, fieldname: (
				(doctype == "BEI Store Receiving" and fieldname == "stock_entry")
				or (doctype == "Material Request" and fieldname == "custom_store_order")
				or (doctype == "Stock Entry" and fieldname.startswith("custom_"))
			),
		)

		def _new_doc(doctype):
			if doctype == "BEI Store Receiving":
				doc = _FakeStoreReceiving()
			elif doctype == "Stock Entry":
				doc = _FakeStockEntry()
			else:
				raise AssertionError(f"Unexpected doctype {doctype}")
			_DOCS_CREATED.append(doc)
			return doc

		def _get_doc(doctype, name=None):
			if doctype == "BEI Distribution Trip":
				return types.SimpleNamespace(route="BEI-ROUTE-0001", route_name="Dry Route")
			if doctype == "Material Request":
				finance_treatment = "intercompany" if name == "MAT-REQ-TEST-0001" else "same_company"
				return _material_request_factory(finance_treatment)
			if doctype == "Item":
				return types.SimpleNamespace(
					item_name=f"Item {name}",
					description=f"Desc {name}",
					stock_uom="Nos",
				)
			raise AssertionError(f"Unexpected get_doc {doctype} {name}")

		frappe.new_doc = _new_doc
		frappe.get_doc = _get_doc
		frappe.get_all = lambda *args, **kwargs: []
		frappe.utils = utils

		utils.add_days = lambda date, days: date
		utils.cint = lambda value: int(value or 0)
		utils.flt = lambda value, precision=None: float(value or 0)
		utils.get_datetime = lambda value=None: value
		utils.getdate = lambda value=None: value
		utils.now_datetime = lambda: "2026-03-12 12:00:00"
		utils.nowdate = lambda: "2026-03-12"
		utils.today = lambda: "2026-03-12"
		utils.nowtime = lambda: "12:00:00"

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
		bei_config_mod.get_company = lambda: "Bebang Enterprise Inc."
		sys.modules["hrms.utils.bei_config"] = bei_config_mod

	if "hrms.utils.scm_roles" not in sys.modules:
		scm_roles_mod = types.ModuleType("hrms.utils.scm_roles")
		scm_roles_mod.SCM_APPROVAL_ROLES = ["Store Staff"]
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


class TestS37StoreReceivingContract(unittest.TestCase):
	def setUp(self):
		_DOCS_CREATED.clear()

	def test_complete_receiving_posts_intercompany_stock_to_store(self):
		original_get_doc = store.frappe.get_doc
		try:
			store.frappe.get_doc = lambda doctype, name=None: (
				_material_request_factory("intercompany")
				if doctype == "Material Request"
				else original_get_doc(doctype, name)
			)

			result = store.complete_receiving(
				store="TEST-STORE-BGC - BEI",
				trip="TRIP-INTER",
				items=[
					{
						"item_code": "FG-001",
						"expected_qty": 5,
						"received_qty": 4,
						"check_condition": 1,
						"check_packaging": 1,
						"check_expiry": 1,
						"check_temperature": 1,
						"check_food_quality": 1,
						"has_issue": 1,
					}
				],
			)
		finally:
			store.frappe.get_doc = original_get_doc

		self.assertTrue(result["success"])
		self.assertEqual(result["receiving"], "BEI-RCV-TEST-0001")
		self.assertEqual(result["stock_entry"], "MAT-STE-STORE-0001")
		self.assertEqual(len(_DOCS_CREATED), 2)

		receiving = _DOCS_CREATED[0]
		stock_entry = _DOCS_CREATED[1]
		self.assertTrue(receiving.insert_called)
		self.assertTrue(receiving.save_called)
		self.assertEqual(receiving.stock_entry, "MAT-STE-STORE-0001")
		self.assertEqual(stock_entry.stock_entry_type, "Material Receipt")
		self.assertEqual(stock_entry.company, "Bebang Enterprise Inc.")
		self.assertEqual(stock_entry.to_warehouse, "TEST-STORE-BGC - BEI")
		self.assertEqual(stock_entry.custom_request_source, "store_order")
		self.assertEqual(stock_entry.custom_source_company, "Bebang Kitchen Inc.")
		self.assertEqual(stock_entry.custom_target_company, "Bebang Enterprise Inc.")
		self.assertEqual(stock_entry.custom_finance_treatment, "intercompany")
		self.assertTrue(stock_entry.insert_called)
		self.assertTrue(stock_entry.submit_called)
		self.assertEqual(len(stock_entry.items), 1)
		self.assertEqual(stock_entry.items[0].item_code, "FG-001")
		self.assertEqual(stock_entry.items[0].qty, 4)
		self.assertEqual(stock_entry.items[0].t_warehouse, "TEST-STORE-BGC - BEI")

	def test_complete_receiving_skips_duplicate_stock_posting_for_same_company(self):
		original_get_doc = store.frappe.get_doc
		try:
			store.frappe.get_doc = lambda doctype, name=None: (
				_material_request_factory("same_company")
				if doctype == "Material Request"
				else original_get_doc(doctype, name)
			)

			result = store.complete_receiving(
				store="TEST-STORE-BGC - BEI",
				trip="TRIP-SAME",
				items=[
					{
						"item_code": "FG-002",
						"expected_qty": 3,
						"received_qty": 3,
						"check_condition": 1,
						"check_packaging": 1,
						"check_expiry": 1,
						"check_temperature": 1,
						"check_food_quality": 1,
						"has_issue": 0,
					}
				],
			)
		finally:
			store.frappe.get_doc = original_get_doc

		self.assertTrue(result["success"])
		self.assertNotIn("stock_entry", result)
		self.assertEqual(len(_DOCS_CREATED), 1)
		receiving = _DOCS_CREATED[0]
		self.assertTrue(receiving.insert_called)
		self.assertFalse(receiving.save_called)
		self.assertIsNone(receiving.stock_entry)


if __name__ == "__main__":
	unittest.main()
