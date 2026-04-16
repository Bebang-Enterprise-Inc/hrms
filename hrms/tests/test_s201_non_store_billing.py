"""S201: Non-store billing classifier tests.

These tests run without a Frappe context (is_non_store_billing accepts plain
fields). The branch-category rule is mocked by monkey-patching the import.
"""

import unittest
from unittest.mock import patch

from hrms.utils import non_store_billing


class NonStoreBillingTests(unittest.TestCase):
    # --- Rule 1: roving bio_id ---

    def test_roving_bio_returns_true(self):
        # 9000037 is in ROVING_EMPLOYEES (Kenneth Serinas)
        self.assertTrue(
            non_store_billing.is_non_store_billing(
                bio_id="9000037", department="Operations", branch="SM MEGAMALL"
            )
        )

    def test_non_roving_bio_does_not_trigger_rule1(self):
        # 9999999 is NOT in the dict
        self.assertFalse(
            non_store_billing.is_non_store_billing(
                bio_id="9999999",
                department="Operations",
                designation="CASHIER",
                branch="SM MEGAMALL",
            )
        )

    # --- Rule 2: designation keywords ---

    def test_area_supervisor_designation(self):
        self.assertTrue(
            non_store_billing.is_non_store_billing(
                designation="AREA SUPERVISOR", department="Operations"
            )
        )

    def test_regional_manager_designation(self):
        self.assertTrue(
            non_store_billing.is_non_store_billing(designation="Regional Manager")
        )

    def test_projects_manager_designation(self):
        self.assertTrue(
            non_store_billing.is_non_store_billing(designation="Projects Manager")
        )

    def test_ceo_chief_keyword(self):
        self.assertTrue(
            non_store_billing.is_non_store_billing(designation="Chief Executive Officer")
        )
        self.assertTrue(
            non_store_billing.is_non_store_billing(designation="CFO")
        )

    def test_store_supervisor_does_not_trigger(self):
        # "STORE SUPERVISOR" should NOT match "AREA SUPERVISOR" keyword.
        self.assertFalse(
            non_store_billing.is_non_store_billing(
                designation="STORE SUPERVISOR",
                department="Operations",
                branch="SM MEGAMALL",
            )
        )

    # --- Rule 3: HO departments ---

    def test_finance_dept(self):
        self.assertTrue(non_store_billing.is_non_store_billing(department="Finance and Accounting"))

    def test_it_dept(self):
        self.assertTrue(non_store_billing.is_non_store_billing(department="IT"))

    def test_marketing_dept(self):
        self.assertTrue(non_store_billing.is_non_store_billing(department="Marketing"))

    def test_projects_dept(self):
        self.assertTrue(non_store_billing.is_non_store_billing(department="Projects"))

    def test_executive_dept(self):
        self.assertTrue(non_store_billing.is_non_store_billing(department="Executive"))

    def test_rd_dept(self):
        self.assertTrue(non_store_billing.is_non_store_billing(department="R&D"))

    def test_scm_dept(self):
        self.assertTrue(non_store_billing.is_non_store_billing(department="SCM"))

    def test_operations_dept_is_NOT_ho(self):
        self.assertFalse(
            non_store_billing.is_non_store_billing(
                department="Operations",
                designation="CASHIER",
                branch="SM MEGAMALL",
            )
        )

    def test_operations_caps_variant_is_NOT_ho(self):
        # Case-drift safety: "OPERATIONS" (all caps) also NOT HO.
        self.assertFalse(
            non_store_billing.is_non_store_billing(
                department="OPERATIONS",
                designation="ASSISTANT STORE SUPERVISOR",
                branch="SM MEGAMALL",
            )
        )

    def test_commissary_dept_is_NOT_ho(self):
        # Commissary dept bills to BKI, not BEI parent — so NOT non_store.
        self.assertFalse(
            non_store_billing.is_non_store_billing(
                department="Commissary", branch="SHAW COMMISSARY - PRODUCTION"
            )
        )

    def test_customer_service_dept_is_NOT_ho(self):
        self.assertFalse(
            non_store_billing.is_non_store_billing(
                department="Customer Service",
                designation="CASHIER",
                branch="SM MEGAMALL",
            )
        )

    # --- Rule 4: branch category == HO ---

    def test_ho_branch_routes_to_parent(self):
        with patch.object(non_store_billing, "get_branch_category", return_value="HO"):
            self.assertTrue(
                non_store_billing.is_non_store_billing(
                    department="Operations", branch="BRITTANY OFFICE"
                )
            )

    def test_scm_logistics_commissary_branch_routes_to_ho(self):
        # Per Sam 2026-04-17: SCM team at commissary -> BEI parent.
        # Map rows SHAW COMMISSARY - LOGISTICS and SHAW COMMISSARY - RD QC
        # have target_category='HO'.
        with patch.object(non_store_billing, "get_branch_category", return_value="HO"):
            self.assertTrue(
                non_store_billing.is_non_store_billing(
                    department="Operations",
                    branch="SHAW COMMISSARY - LOGISTICS",
                )
            )

    def test_store_branch_does_not_trigger(self):
        with patch.object(non_store_billing, "get_branch_category", return_value="Store"):
            self.assertFalse(
                non_store_billing.is_non_store_billing(
                    department="Operations",
                    designation="CASHIER",
                    branch="SM MEGAMALL",
                )
            )

    def test_missing_map_file_fails_open(self):
        # If company_lookup can't load map, we should NOT throw — return False.
        with patch.object(
            non_store_billing, "get_branch_category", side_effect=RuntimeError("no map")
        ):
            self.assertFalse(
                non_store_billing.is_non_store_billing(
                    department="Operations",
                    designation="CASHIER",
                    branch="SM MEGAMALL",
                )
            )


if __name__ == "__main__":
    unittest.main()
