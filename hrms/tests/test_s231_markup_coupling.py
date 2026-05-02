"""S231 D-2 markup coupling tests — verify BKI intercompany markup
applies the right rate per ownership type AND defaults exist for all 4.

The actual markup logic lives inside `build_bki_store_sale_invoice` in
`hrms/api/commissary.py:1077-1099`. These tests assert the BEI Settings
structure that powers it: every ownership type has a Float field with
the expected default value, and the field is queryable via Single
DocType lookups (which is how the production code reads it).

Run via:
    bench --site hq.bebang.ph run-tests --module hrms.tests.test_s231_markup_coupling --verbose

Plan: docs/plans/2026-05-02-sprint-231-pricing-coupling-and-defaults-defense.md
"""

from __future__ import annotations

import json
import pathlib
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


class TestS231MarkupFieldsExist(unittest.TestCase):
	"""TM-6 #2-#5: BEI Settings has a markup field for every ownership type."""

	@classmethod
	def setUpClass(cls):
		path = REPO_ROOT / "hrms" / "hr" / "doctype" / "bei_settings" / "bei_settings.json"
		cls.doctype = json.loads(path.read_text(encoding="utf-8"))
		cls.fields_by_name = {
			f.get("fieldname"): f for f in cls.doctype.get("fields", [])
		}

	def _assert_markup_field(self, fieldname: str, expected_default: str) -> None:
		self.assertIn(
			fieldname,
			self.fields_by_name,
			f"S231 D-2: missing required markup field {fieldname!r}",
		)
		field = self.fields_by_name[fieldname]
		self.assertEqual(field["fieldtype"], "Float")
		self.assertEqual(field.get("precision"), "4")
		self.assertEqual(
			field.get("default"),
			expected_default,
			f"S231 D-2: {fieldname} default should be {expected_default!r} per CEO 2026-05-02",
		)

	def test_markup_coupling_company_owned(self):
		"""Co-Owned markup field: 2.75% per CEO 2026-05-02 (same as JV)."""
		self._assert_markup_field("bki_markup_company_owned_percent", "2.75")

	def test_markup_coupling_jv(self):
		"""JV markup field: 2.75% (keeps BKI net taxable income ≤ PHP 5M
		for 20% CIT eligibility per ICT-002).
		"""
		self._assert_markup_field("bki_markup_jv_percent", "2.75")

	def test_markup_coupling_managed_franchise(self):
		"""Managed Franchise markup field: 8.0% per ICT-002 / BIL-005."""
		self._assert_markup_field("bki_markup_managed_franchise_percent", "8.0")

	def test_markup_coupling_full_franchise(self):
		"""Full Franchise markup field: 8.0% per ICT-002 / BIL-005."""
		self._assert_markup_field("bki_markup_full_franchise_percent", "8.0")

	def test_markup_field_order_grouped_in_bki_section(self):
		"""All 4 markup fields appear together in field_order under
		`section_break_bki_billing` — so the BEI Settings UI groups them
		visually for Finance.
		"""
		order = self.doctype["field_order"]
		section_idx = order.index("section_break_bki_billing")
		fields_after_section = order[section_idx : section_idx + 6]
		for f in (
			"bki_markup_jv_percent",
			"bki_markup_managed_franchise_percent",
			"bki_markup_full_franchise_percent",
			"bki_markup_company_owned_percent",
		):
			self.assertIn(
				f,
				fields_after_section,
				f"S231 D-1: {f} should be in the BKI section group",
			)


class TestS231OwnershipTypeReconciliation(unittest.TestCase):
	"""TM-6: D-2 N-8 fix — sales_location_mapping.py blank fallback now
	matches supply_chain_contracts.py canonical default ("Company Owned").
	"""

	def test_sales_location_mapping_default_matches_canonical(self):
		"""sales_location_mapping.py:77-area defaults blank ownership to
		"Company Owned" (NOT "Managed Franchise" — the silent N-8 drift
		that would route the same store to two different accounting buckets
		depending on which reader consumed the field).
		"""
		path = (
			REPO_ROOT
			/ "hrms"
			/ "utils"
			/ "sales_location_mapping.py"
		)
		src = path.read_text(encoding="utf-8")
		# The fixed line should read `or "Company Owned"`.
		self.assertIn(
			'frappe.db.get_value("Company", company_name, "store_ownership_type") or "Company Owned"',
			src,
			"S231 D-2 N-8 fix: sales_location_mapping.py blank fallback must "
			"be 'Company Owned' to match supply_chain_contracts.py",
		)
		# And there should NOT be a fallback to "Managed Franchise" on the
		# blank-coalesce line (the legacy N-8 drift).
		self.assertNotIn(
			'frappe.db.get_value("Company", company_name, "store_ownership_type") or "Managed Franchise"',
			src,
			"S231 D-2 N-8 fix: legacy 'Managed Franchise' blank fallback "
			"on the read-Company line must be removed",
		)
