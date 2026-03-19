import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_fake_frappe():
    frappe = types.ModuleType("frappe")
    sys.modules["frappe"] = frappe

    utils = types.ModuleType("frappe.utils")
    utils.flt = lambda value, precision=None: round(float(value or 0), int(precision)) if precision is not None else float(value or 0)
    utils.nowdate = lambda: "2026-03-19"
    sys.modules["frappe.utils"] = utils

    model = types.ModuleType("frappe.model")
    sys.modules["frappe.model"] = model
    document_mod = types.ModuleType("frappe.model.document")
    sys.modules["frappe.model.document"] = document_mod

    class Document:
        def add_comment(self, *_args, **_kwargs):
            return None

        def get_doc_before_save(self):
            return None

    document_mod.Document = Document

    class FakeDB:
        ACCOUNT_MAP = {
            "4000305": "4000305 - Delivery Income - BEI",
            "4000306": "4000306 - Logistics Income - BEI",
            "4000300": "4000300 - Franchise Income - BEI",
            "1103101": "1103101 - Accounts Receivable - BEI",
        }

        def get_value(self, doctype, filters, fieldname):
            if doctype != "Account" or fieldname != "name":
                return None
            return self.ACCOUNT_MAP.get(str(filters.get("account_number")))

    class FakeJournalEntry:
        def __init__(self):
            self.accounts = []
            self.posting_date = None
            self.voucher_type = None
            self.company = None
            self.user_remark = None
            self.name = "ACC-JV-TEST-0001"
            self.insert_called = False
            self.submit_called = False

        def append(self, fieldname, row):
            assert fieldname == "accounts"
            self.accounts.append(row)

        def insert(self, ignore_permissions=False):
            self.insert_called = True

        def submit(self):
            self.submit_called = True

    frappe.db = FakeDB()
    journal_entries = []

    def new_doc(doctype):
        assert doctype == "Journal Entry"
        doc = FakeJournalEntry()
        journal_entries.append(doc)
        return doc

    frappe.new_doc = new_doc
    frappe.throw = lambda message, exc=None: (_ for _ in ()).throw(Exception(message))
    frappe._ = lambda text: text
    frappe.get_roles = lambda *_args, **_kwargs: []
    frappe.session = types.SimpleNamespace(user="test.hr@bebang.ph")
    frappe.whitelist = lambda *args, **kwargs: (lambda fn: fn)
    frappe.log_error = lambda *args, **kwargs: None
    frappe.model = model
    frappe.utils = utils
    return journal_entries


def _install_stub_dependencies():
    bei_config = types.ModuleType("hrms.utils.bei_config")
    bei_config.get_company = lambda: "Bebang Enterprises Inc."
    sys.modules["hrms.utils.bei_config"] = bei_config


class TestBillingGlReferenceContract(unittest.TestCase):
    def setUp(self):
        self.journal_entries = _install_fake_frappe()
        _install_stub_dependencies()

        spec = importlib.util.spec_from_file_location(
            "bei_billing_schedule_under_test",
            ROOT / "hrms" / "hr" / "doctype" / "bei_billing_schedule" / "bei_billing_schedule.py",
        )
        self.module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(self.module)

    def test_credit_rows_do_not_write_invalid_custom_reference_type(self):
        billing = self.module.BEIBillingSchedule()
        billing.name = "BILL-MF-TEST-0001"
        billing.store = "TEST-STORE-BGC - BEI"
        billing.billing_type = "Delivery"
        billing.royalty_fee = 0
        billing.management_fee = 0
        billing.marketing_fee = 0
        billing.ecommerce_fee = 0
        billing.delivery_fee = 1500
        billing.logistics_fee = 800
        billing.repairs_maintenance = 0
        billing.preventive_maintenance = 0
        billing.goods_value = 15000
        billing.handling_fee = 1200
        billing.line_items = []

        billing._create_gl_entries()

        self.assertEqual(len(self.journal_entries), 1)
        entry = self.journal_entries[0]
        self.assertTrue(entry.insert_called)
        self.assertTrue(entry.submit_called)

        credit_rows = [row for row in entry.accounts if row.get("credit_in_account_currency")]
        self.assertGreaterEqual(len(credit_rows), 3)
        for row in credit_rows:
            self.assertNotIn("reference_type", row)
            self.assertNotIn("reference_name", row)

        debit_rows = [row for row in entry.accounts if row.get("debit_in_account_currency")]
        self.assertEqual(len(debit_rows), 1)
        self.assertEqual(debit_rows[0].get("against_voucher_type"), "BEI Billing Schedule")
        self.assertEqual(debit_rows[0].get("against_voucher"), "BILL-MF-TEST-0001")


if __name__ == "__main__":
    unittest.main()
