# Copyright (c) 2026, Bebang Enterprise Inc.
# License: MIT
"""S233 unit tests for create_store_company + list_eligible_parent_companies."""
from __future__ import annotations
import unittest

import frappe

from hrms.api.company_master import (
	create_store_company,
	list_eligible_parent_companies,
)


class TestS233CreateStoreCompany(unittest.TestCase):
	TEST_STORE_LABEL = "S233-TEST-UNIT"
	TEST_PARENT = "BEBANG FT INC."  # is_group=1 + entity_category="Holding Company" since v3 A14 backfill
	TEST_ABBR = "S233UN"  # 3-6 chars uppercase + digits per v3 A18
	TEST_COMPANY_NAME = f"{TEST_STORE_LABEL} - {TEST_PARENT}"
	TEST_INTERNAL = f"{TEST_STORE_LABEL} (Internal)"

	def setUp(self):
		self._cleanup_records()

	def tearDown(self):
		self._cleanup_records()

	def _cleanup_records(self):
		"""Remove test records from any prior run (idempotent)."""
		for dt, name in [
			("Customer", self.TEST_INTERNAL),
			("Customer", self.TEST_COMPANY_NAME),
			("Warehouse", self.TEST_COMPANY_NAME),
			("Company", self.TEST_COMPANY_NAME),
		]:
			if frappe.db.exists(dt, name):
				try:
					frappe.delete_doc(dt, name, force=True, ignore_permissions=True, ignore_on_trash=True)
				except Exception:
					pass
		frappe.db.commit()

	def _all_records_absent(self) -> bool:
		return not any([
			frappe.db.exists("Company", self.TEST_COMPANY_NAME),
			frappe.db.exists("Warehouse", self.TEST_COMPANY_NAME),
			frappe.db.exists("Customer", self.TEST_COMPANY_NAME),
			frappe.db.exists("Customer", self.TEST_INTERNAL),
		])

	def test_happy_path_creates_4_canonical_records(self):
		"""Plan Phase 5 S1: helper creates Company + Warehouse + 2 Customers."""
		out = create_store_company(
			store_label=self.TEST_STORE_LABEL,
			parent_company=self.TEST_PARENT,
			abbr=self.TEST_ABBR,
			store_ownership_type="Managed Franchise",
		)
		self.assertEqual(out["company"], self.TEST_COMPANY_NAME)
		self.assertEqual(out["warehouse"], self.TEST_COMPANY_NAME)
		self.assertEqual(out["billing_customer"], self.TEST_COMPANY_NAME)
		self.assertEqual(out["internal_customer"], self.TEST_INTERNAL)
		self.assertEqual(out["first_provision_done"], 0)
		# All 4 records exist in DB
		self.assertTrue(frappe.db.exists("Company", self.TEST_COMPANY_NAME))
		self.assertTrue(frappe.db.exists("Warehouse", self.TEST_COMPANY_NAME))
		self.assertTrue(frappe.db.exists("Customer", self.TEST_COMPANY_NAME))
		self.assertTrue(frappe.db.exists("Customer", self.TEST_INTERNAL))

	def test_rejects_non_group_parent(self):
		"""v2 A4 / v3 A14: parent must be is_group=1."""
		# Find a per-store Company (is_group=0) to use as fake parent
		non_group = frappe.db.get_value("Company", {"is_group": 0}, "name")
		self.assertIsNotNone(non_group, "test fixture: at least one is_group=0 Company should exist")
		with self.assertRaises(frappe.ValidationError):
			create_store_company(
				store_label=self.TEST_STORE_LABEL,
				parent_company=non_group,
				abbr=self.TEST_ABBR,
				store_ownership_type="Managed Franchise",
			)
		self.assertTrue(self._all_records_absent(), "no records should be created when parent is non-group")

	def test_rejects_duplicate_abbr(self):
		"""v3 A18: abbr must be unique."""
		# First create succeeds
		create_store_company(
			store_label=self.TEST_STORE_LABEL,
			parent_company=self.TEST_PARENT,
			abbr=self.TEST_ABBR,
			store_ownership_type="Managed Franchise",
		)
		# Second create with different label but same abbr fails
		with self.assertRaises(frappe.ValidationError):
			create_store_company(
				store_label="S233-TEST-DIFFERENT",
				parent_company=self.TEST_PARENT,
				abbr=self.TEST_ABBR,
				store_ownership_type="JV",
			)

	def test_rejects_existing_company_name(self):
		"""Canonical company_name uniqueness."""
		create_store_company(
			store_label=self.TEST_STORE_LABEL,
			parent_company=self.TEST_PARENT,
			abbr=self.TEST_ABBR,
			store_ownership_type="Managed Franchise",
		)
		# Same label + same parent → same canonical name
		with self.assertRaises(frappe.ValidationError):
			create_store_company(
				store_label=self.TEST_STORE_LABEL,
				parent_company=self.TEST_PARENT,
				abbr="S233UB",  # different abbr to bypass that check
				store_ownership_type="Managed Franchise",
			)

	def test_rejects_invalid_abbr_pattern(self):
		"""v3 A18: abbr regex ^[A-Z0-9]{3,6}$."""
		for bad_abbr in ["AB", "TOOLONG7C", "with-hyphen", "lowercase", "WITH SPACE", ""]:
			with self.subTest(abbr=bad_abbr):
				with self.assertRaises(frappe.ValidationError):
					create_store_company(
						store_label=self.TEST_STORE_LABEL,
						parent_company=self.TEST_PARENT,
						abbr=bad_abbr,
						store_ownership_type="Managed Franchise",
					)

	def test_atomicity_partial_failure_rolls_back_all_4(self):
		"""v2 A2: savepoint rolls back all 4 records if any insert fails.

		Force a failure by passing an invalid (but precondition-passing)
		ownership type via a direct helper call AFTER preconditions pass —
		simulated by patching one of the inner inserts to raise.
		"""
		from unittest.mock import patch
		import hrms.api.create_new_store as helper

		# Patch the second-to-last frappe.new_doc call to raise
		original_new_doc = frappe.new_doc
		call_count = {"n": 0}

		def fake_new_doc(doctype, *args, **kwargs):
			call_count["n"] += 1
			# Allow Company + Warehouse + first Customer; fail on internal Customer
			if call_count["n"] == 4:
				raise frappe.ValidationError("simulated failure on internal Customer insert")
			return original_new_doc(doctype, *args, **kwargs)

		with patch.object(frappe, "new_doc", side_effect=fake_new_doc):
			with self.assertRaises(frappe.ValidationError):
				create_store_company(
					store_label=self.TEST_STORE_LABEL,
					parent_company=self.TEST_PARENT,
					abbr=self.TEST_ABBR,
					store_ownership_type="Managed Franchise",
				)
		# All 4 records absent — savepoint rolled back the partial work
		self.assertTrue(self._all_records_absent(), "savepoint must roll back all 4 records on failure")

	def test_list_eligible_parents_returns_only_group_companies(self):
		"""list_eligible_parent_companies filters correctly."""
		rows = list_eligible_parent_companies()
		self.assertGreater(len(rows), 0, "at least one canonical parent must exist")
		for row in rows:
			# Every row must have entity_category in the allowed set
			self.assertIn(
				row["entity_category"],
				{"Head Office", "Holding Company", "Franchisor", "Commissary"},
				f"row {row} has wrong entity_category",
			)
			# And every parent must be is_group=1
			is_group = frappe.db.get_value("Company", row["name"], "is_group")
			self.assertEqual(is_group, 1, f"row {row['name']} is not is_group=1")
		# After v3 A14 backfill, BFI2 should appear
		names = [r["name"] for r in rows]
		self.assertIn("BEBANG FT INC.", names, "v3 A14: BFI2 must appear after backfill")
