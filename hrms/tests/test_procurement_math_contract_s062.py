import importlib.util
import inspect
import json
import sys
import types
import unittest
from datetime import date
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
	model = types.ModuleType("frappe.model")
	document = types.ModuleType("frappe.model.document")

	class ValidationError(Exception):
		pass

	class PermissionError(Exception):
		pass

	class Document:
		pass

	def whitelist(*args, **kwargs):
		def decorator(fn):
			return fn

		return decorator

	def _throw(message, exc=None, title=None):
		if isinstance(exc, type) and issubclass(exc, Exception):
			raise exc(message)
		raise Exception(message)

	def _flt(value, precision=None):
		num = float(value or 0)
		if precision is not None:
			return round(num, int(precision))
		return num

	frappe.whitelist = whitelist
	frappe._ = lambda text: text
	frappe.throw = _throw
	frappe.ValidationError = ValidationError
	frappe.PermissionError = PermissionError
	frappe.__dict__["session"] = types.SimpleNamespace(user="Administrator")
	frappe.parse_json = lambda value: json.loads(value) if isinstance(value, str) else value
	frappe.has_permission = lambda *args, **kwargs: True
	frappe.get_roles = lambda user=None: ["System Manager"]
	frappe.log_error = lambda *args, **kwargs: None
	frappe.msgprint = lambda *args, **kwargs: None
	frappe.get_doc = lambda *args, **kwargs: None
	frappe.get_all = lambda *args, **kwargs: []
	frappe.__dict__["db"] = types.SimpleNamespace(
		exists=lambda *args, **kwargs: None,
		get_value=lambda *args, **kwargs: None,
		set_value=lambda *args, **kwargs: None,
		sql=lambda *args, **kwargs: [],
	)

	utils.flt = _flt
	utils.cint = lambda value: int(float(value or 0))
	utils.getdate = lambda value=None: value or "2026-03-18"
	utils.nowdate = lambda: "2026-03-18"
	utils.now_datetime = lambda: "2026-03-18 00:00:00"
	utils.add_days = lambda date_obj, days: date_obj
	utils.date_diff = lambda end_date, start_date: 0
	utils.get_first_day = lambda date_obj: date_obj
	utils.get_last_day = lambda date_obj: date_obj
	document.Document = Document

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils
	sys.modules["frappe.model"] = model
	sys.modules["frappe.model.document"] = document


def _install_stub_dependencies():
	hrms_api = types.ModuleType("hrms.api")

	bei_config = types.ModuleType("hrms.utils.bei_config")
	bei_config.get_company = lambda: "Bebang Enterprises Inc."

	delivery_policy = types.ModuleType("hrms.utils.delivery_billing_policy")
	delivery_policy.CPO_APPROVER_EMAIL = "mae@bebang.ph"
	delivery_policy.CFO_APPROVER_EMAIL = "butch@bebang.ph"
	delivery_policy.append_approval_audit_log = lambda *args, **kwargs: None

	standard_buying_bridge = types.ModuleType("hrms.utils.standard_buying_bridge")
	standard_buying_bridge.apply_standard_buying_context = lambda *args, **kwargs: None

	sys.modules["hrms.api"] = hrms_api
	sys.modules["hrms.utils.bei_config"] = bei_config
	sys.modules["hrms.utils.delivery_billing_policy"] = delivery_policy
	sys.modules["hrms.utils.standard_buying_bridge"] = standard_buying_bridge


_install_fake_frappe()
_install_stub_dependencies()

procurement_spec = importlib.util.spec_from_file_location(
	"procurement_under_test_s062",
	ROOT / "hrms" / "api" / "procurement.py",
)
procurement = importlib.util.module_from_spec(procurement_spec)
assert procurement_spec and procurement_spec.loader
procurement_spec.loader.exec_module(procurement)

purchase_order_spec = importlib.util.spec_from_file_location(
	"bei_purchase_order_under_test_s062",
	ROOT / "hrms" / "hr" / "doctype" / "bei_purchase_order" / "bei_purchase_order.py",
)
bei_purchase_order = importlib.util.module_from_spec(purchase_order_spec)
assert purchase_order_spec and purchase_order_spec.loader
purchase_order_spec.loader.exec_module(bei_purchase_order)

invoice_spec = importlib.util.spec_from_file_location(
	"bei_invoice_under_test_s062",
	ROOT / "hrms" / "hr" / "doctype" / "bei_invoice" / "bei_invoice.py",
)
bei_invoice = importlib.util.module_from_spec(invoice_spec)
assert invoice_spec and invoice_spec.loader
invoice_spec.loader.exec_module(bei_invoice)

payment_request_spec = importlib.util.spec_from_file_location(
	"bei_payment_request_under_test_s062",
	ROOT / "hrms" / "hr" / "doctype" / "bei_payment_request" / "bei_payment_request.py",
)
bei_payment_request = importlib.util.module_from_spec(payment_request_spec)
assert payment_request_spec and payment_request_spec.loader
payment_request_spec.loader.exec_module(bei_payment_request)


class _InsertedDoc:
	def __init__(self, name):
		self.name = name
		self.insert_calls = 0

	def insert(self, ignore_permissions=False):
		self.insert_calls += 1
		return self


class TestProcurementMathContractS062(unittest.TestCase):
	def setUp(self):
		procurement.frappe.__dict__["session"] = types.SimpleNamespace(user="Administrator")
		procurement.frappe.db.exists = MagicMock(return_value=True)
		procurement.frappe.db.get_value = MagicMock(return_value=None)
		procurement.frappe.db.sql = MagicMock(return_value=[])
		procurement.frappe.get_doc = MagicMock()

	def test_normalize_purchase_order_payload_recalculates_all_line_and_document_totals(self):
		payload = procurement._normalize_purchase_order_payload(
			{
				"discount_amount": 5000,
				"delivery_fee": 1500,
				"grand_total": 100,
				"items": [
					{"item_code": "RM018", "qty": 2000, "rate": 137, "vat_rate": 0, "uom": "Kg"},
					{"item_code": "CM34", "qty": 5000, "rate": 4.55, "vat_rate": 12, "uom": "Pc"},
				],
			}
		)

		self.assertEqual(payload["subtotal"], 296750.0)
		self.assertEqual(payload["vat_amount"], 2730.0)
		self.assertEqual(payload["grand_total"], 295980.0)
		self.assertEqual(payload["requires_dual_approval"], 0)
		self.assertEqual(payload["items"][0]["unit_cost"], 137.0)
		self.assertEqual(payload["items"][0]["amount"], 274000.0)
		self.assertEqual(payload["items"][1]["amount"], 25480.0)

	def test_create_purchase_order_uses_recalculated_grand_total_for_tin_threshold(self):
		supplier = types.SimpleNamespace(
			supplier_name="Marivic's Ube",
			tin=None,
			bir_2307="FILE-001",
			business_permit="FILE-002",
		)

		def _get_doc(*args, **kwargs):
			if args and args[0] == "BEI Supplier":
				return supplier
			raise AssertionError(f"Unexpected get_doc call: {args} {kwargs}")

		procurement.frappe.get_doc = MagicMock(side_effect=_get_doc)
		procurement.frappe.db.sql = MagicMock(return_value=[(0,)])

		with self.assertRaises(Exception) as exc:
			procurement.create_purchase_order(
				{
					"supplier": "MU9",
					"grand_total": 1,
					"items": [{"item_code": "FG012", "qty": 3000, "rate": 138, "vat_rate": 0, "uom": "Pack"}],
				}
			)

		self.assertIn("TIN registration", str(exc.exception))

	def test_create_invoice_recalculates_totals_from_items_and_drops_ui_only_payload(self):
		inserted_doc = _InsertedDoc("INV-2026-00001")
		captured_payload = {}

		def _get_doc(*args, **kwargs):
			if args and isinstance(args[0], dict):
				captured_payload.update(args[0])
				return inserted_doc
			raise AssertionError(f"Unexpected get_doc call: {args} {kwargs}")

		procurement.frappe.get_doc = MagicMock(side_effect=_get_doc)

		result = procurement.create_invoice(
			{
				"supplier": "MU9",
				"supplier_name": "Marivic's Ube",
				"supplier_invoice_no": "SI-001",
				"invoice_date": "2026-03-18",
				"due_date": "2026-04-17",
				"items": [
					{"item_code": "CM34", "qty": 5000, "rate": 4.55, "vat_rate": 12},
					{"item_code": "FG012", "qty": 1200, "rate": 135, "vat_rate": 0},
				],
				"subtotal": 1,
				"vat_amount": 1,
			}
		)

		self.assertTrue(result["success"])
		self.assertEqual(result["name"], "INV-2026-00001")
		self.assertEqual(inserted_doc.insert_calls, 1)
		self.assertEqual(captured_payload["subtotal"], 184750.0)
		self.assertEqual(captured_payload["vat_amount"], 2730.0)
		self.assertEqual(captured_payload["grand_total"], 187480.0)
		self.assertNotIn("items", captured_payload)

	def test_create_payment_request_allows_vatable_partial_receipt_up_to_gross_invoice_amount(self):
		invoice = types.SimpleNamespace(
			supplier="MU9",
			supplier_name="Marivic's Ube",
			purchase_order="PO-2026-00001",
			goods_receipt="GR-2026-00001",
			balance_due=142.10,
			grand_total=142.10,
			invoice_date="2026-03-18",
		)
		po = types.SimpleNamespace(grand_total=289.288, po_no="PO-2026-00001")
		inserted_doc = _InsertedDoc("PAY-2026-00001")
		captured_payload = {}

		def _sql(query, params=None, as_dict=False):
			if "SUM(advance_outstanding)" in query:
				return [(0,)]
			if "FROM `tabBEI PO Item`" in query:
				return [
					{
						"item_code": "RM018",
						"qty": 2,
						"unit_cost": 137,
						"vat_rate": 0,
						"vat_amount": 0,
					},
					{
						"item_code": "CM34",
						"qty": 3,
						"unit_cost": 4.55,
						"vat_rate": 12,
						"vat_amount": 1.638,
					},
				]
			if "FROM `tabBEI GR Item`" in query:
				return [
					{
						"item_code": "RM018",
						"accepted_qty": 1,
						"received_qty": 1,
						"rejected_qty": 0,
						"unit_cost": 137,
					},
					{
						"item_code": "CM34",
						"accepted_qty": 1,
						"received_qty": 1,
						"rejected_qty": 0,
						"unit_cost": 4.55,
					},
				]
			raise AssertionError(f"Unexpected SQL query: {query}")

		def _get_value(doctype, filters=None, fieldname=None, as_dict=False):
			if doctype == "BEI Invoice" and fieldname == "purchase_order":
				return "PO-2026-00001"
			return None

		def _get_doc(*args, **kwargs):
			if args and args[0] == "BEI Invoice":
				return invoice
			if args and args[0] == "BEI Purchase Order":
				return po
			if args and isinstance(args[0], dict):
				captured_payload.update(args[0])
				return inserted_doc
			raise AssertionError(f"Unexpected get_doc call: {args} {kwargs}")

		procurement.frappe.db.get_value = MagicMock(side_effect=_get_value)
		procurement.frappe.db.exists = MagicMock(return_value=True)
		procurement.frappe.db.sql = MagicMock(side_effect=_sql)
		procurement.frappe.get_doc = MagicMock(side_effect=_get_doc)

		result = procurement.create_payment_request(
			{
				"invoice": "INV-2026-00001",
				"payment_amount": 142.10,
				"payment_mode": "Bank Transfer",
			}
		)

		self.assertTrue(result["success"])
		self.assertEqual(result["name"], "PAY-2026-00001")
		self.assertEqual(inserted_doc.insert_calls, 1)
		self.assertEqual(captured_payload["invoice"], "INV-2026-00001")
		self.assertEqual(captured_payload["supplier"], "MU9")
		self.assertEqual(captured_payload["supplier_name"], "Marivic's Ube")
		self.assertEqual(captured_payload["purchase_order"], "PO-2026-00001")
		self.assertEqual(captured_payload["goods_receipt"], "GR-2026-00001")
		self.assertEqual(captured_payload["payment_amount"], 142.10)
		self.assertEqual(captured_payload["rfp_type"], "Vendor Invoice")

	def test_purchase_order_doctype_rounds_vat_and_grand_total_to_centavos(self):
		doc = types.SimpleNamespace(
			items=[
				types.SimpleNamespace(qty=3, unit_cost=4.55, vat_rate=12, vat_amount=0, amount=0),
			],
			discount_amount=0,
			delivery_fee=0,
		)

		bei_purchase_order.BEIPurchaseOrder.calculate_totals(doc)

		self.assertEqual(doc.items[0].vat_amount, 1.64)
		self.assertEqual(doc.items[0].amount, 15.29)
		self.assertEqual(doc.subtotal, 13.65)
		self.assertEqual(doc.vat_amount, 1.64)
		self.assertEqual(doc.grand_total, 15.29)

	def test_invoice_record_payment_annotation_accepts_date_inputs(self):
		annotation = (
			inspect.signature(bei_invoice.BEIInvoice.record_payment).parameters["payment_date"].annotation
		)
		self.assertIn("date", str(annotation))

		doc = types.SimpleNamespace(
			amount_paid=0,
			balance_due=100,
			payment_status="Unpaid",
			status="Verified",
			last_payment_date=None,
		)
		doc.calculate_totals = lambda: setattr(doc, "payment_status", "Partially Paid")
		doc.save = lambda: None

		result = bei_invoice.BEIInvoice.record_payment(
			doc,
			amount=50,
			payment_date=date(2026, 3, 18),
		)

		self.assertTrue(result["success"])
		self.assertEqual(doc.amount_paid, 50)
		self.assertEqual(doc.last_payment_date, date(2026, 3, 18))
		self.assertEqual(doc.status, "Partially Paid")

	def test_payment_request_auto_submits_linked_frappe_pi_before_creating_payment_entry(self):
		bei_invoice_doc = types.SimpleNamespace(
			status="Verified",
			supplier="S062SUP",
			frappe_purchase_invoice="PINV-0001",
			submit_calls=0,
		)
		supplier_doc = types.SimpleNamespace(
			supplier_name="Marivic's Ube",
			get_or_create_frappe_supplier=lambda: "SUP-MARIVIC",
		)
		pi_doc = types.SimpleNamespace(
			docstatus=0,
			credit_to="2101000 - ACCOUNTS PAYABLE - TRADE - BEI",
			grand_total=142.10,
			outstanding_amount=142.10,
		)

		def _submit_frappe_invoice():
			bei_invoice_doc.submit_calls += 1
			pi_doc.docstatus = 1

		bei_invoice_doc.submit_frappe_invoice = _submit_frappe_invoice

		class _PaymentEntry:
			def __init__(self):
				self.name = "PE-0001"
				self.references = []
				self.insert_calls = 0
				self.submit_calls = 0

			def append(self, fieldname, payload):
				if fieldname == "references":
					self.references.append(payload)

			def insert(self, ignore_permissions=False):
				self.insert_calls += 1
				return self

			def submit(self):
				self.submit_calls += 1

		payment_entry = _PaymentEntry()

		def _get_doc(*args, **kwargs):
			if args and args[0] == "BEI Invoice":
				return bei_invoice_doc
			if args and args[0] == "Purchase Invoice":
				return pi_doc
			if args and args[0] == "BEI Supplier":
				return supplier_doc
			if args and isinstance(args[0], dict):
				return payment_entry
			raise AssertionError(f"Unexpected get_doc call: {args} {kwargs}")

		bei_payment_request.frappe.get_doc = MagicMock(side_effect=_get_doc)

		doc = types.SimpleNamespace(
			status="Approved",
			invoice="INV-0001",
			supplier="S062SUP",
			payment_mode="Bank Transfer",
			payment_amount=142.10,
			payment_date="2026-03-18",
			transaction_reference="TXN-0001",
			check_number="",
			name="PAY-0001",
			_get_payment_accounts=lambda: ("1100 - Cash and Bank - BEI", "Wire Transfer"),
			db_set=lambda *args, **kwargs: None,
		)
		doc.get = lambda fieldname, default=None: getattr(doc, fieldname, default)

		result = bei_payment_request.BEIPaymentRequest.create_frappe_payment_entry(doc)

		self.assertEqual(result, "PE-0001")
		self.assertEqual(bei_invoice_doc.submit_calls, 1)
		self.assertEqual(payment_entry.insert_calls, 1)
		self.assertEqual(payment_entry.submit_calls, 1)
		self.assertEqual(payment_entry.references[0]["reference_name"], "PINV-0001")

	def test_payment_request_populates_missing_invoice_context_during_validate(self):
		invoice_doc = types.SimpleNamespace(
			supplier="MU9",
			supplier_name="Marivic's Ube",
			purchase_order="PO-2026-00001",
			goods_receipt="GR-2026-00001",
			balance_due=142.10,
			grand_total=142.10,
		)
		bei_payment_request.frappe.get_doc = MagicMock(return_value=invoice_doc)
		bei_payment_request.frappe.db.get_value = MagicMock(return_value="Marivic's Ube")

		doc = types.SimpleNamespace(
			invoice="INV-2026-00001",
			supplier="",
			supplier_name="",
			purchase_order="",
			goods_receipt="",
			payment_amount=0,
			rfp_type="",
		)

		bei_payment_request.BEIPaymentRequest.populate_invoice_context(doc)

		self.assertEqual(doc.supplier, "MU9")
		self.assertEqual(doc.supplier_name, "Marivic's Ube")
		self.assertEqual(doc.purchase_order, "PO-2026-00001")
		self.assertEqual(doc.goods_receipt, "GR-2026-00001")
		self.assertEqual(doc.payment_amount, 142.10)
		self.assertEqual(doc.rfp_type, "Vendor Invoice")

	def test_payment_request_falls_back_to_invoice_supplier_when_legacy_row_is_blank(self):
		bei_invoice_doc = types.SimpleNamespace(
			status="Verified",
			supplier="S062SUP",
			frappe_purchase_invoice="PINV-0001",
			submit_calls=0,
		)
		supplier_doc = types.SimpleNamespace(
			supplier_name="Marivic's Ube",
			get_or_create_frappe_supplier=lambda: "SUP-MARIVIC",
		)
		pi_doc = types.SimpleNamespace(
			docstatus=1,
			credit_to="2101000 - ACCOUNTS PAYABLE - TRADE - BEI",
			grand_total=142.10,
			outstanding_amount=142.10,
		)

		class _PaymentEntry:
			def __init__(self):
				self.name = "PE-0002"
				self.references = []

			def append(self, fieldname, payload):
				if fieldname == "references":
					self.references.append(payload)

			def insert(self, ignore_permissions=False):
				return self

			def submit(self):
				return None

		payment_entry = _PaymentEntry()
		db_set_calls = []

		def _get_doc(*args, **kwargs):
			if args and args[0] == "BEI Invoice":
				return bei_invoice_doc
			if args and args[0] == "Purchase Invoice":
				return pi_doc
			if args and args[0] == "BEI Supplier":
				self.assertEqual(args[1], "S062SUP")
				return supplier_doc
			if args and isinstance(args[0], dict):
				return payment_entry
			raise AssertionError(f"Unexpected get_doc call: {args} {kwargs}")

		bei_payment_request.frappe.get_doc = MagicMock(side_effect=_get_doc)

		doc = types.SimpleNamespace(
			status="Approved",
			invoice="INV-0001",
			supplier="",
			payment_mode="Bank Transfer",
			payment_amount=142.10,
			payment_date="2026-03-18",
			transaction_reference="TXN-0002",
			check_number="",
			name="PAY-0002",
			_get_payment_accounts=lambda: ("1100 - Cash and Bank - BEI", "Wire Transfer"),
			db_set=lambda *args, **kwargs: db_set_calls.append((args, kwargs)),
		)
		doc.get = lambda fieldname, default=None: getattr(doc, fieldname, default)

		result = bei_payment_request.BEIPaymentRequest.create_frappe_payment_entry(doc)

		self.assertEqual(result, "PE-0002")
		self.assertEqual(doc.supplier, "S062SUP")
		self.assertTrue(db_set_calls)


if __name__ == "__main__":
	unittest.main()
