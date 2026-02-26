import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.utils import add_days, getdate, nowdate

from hrms.api import transfer_requests


class _FakeTransferDoc:
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


class _FakeInsertDoc(_FakeTransferDoc):
	def insert(self, ignore_permissions=False):
		if not getattr(self, "name", None):
			self.name = "BEI-TRF-TEST-00001"
		return self


class _FakeEmployeeDoc:
	def __init__(self, **kwargs):
		self.__dict__.update(kwargs)


class TestTransferRequestsL4(unittest.TestCase):
	def test_create_transfer_request_persists_store_warehouse(self):
		employee_doc = _FakeEmployeeDoc(
			name="EMP-0001",
			branch="SM MOA",
			department="Operations - BEI",
			designation="Store Supervisor",
			reports_to="EMP-AREA-001",
		)
		insert_holder = {}

		def _fake_get_doc(*args, **kwargs):
			if len(args) == 2 and args[0] == "Employee":
				return employee_doc
			if args and isinstance(args[0], dict):
				doc = _FakeInsertDoc(**args[0])
				insert_holder["doc"] = doc
				return doc
			raise AssertionError(f"Unexpected get_doc call: args={args}, kwargs={kwargs}")

		with patch.object(frappe, "session", SimpleNamespace(user="test.supervisor@bebang.ph")), patch(
			"hrms.api.transfer_requests._require_any_role"
		), patch("hrms.api.transfer_requests._notify_transfer_event"), patch(
			"frappe.db.exists", return_value=True
		), patch(
			"frappe.get_doc", side_effect=_fake_get_doc
		), patch(
			"hrms.api.transfer_requests._validate_store_warehouse_for_transfer",
			return_value={"warehouse": "BRITTANY OFFICE - BEI", "branch": "BRITTANY OFFICE", "company": "Bebang Enterprise Inc."},
		):
			result = transfer_requests.create_transfer_request(
				employee="EMP-0001",
				effective_date=nowdate(),
				reason="Store requirement",
				to_branch="BRITTANY OFFICE",
				store_warehouse="BRITTANY OFFICE - BEI",
			)

		self.assertTrue(result["success"])
		self.assertEqual(result["current_stage"], transfer_requests.STAGE_PENDING_AREA)
		self.assertEqual(insert_holder["doc"].store_warehouse, "BRITTANY OFFICE - BEI")
		self.assertEqual(insert_holder["doc"].to_branch, "BRITTANY OFFICE")

	def test_create_transfer_request_derives_to_branch_from_warehouse_when_missing(self):
		employee_doc = _FakeEmployeeDoc(
			name="EMP-0009",
			branch="SM MOA",
			department="Operations - BEI",
			designation="Store Supervisor",
			reports_to="EMP-AREA-001",
		)
		insert_holder = {}

		def _fake_get_doc(*args, **kwargs):
			if len(args) == 2 and args[0] == "Employee":
				return employee_doc
			if args and isinstance(args[0], dict):
				doc = _FakeInsertDoc(**args[0])
				insert_holder["doc"] = doc
				return doc
			raise AssertionError(f"Unexpected get_doc call: args={args}, kwargs={kwargs}")

		with patch.object(frappe, "session", SimpleNamespace(user="test.supervisor@bebang.ph")), patch(
			"hrms.api.transfer_requests._require_any_role"
		), patch("hrms.api.transfer_requests._notify_transfer_event"), patch(
			"frappe.db.exists", return_value=True
		), patch(
			"frappe.get_doc", side_effect=_fake_get_doc
		), patch(
			"hrms.api.transfer_requests._validate_store_warehouse_for_transfer",
			return_value={"warehouse": "BRITTANY OFFICE - BEI", "branch": "BRITTANY OFFICE", "company": "Bebang Enterprise Inc."},
		):
			result = transfer_requests.create_transfer_request(
				employee="EMP-0009",
				effective_date=nowdate(),
				reason="Warehouse-driven branch derive",
				store_warehouse="BRITTANY OFFICE - BEI",
			)

		self.assertTrue(result["success"])
		self.assertEqual(insert_holder["doc"].to_branch, "BRITTANY OFFICE")

	def test_approve_transfer_stage_moves_hr_to_it_and_creates_employee_transfer(self):
		doc = _FakeTransferDoc(
			name="BEI-TRF-2026-00001",
			employee="EMP-0001",
			employee_name="Test Employee",
			current_stage=transfer_requests.STAGE_PENDING_HR,
			stage_status="Pending",
			effective_date=getdate(nowdate()),
			store_warehouse="BRITTANY OFFICE - BEI",
			to_designation="Store Supervisor",
		)
		ensure_calls = []

		def _fake_ensure(doc_arg, submit_now):
			ensure_calls.append({"name": doc_arg.name, "submit_now": submit_now})
			return SimpleNamespace(name="ET-0001", docstatus=1)

		with patch.object(frappe, "session", SimpleNamespace(user="test.hr@bebang.ph")), patch(
			"frappe.db.exists", return_value=True
		), patch("frappe.get_doc", return_value=doc), patch(
			"hrms.api.transfer_requests._require_stage_approver"
		), patch(
			"hrms.api.transfer_requests._require_store_warehouse_mapping"
		), patch(
			"hrms.api.transfer_requests._ensure_employee_transfer", side_effect=_fake_ensure
		), patch(
			"hrms.api.transfer_requests._sync_designation_roles",
			return_value={"added": ["HQ User"], "removed": []},
		), patch(
			"hrms.api.transfer_requests._notify_transfer_event"
		):
			result = transfer_requests.approve_transfer_stage(doc.name, remarks="Approved")

		self.assertTrue(result["success"])
		self.assertEqual(result["from_stage"], transfer_requests.STAGE_PENDING_HR)
		self.assertEqual(result["to_stage"], transfer_requests.STAGE_PENDING_IT)
		self.assertEqual(doc.current_stage, transfer_requests.STAGE_PENDING_IT)
		self.assertTrue(doc.saved)
		self.assertEqual(len(ensure_calls), 1)
		self.assertTrue(ensure_calls[0]["submit_now"])

	def test_reject_transfer_stage_sets_rejected_state(self):
		doc = _FakeTransferDoc(
			name="BEI-TRF-2026-00002",
			employee="EMP-0002",
			employee_name="Reject Employee",
			current_stage=transfer_requests.STAGE_PENDING_HR,
			stage_status="Pending",
			store_warehouse="BRITTANY OFFICE - BEI",
		)

		with patch.object(frappe, "session", SimpleNamespace(user="test.hr@bebang.ph")), patch(
			"frappe.db.exists", return_value=True
		), patch("frappe.get_doc", return_value=doc), patch(
			"hrms.api.transfer_requests._require_stage_approver"
		), patch(
			"hrms.api.transfer_requests._notify_transfer_event"
		):
			result = transfer_requests.reject_transfer_stage(doc.name, "Invalid request")

		self.assertTrue(result["success"])
		self.assertEqual(result["current_stage"], transfer_requests.STAGE_REJECTED)
		self.assertEqual(doc.current_stage, transfer_requests.STAGE_REJECTED)
		self.assertEqual(doc.rejection_reason, "Invalid request")
		self.assertTrue(doc.saved)

	def test_retry_transfer_sync_for_failed_request_dispatches_force_retry(self):
		doc = _FakeTransferDoc(
			name="BEI-TRF-2026-00003",
			current_stage=transfer_requests.STAGE_SYNC_FAILED,
			store_warehouse="BRITTANY OFFICE - BEI",
		)
		dispatch_calls = []

		def _fake_dispatch(doc_arg, force_retry_failed=False, remarks=None):
			dispatch_calls.append(
				{"name": doc_arg.name, "force_retry_failed": force_retry_failed, "remarks": remarks}
			)
			return {"success": True, "name": doc_arg.name}

		with patch.object(frappe, "session", SimpleNamespace(user="test.it@bebang.ph")), patch(
			"frappe.db.exists", return_value=True
		), patch("frappe.get_doc", return_value=doc), patch(
			"hrms.api.transfer_requests._require_any_role"
		), patch(
			"hrms.api.transfer_requests._dispatch_transfer_sync", side_effect=_fake_dispatch
		):
			result = transfer_requests.retry_transfer_sync(doc.name, remarks="Retry now")

		self.assertTrue(result["success"])
		self.assertEqual(len(dispatch_calls), 1)
		self.assertTrue(dispatch_calls[0]["force_retry_failed"])
		self.assertEqual(dispatch_calls[0]["remarks"], "Retry now")

	def test_run_due_transfer_submissions_moves_waiting_to_pending_it(self):
		doc = _FakeTransferDoc(
			name="BEI-TRF-2026-00004",
			employee="EMP-0004",
			employee_name="Due Employee",
			current_stage=transfer_requests.STAGE_WAITING_EFFECTIVE,
			stage_status="Pending",
			effective_date=add_days(getdate(nowdate()), -1),
			store_warehouse="BRITTANY OFFICE - BEI",
			to_designation="Store Supervisor",
		)
		ensure_calls = []

		def _fake_ensure(doc_arg, submit_now):
			ensure_calls.append({"name": doc_arg.name, "submit_now": submit_now})
			return SimpleNamespace(name="ET-0004", docstatus=1)

		with patch.object(frappe, "session", SimpleNamespace(user="Administrator")), patch(
			"frappe.get_all", return_value=[frappe._dict({"name": doc.name})]
		), patch(
			"frappe.get_doc", return_value=doc
		), patch(
			"hrms.api.transfer_requests._require_store_warehouse_mapping"
		), patch(
			"hrms.api.transfer_requests._ensure_employee_transfer", side_effect=_fake_ensure
		), patch(
			"hrms.api.transfer_requests._sync_designation_roles",
			return_value={"added": [], "removed": []},
		), patch(
			"hrms.api.transfer_requests._notify_transfer_event"
		):
			result = transfer_requests.run_due_transfer_submissions(limit=10)

		self.assertEqual(result["processed"], 1)
		self.assertEqual(doc.current_stage, transfer_requests.STAGE_PENDING_IT)
		self.assertTrue(doc.saved)
		self.assertEqual(len(ensure_calls), 1)
		self.assertTrue(ensure_calls[0]["submit_now"])

	def test_run_ready_transfer_sync_dispatches_ready_items(self):
		doc = _FakeTransferDoc(
			name="BEI-TRF-2026-00005",
			current_stage=transfer_requests.STAGE_READY_SYNC,
			store_warehouse="BRITTANY OFFICE - BEI",
			effective_date=nowdate(),
		)
		dispatch_calls = []

		def _fake_dispatch(doc_arg, force_retry_failed=False, remarks=None):
			dispatch_calls.append(
				{"name": doc_arg.name, "force_retry_failed": force_retry_failed, "remarks": remarks}
			)
			return {"success": True, "name": doc_arg.name}

		with patch.object(frappe, "session", SimpleNamespace(user="Administrator")), patch(
			"frappe.get_all", return_value=[frappe._dict({"name": doc.name})]
		), patch(
			"frappe.get_doc", return_value=doc
		), patch(
			"hrms.api.transfer_requests._dispatch_transfer_sync", side_effect=_fake_dispatch
		):
			result = transfer_requests.run_ready_transfer_sync(limit=10)

		self.assertEqual(result["processed"], 1)
		self.assertEqual(len(dispatch_calls), 1)
		self.assertFalse(dispatch_calls[0]["force_retry_failed"])

	def test_audit_transfer_store_mappings_reports_blocked_rows(self):
		def _fake_exists(doctype, value):
			if doctype == "Warehouse":
				return value == "BRITTANY OFFICE - BEI"
			return True

		with patch.object(frappe, "session", SimpleNamespace(user="test.hr@bebang.ph")), patch(
			"hrms.api.transfer_requests._require_any_role"
		), patch("frappe.db.exists", side_effect=_fake_exists):
			result = transfer_requests.audit_transfer_store_mappings(
				"BRITTANY OFFICE - BEI,UNKNOWN STORE - BEI"
			)

		self.assertEqual(result["total"], 2)
		self.assertEqual(result["ok"], 1)
		self.assertEqual(result["blocked"], 1)
		self.assertIn("UNKNOWN STORE - BEI", result["missing_warehouse"])

	def test_get_transfer_form_options_returns_filtered_warehouse_rows(self):
		expected = [
			{
				"warehouse": "AYALA EVO - BEI",
				"warehouse_label": "AYALA EVO",
				"branch": "AYALA EVO",
				"company": "Bebang Enterprise Inc.",
			}
		]

		with patch.object(frappe, "session", SimpleNamespace(user="test.supervisor@bebang.ph")), patch(
			"hrms.api.transfer_requests._require_any_role"
		), patch(
			"hrms.api.transfer_requests._list_transfer_store_warehouse_options",
			return_value=expected,
		):
			result = transfer_requests.get_transfer_form_options(search_text="ayala", limit=20)

		self.assertEqual(result["total"], 1)
		self.assertEqual(result["warehouses"][0]["branch"], "AYALA EVO")
