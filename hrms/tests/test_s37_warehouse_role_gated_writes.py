import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

_DOCS_CREATED: list[object] = []
_PO_DOC = None
_MR_DOC = None


class _FakeFrappe(types.ModuleType):
	def __getattr__(self, name):
		if name == "db":
			return self.local.db
		if name == "session":
			return self.local.session
		raise AttributeError(name)


class _FakePOItem:
	def __init__(self):
		self.name = "PO-ITEM-0001"
		self.item_code = "A026"
		self.item_name = "BROWN SUGAR"
		self.description = "BROWN SUGAR"
		self.qty = 1
		self.received_qty = 0
		self.uom = "SACK"
		self.stock_uom = "SACK"
		self.conversion_factor = 1
		self.rate = 100
		self.warehouse = "SM Taytay - BKI"


class _FakePurchaseOrder:
	def __init__(self):
		self.name = "PUR-ORD-TEST-0001"
		self.supplier = "S037 E2E Temp Supplier"
		self.supplier_name = "S037 E2E Temp Supplier"
		self.company = "Bebang Kitchen Inc."
		self.currency = "PHP"
		self.buying_price_list = "Standard Buying"
		self.price_list_currency = "PHP"
		self.plc_conversion_rate = 1
		self.conversion_rate = 1
		self.set_warehouse = "SM Taytay - BKI"
		self.items = [_FakePOItem()]


class _FakeMaterialRequestItem:
	def __init__(self):
		self.name = "MRI-0001"
		self.item_code = "FG002-A"


class _FakeMaterialRequest:
	def __init__(self):
		self.name = "MAT-REQ-TEST-0001"
		self.status = "Ordered"
		self.custom_request_source = "store_order"
		self.custom_cargo_lane = "DRY"
		self.custom_source_warehouse = "Shaw BLVD - BKI"
		self.custom_destination_warehouse = "TEST-STORE-BGC - BEI"
		self.custom_source_company = "Bebang Kitchen Inc."
		self.custom_target_company = "Bebang Enterprise Inc."
		self.custom_finance_treatment = "intercompany"
		self.items = [_FakeMaterialRequestItem()]


class _FakeItem:
	def __init__(self, item_code):
		self.name = item_code
		self.item_name = "BANANA CINNAMON" if item_code == "FG002-A" else f"Item {item_code}"
		self.description = f"Desc {item_code}"
		self.stock_uom = "KG" if item_code == "FG002-A" else "Nos"
		self.has_batch_no = False
		self.uoms = [types.SimpleNamespace(uom=self.stock_uom)]


class _FakePurchaseReceipt:
	def __init__(self):
		self.doctype = "Purchase Receipt"
		self.name = "MAT-PRE-TEST-0001"
		self.flags = None
		self.supplier = None
		self.supplier_name = None
		self.company = None
		self.currency = None
		self.buying_price_list = None
		self.price_list_currency = None
		self.plc_conversion_rate = None
		self.conversion_rate = None
		self.set_warehouse = None
		self.posting_date = None
		self.posting_time = None
		self.remarks = None
		self.items = []
		self.insert_kwargs = None
		self.submit_called = False
		self.grand_total = 100

	def append(self, table, row):
		self.items.append(types.SimpleNamespace(**row))

	def insert(self, ignore_permissions=False):
		self.insert_kwargs = {"ignore_permissions": ignore_permissions}
		return self

	def submit(self):
		self.submit_called = True
		return self


class _FakeStockEntry:
	def __init__(self):
		self.doctype = "Stock Entry"
		self.name = "MAT-STE-TEST-0001"
		self.flags = None
		self.stock_entry_type = None
		self.company = None
		self.posting_date = None
		self.posting_time = None
		self.from_warehouse = None
		self.to_warehouse = None
		self.remarks = None
		self.items = []
		self.insert_kwargs = None
		self.submit_called = False

	def append(self, table, row):
		self.items.append(types.SimpleNamespace(**row))

	def insert(self, ignore_permissions=False):
		self.insert_kwargs = {"ignore_permissions": ignore_permissions}
		return self

	def submit(self):
		self.submit_called = True
		return self


def _install_fake_modules():
	global _PO_DOC, _MR_DOC
	_PO_DOC = _FakePurchaseOrder()
	_MR_DOC = _FakeMaterialRequest()

	if "frappe" not in sys.modules:
		frappe = _FakeFrappe("frappe")
		utils = types.ModuleType("frappe.utils")

		def whitelist(*args, **kwargs):
			def decorator(fn):
				return fn

			return decorator

		def _throw(message, exc=None, title=None):
			if isinstance(exc, type) and issubclass(exc, Exception):
				raise exc(message)
			raise Exception(message)

		frappe.whitelist = whitelist
		frappe._ = lambda text: text
		frappe.throw = _throw
		frappe.PermissionError = type("PermissionError", (Exception,), {})
		frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
		frappe.local = types.SimpleNamespace(session=types.SimpleNamespace(user="test.warehouse@bebang.ph"))
		frappe.log_error = lambda *args, **kwargs: None
		frappe.get_traceback = lambda: "traceback"
		frappe.parse_json = json.loads

		def _exists(doctype, value):
			if doctype == "Purchase Order":
				return value == _PO_DOC.name
			if doctype == "Material Request":
				return value == _MR_DOC.name
			if doctype == "UOM":
				return value in {"Nos", "KG", "SACK"}
			return False

		frappe.local.db = types.SimpleNamespace(
			exists=_exists,
			get_value=lambda *args, **kwargs: None,
			has_column=lambda *args, **kwargs: False,
		)

		def _new_doc(doctype):
			if doctype == "Purchase Receipt":
				doc = _FakePurchaseReceipt()
			elif doctype == "Stock Entry":
				doc = _FakeStockEntry()
			else:
				raise AssertionError(f"Unexpected doctype {doctype}")
			_DOCS_CREATED.append(doc)
			return doc

		def _get_doc(doctype, name=None):
			if doctype == "Purchase Order":
				return _PO_DOC
			if doctype == "Material Request":
				return _MR_DOC
			if doctype == "Item":
				return _FakeItem(name)
			raise AssertionError(f"Unexpected get_doc {doctype} {name}")

		frappe.new_doc = _new_doc
		frappe.get_doc = _get_doc
		frappe.get_all = lambda *args, **kwargs: []
		frappe.get_roles = lambda user=None: ["Warehouse User"]
		frappe.utils = utils

		utils.cint = lambda value: int(value or 0)
		utils.flt = lambda value, precision=None: float(value or 0)
		utils.now_datetime = lambda: "2026-03-12 12:00:00"
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

	bei_config_mod = types.ModuleType("hrms.utils.bei_config")
	bei_config_mod.get_company = lambda: "Bebang Enterprise Inc."
	sys.modules["hrms.utils.bei_config"] = bei_config_mod

	standard_buying_bridge_mod = types.ModuleType("hrms.utils.standard_buying_bridge")
	standard_buying_bridge_mod.apply_standard_buying_context = (
		lambda doc, store_label=None, legal_entity=None: setattr(
			doc,
			"_standard_buying_context",
			{"store_label": store_label, "legal_entity": legal_entity},
		)
	)
	sys.modules["hrms.utils.standard_buying_bridge"] = standard_buying_bridge_mod

	scm_roles_mod = types.ModuleType("hrms.utils.scm_roles")
	scm_roles_mod.SCM_APPROVAL_ROLES = {"Warehouse User", "System Manager"}
	scm_roles_mod.SCM_DISPATCH_ROLES = {"Warehouse User", "System Manager"}
	scm_roles_mod.SCM_RECEIVING_ROLES = {"Warehouse User", "System Manager"}
	scm_roles_mod.check_scm_permission = lambda roles, action="": None
	sys.modules["hrms.utils.scm_roles"] = scm_roles_mod

	contracts_mod = types.ModuleType("hrms.utils.supply_chain_contracts")
	contracts_mod.CANONICAL_COMMISSARY_OPERATION_WAREHOUSE = "TEST-COMMISSARY - BKI"
	contracts_mod.TEST_COMMISSARY_OPERATION_WAREHOUSE = "TEST-COMMISSARY - BKI"
	contracts_mod.FINANCE_TREATMENT_INTERCOMPANY = "intercompany"
	contracts_mod.FINANCE_TREATMENT_SAME_COMPANY = "same_company"
	contracts_mod.REQUEST_SOURCE_COMMISSARY_FG_TRANSFER = "commissary_fg_transfer"
	contracts_mod.REQUEST_SOURCE_STORE_ORDER = "store_order"
	contracts_mod.get_preferred_commissary_warehouses = lambda include_legacy=False: []
	contracts_mod.get_request_source_label = lambda source: source
	contracts_mod.infer_finance_treatment = (
		lambda source_company, target_company: "same_company"
		if source_company == target_company
		else "intercompany"
	)
	contracts_mod.resolve_material_request_contract = lambda mr: {
		"request_source": mr.custom_request_source,
		"cargo_lane": mr.custom_cargo_lane,
		"destination_warehouse": mr.custom_destination_warehouse,
		"source_company": mr.custom_source_company,
		"target_company": mr.custom_target_company,
		"finance_treatment": mr.custom_finance_treatment,
	}
	contracts_mod.resolve_warehouse_company = lambda warehouse: {
		"SM Taytay - BKI": "Bebang Kitchen Inc.",
		"Shaw BLVD - BKI": "Bebang Kitchen Inc.",
		"TEST-STORE-BGC - BEI": "Bebang Enterprise Inc.",
	}.get(warehouse)
	contracts_mod.stamp_stock_entry_contract = lambda doc, **kwargs: [
		setattr(doc, f"custom_{key}", value) for key, value in kwargs.items()
	]
	contracts_mod.strip_company_suffix = lambda name: str(name).split(" - ")[0]
	sys.modules["hrms.utils.supply_chain_contracts"] = contracts_mod


_install_fake_modules()

spec = importlib.util.spec_from_file_location(
	"warehouse_under_test",
	ROOT / "hrms" / "api" / "warehouse.py",
)
warehouse = importlib.util.module_from_spec(spec)
spec.loader.exec_module(warehouse)


class TestS37WarehouseRoleGatedWrites(unittest.TestCase):
	def setUp(self):
		_DOCS_CREATED.clear()
		_MR_DOC.custom_destination_warehouse = "TEST-STORE-BGC - BEI"
		_MR_DOC.custom_target_company = "Bebang Enterprise Inc."
		_MR_DOC.custom_finance_treatment = "intercompany"

	def test_create_purchase_receipt_uses_receiving_roles_and_ignore_permissions(self):
		calls = []
		warehouse.check_scm_permission = lambda roles, action="": calls.append((set(roles), action))

		result = warehouse.create_purchase_receipt(
			_PO_DOC.name,
			[
				{
					"item_code": "A026",
					"received_qty": 1,
					"rejected_qty": 0,
					"warehouse": "SM Taytay - BKI",
				}
			],
			remarks="S037 supplier receive",
		)

		self.assertTrue(result["success"])
		self.assertEqual(result["data"]["name"], "MAT-PRE-TEST-0001")
		self.assertEqual(calls, [(set(warehouse.SCM_RECEIVING_ROLES), "receive supplier purchase orders")])
		created = _DOCS_CREATED[0]
		self.assertEqual(created.insert_kwargs, {"ignore_permissions": True})
		self.assertTrue(created.submit_called)
		self.assertTrue(created.flags.ignore_permissions)
		self.assertTrue(created.flags.ignore_user_permissions)
		self.assertEqual(created.currency, "PHP")
		self.assertEqual(created.buying_price_list, "Standard Buying")
		self.assertEqual(created.price_list_currency, "PHP")
		self.assertEqual(created.plc_conversion_rate, 1)
		self.assertEqual(created.conversion_rate, 1)
		self.assertEqual(created.set_warehouse, "SM Taytay - BKI")
		self.assertEqual(
			created._standard_buying_context,
			{"store_label": "SM Taytay - BKI", "legal_entity": "Bebang Kitchen Inc."},
		)

	def test_create_stock_transfer_uses_dispatch_roles_and_ignore_permissions(self):
		calls = []
		warehouse.check_scm_permission = lambda roles, action="": calls.append((set(roles), action))

		result = warehouse.create_stock_transfer(
			source_warehouse="Shaw BLVD - BKI",
			target_warehouse="TEST-STORE-BGC - BEI",
			items=[
				{
					"item_code": "FG002-A",
					"qty": 1,
					"uom": "Nos",
				}
			],
			mr_name=_MR_DOC.name,
			remarks="S037 dispatch",
		)

		self.assertTrue(result["success"])
		self.assertEqual(result["data"]["name"], "MAT-STE-TEST-0001")
		self.assertEqual(calls, [(set(warehouse.SCM_DISPATCH_ROLES), "dispatch warehouse stock transfers")])
		created = _DOCS_CREATED[0]
		self.assertEqual(created.insert_kwargs, {"ignore_permissions": True})
		self.assertTrue(created.submit_called)
		self.assertTrue(created.flags.ignore_permissions)
		self.assertTrue(created.flags.ignore_user_permissions)

	def test_create_stock_transfer_uses_contract_destination_for_same_company(self):
		_MR_DOC.custom_destination_warehouse = "Shaw BLVD - BKI"
		_MR_DOC.custom_target_company = "Bebang Kitchen Inc."
		_MR_DOC.custom_finance_treatment = "same_company"

		result = warehouse.create_stock_transfer(
			source_warehouse="SM Taytay - BKI",
			target_warehouse="TEST-COMMISSARY - BKI",
			items=[
				{
					"item_code": "FG002-A",
					"qty": 1,
					"uom": "Nos",
				}
			],
			mr_name=_MR_DOC.name,
			remarks="S037 same-company RM handoff",
		)

		self.assertTrue(result["success"])
		created = _DOCS_CREATED[0]
		self.assertEqual(created.to_warehouse, "Shaw BLVD - BKI")
		self.assertEqual(created.items[0].t_warehouse, "Shaw BLVD - BKI")

	def test_create_stock_transfer_falls_back_to_valid_stock_uom_when_requested_uom_missing(self):
		result = warehouse.create_stock_transfer(
			source_warehouse="Shaw BLVD - BKI",
			target_warehouse="TEST-STORE-BGC - BEI",
			items=[
				{
					"item_code": "FG002-A",
					"qty": 1,
					"uom": "TRAY",
				}
			],
			mr_name=_MR_DOC.name,
			remarks="S037 invalid packaging uom fallback",
		)

		self.assertTrue(result["success"])
		created = _DOCS_CREATED[0]
		self.assertEqual(created.items[0].uom, "KG")
		self.assertEqual(created.items[0].stock_uom, "KG")


if __name__ == "__main__":
	unittest.main()
