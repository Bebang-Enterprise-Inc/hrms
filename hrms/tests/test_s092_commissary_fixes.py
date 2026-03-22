"""S092 — Commissary & RBAC Bug Fixes.

Tests for FIX-6 (wastage hardening), FIX-7 (labor plan visibility),
and _run_as_system_user removal in commissary_quality.
"""

import os
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read_source(rel_path):
    with open(os.path.join(REPO_ROOT, rel_path), "r", encoding="utf-8") as f:
        return f.read()


def _extract_function(source, func_name):
    marker = f"def {func_name}("
    idx = source.find(marker)
    if idx == -1:
        return None
    end_idx = source.find("\ndef ", idx + 1)
    return source[idx : end_idx if end_idx != -1 else len(source)]


class TestWastageHardening(unittest.TestCase):
    """FIX-6: Wastage logging error handling and permissions."""

    def test_wastage_has_permission_check(self):
        source = _read_source("hrms/api/commissary_quality.py")
        func = _extract_function(source, "log_wastage")
        self.assertIsNotNone(func)
        self.assertIn("check_scm_permission", func)

    def test_wastage_seven_reason_codes(self):
        source = _read_source("hrms/api/commissary_quality.py")
        for code in ["expired", "damaged", "quality_fail", "contaminated",
                      "production_loss", "sampling", "other"]:
            self.assertIn(f'"{code}"', source, f"Missing reason code: {code}")

    def test_wastage_structured_error_on_failure(self):
        """Final stock entry failure should return structured error, not raise."""
        source = _read_source("hrms/api/commissary_quality.py")
        func = _extract_function(source, "log_wastage")
        self.assertIsNotNone(func)
        self.assertIn('"success": False', func)
        self.assertIn("Stock entry failed", func)

    def test_wastage_no_run_as_system_user(self):
        source = _read_source("hrms/api/commissary_quality.py")
        func = _extract_function(source, "log_wastage")
        self.assertIsNotNone(func)
        self.assertNotIn("_run_as_system_user", func)

    def test_wastage_logs_warehouse_resolution(self):
        source = _read_source("hrms/api/commissary_quality.py")
        func = _extract_function(source, "log_wastage")
        self.assertIsNotNone(func)
        self.assertIn("Wastage warehouse resolved to", func)


class TestLaborPlanVisibility(unittest.TestCase):
    """FIX-7: Commissary Supervisor should have labor plan access."""

    def test_commissary_supervisor_in_store_schedule_roles(self):
        source = _read_source("hrms/api/supervisor.py")
        func = _extract_function(source, "_user_can_manage_store_schedule")
        self.assertIsNotNone(func)
        self.assertIn("Commissary Supervisor", func)

    def test_commissary_supervisor_in_commissary_schedule_roles(self):
        source = _read_source("hrms/api/supervisor.py")
        func = _extract_function(source, "_user_can_manage_commissary_schedule")
        self.assertIsNotNone(func)
        self.assertIn("Commissary Supervisor", func)


if __name__ == "__main__":
    unittest.main()
