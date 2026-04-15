"""S196 tests — canonical orderable-store helpers.

Tests `get_orderable_companies` + `get_orderable_store_warehouses` against
post-Phase-2 production data (via bench unit tests running on hq.bebang.ph).
"""
from __future__ import annotations

import unittest

import frappe

from hrms.api.company_master import (
    get_orderable_companies,
    get_orderable_store_warehouses,
)


class TestS196OrderableCompanies(unittest.TestCase):
    """S196 Phase 4 tests (audit v3 P4-T1, 12 cases)."""

    def test_a_returns_store_companies(self):
        """a: helper returns at least 47 Companies (post-S196 universe ~50)."""
        result = get_orderable_companies(include_commissary=True)
        self.assertGreaterEqual(len(result), 47, f"Expected >= 47 orderable, got {len(result)}")

    def test_b_excludes_permanently_closed(self):
        """b: Companies with operational_status=Permanently Closed are excluded."""
        result = set(get_orderable_companies(include_commissary=True))
        closed = frappe.get_all(
            "Company",
            filters={"operational_status": "Permanently Closed"},
            pluck="name",
        )
        for c in closed:
            self.assertNotIn(c, result, f"{c!r} is Permanently Closed but leaked into result")

    def test_c_excludes_non_store_categories(self):
        """c: Head Office / Holding / Franchisor / Warehouse / Archived entity_category excluded."""
        result = set(get_orderable_companies(include_commissary=True))
        non_store = frappe.get_all(
            "Company",
            filters={"entity_category": ["in", ["Head Office", "Holding Company", "Franchisor", "Warehouse", "Archived"]]},
            pluck="name",
        )
        for c in non_store:
            self.assertNotIn(c, result, f"{c!r} is non-store entity_category but leaked into result")

    def test_d_commissary_included_when_true(self):
        """d: Bebang Kitchen Inc. (commissary) in result when include_commissary=True."""
        result = set(get_orderable_companies(include_commissary=True))
        self.assertIn("Bebang Kitchen Inc.", result)

    def test_e_commissary_excluded_when_false(self):
        """e: Bebang Kitchen Inc. excluded when include_commissary=False."""
        result = set(get_orderable_companies(include_commissary=False))
        self.assertNotIn("Bebang Kitchen Inc.", result)

    def test_f_warehouse_list_min_count(self):
        """f: get_orderable_store_warehouses returns >= 47 rows."""
        result = get_orderable_store_warehouses(include_commissary=True)
        self.assertGreaterEqual(len(result), 47, f"Expected >= 47 warehouse rows, got {len(result)}")

    def test_g_every_wh_passes_is_orderable(self):
        """g: every returned warehouse passes _is_orderable_store."""
        from hrms.api.store import _is_orderable_store

        result = get_orderable_store_warehouses(include_commissary=True)
        for row in result:
            meta = row["warehouse_meta"]
            self.assertTrue(
                _is_orderable_store(meta),
                f"Row {row['warehouse']!r} failed _is_orderable_store",
            )

    def test_h1_negative_head_office_warehouses(self):
        """h1: BGC CAPITAL HOUSE / BRITTANY OFFICE (head office warehouses) NOT in result."""
        result = get_orderable_store_warehouses(include_commissary=True)
        names = {row["warehouse"] for row in result}
        for hq_wh in ("BGC CAPITAL HOUSE", "BRITTANY OFFICE"):
            matching = [n for n in names if hq_wh in n]
            self.assertEqual(matching, [], f"Head Office warehouse leaked: {matching}")

    def test_h2_empty_list_short_circuit(self):
        """h2: G1 empty-list short-circuit — if get_orderable_companies returns [], wh list is []."""
        import hrms.api.company_master as cm
        original = cm.get_orderable_companies
        try:
            cm.get_orderable_companies = lambda include_commissary=True: []
            result = cm.get_orderable_store_warehouses()
            self.assertEqual(result, [], "Empty orderable should yield empty wh list (G1 short-circuit)")
        finally:
            cm.get_orderable_companies = original

    def test_h3_multi_wh_determinism(self):
        """h3: 3 consecutive calls return same warehouse per Company (tie-break deterministic)."""
        r1 = {row["company"]: row["warehouse"] for row in get_orderable_store_warehouses(True)}
        r2 = {row["company"]: row["warehouse"] for row in get_orderable_store_warehouses(True)}
        r3 = {row["company"]: row["warehouse"] for row in get_orderable_store_warehouses(True)}
        self.assertEqual(r1, r2)
        self.assertEqual(r2, r3)

    def test_h4_archived_entity_category_excluded(self):
        """h4: Companies with entity_category set via raw SQL to non-Select value (e.g., Archived) are excluded."""
        # Production has 2 rows with entity_category="Archived" (not a valid Select option)
        # — those must not appear in orderable result.
        result = set(get_orderable_companies(include_commissary=True))
        archived = frappe.db.sql(
            "SELECT name FROM `tabCompany` WHERE entity_category = %s",
            ("Archived",),
            as_dict=True,
        )
        for a in archived:
            self.assertNotIn(
                a["name"], result,
                f"Archived entity_category {a['name']!r} leaked into result",
            )

    def test_h5_null_operational_status_excluded(self):
        """h5: Companies with NULL operational_status are EXCLUDED by allowlist filter (CR-7)."""
        result = set(get_orderable_companies(include_commissary=True))
        null_status = frappe.db.sql(
            "SELECT name FROM `tabCompany` WHERE (operational_status IS NULL OR operational_status = '')",
            as_dict=True,
        )
        for row in null_status:
            self.assertNotIn(
                row["name"], result,
                f"NULL operational_status {row['name']!r} leaked (CR-7 allowlist should exclude)",
            )


if __name__ == "__main__":
    unittest.main()
