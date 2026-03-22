import unittest
from unittest.mock import patch

import frappe

from hrms.api import supervisor


class _DummyQueueDoc:
	def __init__(self, reference_doctype):
		self.reference_doctype = reference_doctype
		self.reference_name = "BEI-TRF-2026-00001"
		self.status = "Pending"
		self.approved_by = None
		self.approved_at = None
		self.rejection_reason = None
		self.saved = False

	def save(self):
		self.saved = True


class TestSupervisorTransferQueue(unittest.TestCase):
	def test_approve_item_blocks_transfer_request_generic_mutator(self):
		doc = _DummyQueueDoc("BEI Transfer Request")
		with patch("frappe.get_doc", return_value=doc):
			with self.assertRaises(frappe.ValidationError):
				supervisor.approve_item("BEI-APQ-2026-00001")
		self.assertFalse(doc.saved)

	def test_reject_item_blocks_transfer_request_generic_mutator(self):
		doc = _DummyQueueDoc("BEI Transfer Request")
		with patch("frappe.get_doc", return_value=doc):
			with self.assertRaises(frappe.ValidationError):
				supervisor.reject_item("BEI-APQ-2026-00001", "No")
		self.assertFalse(doc.saved)

	def test_unified_queue_includes_transfer_request_items(self):
		def _mock_get_all(doctype, **kwargs):
			if doctype == "BEI Transfer Request":
				return [
					frappe._dict(
						{
							"name": "BEI-TRF-2026-00001",
							"employee": "EMP-0001",
							"employee_name": "Test Crew",
							"requested_by": "test.supervisor@bebang.ph",
							"requested_on": "2026-02-26 08:00:00",
							"effective_date": "2026-02-27",
							"current_stage": "Pending HR Approval",
							"to_branch": "STORE-2",
							"store_warehouse": "STORE-2 - BEI",
						}
					)
				]
			return []

		with patch("frappe.get_roles", return_value=["HR User"]), patch(
			"frappe.get_all", side_effect=_mock_get_all
		), patch("frappe.db.get_value", return_value=None):
			result = supervisor.get_unified_approval_queue(approver="test.hr@bebang.ph")

		transfer_items = [item for item in result.get("items", []) if item.get("type") == "transfer_request"]
		self.assertEqual(len(transfer_items), 1)
		self.assertEqual(transfer_items[0]["name"], "BEI-TRF-2026-00001")
		self.assertEqual(transfer_items[0]["stage"], "Pending HR Approval")

