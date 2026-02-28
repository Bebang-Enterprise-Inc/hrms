import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from hrms.hr.doctype.bei_transfer_request.bei_transfer_request import BEITransferRequest


def _make_doc(*, is_new, to_department=None, to_designation=None, previous=None):
	doc = BEITransferRequest.__new__(BEITransferRequest)
	doc.to_department = to_department
	doc.to_designation = to_designation
	doc.is_new = lambda: is_new
	doc.get_doc_before_save = lambda: previous
	return doc


class TestBEITransferRequestPermissions(unittest.TestCase):
	def test_non_hr_cannot_set_department_or_designation_on_new_doc(self):
		doc = _make_doc(is_new=True, to_department="Operations - BEI")

		with patch("frappe.get_roles", return_value=["Store Supervisor"]):
			with self.assertRaises(frappe.PermissionError):
				doc._enforce_org_change_permissions()

	def test_non_hr_cannot_change_existing_department_or_designation(self):
		previous = SimpleNamespace(to_department="Operations - BEI", to_designation=None)
		doc = _make_doc(
			is_new=False,
			to_department="Finance - BEI",
			to_designation=None,
			previous=previous,
		)

		with patch("frappe.get_roles", return_value=["Area Supervisor"]):
			with self.assertRaises(frappe.PermissionError):
				doc._enforce_org_change_permissions()

	def test_non_hr_can_save_when_org_change_fields_are_unchanged(self):
		previous = SimpleNamespace(to_department="Operations - BEI", to_designation=None)
		doc = _make_doc(
			is_new=False,
			to_department="Operations - BEI",
			to_designation=None,
			previous=previous,
		)

		with patch("frappe.get_roles", return_value=["Store Supervisor"]):
			doc._enforce_org_change_permissions()

	def test_hr_can_set_or_change_org_change_fields(self):
		previous = SimpleNamespace(to_department=None, to_designation=None)
		doc = _make_doc(
			is_new=False,
			to_department="Finance - BEI",
			to_designation="Store Supervisor",
			previous=previous,
		)

		with patch("frappe.get_roles", return_value=["HR User"]):
			doc._enforce_org_change_permissions()
