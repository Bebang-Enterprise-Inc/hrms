import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, now_datetime, nowdate

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
			transfer_requests._normalize_store_key("SM MOA"),
			"SMMOA",
		)

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
				"store_warehouse": "BRITTANY OFFICE - BEI",
				"to_branch": "BRITTANY OFFICE",
				"from_branch": "SM MOA",
			}
		)
		plan = transfer_requests._compute_transfer_device_plan(doc, bio_id="9001999")
		self.assertFalse(plan["is_roving"])
		self.assertIn("UDP3251600245", plan["target_devices"])
		self.assertIn("UDP3251400192", plan["remove_devices"])
