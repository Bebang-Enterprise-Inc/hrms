# Copyright (c) 2026, Bebang Enterprise Inc.
# For license information, please see license.txt

import unittest
import types
import sys
import importlib.util
from pathlib import Path


def _load_module():
    if "frappe" not in sys.modules:
        fake_frappe = types.ModuleType("frappe")
        fake_frappe.db = types.SimpleNamespace(get_value=lambda *args, **kwargs: 0)
        fake_frappe.session = types.SimpleNamespace(user="test@example.com")
        fake_frappe.throw = lambda msg: (_ for _ in ()).throw(RuntimeError(msg))
        sys.modules["frappe"] = fake_frappe

        frappe_utils = types.ModuleType("frappe.utils")
        frappe_utils.flt = float
        frappe_utils.now_datetime = lambda: None
        sys.modules["frappe.utils"] = frappe_utils

        frappe_model = types.ModuleType("frappe.model")
        sys.modules["frappe.model"] = frappe_model

        frappe_model_document = types.ModuleType("frappe.model.document")
        frappe_model_document.Document = object
        sys.modules["frappe.model.document"] = frappe_model_document

    module_path = Path(__file__).resolve().parent / "bei_match_exception.py"
    spec = importlib.util.spec_from_file_location("bei_match_exception", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load_module()
get_approval_tier = MODULE.get_approval_tier
get_tier_status = MODULE.get_tier_status


class TestBEIMatchException(unittest.TestCase):
    def test_tier_under_500k(self):
        self.assertEqual(get_approval_tier(100000), "CPO")
        self.assertEqual(get_approval_tier(499999), "CPO")

    def test_tier_500k_to_1m(self):
        self.assertEqual(get_approval_tier(500000), "CPO+CFO")
        self.assertEqual(get_approval_tier(999999), "CPO+CFO")

    def test_tier_1m_and_above(self):
        self.assertEqual(get_approval_tier(1000000), "CPO+CEO")
        self.assertEqual(get_approval_tier(5000000), "CPO+CEO")

    def test_tier_zero(self):
        self.assertEqual(get_approval_tier(0), "CPO")

    def test_tier_status_mapping(self):
        self.assertEqual(get_tier_status("CPO"), "Pending CPO")
        self.assertEqual(get_tier_status("CFO"), "Pending CFO")
        self.assertEqual(get_tier_status("CEO"), "Pending CEO")
        self.assertEqual(get_tier_status("CPO+CFO"), "Pending CPO")
        self.assertEqual(get_tier_status("CPO+CEO"), "Pending CPO")


if __name__ == "__main__":
    unittest.main()
