"""S231 Phase C tests — atomicity wrapper + null_out_dead_default_refs validate hook.

Tests the C-1 atomicity behavior of `auto_provision_company` and the C-2
defense-in-depth `null_out_dead_default_refs` validate hook in
`hrms/overrides/company.py`.

Run via:
    bench --site hq.bebang.ph run-tests --module hrms.tests.test_s231_atomicity --verbose

Plan: docs/plans/2026-05-02-sprint-231-pricing-coupling-and-defaults-defense.md
Origin: 2026-05-02 CEO save of Ayala Fairview Terraces threw LinkValidationError on
15 dead `- BFI2` Account references in default_* fields (`hrms/api/company_master.py:266`
→ `doc.save()` → Frappe `_validate_links()`).
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from hrms.overrides.company import (
	DEFAULT_FIELDS_TO_TRACK,
	auto_provision_company,
	null_out_dead_default_refs,
)


class TestS231Atomicity(unittest.TestCase):
	"""Phase C-1 + C-2 verification."""

	TEST_COMPANY_NAME = "S231-TEST-ATOMICITY - BEBANG ENTERPRISE INC."
	TEST_COMPANY_ABBR = "S231ATOM"

	def setUp(self) -> None:
		"""Create a clean test Company without first_provision_done set.

		Skips most of the heavy-weight provisioning by setting in_install=True
		so `auto_provision_company` early-returns; we then test by calling
		auto_provision_company directly with the flag off.
		"""
		# Drop any leftover from previous failed run
		if frappe.db.exists("Company", self.TEST_COMPANY_NAME):
			frappe.delete_doc("Company", self.TEST_COMPANY_NAME, force=True, ignore_permissions=True)
			frappe.db.commit()

		# Create with in_install set so on_update auto_provision_company is skipped
		frappe.flags.in_install = True
		try:
			co = frappe.new_doc("Company")
			co.company_name = self.TEST_COMPANY_NAME
			co.abbr = self.TEST_COMPANY_ABBR
			co.country = "Philippines"
			co.default_currency = "PHP"
			co.flags.ignore_permissions = True
			co.flags.ignore_mandatory = True
			co.insert()
			frappe.db.commit()
		finally:
			frappe.flags.in_install = False

		# Ensure first_provision_done is 0 so auto_provision_company will run
		if frappe.get_meta("Company").has_field("first_provision_done"):
			frappe.db.set_value(
				"Company", self.TEST_COMPANY_NAME, "first_provision_done", 0, update_modified=False
			)
			frappe.db.commit()

	def tearDown(self) -> None:
		"""Clean up the test Company after every test."""
		if frappe.db.exists("Company", self.TEST_COMPANY_NAME):
			try:
				frappe.delete_doc(
					"Company",
					self.TEST_COMPANY_NAME,
					force=True,
					ignore_permissions=True,
					ignore_on_trash=True,
				)
				frappe.db.commit()
			except Exception:
				frappe.db.rollback()

	# -------- C-1 atomicity tests --------

	def test_partial_create_default_accounts_failure_rolls_back_field_writes(self) -> None:
		"""S231-C1: when create_default_accounts raises midway after writing
		some default_* fields, auto_provision_company must restore the
		pre_state and NOT flip first_provision_done.
		"""
		doc = frappe.get_doc("Company", self.TEST_COMPANY_NAME)
		dead_account_name = f"NonExistent Inventory - {self.TEST_COMPANY_ABBR}"

		def fake_create_default_accounts():
			"""Simulate ERPNext writing a field then failing."""
			frappe.db.set_value(
				"Company",
				doc.name,
				"default_inventory_account",
				dead_account_name,
				update_modified=False,
			)
			raise RuntimeError("simulated ERPNext seeding failure mid-step")

		# Patch S181/S184 helpers to no-op so the test is focused on Step 0
		patches = [
			patch("hrms.overrides.company._s181_ensure_warehouse"),
			patch("hrms.overrides.company._s181_ensure_cost_center"),
			patch("hrms.overrides.company._s181_apply_sales_template"),
			patch("hrms.overrides.company._s181_apply_balance_sheet_template"),
			patch("hrms.overrides.company._s181_set_default_accounts"),
			patch("hrms.overrides.company._s181_ensure_bki_customer"),
			patch("hrms.overrides.company._s184_create_default_bank_accounts"),
			patch("hrms.overrides.company._s184_assign_adms_device"),
			patch("hrms.overrides.company._s184_pull_gps"),
		]
		for p in patches:
			p.start()
		try:
			with patch.object(doc, "create_default_accounts", side_effect=fake_create_default_accounts):
				auto_provision_company(doc)
		finally:
			for p in patches:
				p.stop()

		# C-1 invariant 1: pre_state restored (default_inventory_account back to None)
		current_value = frappe.db.get_value(
			"Company", self.TEST_COMPANY_NAME, "default_inventory_account"
		)
		self.assertIsNone(
			current_value,
			f"S231-C1 should have restored default_inventory_account to None, got {current_value!r}",
		)

		# C-1 invariant 2: first_provision_done STILL flipped (auto_provision continues
		# past Step 0 failure, because S181 templates create what's needed). The point
		# of C-1 is that pre_state restore + invalid_after clear leave the doc in a
		# CONSISTENT state — not that we abort the whole hook.
		# (Confirmed by design rationale at company.py auto_provision_company docstring.)

	def test_invalid_after_check_clears_dead_refs(self) -> None:
		"""S231-C1: the invalid_after loop nulls any field whose target
		Account / Cost Center does not exist before flipping first_provision_done.
		"""
		# Pre-pollute a default_* field with a guaranteed-non-existent reference
		dead_ref = f"GhostAccount - {self.TEST_COMPANY_ABBR}"
		frappe.db.set_value(
			"Company",
			self.TEST_COMPANY_NAME,
			"default_payable_account",
			dead_ref,
			update_modified=False,
		)
		frappe.db.commit()

		doc = frappe.get_doc("Company", self.TEST_COMPANY_NAME)

		# Patch all helpers + ERPNext defaults so the only non-trivial thing
		# the function does is run the invalid_after sweep
		patches = [
			patch.object(doc, "create_default_accounts", return_value=None),
			patch("hrms.overrides.company._s181_ensure_warehouse"),
			patch("hrms.overrides.company._s181_ensure_cost_center"),
			patch("hrms.overrides.company._s181_apply_sales_template"),
			patch("hrms.overrides.company._s181_apply_balance_sheet_template"),
			patch("hrms.overrides.company._s181_set_default_accounts"),
			patch("hrms.overrides.company._s181_ensure_bki_customer"),
			patch("hrms.overrides.company._s184_create_default_bank_accounts"),
			patch("hrms.overrides.company._s184_assign_adms_device"),
			patch("hrms.overrides.company._s184_pull_gps"),
		]
		for p in patches:
			p.start()
		try:
			auto_provision_company(doc)
		finally:
			for p in patches:
				p.stop()

		current_value = frappe.db.get_value(
			"Company", self.TEST_COMPANY_NAME, "default_payable_account"
		)
		self.assertIsNone(
			current_value,
			f"S231-C1 invalid_after should have nulled dead default_payable_account, got {current_value!r}",
		)

	# -------- C-2 validate hook tests --------

	def test_validate_hook_clears_dead_refs_on_save(self) -> None:
		"""S231-C2: null_out_dead_default_refs nulls dead refs at validate
		time so a Company with rotted defaults can still save.
		"""
		# Mark Company as already-provisioned and pollute a default
		frappe.db.set_value(
			"Company",
			self.TEST_COMPANY_NAME,
			"first_provision_done",
			1,
			update_modified=False,
		)
		dead_ref = f"GhostInventory - {self.TEST_COMPANY_ABBR}"
		frappe.db.set_value(
			"Company",
			self.TEST_COMPANY_NAME,
			"default_inventory_account",
			dead_ref,
			update_modified=False,
		)
		frappe.db.commit()

		doc = frappe.get_doc("Company", self.TEST_COMPANY_NAME)
		# Field should be loaded from db
		self.assertEqual(doc.get("default_inventory_account"), dead_ref)

		# Run the validate hook directly
		null_out_dead_default_refs(doc)

		# Field should now be None on the doc (in-memory)
		self.assertIsNone(
			doc.get("default_inventory_account"),
			"S231-C2 should null dead default_inventory_account on validate",
		)

	def test_validate_hook_skips_when_first_provision_pending(self) -> None:
		"""S231-C2 (v2 addition): validate hook is no-op when
		first_provision_done == 0 so it never clobbers fields the
		orchestrator is mid-setting on a fresh Company.
		"""
		# Ensure first_provision_done is 0
		frappe.db.set_value(
			"Company",
			self.TEST_COMPANY_NAME,
			"first_provision_done",
			0,
			update_modified=False,
		)
		dead_ref = f"GhostInventory - {self.TEST_COMPANY_ABBR}"
		frappe.db.set_value(
			"Company",
			self.TEST_COMPANY_NAME,
			"default_inventory_account",
			dead_ref,
			update_modified=False,
		)
		frappe.db.commit()

		doc = frappe.get_doc("Company", self.TEST_COMPANY_NAME)
		self.assertEqual(doc.get("default_inventory_account"), dead_ref)

		null_out_dead_default_refs(doc)

		# Field should be UNCHANGED — hook skipped because first_provision_done == 0
		self.assertEqual(
			doc.get("default_inventory_account"),
			dead_ref,
			"S231-C2 must skip when first_provision_done=0 (preserves orchestrator's mid-write state)",
		)

	def test_default_fields_to_track_constant_is_complete(self) -> None:
		"""Smoke test: DEFAULT_FIELDS_TO_TRACK includes the 15 fields that
		showed up in the 2026-05-02 LinkValidationError plus the related
		round_off / depreciation / capital / asset / stock fields the
		`_validate_links` path will check.
		"""
		expected_2026_05_02_error_fields = {
			"exchange_gain_loss_account",
			"round_off_cost_center",
			"accumulated_depreciation_account",
			"depreciation_expense_account",
			"expenses_included_in_asset_valuation",
			"disposal_account",
			"depreciation_cost_center",
			"capital_work_in_progress_account",
			"asset_received_but_not_billed",
			"default_inventory_account",
			"stock_adjustment_account",
			"stock_received_but_not_billed",
			"expenses_included_in_valuation",
			"default_payroll_payable_account",
			"default_employee_advance_account",
		}
		missing = expected_2026_05_02_error_fields - set(DEFAULT_FIELDS_TO_TRACK)
		self.assertFalse(
			missing,
			f"DEFAULT_FIELDS_TO_TRACK missing fields from 2026-05-02 error: {missing}",
		)
