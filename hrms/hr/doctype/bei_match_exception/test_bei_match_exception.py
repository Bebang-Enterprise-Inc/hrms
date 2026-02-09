# Copyright (c) 2026, Bebang Enterprise Inc.
# For license information, please see license.txt

import unittest

from hrms.hr.doctype.bei_match_exception.bei_match_exception import (
    get_approval_tier,
    get_tier_status,
)


class TestBEIMatchException(unittest.TestCase):
    def test_tier_under_500k(self):
        self.assertEqual(get_approval_tier(100000), "CPO")
        self.assertEqual(get_approval_tier(499999), "CPO")

    def test_tier_500k_to_1m(self):
        self.assertEqual(get_approval_tier(500000), "CFO")
        self.assertEqual(get_approval_tier(999999), "CFO")

    def test_tier_1m_and_above(self):
        self.assertEqual(get_approval_tier(1000000), "CEO")
        self.assertEqual(get_approval_tier(5000000), "CEO")

    def test_tier_zero(self):
        self.assertEqual(get_approval_tier(0), "CPO")

    def test_tier_status_mapping(self):
        self.assertEqual(get_tier_status("CPO"), "Pending CPO")
        self.assertEqual(get_tier_status("CFO"), "Pending CFO")
        self.assertEqual(get_tier_status("CEO"), "Pending CEO")


if __name__ == "__main__":
    unittest.main()
