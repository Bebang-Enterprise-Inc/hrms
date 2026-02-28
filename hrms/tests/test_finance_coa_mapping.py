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
	if "frappe" in sys.modules:
		return

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
		savepoint=lambda *args, **kwargs: None,
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

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils
	sys.modules["frappe.model"] = model
	sys.modules["frappe.model.document"] = model_document


_install_fake_frappe()

if "hrms.utils" not in sys.modules:
	sys.modules["hrms.utils"] = types.ModuleType("hrms.utils")

fake_bei_config = types.ModuleType("hrms.utils.bei_config")
fake_bei_config.get_company = lambda: "Bebang Enterprise Inc."
sys.modules["hrms.utils.bei_config"] = fake_bei_config

billing_spec = importlib.util.spec_from_file_location(
	"billing_schedule_under_test",
	ROOT / "hrms" / "hr" / "doctype" / "bei_billing_schedule" / "bei_billing_schedule.py",
)
billing_schedule = importlib.util.module_from_spec(billing_spec)
assert billing_spec and billing_spec.loader
billing_spec.loader.exec_module(billing_schedule)

payment_spec = importlib.util.spec_from_file_location(
	"payment_request_under_test",
	ROOT / "hrms" / "hr" / "doctype" / "bei_payment_request" / "bei_payment_request.py",
)
payment_request = importlib.util.module_from_spec(payment_spec)
assert payment_spec and payment_spec.loader
payment_spec.loader.exec_module(payment_request)


class _FakeJournalEntry:
	def __init__(self):
		self.name = "ACC-JE-0001"
		self.accounts = []
		self.posting_date = None
		self.voucher_type = None
		self.company = None
		self.user_remark = None

	def append(self, table, row):
		if table == "accounts":
			self.accounts.append(row)

	def insert(self, ignore_permissions=False):
		return self

	def submit(self):
		return None


class TestFinanceCoaMapping(unittest.TestCase):
	def _build_billing_doc(self, **overrides):
		doc = billing_schedule.BEIBillingSchedule()
		doc.name = overrides.get("name", "BILL-0001")
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

	def test_billing_schedule_resolves_canonical_franchise_income_accounts(self):
		lookup_calls = []
		account_map = {
			"4000003": "4000003 - Royalty Income - BEI",
			"4000004": "4000004 - Management Fee Income - BEI",
			"4000006": "4000006 - Marketing Income - BEI",
			"2102205": "2102205 - Output VAT Payable - BEI",
			"1103101": "1103101 - Accounts Receivable - BEI",
		}

		def _db_get_value(doctype, filters=None, fieldname=None):
			if doctype == "Account" and isinstance(filters, dict):
				code = str(filters.get("account_number"))
				lookup_calls.append(code)
				return account_map.get(code)
			return None

		doc = self._build_billing_doc()
		fake_je = _FakeJournalEntry()

		with (
			patch.object(billing_schedule.frappe.db, "get_value", side_effect=_db_get_value),
			patch.object(billing_schedule.frappe, "new_doc", return_value=fake_je),
		):
			doc._create_gl_entries()

		for code in ("4000003", "4000004", "4000006"):
			self.assertIn(code, lookup_calls)

		posted_accounts = {row.get("account") for row in fake_je.accounts}
		self.assertIn("4000003 - Royalty Income - BEI", posted_accounts)
		self.assertIn("4000004 - Management Fee Income - BEI", posted_accounts)
		self.assertIn("4000006 - Marketing Income - BEI", posted_accounts)

	def test_billing_schedule_raises_validation_error_when_canonical_account_missing(self):
		doc = self._build_billing_doc(management_fee=0, marketing_fee=0)
		fake_je = _FakeJournalEntry()

		with (
			patch.object(billing_schedule.frappe.db, "get_value", return_value=None),
			patch.object(billing_schedule.frappe, "new_doc", return_value=fake_je),
		):
			with self.assertRaises(billing_schedule.frappe.ValidationError) as exc_info:
				doc._create_gl_entries()

		self.assertIn("4000003", str(exc_info.exception))

	def test_payment_request_account_resolution_prefers_canonical_account(self):
		account_map = {
			"4000003": "4000003 - Royalty Income - BEI",
			"4000301": "4000301 - Royalties Income - BEI",
		}

		def _db_get_value(doctype, filters=None, fieldname=None):
			if doctype == "Account" and isinstance(filters, dict):
				return account_map.get(str(filters.get("account_number")))
			return None

		with patch.object(payment_request.frappe.db, "get_value", side_effect=_db_get_value):
			account_name = payment_request._resolve_account_by_codes(("4000003", "4000301"))

		self.assertEqual(account_name, "4000003 - Royalty Income - BEI")


if __name__ == "__main__":
	unittest.main()
