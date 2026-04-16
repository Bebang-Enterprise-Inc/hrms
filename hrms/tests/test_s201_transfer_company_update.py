"""S201: Transfer API sets new_company based on new_branch.

Pure-unit coverage of `_derive_new_company` without a Frappe context.
"""

import sys
import types
import unittest
from unittest.mock import patch


class _FakeEmp:
    def __init__(self, **kwargs):
        self.attendance_device_id = kwargs.get("attendance_device_id")
        self.new_attendance_device_id = kwargs.get("new_attendance_device_id")
        self.department = kwargs.get("department")
        self.designation = kwargs.get("designation")
        self.company = kwargs.get("company", "BEBANG ENTERPRISE INC.")


class TransferCompanyUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Import lazily after Frappe shim is in place (tests run under
        # Frappe's test runner which provides real frappe).
        from hrms.api import transfers
        cls.transfers = transfers

    def test_store_crew_new_branch_sets_store_company(self):
        """Operations cashier transferred SM MEGAMALL -> SM TANZA updates company."""
        emp = _FakeEmp(
            department="Operations",
            designation="CASHIER",
            company="SM MEGAMALL - BEBANG ENTERPRISE INC.",
        )
        mock_index = {
            "SM TANZA": "SM TANZA - BEBANG MEGA INC.",
        }
        from hrms.utils import company_lookup
        with patch.object(
            company_lookup, "_load_store_company_index", return_value=mock_index
        ):
            company_lookup.clear_cache()
            result = self.transfers._derive_new_company(emp, "SM TANZA")
        self.assertEqual(result, "SM TANZA - BEBANG MEGA INC.")

    def test_roving_transfer_keeps_bei_parent(self):
        """Roving bio_id employee stays on BEI parent even if branch changes."""
        emp = _FakeEmp(
            attendance_device_id="9000037",  # Kenneth Serinas (roving)
            department="Operations",
            designation="ROVING",
            company="BEBANG ENTERPRISE INC.",
        )
        result = self.transfers._derive_new_company(emp, "SM TANZA")
        self.assertEqual(result, "BEBANG ENTERPRISE INC.")

    def test_area_supervisor_transfer_keeps_bei_parent(self):
        """AS transfer keeps BEI parent regardless of new branch."""
        emp = _FakeEmp(
            department="Operations",
            designation="AREA SUPERVISOR",
            company="BEBANG ENTERPRISE INC.",
        )
        result = self.transfers._derive_new_company(emp, "SM TANZA")
        self.assertEqual(result, "BEBANG ENTERPRISE INC.")

    def test_it_dept_transfer_to_store_still_bei(self):
        """IT dept employee transferred to a store branch stays BEI parent."""
        emp = _FakeEmp(
            department="IT",
            designation="System Administrator",
            company="BEBANG ENTERPRISE INC.",
        )
        result = self.transfers._derive_new_company(emp, "SM MEGAMALL")
        self.assertEqual(result, "BEBANG ENTERPRISE INC.")

    def test_commissary_crew_transfer_routes_to_bki(self):
        """Commissary department employee transferred to bare SHAW COMMISSARY -> BKI."""
        emp = _FakeEmp(
            department="Commissary",
            designation="PRODUCTION CREW",
            company="BEBANG KITCHEN INC.",
        )
        result = self.transfers._derive_new_company(emp, "SHAW COMMISSARY")
        self.assertEqual(result, "BEBANG KITCHEN INC.")

    def test_scm_at_commissary_transfer_to_logistics_branch_routes_to_bei(self):
        """SCM team at commissary (Logistics branch) -> BEI parent per Sam."""
        emp = _FakeEmp(
            department="Operations",
            designation="LOGISTICS COORDINATOR",
            company="BEBANG ENTERPRISE INC.",
        )
        result = self.transfers._derive_new_company(emp, "SHAW COMMISSARY - Logistics")
        self.assertEqual(result, "BEBANG ENTERPRISE INC.")

    def test_unknown_branch_keeps_existing_company(self):
        """Unresolvable branch leaves company unchanged (don't throw, don't pivot)."""
        emp = _FakeEmp(
            department="Operations",
            designation="CASHIER",
            company="SM MEGAMALL - BEBANG ENTERPRISE INC.",
        )
        result = self.transfers._derive_new_company(emp, "TOTALLY UNKNOWN BRANCH")
        self.assertEqual(result, "SM MEGAMALL - BEBANG ENTERPRISE INC.")


if __name__ == "__main__":
    unittest.main()
