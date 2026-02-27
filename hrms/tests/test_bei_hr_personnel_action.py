import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from hrms.api import personnel_actions


class _FakePersonnelAction:
	def __init__(self, **kwargs):
		self.__dict__.update(kwargs)
		self.saved = False
		self.comments = []

	def save(self, ignore_permissions=False):
		self.saved = True
		return self

	def add_comment(self, comment_type, text=None):
		self.comments.append({"comment_type": comment_type, "text": text})
		return self


class _FakeEmployee:
	def __init__(self, **kwargs):
		self.__dict__.update(kwargs)
		self.saved = False

	def save(self, ignore_permissions=False):
		self.saved = True
		return self


class TestBEIHRPersonnelAction(unittest.TestCase):
	def test_parse_compensation_rows_accepts_json_string(self):
		rows = personnel_actions._parse_compensation_rows(
			'[{"component":"Basic Salary","from_amount":10000,"to_amount":12000}]'
		)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["component"], "Basic Salary")
		self.assertEqual(rows[0]["to_amount"], 12000)

	def test_create_personnel_action_blocks_non_hr_user(self):
		with patch.object(frappe, "session", SimpleNamespace(user="test.supervisor@bebang.ph")), patch(
			"hrms.api.personnel_actions._has_hr_personnel_action_role", return_value=False
		):
			with self.assertRaises(frappe.PermissionError):
				personnel_actions.create_personnel_action(
					employee="EMP-0001",
					effective_date="2026-02-27",
					reason="Promotion",
				)

	def test_approve_personnel_action_updates_employee_master_fields(self):
		action_doc = _FakePersonnelAction(
			name="HRPA-0001",
			employee="EMP-0001",
			status="Pending HR Approval",
			to_branch="AYALA EVO",
			to_department="Operations - BEI",
			to_designation="Store Supervisor",
			to_reports_to="EMP-AREA-001",
			approved_by=None,
			approved_on=None,
		)
		employee_doc = _FakeEmployee(
			name="EMP-0001",
			branch="SM MOA",
			department="Operations - BEI",
			designation="Crew",
			reports_to="EMP-SUP-001",
		)

		def _fake_get_doc(doctype, name):
			if doctype == personnel_actions.DOCTYPE_PERSONNEL_ACTION:
				return action_doc
			if doctype == "Employee":
				return employee_doc
			raise AssertionError(f"Unexpected doctype {doctype}")

		with patch.object(frappe, "session", SimpleNamespace(user="test.hr@bebang.ph")), patch(
			"hrms.api.personnel_actions._require_hr_personnel_action_role"
		), patch(
			"frappe.db.exists", return_value=True
		), patch(
			"frappe.get_doc", side_effect=_fake_get_doc
		):
			result = personnel_actions.approve_personnel_action("HRPA-0001")

		self.assertTrue(result["success"])
		self.assertEqual(action_doc.status, "Approved")
		self.assertTrue(action_doc.saved)
		self.assertEqual(employee_doc.branch, "AYALA EVO")
		self.assertEqual(employee_doc.designation, "Store Supervisor")
		self.assertTrue(employee_doc.saved)

