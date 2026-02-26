
import sys
import unittest
from unittest.mock import MagicMock
import os
from datetime import datetime

# Full Mock Suite
frappe_mock = MagicMock()
sys.modules['frappe'] = frappe_mock
sys.modules['frappe.model'] = MagicMock()
sys.modules['frappe.model.workflow'] = MagicMock()
sys.modules['frappe.model.document'] = MagicMock()
sys.modules['frappe.utils'] = MagicMock()
sys.modules['frappe.utils.data'] = MagicMock()
sys.modules['frappe.query_builder'] = MagicMock()
sys.modules['frappe.rate_limiter'] = MagicMock()

sys.modules['erpnext'] = MagicMock()
sys.modules['erpnext.setup'] = MagicMock()
sys.modules['erpnext.setup.doctype'] = MagicMock()
sys.modules['erpnext.setup.doctype.employee'] = MagicMock()
sys.modules['erpnext.setup.doctype.employee.employee'] = MagicMock()
sys.modules['PIL'] = MagicMock()
sys.modules['boto3'] = MagicMock()

# hrms utils mock (if needed)
sys.modules['hrms.utils.google_oauth'] = MagicMock()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from hrms.utils.pos_parser import _parse_date, _safe_float, _safe_int

class TestPOSUtils(unittest.TestCase):

    def test_safe_float_accounting_format(self):
        self.assertEqual(_safe_float("1,000.50"), 1000.50)
        self.assertEqual(_safe_float("-1,000.50"), -1000.50)
        # Negative with parentheses (Accounting)
        self.assertEqual(_safe_float("(500.00)"), -500.00)
        self.assertEqual(_safe_float("(1,500.50)"), -1500.50)
        # Garbage
        self.assertEqual(_safe_float("abc"), 0.0)
        self.assertEqual(_safe_float(None), 0.0)

    def test_parse_date_variations(self):
        # Standard ISO
        self.assertEqual(_parse_date("2026-02-18"), "2026-02-18")
        # US Format
        self.assertEqual(_parse_date("02/18/2026"), "2026-02-18")
        # Written Month
        self.assertEqual(_parse_date("Feb-18-2026"), "2026-02-18")
        self.assertEqual(_parse_date("18-Feb-2026"), "2026-02-18")
        # Datetime object
        dt = datetime(2026, 2, 18, 10, 30)
        self.assertEqual(_parse_date(dt), "2026-02-18")
        # Garbage
        self.assertIsNone(_parse_date("Not a date"))

if __name__ == '__main__':
    unittest.main()
