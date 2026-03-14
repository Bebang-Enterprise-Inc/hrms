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


class _FakeStockEntry:
	counter = 0

	def __init__(self):
		type(self).counter += 1
		self.doctype = "Stock Entry"
		self.name = f"MAT-STE-TEST-{type(self).counter:04d}"
		self.stock_entry_type = None
		self.company = None
		self.posting_date = None
		self.posting_time = None
		self.from_warehouse = None
		self.to_warehouse = None
		self.remarks = None
		self.items = []
		self.custom_request_source = None
		self.custom_return_photo = None
		self.insert_called = False
		self.submit_called = False

	def append(self, table, row):
		self.items.append(types.SimpleNamespace(**row))

	def insert(self, ignore_permissions=True):
		self.insert_called = True

	def submit(self):
		self.submit_called = True


class _FakeBillingSchedule:
	counter = 0

	def __init__(self):
		type(self).counter += 1
		self.doctype = "BEI Billing Schedule"
		self.name = f"BILL-CN-TEST-{type(self).counter:04d}"
		self.flags = types.SimpleNamespace(ignore_mandatory=False)
		self.insert_called = False

	def insert(self, ignore_permissions=True):
		self.insert_called = True


_DOCS_CREATED: list[_FakeStockEntry] = []


def _install_fake_modules():
	if "frappe" not in sys.modules:
		frappe = _FakeFrappe("frappe")
		utils = types.ModuleType("frappe.utils")

		def whitelist(*args, **kwargs):
			def decorator(fn):
				return fn

			return decorator

		def _db_exists(doctype, value):
			if doctype == "BEI Distribution Trip":
				return value == "TRIP-TEST-001"
			if doctype == "BEI Route":
				return value == "ROUTE-TEST-001"
			return False

		def _db_get_value(doctype, filters, fieldname=None, order_by=None, as_dict=False):
			if doctype == "Warehouse":
				name = filters if isinstance(filters, str) else ""
				if name == "TEST-STORE-BGC - BEI":
					return "Bebang Enterprise Inc."
				if name == "SM Taytay - BKI":
					return "Bebang Kitchen Inc."
			if doctype == "BEI Route":
				return "SM Taytay - BKI"
			return None

		frappe.whitelist = whitelist
		frappe._ = lambda text: text
		frappe.throw = lambda message, exc=None, title=None: (_ for _ in ()).throw(Exception(message))
		frappe.log_error = lambda *args, **kwargs: None
		frappe.local = types.SimpleNamespace(session=types.SimpleNamespace(user="test.staff@bebang.ph"))
		frappe.get_roles = lambda user=None: ["Store Staff", "Store Supervisor"]
		frappe.local.db = types.SimpleNamespace(
			exists=_db_exists,
			get_value=_db_get_value,
			has_column=lambda doctype, fieldname: True,
			savepoint=lambda name: None,
			release_savepoint=lambda name: None,
			rollback=lambda save_point=None: None,
		)

		def _new_doc(doctype):
			doc = _FakeStockEntry()
			_DOCS_CREATED.append(doc)
			return doc

		def _get_doc(doctype, name=None):
			if doctype == "BEI Store Receiving":
				return types.SimpleNamespace(store="TEST-STORE-BGC - BEI", trip="TRIP-TEST-001")
			if doctype == "BEI Distribution Trip":
				return types.SimpleNamespace(route="ROUTE-TEST-001")
			if doctype == "Item":
				return types.SimpleNamespace(
					item_name=f"Item {name}", description=f"Item {name}", stock_uom="Nos"
				)
			if doctype == "Stock Entry":
				return types.SimpleNamespace(
					name=name,
					docstatus=1,
					stock_entry_type="Material Issue",
					custom_request_source="store_return",
					from_warehouse="TEST-STORE-BGC - BEI",
					remarks="Store Return from TEST-STORE-BGC - BEI | Receiving: BEI-RCV-TEST-0001 | Reason: quality",
					items=[types.SimpleNamespace(item_code="FG-001", qty=2)],
				)
			return None

		frappe.new_doc = _new_doc
		frappe.get_doc = _get_doc
		frappe.get_all = lambda *args, **kwargs: []
		frappe.utils = utils

		utils.add_days = lambda date, days: "2026-03-13"
		utils.cint = lambda value: int(value or 0)
		utils.flt = lambda value, precision=None: float(value or 0)
		utils.get_datetime = lambda value=None: value
		utils.getdate = lambda value=None: value
		utils.now_datetime = lambda: "2026-03-12 09:00:00"
		utils.nowdate = lambda: "2026-03-12"
		utils.today = lambda: "2026-03-12"

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
		bei_config_mod.SPACE_OPS = "SPACE_OPS"
		bei_config_mod.get_chat_space = lambda *args, **kwargs: "spaces/TEST"
		bei_config_mod.get_company = lambda: "Bebang Enterprise Inc."
		sys.modules["hrms.utils.bei_config"] = bei_config_mod

	if "hrms.utils.scm_roles" not in sys.modules:
		scm_roles_mod = types.ModuleType("hrms.utils.scm_roles")
		scm_roles_mod.SCM_APPROVAL_ROLES = ["Warehouse User"]
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


class TestS37StoreReturnContract(unittest.TestCase):
	def setUp(self):
		_DOCS_CREATED.clear()
		_FakeStockEntry.counter = 0
		_FakeBillingSchedule.counter = 0

	def test_create_store_return_creates_intercompany_issue_and_receipt_pair(self):
		original_stamp = store.stamp_stock_entry_contract
		original_save_image = store.save_base64_image
		stamp_calls = []
		try:
			store.stamp_stock_entry_contract = lambda doc, **kwargs: stamp_calls.append((doc, kwargs))
			store.save_base64_image = (
				lambda photo, doctype, docname=None, fieldname="photo": "/files/return-proof.jpg"
			)

			result = store.create_store_return(
				receiving="BEI-RCV-TEST-0001",
				items=[{"item_code": "FG-001", "qty": 2, "reason": "quality"}],
				reason="quality",
				photo="data:image/png;base64,ZmFrZQ==",
			)
		finally:
			store.stamp_stock_entry_contract = original_stamp
			store.save_base64_image = original_save_image

		self.assertTrue(result["success"])
		self.assertEqual(result["stock_entry"], "MAT-STE-TEST-0001")
		self.assertEqual(result["warehouse_receipt"], "MAT-STE-TEST-0002")
		self.assertEqual(result["movement_type"], "Material Issue")
		self.assertEqual(result["finance_treatment"], "intercompany")
		self.assertEqual(len(_DOCS_CREATED), 2)

		issue_entry = _DOCS_CREATED[0]
		receipt_entry = _DOCS_CREATED[1]

		self.assertEqual(issue_entry.stock_entry_type, "Material Issue")
		self.assertEqual(issue_entry.company, "Bebang Enterprise Inc.")
		self.assertEqual(issue_entry.from_warehouse, "TEST-STORE-BGC - BEI")
		self.assertIsNone(issue_entry.to_warehouse)
		self.assertEqual(issue_entry.custom_return_photo, "/files/return-proof.jpg")
		self.assertTrue(issue_entry.insert_called)
		self.assertTrue(issue_entry.submit_called)
		self.assertEqual(issue_entry.items[0].s_warehouse, "TEST-STORE-BGC - BEI")
		self.assertFalse(hasattr(issue_entry.items[0], "t_warehouse"))

		self.assertEqual(receipt_entry.stock_entry_type, "Material Receipt")
		self.assertEqual(receipt_entry.company, "Bebang Kitchen Inc.")
		self.assertEqual(receipt_entry.to_warehouse, "SM Taytay - BKI")
		self.assertTrue(receipt_entry.insert_called)
		self.assertTrue(receipt_entry.submit_called)
		self.assertEqual(receipt_entry.items[0].t_warehouse, "SM Taytay - BKI")
		self.assertFalse(hasattr(receipt_entry.items[0], "s_warehouse"))

		self.assertEqual(stamp_calls[0][1]["request_source"], "store_return")
		self.assertEqual(stamp_calls[0][1]["finance_treatment"], "intercompany")
		self.assertEqual(stamp_calls[1][1]["request_source"], "store_return")
		self.assertEqual(stamp_calls[1][1]["finance_treatment"], "intercompany")

	def test_process_store_return_accepts_intercompany_material_issue(self):
		original_credit = store._create_store_issue_credit_note
		original_notify = store._notify_store_issue_processed
		original_get_value = store.frappe.db.get_value
		try:
			store._create_store_issue_credit_note = lambda se, store_name, reason, receiving_name=None: (
				"BILL-CN-TEST-0001",
				"ACC-JV-TEST-0001",
			)
			store._notify_store_issue_processed = lambda *args, **kwargs: None
			store.frappe.db.get_value = (
				lambda doctype, filters, fieldname=None, order_by=None, as_dict=False: "Pending"
				if doctype == "BEI Billing Schedule"
				else original_get_value(doctype, filters, fieldname, order_by, as_dict)
			)

			result = store.process_store_return("MAT-STE-TEST-0001")
		finally:
			store._create_store_issue_credit_note = original_credit
			store._notify_store_issue_processed = original_notify
			store.frappe.db.get_value = original_get_value

		self.assertTrue(result["success"])
		self.assertEqual(result["stock_entry"], "MAT-STE-TEST-0001")
		self.assertEqual(result["credit_note"], "BILL-CN-TEST-0001")
		self.assertEqual(result["credit_note_status"], "Pending")
		self.assertEqual(result["journal_entry"], "ACC-JV-TEST-0001")
		self.assertEqual(result["items_returned"], 1)

	def test_create_store_issue_credit_note_uses_delivery_billing_goods_and_markup(self):
		credit_notes: list[_FakeBillingSchedule] = []
		stock_entry = types.SimpleNamespace(
			name="MAT-STE-TEST-0009",
			items=[types.SimpleNamespace(item_code="FG-001", qty=1)],
			total_outgoing_value=0,
		)
		original_find_credit = store._find_existing_store_issue_credit
		original_find_billing = store._find_original_billing
		original_resolve_pricing = store._resolve_store_order_item_pricing
		original_new_doc = store.frappe.new_doc
		try:
			store._find_existing_store_issue_credit = lambda stock_entry_name: (None, None)
			store._find_original_billing = lambda store_name, receiving_name=None: {
				"name": "BILL-DL-TEST-0001",
				"billing_type": "Delivery",
				"store": "TEST-STORE-BGC - BEI",
				"status": "Pending",
				"store_type": "JV",
				"trip_reference": "TRIP-TEST-001",
				"trip_stop_idx": 1,
				"cargo_type": "DRY",
				"goods_value": 300.0,
				"handling_fee": 7.5,
				"custom_markup_percent": 2.5,
				"_origin_context": {"store_order": "SO-TEST-001"},
			}
			store._resolve_store_order_item_pricing = lambda store_order_name: {
				"FG-001": {"unit_price": 100.0, "delivered_qty": 3.0}
			}

			def _new_doc(doctype):
				if doctype == "BEI Billing Schedule":
					doc = _FakeBillingSchedule()
					credit_notes.append(doc)
					return doc
				return original_new_doc(doctype)

			store.frappe.new_doc = _new_doc

			credit_note_name, journal_entry_name = store._create_store_issue_credit_note(
				stock_entry,
				"TEST-STORE-BGC - BEI",
				"quality",
				receiving_name="BEI-RCV-TEST-0001",
			)
		finally:
			store._find_existing_store_issue_credit = original_find_credit
			store._find_original_billing = original_find_billing
			store._resolve_store_order_item_pricing = original_resolve_pricing
			store.frappe.new_doc = original_new_doc

		self.assertEqual(credit_note_name, "BILL-CN-TEST-0001")
		self.assertIsNone(journal_entry_name)
		self.assertEqual(len(credit_notes), 1)
		credit_note = credit_notes[0]
		self.assertTrue(credit_note.insert_called)
		self.assertEqual(credit_note.status, "Pending")
		self.assertEqual(credit_note.goods_value, -100.0)
		self.assertEqual(credit_note.handling_fee, -2.5)
		self.assertEqual(credit_note.total_amount, -102.5)
		self.assertEqual(credit_note.balance_due, -102.5)


if __name__ == "__main__":
	unittest.main()
