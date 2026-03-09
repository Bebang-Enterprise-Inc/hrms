# Copyright (c) 2026, Frappe Technologies Pvt. Ltd.
# For license information, please see license.txt

"""Regression coverage for POS upload attachment handling."""

import base64
import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_runtime():
	import frappe

	frappe_utils = sys.modules["frappe.utils"]
	frappe_utils.get_datetime = lambda value=None: value
	frappe_utils.getdate = lambda value=None: value

	if "hrms.utils.bei_config" not in sys.modules:
		bei_config = types.ModuleType("hrms.utils.bei_config")
		bei_config.get_company = lambda: "Bebang Enterprise Inc."
		sys.modules["hrms.utils.bei_config"] = bei_config

	scm_roles = sys.modules.get("hrms.utils.scm_roles")
	if scm_roles is None:
		scm_roles = types.ModuleType("hrms.utils.scm_roles")
		sys.modules["hrms.utils.scm_roles"] = scm_roles
	scm_roles.SCM_APPROVAL_ROLES = ["Area Supervisor", "Regional Manager", "System Manager"]
	scm_roles.check_scm_permission = lambda *_args, **_kwargs: None

	if "hrms.utils.pos_parser" not in sys.modules:
		pos_parser = types.ModuleType("hrms.utils.pos_parser")
		pos_parser.parse_sales_summary = lambda _content: {
			"metadata": {"from_date": "2026-03-09"},
			"success": True,
		}
		sys.modules["hrms.utils.pos_parser"] = pos_parser


def _load_module(module_name: str, relative_path: str):
	spec = importlib.util.spec_from_file_location(module_name, ROOT / relative_path)
	module = importlib.util.module_from_spec(spec)
	sys.modules[module_name] = module
	spec.loader.exec_module(module)
	return module


_install_runtime()
store = _load_module("hrms.api.store", "hrms/api/store.py")


class _FakeFileDoc:
	def __init__(self, payload):
		self.payload = payload
		self.file_url = f"/files/{payload['file_name']}"

	def save(self, ignore_permissions=False):
		self.ignore_permissions = bool(ignore_permissions)


class _FakePosUploadDoc:
	def __init__(self):
		self.name = "POS-TEST-0001"
		self.inserted = False

	def insert(self):
		self.inserted = True


class TestStorePosUploadContract(unittest.TestCase):
	def setUp(self):
		self.original_get_doc = store.frappe.get_doc
		self.original_new_doc = store.frappe.new_doc
		self.original_set_value = store.frappe.db.set_value
		self.original_validate_role = store.validate_store_ops_role
		self.original_resolve_warehouse = store.resolve_warehouse
		self.original_save_base64_file = store.save_base64_file

		store.frappe.session.user = "test.staff@bebang.ph"

	def tearDown(self):
		store.frappe.get_doc = self.original_get_doc
		store.frappe.new_doc = self.original_new_doc
		store.frappe.db.set_value = self.original_set_value
		store.validate_store_ops_role = self.original_validate_role
		store.resolve_warehouse = self.original_resolve_warehouse
		store.save_base64_file = self.original_save_base64_file

	def test_save_base64_file_accepts_spreadsheet_data_url(self):
		captured = {}

		def fake_get_doc(payload):
			captured.update(payload)
			return _FakeFileDoc(payload)

		store.frappe.get_doc = fake_get_doc

		file_url = store.save_base64_file(
			"data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,"
			+ base64.b64encode(b"spreadsheet-bytes").decode(),
			"BEI POS Upload",
			fieldname="sales_summary",
			default_ext="xlsx",
		)

		self.assertEqual(file_url, f"/files/{captured['file_name']}")
		self.assertTrue(captured["file_name"].endswith(".xlsx"))
		self.assertEqual(captured["attached_to_field"], "sales_summary")
		self.assertEqual(captured["content"], b"spreadsheet-bytes")

	def test_upload_pos_data_sets_mismatch_flag_and_uses_generic_file_saver(self):
		set_value_calls = []
		saved_fields = []
		doc = _FakePosUploadDoc()
		payload = base64.b64encode(b"xlsx-bytes").decode()

		store.validate_store_ops_role = lambda: None
		store.resolve_warehouse = lambda value: value
		store.frappe.new_doc = lambda doctype: doc
		store.frappe.db.set_value = lambda doctype, name, fieldname, value: set_value_calls.append(
			(doctype, name, fieldname, value)
		)
		store.save_base64_file = lambda _data, _doctype, fieldname="attachment", default_ext="bin": (
			saved_fields.append((fieldname, default_ext)) or f"/files/{fieldname}.{default_ext}"
		)

		result = store.upload_pos_data(
			store="Araneta Gateway - Bebang Enterprise Inc.",
			pos_date="2026-03-10",
			pos_system="MOSAIC",
			discount_report=payload,
			transaction_report=payload,
			product_mix=payload,
			daily_sales_revenue=payload,
			sales_summary=payload,
			notes="regression test",
		)

		self.assertTrue(result["success"])
		self.assertTrue(result["date_mismatch"])
		self.assertEqual(result["name"], "POS-TEST-0001")
		self.assertTrue(doc.inserted)
		self.assertEqual(
			saved_fields,
			[
				("discount_report", "xlsx"),
				("transaction_report", "xlsx"),
				("product_mix", "xlsx"),
				("daily_sales_revenue", "xlsx"),
				("sales_summary", "xlsx"),
			],
		)
		self.assertEqual(
			set_value_calls,
			[("BEI POS Upload", "POS-TEST-0001", "has_date_mismatch", 1)],
		)


if __name__ == "__main__":
	unittest.main()
