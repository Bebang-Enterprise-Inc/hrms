import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, now_datetime, nowdate
from unittest.mock import patch

from hrms.api import transfer_requests


class TestTransferRequests(FrappeTestCase):
	def test_split_roles_parses_newline_and_comma_separated_values(self):
		raw = "HR User, Area Supervisor\nSystem Manager\n\nStore Supervisor"
		roles = transfer_requests._split_roles(raw)
		self.assertEqual(
			roles,
			["HR User", "Area Supervisor", "System Manager", "Store Supervisor"],
		)

	def test_store_mapping_guard_blocks_missing_mapping(self):
		doc = frappe._dict({"store_warehouse": None})
		with self.assertRaises(frappe.ValidationError):
			transfer_requests._require_store_warehouse_mapping(doc)

	def test_store_mapping_guard_blocks_invalid_mapping(self):
		doc = frappe._dict({"store_warehouse": "UNKNOWN-WH"})
		original_exists = frappe.db.exists
		try:
			frappe.db.exists = lambda doctype, name: False if doctype == "Warehouse" else original_exists(doctype, name)
			with self.assertRaises(frappe.ValidationError):
				transfer_requests._require_store_warehouse_mapping(doc)
		finally:
			frappe.db.exists = original_exists

	def test_effective_date_gate_blocks_ready_for_sync_without_override(self):
		doc = frappe._dict(
			{
				"effective_date": add_days(getdate(nowdate()), 1),
			}
		)
		with self.assertRaises(frappe.ValidationError):
			transfer_requests._enforce_effective_date_dispatch_guard(doc)

	def test_effective_date_gate_allows_override_with_dual_approval(self):
		doc = frappe._dict(
			{
				"effective_date": add_days(getdate(nowdate()), 1),
			}
		)

		original_has_any_role = transfer_requests._has_any_role
		original_exists = frappe.db.exists
		original_get_roles = frappe.get_roles

		try:
			transfer_requests._has_any_role = lambda roles, user=None: True
			frappe.db.exists = lambda doctype, name: True if doctype == "User" else original_exists(doctype, name)
			frappe.get_roles = lambda user=None: ["HR Manager"]

			transfer_requests._enforce_effective_date_dispatch_guard(
				doc,
				allow_emergency_override=1,
				emergency_override_reason="Critical live transfer",
				hr_override_user="test.hr@bebang.ph",
			)
		finally:
			transfer_requests._has_any_role = original_has_any_role
			frappe.db.exists = original_exists
			frappe.get_roles = original_get_roles

		self.assertEqual(doc.emergency_override_requested, 1)
		self.assertEqual(doc.emergency_override_reason, "Critical live transfer")
		self.assertEqual(doc.emergency_override_hr_approved_by, "test.hr@bebang.ph")
		self.assertEqual(doc.emergency_override_system_approved_by, frappe.session.user)
		self.assertIsNotNone(doc.emergency_override_approved_at)

	def test_effective_date_gate_allows_when_effective_date_is_today(self):
		doc = frappe._dict(
			{
				"effective_date": getdate(nowdate()),
			}
		)
		transfer_requests._enforce_effective_date_dispatch_guard(doc)

	def test_effective_date_gate_allows_when_override_was_previously_approved(self):
		doc = frappe._dict(
			{
				"effective_date": add_days(getdate(nowdate()), 2),
				"emergency_override_requested": 1,
				"emergency_override_approved_at": now_datetime(),
			}
		)
		transfer_requests._enforce_effective_date_dispatch_guard(doc)

	def test_normalize_store_key_removes_delimiters_and_company_suffix(self):
		self.assertEqual(
			transfer_requests._normalize_store_key("Brittany Office - BEI"),
			"BRITTANYOFFICE",
		)
		self.assertEqual(
			transfer_requests._normalize_store_key("SM Grand Central - Bebang Enterprise Inc."),
			"SMGRANDCENTRAL",
		)
		self.assertEqual(
			transfer_requests._normalize_store_key("SM MOA"),
			"SMMOA",
		)

	def test_contains_blocked_warehouse_term_detects_3pl_terms(self):
		self.assertTrue(transfer_requests._contains_blocked_warehouse_term("3PL Mega Hub"))
		self.assertTrue(transfer_requests._contains_blocked_warehouse_term("3MD Warehouse"))
		self.assertFalse(transfer_requests._contains_blocked_warehouse_term("Brittany Office - BEI"))

	def test_resolve_branch_from_store_warehouse_uses_normalized_branch_index(self):
		with patch("frappe.db.exists", return_value=False):
			branch = transfer_requests._resolve_branch_from_store_warehouse(
				"Ayala Evo - Bebang Enterprise Inc.",
				branch_index={"AYALAEVO": "AYALA EVO"},
			)
		self.assertEqual(branch, "AYALA EVO")

	def test_validate_store_warehouse_for_transfer_blocks_non_bei_company(self):
		class _FakeWarehouse:
			company = "Other Company"
			is_group = 0
			warehouse_name = "AYALA EVO"
			branch = "AYALA EVO"

		with patch("frappe.db.exists", side_effect=lambda doctype, name: True), patch(
			"frappe.get_doc", return_value=_FakeWarehouse()
		), patch("hrms.api.transfer_requests._get_branch_index", return_value={"AYALAEVO": "AYALA EVO"}):
			with self.assertRaises(frappe.ValidationError):
				transfer_requests._validate_store_warehouse_for_transfer("AYALA EVO - BEI")

	def test_compute_transfer_device_plan_for_roving_employee_targets_all_devices(self):
		doc = frappe._dict(
			{
				"store_warehouse": "Brittany Office - BEI",
				"to_branch": "Brittany Office",
				"from_branch": "SM MOA",
			}
		)
		plan = transfer_requests._compute_transfer_device_plan(doc, bio_id="9000037")
		self.assertTrue(plan["is_roving"])
		self.assertGreater(len(plan["target_devices"]), 1)
		self.assertEqual(plan["remove_devices"], [])

	def test_compute_transfer_device_plan_for_standard_employee_targets_new_store(self):
		doc = frappe._dict(
			{
				"store_warehouse": "Brittany Office - Bebang Enterprise Inc.",
				"to_branch": "BRITTANY OFFICE",
				"from_branch": "SM MOA",
			}
		)
		plan = transfer_requests._compute_transfer_device_plan(doc, bio_id="9001999")
		self.assertFalse(plan["is_roving"])
		self.assertIn("UDP3251600245", plan["target_devices"])
		self.assertIn("UDP3251400192", plan["remove_devices"])

	def test_reconcile_updates_failed_row_when_adms_reports_late_ack(self):
		class _FakeCommandDoc:
			def __init__(self):
				self.name = "CMD-1"
				self.adms_command_id = 123
				self.status = transfer_requests.ADMS_STATUS_FAILED
				self.last_error = "timeout_waiting_for_device_callback"
				self.sent_at = None
				self.acked_at = None
				self.creation = now_datetime()
				self.last_polled_at = None
				self.saved = False

			def save(self, ignore_permissions=True):
				self.saved = True

		fake_cmd = _FakeCommandDoc()
		original_get_rows = transfer_requests._get_command_rows
		original_fetch = transfer_requests._fetch_adms_commands
		original_get_doc = transfer_requests.frappe.get_doc

		try:
			transfer_requests._get_command_rows = lambda name, statuses=None: [
				{"name": "CMD-1", "device_sn": "UDP3252900302"}
			]
			transfer_requests._fetch_adms_commands = lambda device_sn, config, limit=200: {
				"success": True,
				"rows": [
					{
						"id": 123,
						"status": transfer_requests.ADMS_STATUS_ACKED,
						"last_error": None,
						"sent_at": "2026-02-26T06:05:25",
						"acked_at": "2026-02-26T06:05:28",
					}
				],
			}

			def _fake_get_doc(doctype, name):
				if doctype == transfer_requests.DOCTYPE_TRANSFER_DEVICE_COMMAND and name == "CMD-1":
					return fake_cmd
				return original_get_doc(doctype, name)

			transfer_requests.frappe.get_doc = _fake_get_doc

			result = transfer_requests._sync_command_statuses_from_adms(
				frappe._dict({"name": "BEI-TRF-TEST-00001"}),
				config={"stale_timeout_minutes": 30, "base_url": "http://adms.local", "admin_token": "x"},
			)
		finally:
			transfer_requests._get_command_rows = original_get_rows
			transfer_requests._fetch_adms_commands = original_fetch
			transfer_requests.frappe.get_doc = original_get_doc

		self.assertEqual(result["updated"], 1)
		self.assertEqual(fake_cmd.status, transfer_requests.ADMS_STATUS_ACKED)
		self.assertIsNone(fake_cmd.last_error)
		self.assertIsNotNone(fake_cmd.acked_at)
		self.assertTrue(fake_cmd.saved)
