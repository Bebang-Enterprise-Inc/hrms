"""S206 live-Frappe integration tests.

Unit tests in test_s206_labor_allocation.py use mocks — they prove the JE
dict STRUCTURE is DM-1/DM-6 compliant but don't validate against Frappe's
actual validators. That gap let party_type='Company' slip through the
original S206 handoff (see output/s206/audit/POST_EXECUTION_AUDIT_2026-04-18.md).

These tests actually insert and submit a paired Journal Entry against the
live test site, catching real validation failures (e.g., Party Type not
registered, Account not found, inter_company balance mismatch).

Run via:

    docker exec $BACKEND bench --site <test_site> run-tests \
        --app hrms --module hrms.tests.test_s206_integration

Or in CI:

    bench run-tests --app hrms --module hrms.tests.test_s206_integration

Preconditions (all checked by setUpClass — test is SKIPPED if missing):
  - hrms.on_demand.s206_seed_intercompany_accounts has been run
  - At least 2 in-scope Companies exist (home + covered)
  - Salaries Expense account exists on both
  - At least one Employee with punches in the target period
"""

from __future__ import annotations

import unittest
from datetime import date

import frappe

from hrms.utils.labor_allocation import (
    _build_paired_jes,
    _insert_and_link,
    _resolve_company_accounts,
    _resolve_company_parties,
)


class S206JournalEntryIntegrationTests(unittest.TestCase):
    """Verify paired JE actually posts on live Frappe with real validation."""

    HOME_COMPANY = None
    COVERED_COMPANY = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        companies = frappe.db.sql(
            """
            SELECT name FROM tabCompany
            WHERE entity_category = 'Store'
               OR name IN ('BEBANG ENTERPRISE INC.', 'BEBANG KITCHEN INC.')
            ORDER BY name
            LIMIT 2
            """,
            as_dict=True,
        )
        if len(companies) < 2:
            raise unittest.SkipTest("Need at least 2 in-scope Companies; S206 seeder has not run")

        cls.HOME_COMPANY = companies[0]["name"]
        cls.COVERED_COMPANY = companies[1]["name"]

        # Verify accounts + parties exist (seeder prerequisites)
        try:
            _resolve_company_accounts(cls.HOME_COMPANY)
            _resolve_company_accounts(cls.COVERED_COMPANY)
            _resolve_company_parties(cls.HOME_COMPANY)
            _resolve_company_parties(cls.COVERED_COMPANY)
        except frappe.ValidationError as exc:
            raise unittest.SkipTest(f"S206 seeder prerequisites missing: {exc}")

    def _fake_slip(self):
        """Return a stand-in slip with enough attributes to build a JE pair."""
        # Use the first active Employee; fall back to a hard-coded test employee.
        employee = frappe.db.get_value("Employee", {"status": "Active"}, "name")
        if not employee:
            raise unittest.SkipTest("No active employees on test site")

        class _Slip:
            pass

        s = _Slip()
        s.name = "S206-INT-TEST-SLIP"
        s.employee = employee
        s.start_date = date(2026, 4, 1)
        s.end_date = date(2026, 4, 30)
        s.gross_pay = 1000.0
        s.department = frappe.db.get_value("Employee", employee, "department")
        s.company = self.HOME_COMPANY
        return s

    def test_paired_je_inserts_and_submits_cleanly(self):
        """Insert + submit a real paired Journal Entry. Asserts no validation throws."""
        slip = self._fake_slip()
        amount = 500.0
        home_dict, covered_dict = _build_paired_jes(
            slip=slip,
            share=0.5,
            home=self.HOME_COMPANY,
            covered=self.COVERED_COMPANY,
            amount=amount,
        )

        # Wrap in a savepoint so the test doesn't leave posted JEs behind.
        frappe.db.savepoint("s206_integration_test")
        try:
            home_name, covered_name = _insert_and_link(home_dict, covered_dict)

            # Verify both docs exist and are submitted
            home_doc = frappe.get_doc("Journal Entry", home_name)
            covered_doc = frappe.get_doc("Journal Entry", covered_name)
            self.assertEqual(home_doc.docstatus, 1, "Home JE should be submitted")
            self.assertEqual(covered_doc.docstatus, 1, "Covered JE should be submitted")
            self.assertEqual(
                home_doc.inter_company_journal_entry_reference, covered_name,
                "Home JE should reference covered JE",
            )
            self.assertEqual(
                covered_doc.inter_company_journal_entry_reference, home_name,
                "Covered JE should reference home JE",
            )

            # GL rows: verify party_type actually persisted
            home_gl = frappe.db.sql(
                """
                SELECT party_type, party, account, debit, credit
                FROM `tabGL Entry`
                WHERE voucher_no = %(name)s AND is_cancelled = 0
                ORDER BY credit DESC
                """,
                {"name": home_name},
                as_dict=True,
            )
            # Every receivable row should have party_type Customer or Employee
            for row in home_gl:
                if row["party_type"]:
                    self.assertIn(
                        row["party_type"], ("Customer", "Supplier", "Employee"),
                        f"Invalid party_type on GL Entry: {row}",
                    )
                    self.assertNotEqual(
                        row["party_type"], "Company",
                        "party_type='Company' is invalid on Receivable/Payable rows",
                    )
        finally:
            # Always roll back so test doesn't leave GL residue
            frappe.db.rollback(save_point="s206_integration_test")

    def test_party_type_company_would_fail(self):
        """Sanity: posting with party_type='Company' fails — confirms we need Customer/Supplier."""
        slip = self._fake_slip()
        home_accounts = _resolve_company_accounts(self.HOME_COMPANY)
        je = {
            "doctype": "Journal Entry",
            "voucher_type": "Inter Company Journal Entry",
            "company": self.HOME_COMPANY,
            "posting_date": slip.end_date,
            "user_remark": "S206 integration negative test",
            "accounts": [
                {
                    "account": home_accounts["salaries_expense"],
                    "credit_in_account_currency": 100.0,
                    "party_type": "Employee",
                    "party": slip.employee,
                    "cost_center": home_accounts["cost_center"],
                },
                {
                    "account": home_accounts["due_from"],
                    "debit_in_account_currency": 100.0,
                    "party_type": "Company",  # <-- forbidden
                    "party": self.COVERED_COMPANY,
                    "cost_center": home_accounts["cost_center"],
                },
            ],
        }

        frappe.db.savepoint("s206_neg_test")
        try:
            with self.assertRaises(Exception):
                doc = frappe.get_doc(je)
                doc.insert(ignore_permissions=True)
                doc.submit()
        finally:
            try:
                frappe.db.rollback(save_point="s206_neg_test")
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
