import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_frappe():
	sys.modules.pop("frappe", None)
	sys.modules.pop("frappe.utils", None)
	sys.modules.pop("frappe.model", None)
	sys.modules.pop("frappe.model.document", None)
	sys.modules.pop("frappe.model.workflow", None)
	sys.modules.pop("frappe.query_builder", None)

	frappe = types.ModuleType("frappe")
	utils = types.ModuleType("frappe.utils")
	model = types.ModuleType("frappe.model")
	document_module = types.ModuleType("frappe.model.document")
	workflow = types.ModuleType("frappe.model.workflow")
	query_builder = types.ModuleType("frappe.query_builder")

	class Document:
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

	frappe.whitelist = whitelist
	frappe._ = lambda text: text
	frappe.throw = _throw
	frappe.PermissionError = PermissionError
	frappe.msgprint = lambda *args, **kwargs: None
	frappe.log_error = lambda *args, **kwargs: None
	frappe.get_meta = lambda doctype: types.SimpleNamespace(default_print_format="Standard")
	frappe.get_doc = MagicMock()
	frappe.get_all = MagicMock(return_value=[])
	frappe.session = types.SimpleNamespace(user="Administrator")
	frappe.db = types.SimpleNamespace(
		get_value=MagicMock(return_value=None),
		exists=MagicMock(return_value=None),
	)
	frappe.local = types.SimpleNamespace(
		response=types.SimpleNamespace(
			filecontent=None,
			type=None,
			filename=None,
			display_content_as=None,
		)
	)

	utils.cint = lambda value: int(float(value or 0))
	utils.flt = lambda value, precision=None: round(float(value or 0), precision or 0) if precision is not None else float(value or 0)
	utils.now_datetime = lambda: "2026-03-19 20:30:00"
	utils.nowtime = lambda: "20:30:00"
	utils.today = lambda: "2026-03-19"
	utils.add_days = lambda date, days: date
	utils.date_diff = lambda end, start: 0
	utils.getdate = lambda value=None: value
	utils.strip_html = lambda value: value

	document_module.Document = Document
	model.get_permitted_fields = lambda *args, **kwargs: []
	workflow.get_workflow_name = lambda *args, **kwargs: None
	query_builder.Order = types.SimpleNamespace(asc="asc", desc="desc")

	frappe.utils = utils

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils
	sys.modules["frappe.model"] = model
	sys.modules["frappe.model.document"] = document_module
	sys.modules["frappe.model.workflow"] = workflow
	sys.modules["frappe.query_builder"] = query_builder

	return frappe


def _install_stub_dependencies():
	bei_config = types.ModuleType("hrms.utils.bei_config")
	bei_config.get_company = lambda: "Bebang Enterprises Inc."

	standard_buying_bridge = types.ModuleType("hrms.utils.standard_buying_bridge")
	standard_buying_bridge.apply_standard_buying_context = lambda *args, **kwargs: None

	erpnext = types.ModuleType("erpnext")
	erpnext_setup = types.ModuleType("erpnext.setup")
	erpnext_setup_doctype = types.ModuleType("erpnext.setup.doctype")
	erpnext_employee_pkg = types.ModuleType("erpnext.setup.doctype.employee")
	erpnext_employee = types.ModuleType("erpnext.setup.doctype.employee.employee")
	erpnext_employee.get_holiday_list_for_employee = lambda *args, **kwargs: None

	profile_policy = types.ModuleType("hrms.api.profile_policy")
	profile_policy.is_reports_to_candidate = lambda *args, **kwargs: False
	profile_policy.matches_reports_to_query = lambda *args, **kwargs: False
	profile_policy.normalize_text = lambda value: value
	profile_policy.resolve_reports_to_display_name = lambda *args, **kwargs: ""

	print_format = types.ModuleType("frappe.utils.print_format")
	print_format.download_pdf = lambda *args, **kwargs: None

	sys.modules["hrms.utils.bei_config"] = bei_config
	sys.modules["hrms.utils.standard_buying_bridge"] = standard_buying_bridge
	sys.modules["erpnext"] = erpnext
	sys.modules["erpnext.setup"] = erpnext_setup
	sys.modules["erpnext.setup.doctype"] = erpnext_setup_doctype
	sys.modules["erpnext.setup.doctype.employee"] = erpnext_employee_pkg
	sys.modules["erpnext.setup.doctype.employee.employee"] = erpnext_employee
	sys.modules["hrms.api.profile_policy"] = profile_policy
	sys.modules["frappe.utils.print_format"] = print_format


def _load_module(alias: str, relative_path: str):
	spec = importlib.util.spec_from_file_location(alias, ROOT / relative_path)
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(module)
	return module


frappe = _install_fake_frappe()
_install_stub_dependencies()

purchase_order = _load_module(
	"bei_purchase_order_under_test",
	"hrms/hr/doctype/bei_purchase_order/bei_purchase_order.py",
)
goods_receipt = _load_module(
	"bei_goods_receipt_under_test",
	"hrms/hr/doctype/bei_goods_receipt/bei_goods_receipt.py",
)
class _InsertedDoc:
	def __init__(self, payload):
		self.payload = payload
		self.name = "PR-0001"
		self.insert_calls = 0
		self.submit_calls = 0

	def insert(self, ignore_permissions=False):
		self.insert_calls += 1
		return self

	def submit(self):
		self.submit_calls += 1
		return self


class TestProcurementGrSyncBridge(unittest.TestCase):
	def setUp(self):
		frappe.get_doc.reset_mock(return_value=True, side_effect=True)
		frappe.db.get_value = MagicMock(return_value=None)
		frappe.local.response = types.SimpleNamespace(
			filecontent=None,
			type=None,
			filename=None,
			display_content_as=None,
		)

	def test_progressed_po_can_still_sync_to_frappe(self):
		po = purchase_order.BEIPurchaseOrder()
		po.status = "Fully Received"
		po.requires_dual_approval = 0
		po.mae_approval = "Approved"
		po.butch_approval = "Pending"

		self.assertTrue(po.can_create_frappe_purchase_order())

	def test_goods_receipt_backfills_missing_frappe_po_when_po_is_operationally_progressed(self):
		bei_po = types.SimpleNamespace(
			status="Fully Received",
			frappe_po=None,
			ship_to="Main Warehouse - BEI",
			can_create_frappe_purchase_order=MagicMock(return_value=True),
		)

		def _create_frappe_po():
			bei_po.frappe_po = "PO-ERP-0001"
			return bei_po.frappe_po

		bei_po.create_frappe_purchase_order = MagicMock(side_effect=_create_frappe_po)

		supplier_doc = types.SimpleNamespace(
			get_or_create_frappe_supplier=MagicMock(return_value="SUP-ERP-0001")
		)
		inserted_docs = []

		def _get_doc(*args, **kwargs):
			if args and args[0] == "BEI Purchase Order":
				return bei_po
			if args and args[0] == "BEI Supplier":
				return supplier_doc
			if args and isinstance(args[0], dict):
				doc = _InsertedDoc(args[0])
				inserted_docs.append(doc)
				return doc
			raise AssertionError(f"Unexpected get_doc call: {args!r} {kwargs!r}")

		frappe.get_doc.side_effect = _get_doc

		gr = goods_receipt.BEIGoodsReceipt()
		gr.name = "GR-0001"
		gr.frappe_purchase_receipt = None
		gr.status = "Accepted"
		gr.inspection_required = 0
		gr.inspection_status = "Passed"
		gr.purchase_order = "PO-0001"
		gr.supplier = "SUP-0001"
		gr.receipt_date = "2026-03-19"
		gr.warehouse = "Main Warehouse - BEI"
		gr.total_rejected_qty = 0
		gr.items = [
			types.SimpleNamespace(
				name="GRI-0001",
				item_code="ITEM-001",
				item_name="Test Item",
				description="Test Item",
				accepted_qty=5,
				rejected_qty=0,
				unit_cost=100,
				uom="Nos",
			)
		]
		gr._find_frappe_po_item = MagicMock(return_value="POI-0001")
		gr.db_set = MagicMock()

		result = gr.create_frappe_purchase_receipt()

		bei_po.can_create_frappe_purchase_order.assert_called_once_with()
		bei_po.create_frappe_purchase_order.assert_called_once_with()
		self.assertEqual(result, "PR-0001")
		self.assertEqual(gr.frappe_purchase_receipt, "PR-0001")
		self.assertEqual(inserted_docs[0].insert_calls, 1)
		self.assertEqual(inserted_docs[0].submit_calls, 1)

if __name__ == "__main__":
	unittest.main()
