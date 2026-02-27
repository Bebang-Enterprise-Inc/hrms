# Copyright (c) 2026, Frappe Technologies Pvt. Ltd.
# For license information, please see license.txt

"""Sprint 07 lifecycle checks for PCF replenishment + classifier health."""

from unittest import TestCase
from unittest.mock import patch


class TestPCFLifecycleS07(TestCase):
    @patch("hrms.api.expense.os.path.exists", return_value=False)
    @patch("hrms.api.expense.frappe.conf.get", return_value=None)
    @patch("hrms.api.expense_classifier.JOBLIB_AVAILABLE", False)
    def test_classification_runtime_health_critical_when_no_ml_and_no_openai(self, *_mocks):
        from hrms.api.expense import get_classification_runtime_health

        result = get_classification_runtime_health()
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "critical")
        self.assertFalse(result["ml_model_available"])
        self.assertFalse(result["openai_available"])

    @patch("hrms.api.pcf.frappe.db.has_column", return_value=False)
    @patch("hrms.api.pcf._get_account_by_number", return_value=None)
    @patch("hrms.api.pcf._get_replenishment_source_account", return_value=None)
    def test_replenishment_jv_skips_when_accounts_missing(self, *_mocks):
        from hrms.api.pcf import _create_replenishment_journal_entry

        class DummyBatch:
            name = "PCF-BATCH-TEST-0001"
            store = "TEST STORE - BEI"

        je_name, err = _create_replenishment_journal_entry(DummyBatch(), 1000)
        self.assertIsNone(je_name)
        self.assertIn("missing_account_mapping", err)
