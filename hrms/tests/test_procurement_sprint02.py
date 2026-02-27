import datetime
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_frappe():
	if "frappe" in sys.modules:
		return

	frappe = types.ModuleType("frappe")
	utils = types.ModuleType("frappe.utils")

	class ValidationError(Exception):
		pass

	class PermissionError(Exception):
		pass

	def whitelist(*args, **kwargs):
		def decorator(fn):
			return fn

		return decorator

	def _throw(message, exc=None):
		if isinstance(exc, type) and issubclass(exc, Exception):
			raise exc(message)
		raise Exception(message)

	def _getdate(value=None):
		if isinstance(value, datetime.date):
			return value
		if not value:
			return datetime.date(2026, 2, 27)
		return datetime.date.fromisoformat(str(value))

	def _flt(value, precision=None):
		num = float(value or 0)
		if precision is not None:
			return round(num, int(precision))
		return num

	def _add_days(date_obj, days):
		return _getdate(date_obj) + datetime.timedelta(days=int(days))

	def _first_day(date_obj):
		d = _getdate(date_obj)
		return datetime.date(d.year, d.month, 1)

	def _last_day(date_obj):
		d = _getdate(date_obj)
		if d.month == 12:
			return datetime.date(d.year, 12, 31)
		return datetime.date(d.year, d.month + 1, 1) - datetime.timedelta(days=1)

	frappe.whitelist = whitelist
	frappe._ = lambda text: text
	frappe.throw = _throw
	frappe.ValidationError = ValidationError
	frappe.PermissionError = PermissionError
	frappe.session = types.SimpleNamespace(user="Administrator")
	frappe.parse_json = lambda value: json.loads(value) if isinstance(value, str) else value
	frappe.has_permission = lambda *args, **kwargs: True
	frappe.get_roles = lambda user=None: ["System Manager"]
	frappe.log_error = lambda *args, **kwargs: None
	frappe.enqueue = lambda *args, **kwargs: None
	frappe.get_doc = lambda *args, **kwargs: None
	frappe.get_all = lambda *args, **kwargs: []
	frappe.db = types.SimpleNamespace(
		exists=lambda *args, **kwargs: None,
		get_value=lambda *args, **kwargs: None,
		set_value=lambda *args, **kwargs: None,
		sql=lambda *args, **kwargs: [],
	)

	utils.flt = _flt
	utils.cint = lambda value: int(float(value or 0))
	utils.getdate = _getdate
	utils.nowdate = lambda: "2026-02-27"
	utils.add_days = _add_days
	utils.get_first_day = _first_day
	utils.get_last_day = _last_day

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils


def _install_stub_dependencies():
	bei_config = types.ModuleType("hrms.utils.bei_config")
	bei_config.get_company = lambda: "Bebang Enterprises Inc."

	delivery_policy = types.ModuleType("hrms.utils.delivery_billing_policy")
	delivery_policy.CPO_APPROVER_EMAIL = "mae@bebang.ph"
	delivery_policy.CFO_APPROVER_EMAIL = "butch@bebang.ph"
	delivery_policy.append_approval_audit_log = lambda *args, **kwargs: None

	sys.modules["hrms.utils.bei_config"] = bei_config
	sys.modules["hrms.utils.delivery_billing_policy"] = delivery_policy


_install_fake_frappe()
_install_stub_dependencies()

procurement_spec = importlib.util.spec_from_file_location(
	"procurement_under_test",
	ROOT / "hrms" / "api" / "procurement.py",
)
procurement = importlib.util.module_from_spec(procurement_spec)
assert procurement_spec and procurement_spec.loader
procurement_spec.loader.exec_module(procurement)


class _FormDoc:
	def __init__(self, name="BEI-2307-2026-00001"):
		self.name = name
		self.insert_calls = 0
		self.save_calls = 0

	def insert(self, ignore_permissions=False):
		self.insert_calls += 1
		return self

	def save(self, ignore_permissions=False):
		self.save_calls += 1
		return self


class TestProcurementSprint02(unittest.TestCase):
	def setUp(self):
		procurement.frappe.session = types.SimpleNamespace(user="Administrator")
		procurement.frappe.db.exists = MagicMock(return_value=None)
		procurement.frappe.db.get_value = MagicMock(return_value=None)
		procurement.frappe.db.sql = MagicMock(return_value=[])
		procurement.frappe.get_all = MagicMock(return_value=[])
		procurement.frappe.get_doc = MagicMock()

	def test_generate_form_2307_entry_uses_structured_doctype(self):
		pay_req = types.SimpleNamespace(
			supplier="SUP-001",
			supplier_name="Supplier A",
			payment_date="2026-02-27",
			request_date="2026-02-27",
			payment_amount=1000,
			ewt_rate=1,
		)
		new_doc = _FormDoc()

		def _db_get_value(doctype, filters=None, fieldname=None):
			if doctype == "BEI Supplier":
				return "TIN-123456"
			if doctype == "BEI Form 2307":
				return None
			return None

		def _get_doc(*args, **kwargs):
			if args and args[0] == "BEI Payment Request":
				return pay_req
			if args and isinstance(args[0], dict):
				return new_doc
			raise AssertionError(f"Unexpected get_doc call: {args} {kwargs}")

		procurement.frappe.db.get_value = MagicMock(side_effect=_db_get_value)
		procurement.frappe.get_doc = MagicMock(side_effect=_get_doc)

		result = procurement.generate_form_2307_entry("PAY-0001")

		self.assertTrue(result["success"])
		self.assertEqual(new_doc.insert_calls, 1)
		self.assertEqual(result["data"]["payment_request_link"], "PAY-0001")
		self.assertEqual(result["data"]["name"], new_doc.name)

	def test_get_form_2307_data_reads_structured_records(self):
		procurement.frappe.get_all = MagicMock(
			return_value=[
				{
					"name": "BEI-2307-2026-00001",
					"supplier_tin": "TIN-1",
					"supplier_name": "Supplier A",
					"tax_period": "2026-02",
					"atc_code": "WI100",
					"gross_amount": 1000,
					"ewt_rate": 1,
					"ewt_amount": 10,
					"payment_request_link": "PAY-0001",
					"modified": "2026-02-27 10:00:00",
				},
				{
					"name": "BEI-2307-2026-00002",
					"supplier_tin": "TIN-1",
					"supplier_name": "Supplier A",
					"tax_period": "2026-02",
					"atc_code": "WI100",
					"gross_amount": 500,
					"ewt_rate": 1,
					"ewt_amount": 5,
					"payment_request_link": "PAY-0002",
					"modified": "2026-02-27 11:00:00",
				},
			]
		)

		result = procurement.get_form_2307_data()

		self.assertEqual(len(result["entries"]), 2)
		self.assertEqual(len(result["summary"]), 1)
		self.assertEqual(result["summary"][0]["total_gross"], 1500.0)
		self.assertEqual(result["summary"][0]["total_ewt"], 15.0)
		self.assertEqual(result["legacy_count"], 0)

	def test_get_advance_subsidiary_ledger_resolves_supplier_id(self):
		procurement.frappe.db.exists = MagicMock(return_value=True)

		def _db_get_value(doctype, filters=None, fieldname=None):
			if doctype == "BEI Supplier":
				if isinstance(filters, dict):
					return "SUP-001"
				return "Supplier A"
			return None

		def _db_sql(query, values=None, as_dict=False):
			if "FROM `tabBEI Payment Request`" in query:
				return [
					{
						"reference_name": "PAY-0001",
						"reference_type": "BEI Payment Request",
						"posting_date": "2026-02-20",
						"entry_type": "Advance Payment",
						"debit": 1000,
						"credit": 0,
						"remarks": "PO-0001",
					}
				]
			return [
				{
					"reference_name": "JV-0001",
					"reference_type": "Journal Entry",
					"posting_date": "2026-02-25",
					"entry_type": "Advance Clearing",
					"debit": 0,
					"credit": 400,
					"remarks": "Clear partial",
				}
			]

		procurement.frappe.db.get_value = MagicMock(side_effect=_db_get_value)
		procurement.frappe.db.sql = MagicMock(side_effect=_db_sql)

		result = procurement.get_advance_subsidiary_ledger("SUP-001")

		self.assertEqual(result["supplier"], "SUP-001")
		self.assertEqual(result["supplier_name"], "Supplier A")
		self.assertEqual(len(result["entries"]), 2)
		self.assertEqual(result["closing_balance"], 600.0)

	def test_get_g046_intercompany_summary_returns_counters(self):
		procurement.frappe.db.sql = MagicMock(
			side_effect=[
				[(1,)],  # information_schema custom_stock_entry exists
				[
					{
						"total_sales_invoices": 3,
						"mirrored_count": 2,
						"missing_purchase_invoice_count": 1,
						"total_sales_value": 4500,
					}
				],
			]
		)

		result = procurement.get_g046_intercompany_summary()

		self.assertEqual(result["total_sales_invoices"], 3)
		self.assertEqual(result["mirrored_count"], 2)
		self.assertEqual(result["missing_purchase_invoice_count"], 1)
		self.assertEqual(result["total_sales_value"], 4500.0)

	def test_get_g046_intercompany_transactions_paginates(self):
		procurement.frappe.db.sql = MagicMock(
			side_effect=[
				[(1,)],  # information_schema custom_stock_entry exists
				[(2,)],
				[
					{
						"sales_invoice": "SINV-0001",
						"posting_date": "2026-02-27",
						"customer": "Store A",
						"stock_entry": "MAT-STE-0001",
						"target_warehouse": "Store A - BEI",
						"sales_invoice_total": 1200,
						"sales_invoice_status": "Paid",
						"purchase_invoice": "PINV-0001",
						"purchase_invoice_total": 1200,
						"purchase_invoice_status": "Paid",
						"mirror_status": "Mirrored",
					}
				],
			]
		)

		result = procurement.get_g046_intercompany_transactions(page=1, page_size=10)

		self.assertEqual(result["total"], 2)
		self.assertEqual(result["page"], 1)
		self.assertEqual(len(result["data"]), 1)
		self.assertEqual(result["data"][0]["mirror_status"], "Mirrored")

	def test_get_g046_intercompany_transactions_fallback_when_stock_entry_column_missing(self):
		queries = []

		def _db_sql(query, values=None, as_dict=False):
			queries.append(query)
			if "information_schema.COLUMNS" in query:
				return []
			if "SELECT COUNT(*)" in query:
				return [(1,)]
			return [
				{
					"sales_invoice": "SINV-0009",
					"posting_date": "2026-02-27",
					"customer": "Store B",
					"stock_entry": "MAT-STE-0099",
					"target_warehouse": "Store B - BEI",
					"sales_invoice_total": 800,
					"sales_invoice_status": "Paid",
					"purchase_invoice": None,
					"purchase_invoice_total": None,
					"purchase_invoice_status": None,
					"mirror_status": "Sales Only",
				}
			]

		procurement.frappe.db.sql = MagicMock(side_effect=_db_sql)

		result = procurement.get_g046_intercompany_transactions(page=1, page_size=10, search="MAT-STE-0099")

		self.assertEqual(result["total"], 1)
		self.assertEqual(len(result["data"]), 1)
		self.assertEqual(result["data"][0]["mirror_status"], "Sales Only")

		joined_sql = " ".join(queries[1:])
		self.assertNotIn("IFNULL(si.custom_stock_entry, '') !=", joined_sql)
		self.assertIn("Inter-company Sales Invoice for Hub Transfer SE:", joined_sql)

	def test_bei_purchase_order_doctype_is_submittable(self):
		doctype_path = (
			ROOT
			/ "hrms"
			/ "hr"
			/ "doctype"
			/ "bei_purchase_order"
			/ "bei_purchase_order.json"
		)
		payload = json.loads(doctype_path.read_text(encoding="utf-8"))
		self.assertEqual(payload.get("is_submittable"), 1)

		manager_perm = next(
			perm for perm in payload.get("permissions", [])
			if perm.get("role") == "Procurement Manager"
		)
		self.assertEqual(manager_perm.get("submit"), 1)


if __name__ == "__main__":
	unittest.main()
