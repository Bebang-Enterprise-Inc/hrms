import datetime
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_fake_frappe():
    if "frappe" in sys.modules:
        return

    frappe = types.ModuleType("frappe")
    utils = types.ModuleType("frappe.utils")

    def whitelist(*_args, **_kwargs):
        def decorator(fn):
            return fn

        return decorator

    class PermissionError(Exception):
        pass

    def _throw(message, exc=None):
        if isinstance(exc, type) and issubclass(exc, Exception):
            raise exc(message)
        raise Exception(message)

    frappe.whitelist = whitelist
    frappe._ = lambda text: text
    frappe.throw = _throw
    frappe.PermissionError = PermissionError
    frappe.log_error = lambda *args, **kwargs: None
    frappe.logger = lambda: types.SimpleNamespace(info=lambda *args, **kwargs: None)
    frappe.get_traceback = lambda: "traceback"
    frappe.__dict__["session"] = types.SimpleNamespace(user="Administrator")
    frappe.get_roles = lambda user=None: ["System Manager"] if user and user != "Guest" else []
    frappe.__dict__["db"] = types.SimpleNamespace(
        exists=lambda *args, **kwargs: None,
        get_value=lambda *args, **kwargs: None,
        set_value=lambda *args, **kwargs: None,
        savepoint=lambda *args, **kwargs: None,
        release_savepoint=lambda *args, **kwargs: None,
        rollback=lambda *args, **kwargs: None,
    )
    frappe.get_meta = lambda *args, **kwargs: types.SimpleNamespace(has_field=lambda *_: True)

    utils.now_datetime = lambda: datetime.datetime(2026, 1, 1, 8, 0, 0)
    utils.nowdate = lambda: "2026-01-01"
    utils.flt = lambda value: float(value or 0)
    utils.cint = lambda value: int(float(value or 0))
    utils.getdate = (
        lambda value=None: datetime.date.fromisoformat(str(value)) if value else datetime.date(2026, 1, 1)
    )

    sys.modules["frappe"] = frappe
    sys.modules["frappe.utils"] = utils


_install_fake_frappe()
erp_sync_spec = importlib.util.spec_from_file_location(
    "erp_sync_runtime_under_test",
    ROOT / "hrms" / "api" / "erp_sync.py",
)
erp_sync = importlib.util.module_from_spec(erp_sync_spec)
erp_sync_spec.loader.exec_module(erp_sync)


class TestErpSyncRuntime(unittest.TestCase):
    def setUp(self):
        erp_sync._FIELD_CACHE.clear()
        erp_sync.frappe.__dict__["session"] = types.SimpleNamespace(user="Administrator")
        erp_sync.frappe.get_roles = MagicMock(return_value=["System Manager"])
        erp_sync.frappe.db.savepoint = MagicMock(return_value="sp_sync")
        erp_sync.frappe.db.release_savepoint = MagicMock()
        erp_sync.frappe.db.rollback = MagicMock()
        erp_sync.frappe.db.exists = MagicMock(return_value="SINV-0001")
        erp_sync.frappe.db.get_value = MagicMock(return_value=1)
        erp_sync.frappe.db.set_value = MagicMock()
        erp_sync.frappe.get_meta = MagicMock(return_value=types.SimpleNamespace(has_field=lambda *_: True))

    def test_allowed_roles_cover_finance_and_hr(self):
        self.assertTrue({"Accounts Manager", "Accounts User", "HR Manager"}.issubset(erp_sync.SYNC_ALLOWED_ROLES))

    def test_successful_sync_releases_savepoint(self):
        result = erp_sync.sync_ar_aging(
            sheet_name="AR Aging",
            data=[{"invoice_no": "SINV-0001", "outstanding": 1200, "due_date": "2026-01-31"}],
            checksum="runtime-1",
        )

        self.assertEqual(result["rows_failed"], 0)
        erp_sync.frappe.db.savepoint.assert_called_once()
        erp_sync.frappe.db.release_savepoint.assert_called_once()
        erp_sync.frappe.db.rollback.assert_not_called()

    def test_supplier_soa_alias_preserves_payload(self):
        rows = [{"supplier": "Acme", "invoice_no": "INV-001", "amount": 1500}]
        expected = {"rows_processed": 1, "rows_created": 1, "rows_updated": 0, "rows_failed": 0, "errors": []}

        with patch.object(erp_sync, "sync_ap_opening", return_value=expected) as sync_ap_opening:
            result = erp_sync.sync_supplier_soa("Supplier SOA", rows, "runtime-2")

        sync_ap_opening.assert_called_once_with(sheet_name="Supplier SOA", data=rows, checksum="runtime-2")
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
