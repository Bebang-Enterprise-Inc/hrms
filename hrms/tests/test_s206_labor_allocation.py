"""S206 Phase 2 — labor_allocation unit tests.

Focuses on `_build_paired_jes` structure (DM-1/DM-6 compliance) and
`_skip_reason` logic. Full allocate_slip path is exercised via L3 with
live Frappe.
"""

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from hrms.utils import labor_allocation
from hrms.utils.labor_allocation import (
	INTER_COMPANY_VOUCHER_TYPE,
	SKIP_COMMISSARY_PRODUCER,
	SKIP_NON_STORE_BILLING,
	SKIP_ZERO_GROSS,
	_build_paired_jes,
	_skip_reason,
)

# Canonical party names used by the seeder's `internal_party_name()`.
HOME_INTERNAL_CUSTOMER = "BEBANG ENTERPRISE INC. (Internal)"
HOME_INTERNAL_SUPPLIER = "BEBANG ENTERPRISE INC. (Internal)"
COVERED_INTERNAL_CUSTOMER = "SM MEGAMALL (Internal)"
COVERED_INTERNAL_SUPPLIER = "SM MEGAMALL (Internal)"


class BuildPairedJEsTests(unittest.TestCase):
	"""Test _build_paired_jes produces DM-1/DM-6 compliant JE dicts.

	The Due From row references an internal Customer representing the covered
	Company; the Due To row references an internal Supplier representing the
	home Company. party_type='Company' is invalid on Receivable/Payable rows
	in ERPNext v15 — see S206 audit POST_EXECUTION_AUDIT_2026-04-18.
	"""

	def setUp(self):
		self.slip = MagicMock()
		self.slip.name = "SS-2026-04-001"
		self.slip.employee = "BEI-EMP-2026-00123"
		self.slip.start_date = date(2026, 4, 1)
		self.slip.end_date = date(2026, 4, 30)
		self.slip.gross_pay = 30000.0

		self.mock_home_accts = {
			"salaries_expense": "5220001 - Salaries and Wages - BEI",
			"due_from": "1104200 - DUE FROM GROUP ENTITIES - BEI",
			"due_to": "2104200 - DUE TO GROUP ENTITIES - BEI",
			"cost_center": "Main - BEI",
		}
		self.mock_covered_accts = {
			"salaries_expense": "5220001 - Salaries and Wages - SMMM",
			"due_from": "1104200 - DUE FROM GROUP ENTITIES - SMMM",
			"due_to": "2104200 - DUE TO GROUP ENTITIES - SMMM",
			"cost_center": "Main - SMMM",
		}
		self.mock_home_parties = {
			"internal_customer": HOME_INTERNAL_CUSTOMER,
			"internal_supplier": HOME_INTERNAL_SUPPLIER,
		}
		self.mock_covered_parties = {
			"internal_customer": COVERED_INTERNAL_CUSTOMER,
			"internal_supplier": COVERED_INTERNAL_SUPPLIER,
		}

	def _call(self, amount=9000.0, share=0.3):
		def fake_accts(company):
			if "ENTERPRISE" in company and "SM" not in company:
				return self.mock_home_accts
			return self.mock_covered_accts

		def fake_parties(company):
			if "ENTERPRISE" in company and "SM" not in company:
				return self.mock_home_parties
			return self.mock_covered_parties

		with (
			patch.object(labor_allocation, "_resolve_company_accounts", side_effect=fake_accts),
			patch.object(labor_allocation, "_resolve_company_parties", side_effect=fake_parties),
		):
			return _build_paired_jes(
				slip=self.slip,
				share=share,
				home="BEBANG ENTERPRISE INC.",
				covered="SM MEGAMALL - BEBANG ENTERPRISE INC.",
				amount=amount,
			)

	def test_home_je_structure(self):
		home, _covered = self._call()
		self.assertEqual(home["doctype"], "Journal Entry")
		self.assertEqual(home["voucher_type"], INTER_COMPANY_VOUCHER_TYPE)
		self.assertEqual(home["company"], "BEBANG ENTERPRISE INC.")
		self.assertEqual(home["posting_date"], date(2026, 4, 30))
		self.assertIn("S206 cost-sharing recharge", home["user_remark"])
		self.assertIn("BEI-EMP-2026-00123", home["user_remark"])
		self.assertEqual(len(home["accounts"]), 2)

	def test_home_je_salaries_row_is_credit_with_employee_party(self):
		home, _covered = self._call(amount=9000.0)
		salaries_row = next(r for r in home["accounts"] if "Salaries" in r["account"])
		self.assertEqual(salaries_row["credit_in_account_currency"], 9000.0)
		self.assertNotIn("debit_in_account_currency", salaries_row)
		self.assertEqual(salaries_row["party_type"], "Employee")
		self.assertEqual(salaries_row["party"], "BEI-EMP-2026-00123")
		self.assertEqual(salaries_row["cost_center"], "Main - BEI")
		self.assertEqual(salaries_row["reference_type"], "Salary Slip")
		self.assertEqual(salaries_row["reference_name"], "SS-2026-04-001")

	def test_home_je_due_from_row_is_debit_with_customer_party(self):
		home, _covered = self._call(amount=9000.0)
		due_from_row = next(r for r in home["accounts"] if "DUE FROM" in r["account"])
		self.assertEqual(due_from_row["debit_in_account_currency"], 9000.0)
		self.assertNotIn("credit_in_account_currency", due_from_row)
		self.assertEqual(due_from_row["party_type"], "Customer")
		# party = internal Customer representing the COVERED Company
		self.assertEqual(due_from_row["party"], COVERED_INTERNAL_CUSTOMER)
		self.assertEqual(due_from_row["cost_center"], "Main - BEI")

	def test_covered_je_structure(self):
		_home, covered = self._call()
		self.assertEqual(covered["voucher_type"], INTER_COMPANY_VOUCHER_TYPE)
		self.assertEqual(covered["company"], "SM MEGAMALL - BEBANG ENTERPRISE INC.")
		self.assertEqual(len(covered["accounts"]), 2)

	def test_covered_je_salaries_row_is_debit_with_employee_party(self):
		_home, covered = self._call(amount=9000.0)
		salaries_row = next(r for r in covered["accounts"] if "Salaries" in r["account"])
		self.assertEqual(salaries_row["debit_in_account_currency"], 9000.0)
		self.assertEqual(salaries_row["party_type"], "Employee")
		self.assertEqual(salaries_row["party"], "BEI-EMP-2026-00123")
		self.assertEqual(salaries_row["cost_center"], "Main - SMMM")

	def test_covered_je_due_to_row_is_credit_with_supplier_party(self):
		_home, covered = self._call(amount=9000.0)
		due_to_row = next(r for r in covered["accounts"] if "DUE TO" in r["account"])
		self.assertEqual(due_to_row["credit_in_account_currency"], 9000.0)
		self.assertEqual(due_to_row["party_type"], "Supplier")
		# party = internal Supplier representing the HOME Company
		self.assertEqual(due_to_row["party"], HOME_INTERNAL_SUPPLIER)
		self.assertEqual(due_to_row["cost_center"], "Main - SMMM")

	def test_amounts_balance_across_pair(self):
		"""DR total == CR total per JE, and amounts match between home/covered."""
		home, covered = self._call(amount=9000.0)
		home_dr = sum(r.get("debit_in_account_currency", 0) for r in home["accounts"])
		home_cr = sum(r.get("credit_in_account_currency", 0) for r in home["accounts"])
		covered_dr = sum(r.get("debit_in_account_currency", 0) for r in covered["accounts"])
		covered_cr = sum(r.get("credit_in_account_currency", 0) for r in covered["accounts"])
		self.assertEqual(home_dr, home_cr, "Home JE must balance")
		self.assertEqual(covered_dr, covered_cr, "Covered JE must balance")
		self.assertEqual(home_dr, covered_dr, "Same amount on both sides of pair")

	def test_no_party_type_company_anywhere(self):
		"""Regression: party_type='Company' is invalid on ERPNext v15 Receivable/Payable rows."""
		home, covered = self._call(amount=9000.0)
		for je_label, je in (("home", home), ("covered", covered)):
			for row in je["accounts"]:
				self.assertNotEqual(
					row.get("party_type"),
					"Company",
					f"{je_label} JE has forbidden party_type='Company' on row {row}",
				)


class SkipReasonTests(unittest.TestCase):
	"""Test _skip_reason classification."""

	def _slip(self, gross_pay=30000.0):
		slip = MagicMock()
		slip.employee = "EMP-001"
		slip.gross_pay = gross_pay
		return slip

	def test_zero_gross_returns_zero_gross(self):
		slip = self._slip(gross_pay=0)
		self.assertEqual(_skip_reason(slip), SKIP_ZERO_GROSS)

	def test_non_store_billing_returns_reason(self):
		slip = self._slip()
		emp = MagicMock()
		emp.department = "IT"
		emp.designation = "SYSTEM ADMIN"
		emp.branch = "BRITTANY HOTEL"
		with patch.object(labor_allocation, "frappe") as mock_frappe:
			mock_frappe.get_doc.return_value = emp
			with patch.object(labor_allocation, "is_non_store_billing_doc", return_value=True):
				self.assertEqual(_skip_reason(slip), SKIP_NON_STORE_BILLING)

	def test_commissary_producer_returns_reason(self):
		slip = self._slip()
		emp = MagicMock()
		emp.department = "Commissary"
		emp.designation = "PRODUCTION CREW"
		emp.branch = "SHAW COMMISSARY - PRODUCTION"
		with patch.object(labor_allocation, "frappe") as mock_frappe:
			mock_frappe.get_doc.return_value = emp
			with patch.object(labor_allocation, "is_non_store_billing_doc", return_value=False):
				self.assertEqual(_skip_reason(slip), SKIP_COMMISSARY_PRODUCER)

	def test_normal_store_employee_not_skipped(self):
		slip = self._slip()
		emp = MagicMock()
		emp.department = "Operations"
		emp.designation = "CASHIER"
		emp.branch = "SM MEGAMALL"
		with patch.object(labor_allocation, "frappe") as mock_frappe:
			mock_frappe.get_doc.return_value = emp
			with patch.object(labor_allocation, "is_non_store_billing_doc", return_value=False):
				self.assertIsNone(_skip_reason(slip))


if __name__ == "__main__":
	unittest.main()
