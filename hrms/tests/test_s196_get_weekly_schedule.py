"""S196 integration test — get_weekly_schedule returns 47+ stores post-fix.

Calls the public API and asserts the grid universe matches expectations.
"""
from __future__ import annotations

import unittest

import frappe

from hrms.api.store import get_weekly_schedule


class TestS196GetWeeklySchedule(unittest.TestCase):
    """S196 Phase 4 P4-T2 integration test."""

    def setUp(self):
        # Ensure SCM permissions for test execution
        frappe.set_user("Administrator")

    def test_store_meta_has_at_least_47(self):
        """store_meta should have at least 47 entries post-S196."""
        result = get_weekly_schedule(week_start="2026-04-13")
        store_meta = result.get("store_meta", {})
        self.assertGreaterEqual(
            len(store_meta), 47,
            f"Expected >= 47 stores in store_meta, got {len(store_meta)}",
        )

    def test_shaw_blvd_commissary_present(self):
        """Shaw BLVD - BKI (Bebang Kitchen Inc. commissary) must appear."""
        result = get_weekly_schedule(week_start="2026-04-13")
        store_meta = result.get("store_meta", {})
        self.assertIn(
            "Shaw BLVD - BKI", store_meta,
            "Shaw BLVD - BKI (commissary) missing from grid",
        )

    def test_no_head_office_warehouses(self):
        """BGC CAPITAL HOUSE / BRITTANY OFFICE must NOT appear (negative test)."""
        result = get_weekly_schedule(week_start="2026-04-13")
        store_meta = result.get("store_meta", {})
        for hq in ("BGC CAPITAL HOUSE", "BRITTANY OFFICE"):
            matches = [k for k in store_meta.keys() if hq in k]
            self.assertEqual(
                matches, [],
                f"Head Office warehouse {hq} leaked: {matches}",
            )

    def test_no_cryptic_duplicate_warehouses(self):
        """The 3 deleted cryptic duplicates (TRICERN-BV etc) must not appear."""
        result = get_weekly_schedule(week_start="2026-04-13")
        store_meta = result.get("store_meta", {})
        forbidden = [
            "TRICERN FOOD CORP. - BV",
            "DAY ONES FOOD AND DRINK ESTABLISHMENTS CORP. - BST",
            "RED TALDAWA FOODS OPC - BSC2",
            "Tungsten Capital - Gateway Mall - TCH-GW",
            "TAJ Food Corp. - DVerde Calamba - TFC-DVC",
        ]
        for wh in forbidden:
            self.assertNotIn(
                wh, store_meta,
                f"Deleted duplicate {wh!r} reappeared in grid",
            )

    def test_renamed_legacy_warehouses_present(self):
        """The 3 W-6 renamed warehouses should appear under store-first names."""
        result = get_weekly_schedule(week_start="2026-04-13")
        store_meta = result.get("store_meta", {})
        expected = [
            "Vista Mall Taguig - Tricern Food Corp.",
            "SM Taytay - Day Ones Food and Drink Establishments Corp.",
            "SM Clark - Red Taldawa Foods OPC",
        ]
        for wh in expected:
            self.assertIn(
                wh, store_meta,
                f"W-6 renamed warehouse {wh!r} missing from grid",
            )


if __name__ == "__main__":
    unittest.main()
