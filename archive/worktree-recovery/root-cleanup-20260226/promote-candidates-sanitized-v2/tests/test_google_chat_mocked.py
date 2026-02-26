
import sys
import unittest
from unittest.mock import MagicMock, patch
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

# Google Mocks
google_mock = MagicMock()
sys.modules['google'] = google_mock
sys.modules['google.oauth2'] = MagicMock()
sys.modules['google.oauth2.service_account'] = MagicMock()
sys.modules['googleapiclient'] = MagicMock()
sys.modules['googleapiclient.discovery'] = MagicMock()

# Mock dependencies
sys.modules['erpnext'] = MagicMock()
sys.modules['erpnext.setup'] = MagicMock()
sys.modules['erpnext.setup.doctype'] = MagicMock()
sys.modules['erpnext.setup.doctype.employee'] = MagicMock()
sys.modules['erpnext.setup.doctype.employee.employee'] = MagicMock()
sys.modules['PIL'] = MagicMock()
sys.modules['boto3'] = MagicMock()

# hrms utils mock
sys.modules['hrms.utils.google_oauth'] = MagicMock()

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import module under test
from hrms.api.google_chat import send_message_to_space

class TestGoogleChat(unittest.TestCase):

    def setUp(self):
        frappe_mock.reset_mock()
        sys.modules['google.oauth2.service_account'].reset_mock()
        sys.modules['googleapiclient.discovery'].reset_mock()
        
        # Mock get_app_path to return a valid-looking path
        frappe_mock.get_app_path.return_value = "/apps/hrms/hrms"

    @patch('os.path.exists')
    def test_send_message_success(self, mock_exists):
        print("\n[TEST] Google Chat Send (Success)")
        mock_exists.return_value = True # Credential file exists
        
        # Setup Google API build mock
        mock_build = sys.modules['googleapiclient.discovery'].build
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        # Setup chain: chat.spaces().messages().create().execute()
        mock_messages = MagicMock()
        mock_spaces = MagicMock()
        mock_create = MagicMock()
        mock_execute = MagicMock()
        
        mock_service.spaces.return_value = mock_spaces
        mock_spaces.messages.return_value = mock_messages
        mock_messages.create.return_value = mock_create
        mock_create.execute.return_value = {"name": "messages/123"} # Success response
        
        # Run
        result = send_message_to_space("spaces/ABC", "Hello")
        
        # Verify
        self.assertTrue(result)
        mock_create.execute.assert_called_once()
        print(" -> Message sent successfully.")

    @patch('os.path.exists')
    def test_send_message_network_error(self, mock_exists):
        print("\n[TEST] Google Chat Send (Network Error)")
        mock_exists.return_value = True
        
        # Setup Google API to raise exception
        mock_build = sys.modules['googleapiclient.discovery'].build
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        mock_service.spaces.side_effect = Exception("Connection Timeout")
        
        # Run
        result = send_message_to_space("spaces/ABC", "Hello")
        
        # Verify
        self.assertFalse(result)
        # Should call frappe.log_error (or logger.error)
        frappe_mock.log_error.assert_called()
        print(" -> Error caught and logged successfully (no crash).")

    @patch('os.path.exists')
    def test_missing_credentials(self, mock_exists):
        print("\n[TEST] Google Chat Send (Missing Credentials)")
        mock_exists.return_value = False # File missing
        
        result = send_message_to_space("spaces/ABC", "Hello")
        
        self.assertFalse(result)
        # Should log warning but not error
        frappe_mock.logger.return_value.warning.assert_called()
        print(" -> Missing credentials handled gracefully.")

if __name__ == '__main__':
    unittest.main()
