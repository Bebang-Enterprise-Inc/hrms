# Copyright (c) 2026, Bebang Enterprise Inc.
# For license information, please see license.txt

import unittest
import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "utils" / "delivery_billing_policy.py"
SPEC = importlib.util.spec_from_file_location("delivery_billing_policy", MODULE_PATH)
POLICY_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY_MODULE)

DeliveryBillingPolicyError = POLICY_MODULE.DeliveryBillingPolicyError
get_pre_delivery_exception_trace = POLICY_MODULE.get_pre_delivery_exception_trace
should_auto_create_billing_on_delivery = POLICY_MODULE.should_auto_create_billing_on_delivery


class TestDeliveryBillingPolicy(unittest.TestCase):
    def test_default_auto_create_when_setting_missing(self):
        self.assertTrue(should_auto_create_billing_on_delivery(None))
        self.assertFalse(should_auto_create_billing_on_delivery(0))

    def test_pre_delivery_blocked_without_full_dual_approval(self):
        incomplete_exception = {
            "name": "BEI-EXC-0001",
            "approval_tier": "CPO+CFO",
            "status": "Pending CFO",
            "delivery_trip_reference": "TRIP-0001",
            "delivery_stop_idx": 2,
            "cpo_approved_by": "mae@bebang.ph",
            "cpo_approved_at": "2026-02-26 10:00:00",
            "cfo_approved_by": None,
            "cfo_approved_at": None,
        }

        with self.assertRaises(DeliveryBillingPolicyError):
            get_pre_delivery_exception_trace(incomplete_exception, "TRIP-0001", 2)

    def test_pre_delivery_allowed_with_dual_approval(self):
        approved_exception = {
            "name": "BEI-EXC-0002",
            "approval_tier": "CPO+CFO",
            "status": "Approved",
            "delivery_trip_reference": "TRIP-0002",
            "delivery_stop_idx": 5,
            "cpo_approved_by": "mae@bebang.ph",
            "cpo_approved_at": "2026-02-26 11:00:00",
            "cfo_approved_by": "butch@bebang.ph",
            "cfo_approved_at": "2026-02-26 12:00:00",
            "approval_audit_log": "[2026-02-26 11:00:00] CPO Approval\n[2026-02-26 12:00:00] CFO Final Approval",
        }

        trace = get_pre_delivery_exception_trace(approved_exception, "TRIP-0002", 5)
        self.assertEqual(trace["exception_name"], "BEI-EXC-0002")
        self.assertEqual(trace["cpo_approved_by"], "mae@bebang.ph")
        self.assertEqual(trace["cfo_approved_by"], "butch@bebang.ph")
        self.assertIn("CFO Final Approval", trace["approval_audit_log"])


if __name__ == "__main__":
    unittest.main()
