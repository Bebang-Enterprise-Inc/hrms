import datetime
import importlib.util
import re
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_frappe():
	if "frappe" in sys.modules:
		return

	frappe = types.ModuleType("frappe")
	utils = types.ModuleType("frappe.utils")

	def whitelist(*args, **kwargs):
		def decorator(fn):
			return fn

		return decorator

	class DuplicateEntryError(Exception):
		pass

	class PermissionError(Exception):
		pass

	def _throw(message, exc=None):
		if isinstance(exc, type) and issubclass(exc, Exception):
			raise exc(message)
		raise Exception(message)

	frappe.whitelist = whitelist
	frappe._ = lambda text: text
	frappe.throw = _throw
	frappe.DuplicateEntryError = DuplicateEntryError
	frappe.PermissionError = PermissionError
	frappe.log_error = lambda *args, **kwargs: None
	frappe.logger = lambda: types.SimpleNamespace(info=lambda *args, **kwargs: None)
	frappe.get_traceback = lambda: "traceback"
	frappe.defaults = types.SimpleNamespace(get_global_default=lambda key: None)
	frappe.__dict__["session"] = types.SimpleNamespace(user="Administrator")
	frappe.get_roles = lambda user=None: ["System Manager"] if user and user != "Guest" else []
	frappe.request = types.SimpleNamespace(headers={}, data=b"")
	frappe.__dict__["db"] = types.SimpleNamespace(
		exists=lambda *args, **kwargs: None,
		get_value=lambda *args, **kwargs: None,
		set_value=lambda *args, **kwargs: None,
		savepoint=lambda *args, **kwargs: None,
		release_savepoint=lambda *args, **kwargs: None,
		rollback=lambda *args, **kwargs: None,
	)
	frappe.get_all = lambda *args, **kwargs: []
	frappe.get_meta = lambda *args, **kwargs: types.SimpleNamespace(has_field=lambda *_: True)
	frappe.get_doc = lambda *args, **kwargs: types.SimpleNamespace(insert=lambda **_: None, name="DOC-0001")
	frappe.new_doc = lambda *args, **kwargs: types.SimpleNamespace(
		append=lambda *a, **k: None,
		insert=lambda **k: None,
		submit=lambda: None,
	)

	utils.now_datetime = lambda: datetime.datetime(2026, 1, 1, 8, 0, 0)
	utils.nowdate = lambda: "2026-01-01"
	utils.flt = lambda value: float(value or 0)
	utils.cint = lambda value: int(float(value or 0))
	utils.getdate = (
		lambda value=None: datetime.date.fromisoformat(str(value)) if value else datetime.date(2026, 1, 1)
	)

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils


_install_fake_frappe()
erp_sync_spec = importlib.util.spec_from_file_location(
	"erp_sync_under_test",
	ROOT / "hrms" / "api" / "erp_sync.py",
)
erp_sync = importlib.util.module_from_spec(erp_sync_spec)
erp_sync_spec.loader.exec_module(erp_sync)


class _FakeDoc:
	def __init__(self, doctype, on_insert=None):
		self.doctype = doctype
		self.name = None
		self.items = []
		self.remarks = ""
		self._on_insert = on_insert
		self.insert_calls = 0
		self.submit_calls = 0

	def append(self, table, row):
		if table == "items":
			self.items.append(row)

	def insert(self, ignore_permissions=False):
		self.insert_calls += 1
		if self._on_insert:
			self._on_insert(self)
		if not self.name:
			self.name = f"{self.doctype}-0001"
		return self

	def submit(self):
		self.submit_calls += 1


class TestErpSync(unittest.TestCase):
	def setUp(self):
		erp_sync._FIELD_CACHE.clear()
		erp_sync.frappe.__dict__["session"] = types.SimpleNamespace(user="Administrator")
		erp_sync.frappe.get_roles = MagicMock(return_value=["System Manager"])
		erp_sync.frappe.db.savepoint = MagicMock(return_value=None)
		erp_sync.frappe.db.release_savepoint = MagicMock()
		erp_sync.frappe.db.rollback = MagicMock()

	def test_sync_ar_aging_writes_sales_invoice_fields(self):
		erp_sync.frappe.db.exists = MagicMock(return_value="SINV-0001")
		erp_sync.frappe.db.get_value = MagicMock(return_value=1)
		erp_sync.frappe.db.set_value = MagicMock()
		erp_sync.frappe.logger = MagicMock(return_value=types.SimpleNamespace(info=MagicMock()))
		erp_sync.frappe.get_meta = MagicMock(return_value=types.SimpleNamespace(has_field=lambda field: True))

		result = erp_sync.sync_ar_aging(
			sheet_name="AR Aging",
			data=[{"invoice_no": "SINV-0001", "outstanding": 1200, "due_date": "2026-01-31"}],
			checksum="chk-ar-1",
		)

		self.assertEqual(result["rows_updated"], 1)
		self.assertEqual(result["rows_failed"], 0)
		erp_sync.frappe.db.set_value.assert_called_once()
		args = erp_sync.frappe.db.set_value.call_args[0]
		self.assertEqual(args[0], "Sales Invoice")
		self.assertEqual(args[1], "SINV-0001")
		self.assertIn("outstanding_amount", args[2])

	def test_sync_inventory_is_idempotent_by_sync_reference(self):
		created_sync_refs = set()
		created_docs = []

		def db_exists(doctype, name=None):
			if doctype in ("Item", "Warehouse", "Company"):
				return name or True
			return None

		def db_get_value(doctype, filters=None, fieldname=None):
			if doctype == "Stock Reconciliation" and isinstance(filters, dict) and "remarks" in filters:
				like_value = filters["remarks"][1]
				for sync_ref in created_sync_refs:
					if sync_ref in like_value:
						return "SR-0001"
				return None
			return None

		def new_doc(doctype):
			if doctype != "Stock Reconciliation":
				return _FakeDoc(doctype)

			def on_insert(doc):
				doc.name = f"SR-{len(created_docs) + 1:04d}"
				created_docs.append(doc)
				match = re.search(r"\((INV:[^)]+)\)", doc.remarks or "")
				if match:
					created_sync_refs.add(match.group(1))

			return _FakeDoc(doctype, on_insert=on_insert)

		erp_sync.frappe.db.exists = MagicMock(side_effect=db_exists)
		erp_sync.frappe.db.get_value = MagicMock(side_effect=db_get_value)
		erp_sync.frappe.new_doc = MagicMock(side_effect=new_doc)
		erp_sync.frappe.get_meta = MagicMock(return_value=types.SimpleNamespace(has_field=lambda field: True))

		with patch.object(erp_sync, "_normalize_company", return_value="BEI"):
			first = erp_sync.sync_inventory(
				sheet_name="Inventory",
				data=[
					{"item_code": "ITM-001", "warehouse": "Stores - BEI", "qty": 5},
					{"item_code": "ITM-002", "warehouse": "Stores - BEI", "qty": 8},
				],
				checksum="chk-inv-1",
			)
			second = erp_sync.sync_inventory(
				sheet_name="Inventory",
				data=[
					{"item_code": "ITM-001", "warehouse": "Stores - BEI", "qty": 5},
					{"item_code": "ITM-002", "warehouse": "Stores - BEI", "qty": 8},
				],
				checksum="chk-inv-1",
			)

		self.assertEqual(first["rows_created"], 2)
		self.assertEqual(second["rows_updated"], 2)
		self.assertEqual(len(created_docs), 1)

	def test_sync_coa_creates_then_updates_same_account(self):
		created_accounts = {}
		created_docs = []

		def db_get_value(doctype, filters=None, fieldname=None):
			if doctype == "Account" and isinstance(filters, dict):
				account_number = filters.get("account_number")
				if account_number:
					return created_accounts.get(account_number)
				if filters.get("is_group") == 1:
					return "Assets - BEI"
			return None

		def new_doc(doctype):
			if doctype != "Account":
				return _FakeDoc(doctype)

			def on_insert(doc):
				doc.name = f"ACC-{len(created_docs) + 1:04d}"
				created_docs.append(doc)
				created_accounts[doc.account_number] = doc.name

			return _FakeDoc(doctype, on_insert=on_insert)

		erp_sync.frappe.db.get_value = MagicMock(side_effect=db_get_value)
		erp_sync.frappe.db.set_value = MagicMock()
		erp_sync.frappe.new_doc = MagicMock(side_effect=new_doc)
		erp_sync.frappe.get_meta = MagicMock(return_value=types.SimpleNamespace(has_field=lambda field: True))

		row = {"gl_code": "1010", "account_name": "Cash On Hand", "account_type": "Cash", "company": "BEI"}

		with (
			patch.object(erp_sync, "_normalize_company", return_value="BEI"),
			patch.object(erp_sync, "_resolve_parent_account", return_value="Assets - BEI"),
		):
			first = erp_sync.sync_coa("COA", [row], "chk-coa-1")
			second = erp_sync.sync_coa("COA", [row], "chk-coa-1")

		self.assertEqual(first["rows_created"], 1)
		self.assertEqual(second["rows_updated"], 1)
		self.assertEqual(len(created_docs), 1)
		erp_sync.frappe.db.set_value.assert_called_once()

	def test_sync_bank_accounts_creates_then_updates_by_account_number(self):
		created_bank_accounts = {}
		created_docs = []

		def db_get_value(doctype, filters=None, fieldname=None):
			if doctype == "Bank Account" and isinstance(filters, dict):
				account_no = filters.get("bank_account_no")
				if account_no:
					return created_bank_accounts.get(account_no)
			if doctype == "Account" and isinstance(filters, dict):
				if filters.get("account_number") == "1010":
					return "Bank GL - BEI"
			return None

		def new_doc(doctype):
			if doctype != "Bank Account":
				return _FakeDoc(doctype)

			def on_insert(doc):
				doc.name = f"BANK-ACC-{len(created_docs) + 1:04d}"
				created_docs.append(doc)
				created_bank_accounts[doc.bank_account_no] = doc.name

			return _FakeDoc(doctype, on_insert=on_insert)

		erp_sync.frappe.db.get_value = MagicMock(side_effect=db_get_value)
		erp_sync.frappe.db.set_value = MagicMock()
		erp_sync.frappe.db.exists = MagicMock(return_value=True)
		erp_sync.frappe.new_doc = MagicMock(side_effect=new_doc)
		erp_sync.frappe.get_meta = MagicMock(return_value=types.SimpleNamespace(has_field=lambda field: True))

		row = {
			"account_number": "1234567890",
			"account_name": "Main Operating",
			"bank_name": "BDO",
			"gl_code": "1010",
		}

		with (
			patch.object(erp_sync, "_normalize_company", return_value="BEI"),
			patch.object(erp_sync, "_ensure_bank", return_value="BDO"),
		):
			first = erp_sync.sync_bank_accounts("Bank Directory", [row], "chk-bank-1")
			second = erp_sync.sync_bank_accounts("Bank Directory", [row], "chk-bank-1")

		self.assertEqual(first["rows_created"], 1)
		self.assertEqual(second["rows_updated"], 1)
		self.assertEqual(len(created_docs), 1)
		erp_sync.frappe.db.set_value.assert_called_once()

	def test_sync_ap_opening_creates_then_updates_existing_invoice(self):
		created_purchase_invoices = {}
		created_docs = []

		def db_get_value(doctype, filters=None, fieldname=None):
			if doctype == "Purchase Invoice" and isinstance(filters, dict):
				key = (filters.get("supplier"), filters.get("bill_no"), filters.get("company"))
				if key in created_purchase_invoices:
					return created_purchase_invoices[key]
				return None
			if doctype == "Purchase Invoice" and isinstance(filters, str) and fieldname == "remarks":
				return "existing remarks"
			return None

		def new_doc(doctype):
			if doctype != "Purchase Invoice":
				return _FakeDoc(doctype)

			def on_insert(doc):
				doc.name = f"PI-{len(created_docs) + 1:04d}"
				created_docs.append(doc)
				key = (doc.supplier, doc.bill_no, doc.company)
				created_purchase_invoices[key] = doc.name

			return _FakeDoc(doctype, on_insert=on_insert)

		erp_sync.frappe.db.get_value = MagicMock(side_effect=db_get_value)
		erp_sync.frappe.db.set_value = MagicMock()
		erp_sync.frappe.new_doc = MagicMock(side_effect=new_doc)
		erp_sync.frappe.log_error = MagicMock()
		erp_sync.frappe.get_meta = MagicMock(return_value=types.SimpleNamespace(has_field=lambda field: True))

		row = {
			"supplier": "Acme Supply",
			"invoice_no": "INV-001",
			"amount": 24500.0,
			"due_date": "2026-02-15",
		}

		with (
			patch.object(erp_sync, "_ensure_ap_opening_item", return_value="ERP-SYNC-AP-OPENING"),
			patch.object(erp_sync, "_normalize_company", return_value="BEI"),
			patch.object(erp_sync, "_ensure_supplier", return_value="SUP-0001"),
			patch.object(erp_sync, "_default_expense_account", return_value="Expense - BEI"),
			patch.object(erp_sync, "_default_payable_account", return_value="Payable - BEI"),
			patch.object(erp_sync, "_default_cost_center", return_value="Main - BEI"),
			patch.object(erp_sync, "_doctype_has_field", return_value=True),
		):
			first = erp_sync.sync_ap_opening("AP Opening", [row], "chk-ap-1")
			second = erp_sync.sync_ap_opening("AP Opening", [row], "chk-ap-1")

		self.assertEqual(first["rows_created"], 1)
		self.assertEqual(second["rows_updated"], 1)
		self.assertEqual(len(created_docs), 1)
		erp_sync.frappe.db.set_value.assert_called_once()

	def test_sync_supplier_soa_aliases_sync_ap_opening(self):
		rows = [{"supplier": "Acme Supply", "invoice_no": "INV-001"}]
		expected = {"rows_processed": 1, "rows_created": 1, "rows_updated": 0, "rows_failed": 0, "errors": []}
		with patch.object(erp_sync, "sync_ap_opening", return_value=expected) as sync_ap_opening:
			result = erp_sync.sync_supplier_soa("Supplier SOA", rows, "chk-supplier-1")

		sync_ap_opening.assert_called_once_with(
			sheet_name="Supplier SOA",
			data=rows,
			checksum="chk-supplier-1",
		)
		self.assertEqual(result, expected)

	def test_sync_authorization_blocks_guest(self):
		erp_sync.frappe.session.user = "Guest"
		erp_sync.frappe.get_roles = MagicMock(return_value=[])

		with self.assertRaises(erp_sync.frappe.PermissionError):
			erp_sync._assert_sync_authorized()

	def test_sync_authorization_blocks_unscoped_role(self):
		erp_sync.frappe.session.user = "viewer@bebang.ph"
		erp_sync.frappe.get_roles = MagicMock(return_value=["Employee"])

		with self.assertRaises(erp_sync.frappe.PermissionError):
			erp_sync._assert_sync_authorized()

	def test_sync_authorization_allows_scoped_role(self):
		erp_sync.frappe.session.user = "finance@bebang.ph"
		erp_sync.frappe.get_roles = MagicMock(return_value=["Accounts Manager"])

		# Should not raise
		erp_sync._assert_sync_authorized()

	def test_sync_ar_aging_rolls_back_on_row_error(self):
		captured_savepoints = []

		def _capture_savepoint(name):
			captured_savepoints.append(name)
			return None

		erp_sync.frappe.db.savepoint = MagicMock(side_effect=_capture_savepoint)
		erp_sync.frappe.db.rollback = MagicMock()
		erp_sync.frappe.db.release_savepoint = MagicMock()
		erp_sync.frappe.db.exists = MagicMock(side_effect=RuntimeError("db offline"))
		erp_sync.frappe.get_meta = MagicMock(return_value=types.SimpleNamespace(has_field=lambda field: True))

		result = erp_sync.sync_ar_aging(
			sheet_name="AR Aging",
			data=[{"invoice_no": "SINV-ERR", "outstanding": 100}],
			checksum="chk-ar-rollback",
		)

		self.assertEqual(result["rows_failed"], 1)
		self.assertEqual(len(captured_savepoints), 1)
		erp_sync.frappe.db.rollback.assert_called_once_with(save_point=captured_savepoints[0])


if __name__ == "__main__":
	unittest.main()
