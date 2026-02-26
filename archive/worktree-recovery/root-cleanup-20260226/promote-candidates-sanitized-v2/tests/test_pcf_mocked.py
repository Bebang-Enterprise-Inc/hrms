
import sys
import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
import os

# Manual Mock Construction (Robust)
frappe_mock = MagicMock()
sys.modules['frappe'] = frappe_mock

# Make whitelist a passthrough decorator
def whitelist(*args, **kwargs):
    def decorator(func):
        return func
    if len(args) == 1 and callable(args[0]):
        return args[0]
    return decorator

frappe_mock.whitelist = whitelist

# Submodules
sys.modules['frappe.model'] = MagicMock()
sys.modules['frappe.model.workflow'] = MagicMock()
sys.modules['frappe.model.document'] = MagicMock()
sys.modules['frappe.utils'] = MagicMock()
sys.modules['frappe.utils.data'] = MagicMock()
sys.modules['frappe.query_builder'] = MagicMock()
sys.modules['frappe.rate_limiter'] = MagicMock()

# Mock dependencies
sys.modules['erpnext'] = MagicMock()
sys.modules['erpnext.setup'] = MagicMock()
sys.modules['erpnext.setup.doctype'] = MagicMock()
sys.modules['erpnext.setup.doctype.employee'] = MagicMock()
sys.modules['erpnext.setup.doctype.employee.employee'] = MagicMock()
sys.modules['PIL'] = MagicMock()
sys.modules['boto3'] = MagicMock()

# Mock imports that pcf.py uses
sys.modules['hrms.api.store'] = MagicMock()
sys.modules['hrms.hr.doctype.bei_petty_cash_fund.bei_petty_cash_fund'] = MagicMock()
sys.modules['hrms.api.google_chat'] = MagicMock()

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the module under test
from hrms.api.pcf import add_expense_to_pending

class TestPCF(unittest.TestCase):

    def setUp(self):
        # Reset mocks
        frappe_mock.reset_mock()
        sys.modules['hrms.api.store'].reset_mock()
        sys.modules['hrms.hr.doctype.bei_petty_cash_fund.bei_petty_cash_fund'].reset_mock()
        sys.modules['hrms.api.google_chat'].reset_mock()
        
        # Common setup
        frappe_mock.session.user = "test@example.com"
        
        # Mock get_value to return an object with dot access
        def get_value_side_effect(doctype, filters, fields=None, as_dict=False):
            if doctype == "Employee":
                return SimpleNamespace(
                    name="EMP-001",
                    employee_name="Test Employee",
                    branch="Test Store",
                    company="BEI"
                )
            if doctype == "BEI Petty Cash Fund":
                return SimpleNamespace(
                    name="PCF-001",
                    fund_amount=10000,
                    pending_total=1000,
                    threshold_percentage=50
                )
            if doctype == "Warehouse":
                return "Test Store"
            return None
            
        frappe_mock.db.get_value.side_effect = get_value_side_effect
        frappe_mock.db.exists.return_value = True # Assume stores exist
        
        # Mock save_base64_image
        sys.modules['hrms.api.store'].save_base64_image.return_value = "/files/test.jpg"

    def test_add_expense_success_no_threshold(self):
        print("\n[TEST] Add Expense (No Threshold)")
        
        # Mock PCF Doc returned by update_pcf_totals
        mock_pcf_doc = MagicMock()
        mock_pcf_doc.is_at_threshold.return_value = False
        mock_pcf_doc.fund_amount = 10000
        mock_pcf_doc.pending_total = 1000
        mock_pcf_doc.current_balance = 9000
        mock_pcf_doc.threshold_percentage = 50
        mock_pcf_doc.pending_count = 1
        
        update_pcf_totals_mock = sys.modules['hrms.hr.doctype.bei_petty_cash_fund.bei_petty_cash_fund'].update_pcf_totals
        update_pcf_totals_mock.return_value = mock_pcf_doc
        
        # Run
        result = add_expense_to_pending(
            manual_vendor="Jollibee",
            manual_description="Lunch",
            manual_amount=500,
            manual_date="2026-02-18",
            receipt_photo="base64..."
        )
        
        # Verify
        self.assertTrue(result['success'])
        self.assertFalse(result['pcf_status']['at_threshold'])
        print(" -> Success")

    @patch('hrms.api.pcf.send_threshold_notification') 
    def test_add_expense_triggers_threshold(self, mock_send_notification):
        print("\n[TEST] Add Expense (Triggers Threshold)")
        
        # Mock PCF Doc returned by update_pcf_totals
        mock_pcf_doc = MagicMock()
        mock_pcf_doc.is_at_threshold.return_value = True
        mock_pcf_doc.fund_amount = 10000
        mock_pcf_doc.pending_total = 6000
        mock_pcf_doc.current_balance = 4000
        mock_pcf_doc.threshold_percentage = 50
        mock_pcf_doc.pending_count = 5
        
        update_pcf_totals_mock = sys.modules['hrms.hr.doctype.bei_petty_cash_fund.bei_petty_cash_fund'].update_pcf_totals
        update_pcf_totals_mock.return_value = mock_pcf_doc
        
        # Run
        result = add_expense_to_pending(
            manual_vendor="Hardware",
            manual_description="Tools",
            manual_amount=5000,
            manual_date="2026-02-18",
            receipt_photo="base64..."
        )
        
        # Verify
        self.assertTrue(result['success'])
        self.assertTrue(result['pcf_status']['at_threshold'])
        
        # Verify notification was sent
        mock_send_notification.assert_called()
        print(" -> Notification triggered successfully.")

    def test_missing_photo_validation(self):
        print("\n[TEST] Missing Receipt Photo Validation")
        
        frappe_mock.throw.side_effect = Exception("Validation Error")
        
        with self.assertRaises(Exception) as cm:
            add_expense_to_pending("V", "D", 100, "2026-02-18", "")
        
        self.assertEqual(str(cm.exception), "Validation Error")
        print(" -> Validation caught missing photo.")

if __name__ == '__main__':
    unittest.main()
