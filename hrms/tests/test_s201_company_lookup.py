"""S201: company_lookup resolver tests.

We mock the Frappe Company index to avoid requiring a bench context.
"""

import unittest
from unittest.mock import patch

from hrms.utils import company_lookup
from hrms.utils.company_lookup import (
    UnknownBranch,
    resolve_branch_rename,
    resolve_branch_to_company,
)


# Mock store company index — simulates live Frappe state post-S196 rename.
MOCK_STORE_INDEX = {
    "SM MEGAMALL": "SM MEGAMALL - BEBANG ENTERPRISE INC.",
    "SM TANZA": "SM TANZA - BEBANG MEGA INC.",
    "AYALA UP TOWN CENTER": "AYALA UP TOWN CENTER - BEBANG UP TOWN CENTER INC.",
    "AYALA EVO CITY": "AYALA EVO CITY - BEBANG MEGA INC.",
    "XENTROMALL MONTALBAN": "XENTROMALL MONTALBAN - BEBANG ENTERPRISE INC.",
    "ORTIGAS ESTANCIA": "ORTIGAS ESTANCIA - BB ESTANCIA FOOD CORP.",
    "ORTIGAS GREENHILLS": "ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC",
    "BRITTANY HOTEL": "BRITTANY HOTEL - BEBANG ENTERPRISE INC.",
    "BF HOMES PARANAQUE": "BF HOMES PARANAQUE - BEBANG BF HOMES INC.",
    "AYALA MARKET MARKET": "AYALA MARKET MARKET - BEBANG MARKET MARKET INC.",
    "UPTOWN BGC": "UPTOWN BGC - BEBANG UPTOWN BGC INC.",
    "VENICE GRAND CANAL": "VENICE GRAND CANAL - BEBANG VENICE GRAND CANAL INC.",
    "NAIA T3": "NAIA T3 - HALO-HALO TERMINAL FOOD CORP.",
}


def _force_refresh():
    """Reset the module-level cache and force reload."""
    company_lookup.clear_cache()


class CompanyLookupTests(unittest.TestCase):
    def setUp(self):
        _force_refresh()

    def _patch_store_index(self):
        """Apply store index mock and prime the cache."""
        return patch.object(
            company_lookup, "_load_store_company_index", return_value=MOCK_STORE_INDEX
        )

    # --- HO routing ---

    def test_brittany_office_routes_to_parent(self):
        with self._patch_store_index():
            self.assertEqual(
                resolve_branch_to_company("BRITTANY OFFICE"),
                "BEBANG ENTERPRISE INC.",
            )

    def test_capital_house_routes_to_parent(self):
        with self._patch_store_index():
            self.assertEqual(
                resolve_branch_to_company("CAPITAL HOUSE"),
                "BEBANG ENTERPRISE INC.",
            )

    def test_mytown_routes_to_parent(self):
        with self._patch_store_index():
            self.assertEqual(
                resolve_branch_to_company("MYTOWN"),
                "BEBANG ENTERPRISE INC.",
            )

    # --- Commissary routing with dept check ---

    def test_shaw_commissary_production_is_bki(self):
        with self._patch_store_index():
            self.assertEqual(
                resolve_branch_to_company("SHAW COMMISSARY - Production"),
                "BEBANG KITCHEN INC.",
            )

    def test_shaw_commissary_logistics_is_bei_parent(self):
        # SCM team per Sam 2026-04-17
        with self._patch_store_index():
            self.assertEqual(
                resolve_branch_to_company("SHAW COMMISSARY - Logistics"),
                "BEBANG ENTERPRISE INC.",
            )

    def test_shaw_commissary_rdqc_is_bei_parent(self):
        with self._patch_store_index():
            self.assertEqual(
                resolve_branch_to_company("SHAW COMMISSARY - RD QC"),
                "BEBANG ENTERPRISE INC.",
            )

    def test_bare_shaw_commissary_with_commissary_dept_is_bki(self):
        with self._patch_store_index():
            self.assertEqual(
                resolve_branch_to_company("SHAW COMMISSARY", department="Commissary"),
                "BEBANG KITCHEN INC.",
            )

    def test_bare_shaw_commissary_with_other_dept_is_bei_parent(self):
        with self._patch_store_index():
            self.assertEqual(
                resolve_branch_to_company("SHAW COMMISSARY", department="SCM"),
                "BEBANG ENTERPRISE INC.",
            )

    def test_commissary_shaw_alias_resolves_same_as_canonical(self):
        # "COMMISSARY SHAW" is the pre-rename variant of "SHAW COMMISSARY".
        with self._patch_store_index():
            self.assertEqual(
                resolve_branch_to_company("COMMISSARY SHAW", department="Commissary"),
                "BEBANG KITCHEN INC.",
            )

    # --- Store routing ---

    def test_sm_megamall_resolves_to_full_company(self):
        with self._patch_store_index():
            self.assertEqual(
                resolve_branch_to_company("SM MEGAMALL"),
                "SM MEGAMALL - BEBANG ENTERPRISE INC.",
            )

    def test_ayala_uptc_alias_resolves_to_canonical(self):
        with self._patch_store_index():
            self.assertEqual(
                resolve_branch_to_company("AYALA UPTC"),
                "AYALA UP TOWN CENTER - BEBANG UP TOWN CENTER INC.",
            )

    def test_xentro_alias_resolves(self):
        with self._patch_store_index():
            self.assertEqual(
                resolve_branch_to_company("XENTRO MONTALBAN"),
                "XENTROMALL MONTALBAN - BEBANG ENTERPRISE INC.",
            )

    def test_estancia_alias_resolves(self):
        with self._patch_store_index():
            self.assertEqual(
                resolve_branch_to_company("ESTANCIA"),
                "ORTIGAS ESTANCIA - BB ESTANCIA FOOD CORP.",
            )

    def test_greenhills_alias_resolves(self):
        with self._patch_store_index():
            self.assertEqual(
                resolve_branch_to_company("GREENHILLS"),
                "ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC",
            )

    def test_the_terminal_merges_to_naia_t3(self):
        with self._patch_store_index():
            self.assertEqual(
                resolve_branch_to_company("THE TERMINAL"),
                "NAIA T3 - HALO-HALO TERMINAL FOOD CORP.",
            )

    def test_bgc_store_uptown_resolves(self):
        with self._patch_store_index():
            self.assertEqual(
                resolve_branch_to_company("UPTOWN BGC"),
                "UPTOWN BGC - BEBANG UPTOWN BGC INC.",
            )

    def test_bgc_store_venice_resolves(self):
        with self._patch_store_index():
            self.assertEqual(
                resolve_branch_to_company("VENICE GRAND CANAL"),
                "VENICE GRAND CANAL - BEBANG VENICE GRAND CANAL INC.",
            )

    def test_bgc_store_market_market_resolves(self):
        with self._patch_store_index():
            self.assertEqual(
                resolve_branch_to_company("AYALA MARKET MARKET"),
                "AYALA MARKET MARKET - BEBANG MARKET MARKET INC.",
            )

    # --- Case insensitivity ---

    def test_lowercase_branch_resolves(self):
        with self._patch_store_index():
            self.assertEqual(
                resolve_branch_to_company("sm megamall"),
                "SM MEGAMALL - BEBANG ENTERPRISE INC.",
            )

    def test_whitespace_stripped(self):
        with self._patch_store_index():
            self.assertEqual(
                resolve_branch_to_company("  SM MEGAMALL  "),
                "SM MEGAMALL - BEBANG ENTERPRISE INC.",
            )

    # --- Error paths ---

    def test_empty_branch_raises(self):
        with self._patch_store_index():
            with self.assertRaises(UnknownBranch):
                resolve_branch_to_company("")

    def test_unknown_branch_raises(self):
        with self._patch_store_index():
            with self.assertRaises(UnknownBranch):
                resolve_branch_to_company("NOPE NOT A REAL BRANCH")

    def test_bgc_resolves_to_brittany_hotel_ho(self):
        # BGC lone employee (Edlice Dela Cruz, REGIONAL AREA MANAGER) verified
        # via ADMS probe 2026-04-17 as office-based HO — maps to Brittany Hotel HO.
        with self._patch_store_index():
            self.assertEqual(
                resolve_branch_to_company("BGC"),
                "BEBANG ENTERPRISE INC.",
            )

    def test_store_missing_from_frappe_index_raises(self):
        # Branch maps to a store prefix that doesn't exist in the live Company
        # table.
        with patch.object(
            company_lookup, "_load_store_company_index", return_value={}
        ):
            with self.assertRaises(UnknownBranch):
                resolve_branch_to_company("SM MEGAMALL")

    # --- Rename map ---

    def test_rename_ayala_uptc_canonicalizes(self):
        self.assertEqual(
            resolve_branch_rename("AYALA UPTC"), "AYALA UP TOWN CENTER"
        )

    def test_rename_xentro_canonicalizes(self):
        self.assertEqual(
            resolve_branch_rename("XENTRO MONTALBAN"), "XENTROMALL MONTALBAN"
        )

    def test_rename_sm_megamall_no_change(self):
        self.assertEqual(resolve_branch_rename("SM MEGAMALL"), "SM MEGAMALL")

    def test_rename_unknown_returns_none(self):
        self.assertIsNone(resolve_branch_rename("RANDOM UNKNOWN"))


if __name__ == "__main__":
    unittest.main()
