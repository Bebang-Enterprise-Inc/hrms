import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_fake_frappe():
    frappe = types.ModuleType("frappe")
    utils = types.ModuleType("frappe.utils")
    model = types.ModuleType("frappe.model")
    model_document = types.ModuleType("frappe.model.document")

    class Document:
        pass

    class ValidationError(Exception):
        pass

    class PermissionError(Exception):
        pass

    def whitelist(*args, **kwargs):
        def decorator(fn):
            return fn

        return decorator

    def _throw(message, exc=None):
        if isinstance(exc, type) and issubclass(exc, Exception):
            raise exc(message)
        raise Exception(message)

    model_document.Document = Document
    model.document = model_document

    frappe.whitelist = whitelist
    frappe._ = lambda text: text
    frappe.throw = _throw
    frappe.ValidationError = ValidationError
    frappe.PermissionError = PermissionError
    frappe.log_error = lambda *args, **kwargs: None
    frappe.msgprint = lambda *args, **kwargs: None
    frappe.get_roles = lambda user=None: ["System Manager"]
    frappe.session = types.SimpleNamespace(user="Administrator")
    frappe.defaults = types.SimpleNamespace(get_global_default=lambda key: "Bebang Enterprise Inc.")
    frappe.db = types.SimpleNamespace(
        get_value=lambda *args, **kwargs: None,
        exists=lambda *args, **kwargs: None,
        savepoint=lambda *args, **kwargs: "sp",
        rollback=lambda *args, **kwargs: None,
        release_savepoint=lambda *args, **kwargs: None,
    )
    frappe.new_doc = lambda *args, **kwargs: None
    frappe.get_doc = lambda *args, **kwargs: None
    frappe.get_all = lambda *args, **kwargs: []

    utils.flt = lambda value, precision=None: round(float(value or 0), precision) if precision is not None else float(value or 0)
    utils.nowdate = lambda: "2026-02-28"
    utils.now_datetime = lambda: "2026-02-28 08:00:00"
    utils.add_days = lambda value, days: value
    utils.cint = lambda value: int(float(value or 0))

    frappe.utils = utils

    sys.modules["frappe"] = frappe
    sys.modules["frappe.utils"] = utils
    sys.modules["frappe.model"] = model
    sys.modules["frappe.model.document"] = model_document


def _install_fake_bei_config():
    if "hrms.utils" not in sys.modules:
        sys.modules["hrms.utils"] = types.ModuleType("hrms.utils")

    fake_bei_config = types.ModuleType("hrms.utils.bei_config")
    fake_bei_config.get_company = lambda: "Bebang Enterprise Inc."
    sys.modules["hrms.utils.bei_config"] = fake_bei_config


def _load_module(module_name, relative_path):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


_install_fake_frappe()
_install_fake_bei_config()

billing_schedule = _load_module(
    "billing_schedule_tax_integrity_under_test",
    Path("hrms/hr/doctype/bei_billing_schedule/bei_billing_schedule.py"),
)
payment_request = _load_module(
    "payment_request_tax_integrity_under_test",
    Path("hrms/hr/doctype/bei_payment_request/bei_payment_request.py"),
)


class _FakeJournalEntry:
    def __init__(self):
        self.name = "ACC-JE-TAX-0001"
        self.accounts = []
        self.posting_date = None
        self.voucher_type = None
        self.company = None
        self.user_remark = None

    def append(self, table, row):
        if table == "accounts":
            self.accounts.append(dict(row))

    def insert(self, ignore_permissions=False):
        return self

    def submit(self):
        return None


class _FakeSupplierDoc:
    def __init__(self, ewt_applicable):
        self.ewt_applicable = ewt_applicable

    def get_or_create_frappe_supplier(self):
        return "SUPP-0001"


class _FakePaymentEntry:
    def __init__(self):
        self.name = "ACC-PE-TAX-0001"
        self.deductions = []
        self.paid_amount = None
        self.received_amount = None

    def append(self, table, row):
        if table == "deductions":
            self.deductions.append(dict(row))

    def insert(self, ignore_permissions=False):
        return self

    def submit(self):
        return None


class TestFinanceTaxPostingIntegrity(unittest.TestCase):
    def _build_billing_doc(self, **overrides):
        doc = billing_schedule.BEIBillingSchedule()
        doc.name = overrides.get("name", "BILL-TAX-0001")
        doc.store = overrides.get("store", "Store-1")
        doc.billing_type = overrides.get("billing_type", "Monthly")
        doc.royalty_fee = overrides.get("royalty_fee", 112.0)
        doc.management_fee = overrides.get("management_fee", 56.0)
        doc.marketing_fee = overrides.get("marketing_fee", 80.0)
        doc.ecommerce_fee = overrides.get("ecommerce_fee", 0.0)
        doc.delivery_fee = overrides.get("delivery_fee", 0.0)
        doc.logistics_fee = overrides.get("logistics_fee", 0.0)
        doc.handling_fee = overrides.get("handling_fee", 0.0)
        doc.add_comment = lambda *args, **kwargs: None
        return doc

    def _build_payment_request_doc(self, **overrides):
        doc = payment_request.BEIPaymentRequest()
        doc.name = overrides.get("name", "PAYREQ-TAX-0001")
        doc.supplier = overrides.get("supplier", "SUP-0001")
        doc.payment_amount = overrides.get("payment_amount", 1120.0)
        doc.ewt_rate = overrides.get("ewt_rate", 5)
        doc.payment_mode = overrides.get("payment_mode", "Bank Transfer")
        doc.bank_account = overrides.get("bank_account", None)
        doc.transaction_reference = overrides.get("transaction_reference", "TXN-0001")
        doc.check_number = overrides.get("check_number", None)
        doc.purchase_order = overrides.get("purchase_order", None)
        doc.payment_date = overrides.get("payment_date", "2026-02-28")
        doc.db_set_calls = []
        doc.db_set = lambda fieldname, value, update_modified=False: doc.db_set_calls.append(
            (fieldname, value, update_modified)
        )
        return doc

    def test_billing_vat_is_split_only_from_vat_inclusive_fees(self):
        account_map = {
            "4000003": "4000003 - Royalty Income - BEI",
            "4000004": "4000004 - Management Fee Income - BEI",
            "4000006": "4000006 - Marketing Income - BEI",
            "2102205": "2102205 - Output VAT Payable - BEI",
            "1103101": "1103101 - Accounts Receivable - BEI",
        }

        def _db_get_value(doctype, filters=None, fieldname=None):
            if doctype == "Account" and isinstance(filters, dict):
                return account_map.get(str(filters.get("account_number")))
            return None

        fake_je = _FakeJournalEntry()
        doc = self._build_billing_doc()

        with (
            patch.object(billing_schedule.frappe.db, "get_value", side_effect=_db_get_value),
            patch.object(billing_schedule.frappe, "new_doc", return_value=fake_je),
        ):
            doc._create_gl_entries()

        accounts = {row.get("account"): row for row in fake_je.accounts}

        self.assertAlmostEqual(accounts["4000003 - Royalty Income - BEI"]["credit_in_account_currency"], 100.0, places=2)
        self.assertAlmostEqual(accounts["4000004 - Management Fee Income - BEI"]["credit_in_account_currency"], 50.0, places=2)
        self.assertAlmostEqual(accounts["4000006 - Marketing Income - BEI"]["credit_in_account_currency"], 80.0, places=2)
        self.assertAlmostEqual(accounts["2102205 - Output VAT Payable - BEI"]["credit_in_account_currency"], 18.0, places=2)
        self.assertAlmostEqual(accounts["1103101 - Accounts Receivable - BEI"]["debit_in_account_currency"], 248.0, places=2)

        total_credit = sum((row.get("credit_in_account_currency") or 0) for row in fake_je.accounts)
        total_debit = sum((row.get("debit_in_account_currency") or 0) for row in fake_je.accounts)
        self.assertAlmostEqual(total_debit, total_credit, places=2)

    def test_advance_payment_applies_ewt_without_any_vat_row(self):
        doc = self._build_payment_request_doc(payment_amount=1120.0, ewt_rate=5)
        fake_pe = _FakePaymentEntry()

        def _get_doc(*args, **kwargs):
            if len(args) == 2 and args[0] == "BEI Supplier":
                return _FakeSupplierDoc(ewt_applicable=1)
            if len(args) == 1 and isinstance(args[0], dict) and args[0].get("doctype") == "Payment Entry":
                fake_pe.paid_amount = args[0].get("paid_amount")
                fake_pe.received_amount = args[0].get("received_amount")
                return fake_pe
            raise AssertionError(f"Unexpected get_doc call: args={args}, kwargs={kwargs}")

        def _db_get_value(doctype, filters=None, fieldname=None):
            if doctype == "BEI Supplier" and filters == doc.supplier and fieldname == "supplier_name":
                return "Supplier Name"
            return None

        with (
            patch.object(doc, "_get_payment_accounts", return_value=("1100 - Cash and Bank - BEI", "Wire Transfer")),
            patch.object(payment_request.frappe, "get_doc", side_effect=_get_doc),
            patch.object(payment_request.frappe.db, "get_value", side_effect=_db_get_value),
        ):
            pe_name = doc._create_advance_payment_entry()

        self.assertEqual(pe_name, "ACC-PE-TAX-0001")
        self.assertEqual(len(fake_pe.deductions), 1)
        self.assertEqual(fake_pe.deductions[0]["account"], "2102202 - EWT PAYABLE - BEI")
        self.assertAlmostEqual(fake_pe.deductions[0]["amount"], 56.0, places=2)
        self.assertNotIn("2102205 - Output VAT Payable - BEI", [row["account"] for row in fake_pe.deductions])
        self.assertAlmostEqual(fake_pe.paid_amount, 1064.0, places=2)
        self.assertAlmostEqual(fake_pe.received_amount, 1120.0, places=2)
        self.assertAlmostEqual(doc.ewt_amount, 56.0, places=2)
        self.assertIn(("frappe_payment_entry", "ACC-PE-TAX-0001", False), doc.db_set_calls)

    def test_advance_payment_without_supplier_ewt_keeps_full_bank_credit(self):
        doc = self._build_payment_request_doc(payment_amount=560.0, ewt_rate=5)
        fake_pe = _FakePaymentEntry()

        def _get_doc(*args, **kwargs):
            if len(args) == 2 and args[0] == "BEI Supplier":
                return _FakeSupplierDoc(ewt_applicable=0)
            if len(args) == 1 and isinstance(args[0], dict) and args[0].get("doctype") == "Payment Entry":
                fake_pe.paid_amount = args[0].get("paid_amount")
                fake_pe.received_amount = args[0].get("received_amount")
                return fake_pe
            raise AssertionError(f"Unexpected get_doc call: args={args}, kwargs={kwargs}")

        with (
            patch.object(doc, "_get_payment_accounts", return_value=("1100 - Cash and Bank - BEI", "Wire Transfer")),
            patch.object(payment_request.frappe, "get_doc", side_effect=_get_doc),
            patch.object(payment_request.frappe.db, "get_value", return_value="Supplier Name"),
        ):
            pe_name = doc._create_advance_payment_entry()

        self.assertEqual(pe_name, "ACC-PE-TAX-0001")
        self.assertEqual(fake_pe.deductions, [])
        self.assertAlmostEqual(fake_pe.paid_amount, 560.0, places=2)
        self.assertAlmostEqual(fake_pe.received_amount, 560.0, places=2)
        self.assertAlmostEqual(doc.ewt_amount, 0.0, places=2)


if __name__ == "__main__":
    unittest.main()
