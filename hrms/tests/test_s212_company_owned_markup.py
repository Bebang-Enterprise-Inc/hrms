"""S212 DEFECT-5 regression test — build_bki_store_sale_invoice accepts Company Owned.

Source-inspection test that locks in the Company Owned entry in markup_by_type
so a future refactor can't accidentally remove it. The production incident
that motivated this fix: 2026-04-21 R1 sweep — AYALA FAIRVIEW TERRACES
(store_type='Company Owned') failed Draft SI creation with
`ValidationError: Unknown store_type 'Company Owned'`, leaving SE 00621 with
null `custom_sales_invoice_draft`.

Kept as source-inspection (vs live-Frappe) because the function has a
large import graph; the only behavior change to lock in is the presence
of the "Company Owned" key.
"""
from __future__ import annotations
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMMISSARY_PY = ROOT / "hrms" / "api" / "commissary.py"


def _find_function(src: str, name: str) -> str:
	pattern = re.compile(
		rf"^(def {re.escape(name)}\b.*?)(?=^def |^class |\Z)",
		re.M | re.S,
	)
	m = pattern.search(src)
	return m.group(1) if m else ""


class CompanyOwnedMarkupTest(unittest.TestCase):
	def setUp(self):
		src = COMMISSARY_PY.read_text(encoding="utf-8")
		self.fn = _find_function(src, "build_bki_store_sale_invoice")
		self.assertTrue(self.fn, "build_bki_store_sale_invoice not found")

	def test_company_owned_in_markup_map(self):
		self.assertIn(
			'"Company Owned":',
			self.fn,
			"S212 DEFECT-5: expected 'Company Owned' entry in markup_by_type",
		)

	def test_company_owned_markup_reads_from_settings(self):
		self.assertIn(
			"bki_markup_company_owned_percent",
			self.fn,
			"S212 DEFECT-5: expected Company Owned markup to read from "
			"bki_markup_company_owned_percent (matches JV/Franchise pattern)",
		)

	def test_existing_types_still_present(self):
		for key in ('"JV":', '"Managed Franchise":', '"Full Franchise":'):
			self.assertIn(key, self.fn, f"Regression: {key} removed from markup_by_type")


if __name__ == "__main__":
	unittest.main()
