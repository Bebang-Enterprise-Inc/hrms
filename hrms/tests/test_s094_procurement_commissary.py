# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Sprint S094 Phase 1 Tests — Procurement Email + Commissary Filters
Tests: PO email dispatch, auto-send on approval, inventory filters, batch info, production date

Uses source-level inspection to avoid Frappe import chain in test env.
"""

import os
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read_source(rel_path):
	with open(os.path.join(REPO_ROOT, rel_path), encoding="utf-8") as f:
		return f.read()


def _extract_function(source, func_name):
	marker = f"def {func_name}("
	idx = source.find(marker)
	if idx == -1:
		return None
	end_idx = source.find("\ndef ", idx + 1)
	return source[idx : end_idx if end_idx != -1 else len(source)]


class TestPOEmailDispatch(unittest.TestCase):
	"""UX-005: PO email actually sends via frappe.sendmail."""

	@classmethod
	def setUpClass(cls):
		cls.source = _read_source("hrms/api/procurement.py")

	def test_send_po_to_supplier_uses_sendmail(self):
		"""send_po_to_supplier calls frappe.sendmail for email mode."""
		func = _extract_function(self.source, "send_po_to_supplier")
		self.assertIsNotNone(func, "send_po_to_supplier function not found")
		self.assertIn("frappe.sendmail", func)

	def test_send_po_checks_supplier_email(self):
		"""send_po_to_supplier checks if supplier has email."""
		func = _extract_function(self.source, "send_po_to_supplier")
		self.assertIn("supplier.email", func)
		self.assertIn("no email", func.lower())

	def test_pdf_attachment_in_email(self):
		"""Email includes PDF attachment."""
		func = _extract_function(self.source, "send_po_to_supplier")
		self.assertIn("attachments", func)
		self.assertIn(".pdf", func)

	def test_get_po_pdf_bytes_exists(self):
		"""Helper _get_po_pdf_bytes exists."""
		func = _extract_function(self.source, "_get_po_pdf_bytes")
		self.assertIsNotNone(func, "_get_po_pdf_bytes not found")
		self.assertIn("_download_pdf", func)

	def test_get_procurement_finance_cc_list_exists(self):
		"""Helper _get_procurement_finance_cc_list exists."""
		func = _extract_function(self.source, "_get_procurement_finance_cc_list")
		self.assertIsNotNone(func, "_get_procurement_finance_cc_list not found")
		self.assertIn("Procurement Manager", func)

	def test_distribution_event_recorded(self):
		"""Distribution event still recorded after sending."""
		func = _extract_function(self.source, "send_po_to_supplier")
		self.assertIn("record_distribution_event", func)


class TestAutoSendOnApproval(unittest.TestCase):
	"""UX-005: Auto-send triggers on PO full approval."""

	@classmethod
	def setUpClass(cls):
		cls.source = _read_source("hrms/hr/doctype/bei_purchase_order/bei_purchase_order.py")

	def test_on_fully_approved_calls_send(self):
		"""on_fully_approved triggers send_po_to_supplier."""
		func = _extract_function(self.source, "on_fully_approved")
		self.assertIsNotNone(func, "on_fully_approved not found")
		self.assertIn("send_po_to_supplier", func)

	def test_auto_approval_send_mode(self):
		"""Auto-send uses auto_approval send mode."""
		func = _extract_function(self.source, "on_fully_approved")
		self.assertIn("auto_approval", func)

	def test_checks_supplier_email_before_send(self):
		"""Only sends if supplier has email."""
		func = _extract_function(self.source, "on_fully_approved")
		self.assertIn("supplier.email", func)


class TestInventoryFilters(unittest.TestCase):
	"""UX-007: Commissary inventory raw-materials filter."""

	@classmethod
	def setUpClass(cls):
		cls.source = _read_source("hrms/api/commissary.py")

	def test_get_inventory_levels_accepts_item_group(self):
		"""Backend function accepts item_group parameter."""
		func = _extract_function(self.source, "get_inventory_levels")
		self.assertIsNotNone(func)
		self.assertIn("item_group", func.split("\n")[0])

	def test_item_group_used_in_sql_filter(self):
		"""item_group is used in SQL WHERE clause."""
		func = _extract_function(self.source, "get_inventory_levels")
		self.assertIn("i.item_group = %s", func)


class TestBatchCodeVisibility(unittest.TestCase):
	"""UX-008: Batch code visible in inventory views."""

	@classmethod
	def setUpClass(cls):
		cls.source = _read_source("hrms/api/commissary.py")

	def test_inventory_includes_batch_info(self):
		"""get_inventory_levels includes batch data in response."""
		func = _extract_function(self.source, "get_inventory_levels")
		self.assertIn('"batches"', func)
		self.assertIn('"Batch"', func)

	def test_batch_fields_include_expiry(self):
		"""Batch query includes expiry_date field."""
		func = _extract_function(self.source, "get_inventory_levels")
		self.assertIn("expiry_date", func)
		self.assertIn("manufacturing_date", func)


class TestProductionDate(unittest.TestCase):
	"""UX-009: Production date picker."""

	@classmethod
	def setUpClass(cls):
		cls.source = _read_source("hrms/api/commissary_dashboard.py")

	def test_submit_production_output_accepts_production_date(self):
		"""Backend accepts production_date parameter."""
		func = _extract_function(self.source, "submit_production_output")
		self.assertIsNotNone(func)
		sig_lines = func.split("\n")[:8]
		sig_text = "\n".join(sig_lines)
		self.assertIn("production_date", sig_text)

	def test_posting_date_uses_production_date(self):
		"""Stock entry posting_date respects production_date param."""
		func = _extract_function(self.source, "submit_production_output")
		self.assertIn("getdate(production_date)", func)

	def test_batch_manufacturing_date_uses_production_date(self):
		"""Batch manufacturing_date uses production_date when provided."""
		func = _extract_function(self.source, "get_or_create_batch")
		self.assertIsNotNone(func)
		self.assertIn("production_date", func)


if __name__ == "__main__":
	unittest.main()
