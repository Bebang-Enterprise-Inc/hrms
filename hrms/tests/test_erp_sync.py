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
	frappe.get_site_path = lambda *parts: str(ROOT / "tmp_test_site" / Path(*parts))
	frappe.__dict__["session"] = types.SimpleNamespace(user="Administrator")
	frappe.get_roles = lambda user=None: ["System Manager"] if user and user != "Guest" else []
	frappe.__dict__["request"] = types.SimpleNamespace(headers={}, data=b"")
	frappe.__dict__["db"] = types.SimpleNamespace(
		exists=lambda *args, **kwargs: None,
		get_value=lambda *args, **kwargs: None,
		set_value=lambda *args, **kwargs: None,
		savepoint=lambda *args, **kwargs: None,
		release_savepoint=lambda *args, **kwargs: None,
		rollback=lambda *args, **kwargs: None,
		commit=lambda *args, **kwargs: None,
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
	utils.flt = lambda value, precision=None: round(float(value or 0), precision or 2)
	utils.cint = lambda value: int(float(value or 0))
	utils.getdate = (
		lambda value=None: datetime.date.fromisoformat(str(value)) if value else datetime.date(2026, 1, 1)
	)

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils


_install_fake_frappe()


def _install_fake_hrms_utils():
	hrms_pkg = types.ModuleType("hrms")
	hrms_pkg.__path__ = [str(ROOT / "hrms")]
	utils_pkg = types.ModuleType("hrms.utils")
	utils_pkg.__path__ = [str(ROOT / "hrms" / "utils")]

	builder_spec = importlib.util.spec_from_file_location(
		"hrms.utils.store_order_demand_snapshot",
		ROOT / "hrms" / "utils" / "store_order_demand_snapshot.py",
	)
	builder_module = importlib.util.module_from_spec(builder_spec)
	assert builder_spec and builder_spec.loader
	sys.modules["hrms.utils.store_order_demand_snapshot"] = builder_module
	builder_spec.loader.exec_module(builder_module)

	store_inventory_spec = importlib.util.spec_from_file_location(
		"hrms.utils.store_inventory_shadow_sync",
		ROOT / "hrms" / "utils" / "store_inventory_shadow_sync.py",
	)
	store_inventory_module = importlib.util.module_from_spec(store_inventory_spec)
	assert store_inventory_spec and store_inventory_spec.loader
	sys.modules["hrms.utils.store_inventory_shadow_sync"] = store_inventory_module
	store_inventory_spec.loader.exec_module(store_inventory_module)

	utils_pkg.store_order_demand_snapshot = builder_module
	utils_pkg.store_inventory_shadow_sync = store_inventory_module
	hrms_pkg.utils = utils_pkg

	sys.modules["hrms"] = hrms_pkg
	sys.modules["hrms.utils"] = utils_pkg


_install_fake_hrms_utils()
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
		self.flags = types.SimpleNamespace()
		self._on_insert = on_insert
		self.insert_calls = 0
		self.save_calls = 0
		self.submit_calls = 0

	def append(self, table, row):
		if table == "items":
			self.items.append(row)

	def set(self, fieldname, value):
		setattr(self, fieldname, value)

	def insert(self, ignore_permissions=False):
		self.insert_calls += 1
		if self._on_insert:
			self._on_insert(self)
		if not self.name:
			self.name = f"{self.doctype}-0001"
		return self

	def submit(self):
		self.submit_calls += 1

	def save(self, ignore_permissions=False):
		self.save_calls += 1
		return self

	def db_set(self, fieldname, value, update_modified=False):
		setattr(self, fieldname, value)


def _build_fake_get_doc(registry, counters=None):
	counters = counters or {}

	def get_doc(arg1, arg2=None):
		if isinstance(arg1, dict):
			payload = dict(arg1)
			doctype = payload.pop("doctype")
			doc = _FakeDoc(doctype)
			for key, value in payload.items():
				setattr(doc, key, value)
			if not hasattr(doc, "items"):
				doc.items = []

			def on_insert(inserted_doc):
				counters[doctype] = counters.get(doctype, 0) + 1
				if not inserted_doc.name:
					for candidate_field in ("supplier_code", "pr_no", "po_no", "gr_no"):
						candidate_value = getattr(inserted_doc, candidate_field, None)
						if candidate_value:
							inserted_doc.name = candidate_value
							break
				if not inserted_doc.name:
					inserted_doc.name = f"{doctype}-{counters[doctype]:04d}"
				registry.setdefault(doctype, {})[inserted_doc.name] = inserted_doc

			doc._on_insert = on_insert
			return doc

		doctype = arg1
		name = arg2
		return registry[doctype][name]

	return get_doc


class TestErpSync(unittest.TestCase):
	def setUp(self):
		erp_sync._FIELD_CACHE.clear()
		erp_sync.frappe.__dict__["session"] = types.SimpleNamespace(user="Administrator")
		erp_sync.frappe.get_roles = MagicMock(return_value=["System Manager"])
		erp_sync.frappe.db.savepoint = MagicMock(return_value=None)
		erp_sync.frappe.db.release_savepoint = MagicMock()
		erp_sync.frappe.db.rollback = MagicMock()
		erp_sync.frappe.get_meta = MagicMock(return_value=types.SimpleNamespace(has_field=lambda *_: True))

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

	def test_sync_store_demand_snapshot_upserts_by_snapshot_date_warehouse_item(self):
		created_snapshot_rows = {}
		created_docs = []

		def db_exists(doctype, name=None):
			if doctype in ("Item", "Warehouse"):
				return name or True
			return None

		def db_get_value(doctype, filters=None, fieldname=None):
			if doctype == "BEI Inventory Risk Snapshot" and isinstance(filters, dict):
				key = (
					filters.get("snapshot_date"),
					filters.get("warehouse"),
					filters.get("item_code"),
				)
				return created_snapshot_rows.get(key)
			return None

		def db_set_value(doctype, name, values, update_modified=False):
			if doctype != "BEI Inventory Risk Snapshot":
				return None
			for key, row_name in list(created_snapshot_rows.items()):
				if row_name == name:
					created_snapshot_rows[key] = name
					break
			return None

		def new_doc(doctype):
			if doctype != "BEI Inventory Risk Snapshot":
				return _FakeDoc(doctype)

			def on_insert(doc):
				doc.name = f"SNAP-{len(created_docs) + 1:04d}"
				created_docs.append(doc)
				key = (doc.snapshot_date, doc.warehouse, doc.item_code)
				created_snapshot_rows[key] = doc.name

			return _FakeDoc(doctype, on_insert=on_insert)

		erp_sync.frappe.db.exists = MagicMock(side_effect=db_exists)
		erp_sync.frappe.db.get_value = MagicMock(side_effect=db_get_value)
		erp_sync.frappe.db.set_value = MagicMock(side_effect=db_set_value)
		erp_sync.frappe.new_doc = MagicMock(side_effect=new_doc)
		erp_sync.frappe.get_meta = MagicMock(return_value=types.SimpleNamespace(has_field=lambda field: True))

		row = {
			"snapshot_date": "2026-03-09",
			"warehouse": "Store A - BEI",
			"item_code": "RM-001",
			"avg_daily_demand": 4.25,
			"available_qty": 12,
			"projected_sales": 0,
			"bom_consumption": 4.25,
			"lookback_days": 14,
			"signal_source": "sales_bom_snapshot",
		}

		first = erp_sync.sync_store_demand_snapshot(
			sheet_name="Demand Snapshot",
			data=[row],
			checksum="chk-demand-1",
		)
		second = erp_sync.sync_store_demand_snapshot(
			sheet_name="Demand Snapshot",
			data=[row],
			checksum="chk-demand-1",
		)

		self.assertEqual(first["rows_created"], 1)
		self.assertEqual(second["rows_updated"], 1)
		self.assertEqual(len(created_docs), 1)
		erp_sync.frappe.db.set_value.assert_called_once()

	def test_enqueue_scheduled_store_demand_snapshot_sync_queues_daily_job(self):
		erp_sync.frappe.enqueue = MagicMock()

		result = erp_sync.enqueue_scheduled_store_demand_snapshot_sync(
			snapshot_date="2026-03-10", lookback_days=28
		)

		self.assertTrue(result["queued"])
		self.assertEqual(result["job_id"], "scheduled_store_demand_snapshot:2026-03-10")
		erp_sync.frappe.enqueue.assert_called_once_with(
			"hrms.api.erp_sync.run_scheduled_store_demand_snapshot_sync",
			queue="long",
			job_id="scheduled_store_demand_snapshot:2026-03-10",
			enqueue_after_commit=True,
			snapshot_date="2026-03-10",
			lookback_days=28,
		)

	def test_run_scheduled_store_demand_snapshot_sync_builds_and_syncs_rows(self):
		builder_module = erp_sync.store_demand_snapshot_builder
		builder_outputs = {
			"start_date": "2026-02-11",
			"end_date": "2026-03-09",
			"product_daily_rows": [],
			"item_daily_rows": [],
			"snapshot_rows": [
				{
					"snapshot_date": "2026-03-10",
					"warehouse": "Store A - BEI",
					"item_code": "RM-001",
					"avg_daily_demand": 1.25,
					"projected_sales": 0,
					"bom_consumption": 1.25,
					"lookback_days": 28,
					"signal_source": "sales_bom_snapshot",
					"channel_mix": "POS,Web",
					"source_reference": "{}",
				}
			],
			"mapping_audit_rows": [],
			"excluded_rows": [],
			"unmapped_rows": [],
		}

		with (
			patch.object(builder_module, "build_outputs", return_value=builder_outputs) as build_mock,
			patch.object(builder_module, "write_csv", MagicMock()),
			patch.object(
				erp_sync,
				"_sync_store_demand_snapshot_rows",
				return_value={"rows_created": 1, "rows_updated": 0, "rows_failed": 0, "errors": []},
			) as sync_mock,
			patch.object(erp_sync.frappe, "log_error", MagicMock()),
		):
			result = erp_sync.run_scheduled_store_demand_snapshot_sync(
				snapshot_date="2026-03-10",
				lookback_days=28,
			)

		build_mock.assert_called_once()
		sync_mock.assert_called_once()
		self.assertEqual(result["snapshot_rows"], 1)
		self.assertEqual(result["unmapped_products"], 0)
		self.assertEqual(result["sync_result"]["rows_created"], 1)

	def test_enqueue_scheduled_store_inventory_shadow_sync_queues_daily_job(self):
		erp_sync.frappe.enqueue = MagicMock()

		result = erp_sync.enqueue_scheduled_store_inventory_shadow_sync(
			run_date="2026-03-10",
			force=True,
		)

		self.assertTrue(result["queued"])
		self.assertEqual(result["job_id"], "scheduled_store_inventory_shadow_sync:2026-03-10")
		erp_sync.frappe.enqueue.assert_called_once_with(
			"hrms.api.erp_sync.run_scheduled_store_inventory_shadow_sync",
			queue="long",
			job_id="scheduled_store_inventory_shadow_sync:2026-03-10",
			enqueue_after_commit=True,
			run_date="2026-03-10",
			force=True,
		)

	def test_run_scheduled_store_inventory_shadow_sync_executes_builder(self):
		builder_module = erp_sync.store_inventory_shadow_sync_builder
		builder_result = {
			"run_date": "2026-03-10",
			"enabled_stores": 46,
			"imported_stores": 44,
			"skipped_unchanged": 2,
			"rows_created": 3200,
			"rows_updated": 0,
			"rows_failed": 0,
			"failed_stores": [],
		}

		with (
			patch.object(builder_module, "run_store_inventory_shadow_sync", return_value=builder_result) as run_mock,
			patch.object(erp_sync.frappe, "log_error", MagicMock()),
		):
			result = erp_sync.run_scheduled_store_inventory_shadow_sync(
				run_date="2026-03-10",
				force=False,
			)

		run_mock.assert_called_once_with(run_date="2026-03-10", force=False)
		self.assertEqual(result["imported_stores"], 44)
		self.assertEqual(result["rows_created"], 3200)

	def test_resolve_warehouse_accepts_warehouse_name_lookup(self):
		def db_exists(doctype, name=None):
			if doctype == "Warehouse":
				return name == "Store A - BEI"
			return None

		def db_get_value(doctype, filters=None, fieldname=None):
			if doctype == "Warehouse" and filters == {"warehouse_name": "Store A"}:
				return "Store A - BEI"
			return None

		erp_sync.frappe.db.exists = MagicMock(side_effect=db_exists)
		erp_sync.frappe.db.get_value = MagicMock(side_effect=db_get_value)

		assert erp_sync._resolve_warehouse("Store A") == "Store A - BEI"

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
			"billed_to": "BEBANG SHAW INC",
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
		self.assertEqual(created_docs[0].bei_legal_entity, "BEI")
		self.assertEqual(created_docs[0].bei_store_label, "Stores - BEI")
		erp_sync.frappe.db.set_value.assert_called_once()
		update_fields = erp_sync.frappe.db.set_value.call_args[0][2]
		self.assertEqual(update_fields["bei_legal_entity"], "BEI")
		self.assertEqual(update_fields["bei_store_label"], "Stores - BEI")

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

	def test_sync_ap_opening_supports_supplier_soa_headers_and_skips_zero_balance_rows(self):
		created_docs = []

		def db_get_value(doctype, filters=None, fieldname=None):
			if doctype == "Purchase Invoice" and isinstance(filters, dict):
				return None
			return None

		def new_doc(doctype):
			if doctype != "Purchase Invoice":
				return _FakeDoc(doctype)

			def on_insert(doc):
				doc.name = f"PI-{len(created_docs) + 1:04d}"
				created_docs.append(doc)

			return _FakeDoc(doctype, on_insert=on_insert)

		erp_sync.frappe.db.get_value = MagicMock(side_effect=db_get_value)
		erp_sync.frappe.db.set_value = MagicMock()
		erp_sync.frappe.new_doc = MagicMock(side_effect=new_doc)
		erp_sync.frappe.log_error = MagicMock()
		erp_sync.frappe.get_meta = MagicMock(return_value=types.SimpleNamespace(has_field=lambda field: True))

		rows = [
			{
				"supplier_name": "1 TO 1 MARKETING INC.",
				"invoice_no.": "INV-ZERO",
				"amount": 1200,
				"outstanding_balance": 0,
				"invoice_date": "2026-01-05",
				"due_date": "2026-01-20",
				"billed_to": "BEBANG SHAW INC",
			},
			{
				"supplier_name": "1 TO 1 MARKETING INC.",
				"invoice_no.": "INV-OPEN",
				"amount": 1200,
				"outstanding_balance": 40,
				"invoice_date": "2026-01-05",
				"due_date": "2026-01-20",
				"billed_to": "BEBANG SHAW INC",
			},
		]

		with (
			patch.object(erp_sync, "_ensure_ap_opening_item", return_value="ERP-SYNC-AP-OPENING"),
			patch.object(erp_sync, "_normalize_company", return_value="BEI"),
			patch.object(erp_sync, "_ensure_supplier", return_value="SUP-0001"),
			patch.object(erp_sync, "_default_expense_account", return_value="Expense - BEI"),
			patch.object(erp_sync, "_default_payable_account", return_value="Payable - BEI"),
			patch.object(erp_sync, "_default_cost_center", return_value="Main - BEI"),
			patch.object(erp_sync, "_doctype_has_field", return_value=True),
		):
			result = erp_sync.sync_ap_opening("Supplier SOA", rows, "chk-ap-soa-1")

		self.assertEqual(result["rows_created"], 1)
		self.assertEqual(result["rows_updated"], 1)
		self.assertEqual(result["rows_failed"], 0)
		self.assertEqual(len(created_docs), 1)
		self.assertEqual(created_docs[0].bill_no, "INV-OPEN")
		self.assertEqual(created_docs[0].items[0]["rate"], 40)

	def test_sync_procurement_suppliers_creates_then_updates_by_supplier_code(self):
		registry = {}
		counters = {}

		def db_exists(doctype, name=None):
			if doctype == "BEI Supplier":
				return name if name in registry.get("BEI Supplier", {}) else None
			return None

		def db_get_value(doctype, filters=None, fieldname=None):
			if doctype == "BEI Supplier" and isinstance(filters, dict):
				supplier_name = filters.get("supplier_name")
				for supplier in registry.get("BEI Supplier", {}).values():
					if getattr(supplier, "supplier_name", None) == supplier_name:
						return supplier.name
			return None

		erp_sync.frappe.db.exists = MagicMock(side_effect=db_exists)
		erp_sync.frappe.db.get_value = MagicMock(side_effect=db_get_value)
		erp_sync.frappe.get_doc = MagicMock(side_effect=_build_fake_get_doc(registry, counters))

		row = {
			"supplier_code": "GPDNC5",
			"supplier_name": "GLOBAL PACIFIC DISTRIBUTION NETWORK CORP.",
			"contact_no": "09615113774",
			"email_id": "nice@globalpacific.com.ph",
		}
		updated_row = dict(row, contact_no="09170000000")

		first = erp_sync.sync_procurement_suppliers("Procurement Suppliers", [row], "chk-proc-supplier-1")
		second = erp_sync.sync_procurement_suppliers(
			"Procurement Suppliers", [updated_row], "chk-proc-supplier-2"
		)

		self.assertEqual(first["rows_created"], 1)
		self.assertEqual(second["rows_updated"], 1)
		self.assertEqual(len(registry["BEI Supplier"]), 1)
		self.assertEqual(registry["BEI Supplier"]["GPDNC5"].contact_number, "09170000000")

	def test_sync_procurement_requisitions_upserts_parent_and_child_rows(self):
		registry = {}
		counters = {}

		def db_exists(doctype, name=None):
			if doctype == "BEI Purchase Requisition":
				return name if name in registry.get("BEI Purchase Requisition", {}) else None
			if doctype == "User":
				return bool(name and "@" in str(name))
			return None

		def db_get_value(doctype, filters=None, fieldname=None):
			if doctype == "BEI Purchase Requisition" and isinstance(filters, dict):
				pr_no = filters.get("pr_no")
				for doc in registry.get("BEI Purchase Requisition", {}).values():
					if getattr(doc, "pr_no", None) == pr_no:
						return doc.name
			return None

		erp_sync.frappe.db.exists = MagicMock(side_effect=db_exists)
		erp_sync.frappe.db.get_value = MagicMock(side_effect=db_get_value)
		erp_sync.frappe.get_doc = MagicMock(side_effect=_build_fake_get_doc(registry, counters))

		row = {
			"pr_no": "PR202510",
			"timestamp": "2025-09-24 12:38:30",
			"delivery_to": "JENTEC WAREHOUSE",
			"purpose": "warehouse stock replenishment",
			"date_required": "2025-09-26",
			"recurring": "Yes",
			"requested_by": "Ian Dionisio",
			"requested_by_email": "ian@bebang.ph",
			"approval": "Approved",
			"approved_by": "Aldrin",
			"approved_by_email": "aldrin@bebang.ph",
			"approval_timestamp": "2025-09-25 10:38:30",
		}
		related_data = {
			"procurement_pr_items": [
				{
					"pr_no": "PR202510",
					"item_code": "CM34",
					"description": "SANDO ECO BAG LARGE",
					"total_order": 5000,
					"unit_of_issue": "PIECE",
					"po_reference": "PO-20253",
					"added_by": "Ian Dionisio",
				}
			]
		}

		with patch.object(erp_sync, "_resolve_warehouse", return_value="Stores - BEI"):
			first = erp_sync.sync_procurement_requisitions(
				"Procurement Requisitions",
				[row],
				"chk-proc-pr-1",
				related_data=related_data,
			)
			second = erp_sync.sync_procurement_requisitions(
				"Procurement Requisitions",
				[row],
				"chk-proc-pr-2",
				related_data=related_data,
			)

		self.assertEqual(first["rows_created"], 1)
		self.assertEqual(second["rows_updated"], 1)
		stored = next(iter(registry["BEI Purchase Requisition"].values()))
		self.assertEqual(stored.pr_no, "PR202510")
		self.assertEqual(stored.status, "Converted to PO")
		self.assertEqual(len(stored.items), 1)
		self.assertEqual(stored.items[0]["item_code"], "CM34")

	def test_sync_procurement_requisitions_ignores_po_reference_when_child_field_missing(self):
		registry = {}
		counters = {}

		def db_exists(doctype, name=None):
			if doctype == "BEI Purchase Requisition":
				return name if name in registry.get("BEI Purchase Requisition", {}) else None
			if doctype == "User":
				return bool(name and "@" in str(name))
			return None

		def db_get_value(doctype, filters=None, fieldname=None):
			if doctype == "BEI Purchase Requisition" and isinstance(filters, dict):
				pr_no = filters.get("pr_no")
				for doc in registry.get("BEI Purchase Requisition", {}).values():
					if getattr(doc, "pr_no", None) == pr_no:
						return doc.name
			return None

		def fake_get_meta(doctype):
			if doctype == "BEI PR Item":
				return types.SimpleNamespace(has_field=lambda field: field != "po_reference")
			return types.SimpleNamespace(has_field=lambda _field: True)

		erp_sync.frappe.db.exists = MagicMock(side_effect=db_exists)
		erp_sync.frappe.db.get_value = MagicMock(side_effect=db_get_value)
		erp_sync.frappe.get_doc = MagicMock(side_effect=_build_fake_get_doc(registry, counters))
		erp_sync.frappe.get_meta = MagicMock(side_effect=fake_get_meta)

		row = {
			"pr_no": "PR202511",
			"timestamp": "2025-09-24 12:38:30",
			"delivery_to": "JENTEC WAREHOUSE",
			"purpose": "warehouse stock replenishment",
			"date_required": "2025-09-26",
			"requested_by": "Ian Dionisio",
			"requested_by_email": "ian@bebang.ph",
		}
		related_data = {
			"procurement_pr_items": [
				{
					"pr_no": "PR202511",
					"item_code": "CM34",
					"description": "SANDO ECO BAG LARGE",
					"total_order": 5000,
					"unit_of_issue": "PIECE",
					"po_reference": "PO-20253",
				}
			]
		}

		with patch.object(erp_sync, "_resolve_warehouse", return_value="Stores - BEI"):
			result = erp_sync.sync_procurement_requisitions(
				"Procurement Requisitions",
				[row],
				"chk-proc-pr-guard-1",
				related_data=related_data,
			)

		self.assertEqual(result["rows_created"], 1)
		self.assertEqual(result["rows_failed"], 0)
		stored = next(iter(registry["BEI Purchase Requisition"].values()))
		self.assertEqual(stored.status, "Converted to PO")
		self.assertNotIn("po_reference", stored.items[0])

	def test_sync_procurement_requisitions_truncates_long_po_reference(self):
		registry = {}
		counters = {}

		def db_exists(doctype, name=None):
			if doctype == "BEI Purchase Requisition":
				return name if name in registry.get("BEI Purchase Requisition", {}) else None
			if doctype == "User":
				return bool(name and "@" in str(name))
			return None

		def db_get_value(doctype, filters=None, fieldname=None):
			if doctype == "BEI Purchase Requisition" and isinstance(filters, dict):
				pr_no = filters.get("pr_no")
				for doc in registry.get("BEI Purchase Requisition", {}).values():
					if getattr(doc, "pr_no", None) == pr_no:
						return doc.name
			return None

		erp_sync.frappe.db.exists = MagicMock(side_effect=db_exists)
		erp_sync.frappe.db.get_value = MagicMock(side_effect=db_get_value)
		erp_sync.frappe.get_doc = MagicMock(side_effect=_build_fake_get_doc(registry, counters))

		long_po_reference = (
			"DEC 16 - 3MD / 50K CUP AND LID, DEC 17 - JENTEC / 50K CUP AND LID "
			"DEC 18 - 3MD / 50K CUP AND LID, DEC 19 - JENTEC / 50K CUP AND LID "
			"DEC 20 - 3MD / 50K CUP AND LID DEC 22 - 3MD / 50K CUP AND LID"
		)
		row = {
			"pr_no": "PR2025249_12e1548d",
			"timestamp": "2025-12-14 07:28:55",
			"delivery_to": "JENTEC WAREHOUSE",
			"purpose": "Legacy import",
			"date_required": "2025-12-16",
			"requested_by": "Ian Dionisio",
			"requested_by_email": "ian@bebang.ph",
		}
		related_data = {
			"procurement_pr_items": [
				{
					"pr_no": "PR2025249_12e1548d",
					"item_code": "PM001",
					"description": "16OZ CUP WITH LOGO",
					"total_order": 600000,
					"unit_of_issue": "PIECE",
					"po_reference": long_po_reference,
					"added_by": "Ian Dionisio",
				}
			]
		}

		with patch.object(erp_sync, "_resolve_warehouse", return_value="Stores - BEI"):
			result = erp_sync.sync_procurement_requisitions(
				"Procurement Requisitions",
				[row],
				"chk-proc-pr-truncate-1",
				related_data=related_data,
			)

		self.assertEqual(result["rows_created"], 1)
		self.assertEqual(result["rows_failed"], 0)
		stored = next(iter(registry["BEI Purchase Requisition"].values()))
		self.assertLessEqual(len(stored.items[0]["po_reference"]), 140)
		self.assertTrue(stored.items[0]["po_reference"].endswith("..."))

	def test_sync_procurement_purchase_orders_creates_then_updates_status(self):
		registry = {
			"BEI Supplier": {},
			"BEI Purchase Requisition": {},
		}
		counters = {}
		supplier = _FakeDoc("BEI Supplier")
		supplier.name = "1T1MI3"
		supplier.supplier_name = "1 To 1 Marketing, Inc."
		registry["BEI Supplier"][supplier.name] = supplier
		pr_doc = _FakeDoc("BEI Purchase Requisition")
		pr_doc.name = "BEI Purchase Requisition-0001"
		pr_doc.pr_no = "PR202513"
		registry["BEI Purchase Requisition"][pr_doc.name] = pr_doc

		def db_exists(doctype, name=None):
			if doctype in registry:
				return name if name in registry.get(doctype, {}) else None
			return None

		def db_get_value(doctype, filters=None, fieldname=None):
			if doctype == "BEI Purchase Order" and isinstance(filters, dict):
				po_no = filters.get("po_no")
				for doc in registry.get("BEI Purchase Order", {}).values():
					if getattr(doc, "po_no", None) == po_no:
						return doc.name
			if doctype == "BEI Purchase Requisition" and isinstance(filters, dict):
				pr_no = filters.get("pr_no")
				for doc in registry.get("BEI Purchase Requisition", {}).values():
					if getattr(doc, "pr_no", None) == pr_no:
						return doc.name
			if doctype == "BEI Supplier" and isinstance(filters, dict):
				supplier_name = filters.get("supplier_name")
				for doc in registry.get("BEI Supplier", {}).values():
					if getattr(doc, "supplier_name", None) == supplier_name:
						return doc.name
			return None

		erp_sync.frappe.db.exists = MagicMock(side_effect=db_exists)
		erp_sync.frappe.db.get_value = MagicMock(side_effect=db_get_value)
		erp_sync.frappe.get_doc = MagicMock(side_effect=_build_fake_get_doc(registry, counters))

		row = {
			"po_no": "PO-20252",
			"po_date": "2025-09-26",
			"pr_no": "PR202513",
			"supplier_code": "1T1MI3",
			"supplier_name": "1 To 1 Marketing, Inc.",
			"delivery_date": "2025-09-26",
			"terms_of_payment": "30 days",
			"approval": "Approved",
		}
		related_data = {
			"procurement_po_items": [
				{
					"po_no": "PO-20252",
					"item_code": "A016",
					"item_name": "ALASKA EVAP 1L",
					"qty": 50,
					"uom": "BOX",
					"unit_cost": 926.02,
					"vat": 111.12,
				}
			]
		}

		with (
			patch.object(erp_sync, "_resolve_warehouse", return_value="Stores - BEI"),
			patch.object(erp_sync, "_resolve_payment_terms_template", return_value=None),
		):
			first = erp_sync.sync_procurement_purchase_orders(
				"Procurement Purchase Orders",
				[row],
				"chk-proc-po-1",
				related_data=related_data,
			)
			second = erp_sync.sync_procurement_purchase_orders(
				"Procurement Purchase Orders",
				[dict(row, send_po_to_supplier_timestamp="2025-09-26 17:50:45", sent_by="Aldrin")],
				"chk-proc-po-2",
				related_data=related_data,
			)

		self.assertEqual(first["rows_created"], 1)
		self.assertEqual(second["rows_updated"], 1)
		stored = next(iter(registry["BEI Purchase Order"].values()))
		self.assertEqual(stored.po_no, "PO-20252")
		self.assertEqual(stored.status, "Sent to Supplier")
		self.assertEqual(len(stored.items), 1)
		self.assertEqual(stored.items[0]["item_code"], "A016")

	def test_sync_procurement_goods_receipts_updates_po_received_quantities(self):
		registry = {
			"BEI Purchase Order": {},
			"BEI Goods Receipt": {},
		}
		counters = {}

		po_doc = _FakeDoc("BEI Purchase Order")
		po_doc.name = "BEI Purchase Order-0001"
		po_doc.po_no = "PO-20253"
		po_doc.status = "Sent to Supplier"
		po_doc.items = [
			types.SimpleNamespace(
				name="POITEM-0001",
				item_code="CM34",
				qty=5000,
				unit_cost=4.55,
				received_qty=0,
			)
		]
		registry["BEI Purchase Order"][po_doc.name] = po_doc

		def db_exists(doctype, name=None):
			if doctype in registry:
				return name if name in registry.get(doctype, {}) else None
			if doctype == "Item":
				return name == "CM34"
			if doctype == "UOM":
				return bool(name)
			return None

		def db_get_value(doctype, filters=None, fieldname=None):
			if doctype == "BEI Purchase Order" and isinstance(filters, dict):
				po_no = filters.get("po_no")
				for doc in registry.get("BEI Purchase Order", {}).values():
					if getattr(doc, "po_no", None) == po_no:
						return doc.name
			if doctype == "BEI Goods Receipt" and isinstance(filters, dict):
				gr_no = filters.get("gr_no")
				for doc in registry.get("BEI Goods Receipt", {}).values():
					if getattr(doc, "gr_no", None) == gr_no:
						return doc.name
			return None

		erp_sync.frappe.db.exists = MagicMock(side_effect=db_exists)
		erp_sync.frappe.db.get_value = MagicMock(side_effect=db_get_value)
		erp_sync.frappe.db.set_value = MagicMock()
		erp_sync.frappe.get_doc = MagicMock(side_effect=_build_fake_get_doc(registry, counters))

		row = {
			"gr_no": "GR202561",
			"po_no": "PO-20253",
			"date": "2025-10-20",
			"issue_to": "JENTEC",
			"invoice_no": "122952",
			"invoice": "Supplier Invoices/GR202561.Invoice.044645.jpg",
			"approved_by": "Ian Dionisio",
		}
		related_data = {
			"procurement_gr_items": [
				{
					"gr_no": "GR202561",
					"po_no": "PO-20253",
					"item_code": "CM34",
					"item_name": "SANDO ECO BAG LARGE",
					"uom": "PIECE",
					"issued_qty": 5000,
				}
			]
		}

		with (
			patch.object(erp_sync, "_resolve_warehouse", return_value="Stores - BEI"),
			patch.object(erp_sync, "_resolve_uom", return_value="PIECE"),
		):
			result = erp_sync.sync_procurement_goods_receipts(
				"Procurement Goods Receipts",
				[row],
				"chk-proc-gr-1",
				related_data=related_data,
			)

		self.assertEqual(result["rows_created"], 1)
		stored_gr = next(iter(registry["BEI Goods Receipt"].values()))
		self.assertEqual(stored_gr.gr_no, "GR202561")
		self.assertEqual(stored_gr.status, "Accepted")
		self.assertEqual(po_doc.items[0].received_qty, 5000)
		self.assertEqual(po_doc.status, "Fully Received")
		self.assertEqual(stored_gr.supplier_invoice_photo, "/files/GR202561.Invoice.044645.jpg")
		self.assertTrue(stored_gr.flags.ignore_mandatory)

	def test_sync_procurement_goods_receipts_skips_supplier_invoice_photo_when_field_missing(self):
		registry = {
			"BEI Purchase Order": {},
			"BEI Goods Receipt": {},
		}
		counters = {}

		po_doc = _FakeDoc("BEI Purchase Order")
		po_doc.name = "BEI Purchase Order-0002"
		po_doc.po_no = "PO-20254"
		po_doc.status = "Sent to Supplier"
		po_doc.items = [
			types.SimpleNamespace(
				name="POITEM-0002",
				item_code="CM35",
				qty=100,
				unit_cost=4.55,
				received_qty=0,
			)
		]
		registry["BEI Purchase Order"][po_doc.name] = po_doc

		def db_exists(doctype, name=None):
			if doctype in registry:
				return name if name in registry.get(doctype, {}) else None
			if doctype == "Item":
				return name == "CM35"
			if doctype == "UOM":
				return bool(name)
			return None

		def db_get_value(doctype, filters=None, fieldname=None):
			if doctype == "BEI Purchase Order" and isinstance(filters, dict):
				po_no = filters.get("po_no")
				for doc in registry.get("BEI Purchase Order", {}).values():
					if getattr(doc, "po_no", None) == po_no:
						return doc.name
			if doctype == "BEI Goods Receipt" and isinstance(filters, dict):
				gr_no = filters.get("gr_no")
				for doc in registry.get("BEI Goods Receipt", {}).values():
					if getattr(doc, "gr_no", None) == gr_no:
						return doc.name
			return None

		def fake_get_meta(doctype):
			if doctype == "BEI Goods Receipt":
				return types.SimpleNamespace(has_field=lambda field: field != "supplier_invoice_photo")
			return types.SimpleNamespace(has_field=lambda _field: True)

		erp_sync.frappe.db.exists = MagicMock(side_effect=db_exists)
		erp_sync.frappe.db.get_value = MagicMock(side_effect=db_get_value)
		erp_sync.frappe.db.set_value = MagicMock()
		erp_sync.frappe.get_doc = MagicMock(side_effect=_build_fake_get_doc(registry, counters))
		erp_sync.frappe.get_meta = MagicMock(side_effect=fake_get_meta)

		row = {
			"gr_no": "GR202562",
			"po_no": "PO-20254",
			"date": "2025-10-20",
			"issue_to": "JENTEC",
			"invoice_no": "122953",
			"invoice": "Supplier Invoices/GR202562.Invoice.044646.jpg",
			"approved_by": "Ian Dionisio",
		}
		related_data = {
			"procurement_gr_items": [
				{
					"gr_no": "GR202562",
					"po_no": "PO-20254",
					"item_code": "CM35",
					"item_name": "SANDO ECO BAG SMALL",
					"uom": "PIECE",
					"issued_qty": 100,
				}
			]
		}

		with (
			patch.object(erp_sync, "_resolve_warehouse", return_value="Stores - BEI"),
			patch.object(erp_sync, "_resolve_uom", return_value="PIECE"),
		):
			result = erp_sync.sync_procurement_goods_receipts(
				"Procurement Goods Receipts",
				[row],
				"chk-proc-gr-guard-1",
				related_data=related_data,
			)

		self.assertEqual(result["rows_created"], 1)
		self.assertEqual(result["rows_failed"], 0)
		stored_gr = next(iter(registry["BEI Goods Receipt"].values()))
		self.assertFalse(hasattr(stored_gr, "supplier_invoice_photo"))
		self.assertEqual(po_doc.items[0].received_qty, 100)

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
