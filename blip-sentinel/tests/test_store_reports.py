"""
Tests for Phase 4 store report aggregation in store_reports.py
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from store_reports import parse_store_report, _build_store_summary, _extract_store_name


class TestParseStoreReport(unittest.TestCase):

    def test_parse_standard_closing_report(self):
        """Test parsing a standard closing report."""
        text = """CLOSING REPORT
SM Megamall
Total Gross Sales: P94,074.50
Total Net Sales: P88,432.00
Total Cup Sold: 478"""

        result = parse_store_report(text)
        self.assertAlmostEqual(result["gross_sales"], 94074.50)
        self.assertAlmostEqual(result["net_sales"], 88432.00)
        self.assertEqual(result["cups_sold"], 478)
        self.assertEqual(result["fund_issues"], [])

    def test_parse_report_with_peso_sign(self):
        """Test parsing with peso sign instead of P."""
        text = "Total Gross Sales: ₱79,200\nTotal Cup Sold: 398"
        result = parse_store_report(text)
        self.assertAlmostEqual(result["gross_sales"], 79200.0)
        self.assertEqual(result["cups_sold"], 398)

    def test_parse_report_with_fund_issues(self):
        """Test fund issue detection."""
        text = """CLOSING REPORT
SM Caloocan
Total Gross Sales: P45,000
PCF depleted — borrowed P5,000 from delivery fund
Delivery Fund exceeded limit"""

        result = parse_store_report(text)
        self.assertEqual(len(result["fund_issues"]), 2)
        self.assertIn("PCF depleted", result["fund_issues"][0])

    def test_parse_empty_text(self):
        """Test parsing empty text returns None values."""
        result = parse_store_report("")
        self.assertIsNone(result["gross_sales"])
        self.assertIsNone(result["net_sales"])
        self.assertIsNone(result["cups_sold"])
        self.assertEqual(result["fund_issues"], [])

    def test_parse_partial_report(self):
        """Test parsing report with only some fields."""
        text = "Total Gross Sales: P50,000"
        result = parse_store_report(text)
        self.assertAlmostEqual(result["gross_sales"], 50000.0)
        self.assertIsNone(result["net_sales"])
        self.assertIsNone(result["cups_sold"])


class TestExtractStoreName(unittest.TestCase):

    def test_extract_from_closing_report(self):
        """Test extracting store name from closing report format."""
        text = "CLOSING REPORT\nSM Megamall\nTotal Gross Sales: P94,074"
        name = _extract_store_name(text, "Store Ops")
        self.assertEqual(name, "SM Megamall")

    def test_extract_from_daily_report_with_date(self):
        """Test extracting store name with date suffix stripped."""
        text = "DAILY SALES REPORT\nSM North Edsa - Feb 13\nTotal Gross Sales: P63,298"
        name = _extract_store_name(text, "Store Ops")
        self.assertEqual(name, "SM North Edsa")

    def test_fallback_to_space_name(self):
        """Test fallback to space_name when no pattern matches."""
        text = "Random text without store header"
        name = _extract_store_name(text, "Venice Grand Canal")
        self.assertEqual(name, "Venice Grand Canal")


class TestBuildStoreSummary(unittest.TestCase):

    def test_top_5_ranking(self):
        """Test top 5 stores are ranked by gross sales."""
        stores = [
            {"name": f"Store {i}", "gross_sales": i * 10000, "net_sales": None,
             "cups_sold": i * 100, "fund_issues": [], "space_name": f"Space {i}"}
            for i in range(1, 8)
        ]
        result = _build_store_summary(stores)

        self.assertIn("Top 5 by Gross Sales", result)
        self.assertIn("7 stores reported", result)
        self.assertIn("1. Store 7: P70,000 (700 cups)", result)
        self.assertIn("5. Store 3: P30,000 (300 cups)", result)
        # Store 2 and Store 1 should NOT appear (they're 6th and 7th)
        self.assertNotIn("6.", result)

    def test_fund_issues_section(self):
        """Test fund issues section appears when stores have issues."""
        stores = [
            {"name": "SM Caloocan", "gross_sales": 45000, "net_sales": None,
             "cups_sold": 220, "fund_issues": ["PCF depleted"], "space_name": "Space"},
            {"name": "BF Homes", "gross_sales": 38000, "net_sales": None,
             "cups_sold": 190, "fund_issues": ["PCF depleted", "Delivery Fund short"],
             "space_name": "Space"},
        ]
        result = _build_store_summary(stores)

        self.assertIn("Fund Issues", result)
        self.assertIn("2 stores", result)
        self.assertIn("SM Caloocan: PCF depleted", result)
        self.assertIn("BF Homes", result)

    def test_empty_stores_returns_empty(self):
        """Test empty store list returns empty string."""
        result = _build_store_summary([])
        self.assertEqual(result, "")

    def test_no_parsed_sales_shows_count(self):
        """Test stores without parsed sales data shows count."""
        stores = [
            {"name": "Store A", "gross_sales": None, "net_sales": None,
             "cups_sold": None, "fund_issues": [], "space_name": "Space"},
        ]
        result = _build_store_summary(stores)
        self.assertIn("1 store reports received", result)
        self.assertIn("no sales data parsed", result)


if __name__ == "__main__":
    unittest.main()
