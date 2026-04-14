"""S193 — Supplier Status Guard unit tests.

Tests `_assert_supplier_active` policy:
- Blacklisted / Pending Verification: block all three operations
- Inactive: block purchase_order ONLY (invoice and payment_request allowed)
- Active: allow all three operations

Uses mocked frappe modules so tests run offline without a Frappe bench.
"""
from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_fake_frappe() -> None:
    """Install minimal fake frappe modules so procurement.py imports cleanly."""
    if "frappe" in sys.modules:
        return

    frappe = types.ModuleType("frappe")
    utils = types.ModuleType("frappe.utils")

    def whitelist(*_args, **_kwargs):
        def decorator(fn):
            return fn
        return decorator

    class _ValidationError(Exception):
        pass

    class _DoesNotExistError(Exception):
        pass

    class _PermissionError(Exception):
        pass

    def _throw(msg, exc=_ValidationError, **_kwargs):
        raise exc(msg)

    def _noop(*_args, **_kwargs):
        return None

    frappe.whitelist = whitelist
    frappe._ = lambda text: text
    frappe.throw = _throw
    frappe.msgprint = _noop
    frappe.log_error = _noop
    frappe.session = types.SimpleNamespace(user="Administrator")
    frappe.ValidationError = _ValidationError
    frappe.DoesNotExistError = _DoesNotExistError
    frappe.PermissionError = _PermissionError
    frappe.parse_json = lambda v: v
    frappe.get_roles = lambda user: ["System Manager"]
    frappe.get_doc = _noop
    frappe.db = types.SimpleNamespace(
        get_value=_noop, exists=_noop, sql=_noop, count=_noop,
        set_value=_noop, commit=_noop, savepoint=_noop,
        release_savepoint=_noop, rollback_to_savepoint=_noop,
    )
    frappe.enqueue = _noop
    frappe.utils = utils

    def _flt(v, _precision=None):
        try:
            return float(v or 0)
        except (TypeError, ValueError):
            return 0.0

    def _cint(v):
        try:
            return int(v or 0)
        except (TypeError, ValueError):
            return 0

    def _getdate(v=None):
        return v

    def _nowdate():
        return "2026-04-14"

    utils.flt = _flt
    utils.cint = _cint
    utils.getdate = _getdate
    utils.nowdate = _nowdate
    utils.add_days = lambda d, n: d
    utils.get_first_day = lambda d: d
    utils.get_last_day = lambda d: d
    utils.now_datetime = lambda: None

    # Stub hrms.utils.sentry
    sentry = types.ModuleType("hrms.utils.sentry")
    sentry.set_backend_observability_context = _noop

    hrms_utils = types.ModuleType("hrms.utils")
    hrms = types.ModuleType("hrms")
    bei_config = types.ModuleType("hrms.utils.bei_config")
    bei_config.get_company = lambda: "BEI"
    delivery = types.ModuleType("hrms.utils.delivery_billing_policy")
    delivery.CPO_APPROVER_EMAIL = "cpo@bebang.ph"
    delivery.CFO_APPROVER_EMAIL = "cfo@bebang.ph"
    delivery.append_approval_audit_log = _noop
    delivery.get_approver_email = _noop
    procurement_math = types.ModuleType("hrms.utils.procurement_math")
    procurement_math.calculate_goods_receipt_gross_total = _noop

    sys.modules["frappe"] = frappe
    sys.modules["frappe.utils"] = utils
    sys.modules["hrms"] = hrms
    sys.modules["hrms.utils"] = hrms_utils
    sys.modules["hrms.utils.sentry"] = sentry
    sys.modules["hrms.utils.bei_config"] = bei_config
    sys.modules["hrms.utils.delivery_billing_policy"] = delivery
    sys.modules["hrms.utils.procurement_math"] = procurement_math


def _load_procurement_module():
    _install_fake_frappe()
    spec = importlib.util.spec_from_file_location(
        "procurement_under_test",
        ROOT / "hrms" / "api" / "procurement.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SupplierStatusGuardTests(unittest.TestCase):
    """Verify _assert_supplier_active enforces supplier master status policy."""

    @classmethod
    def setUpClass(cls):
        cls.procurement = _load_procurement_module()
        cls.frappe = sys.modules["frappe"]

    def _patch_status(self, status: str, display_name: str = "Test Supplier"):
        """Return a patch context for frappe.db.get_value returning the given status."""
        def fake_get_value(doctype, name, field, *args, **kwargs):
            if doctype != "BEI Supplier":
                return None
            if field == "status":
                return status
            if field == "supplier_name":
                return display_name
            return None
        return patch.object(self.frappe.db, "get_value", side_effect=fake_get_value)

    # --- Test 1: Blacklisted blocks all three operations ---
    def test_assert_supplier_active_blacklisted(self):
        with self._patch_status("Blacklisted"):
            for op in ("purchase_order", "invoice", "payment_request"):
                with self.assertRaises(self.frappe.ValidationError) as ctx:
                    self.procurement._assert_supplier_active("SUP-001", op)
                self.assertIn("Blacklisted", str(ctx.exception))

    # --- Test 2: Pending Verification blocks all three operations ---
    def test_assert_supplier_active_pending_verification(self):
        with self._patch_status("Pending Verification"):
            for op in ("purchase_order", "invoice", "payment_request"):
                with self.assertRaises(self.frappe.ValidationError) as ctx:
                    self.procurement._assert_supplier_active("SUP-002", op)
                self.assertIn("Pending Verification", str(ctx.exception))

    # --- Test 3: Inactive blocks PO ONLY (invoice + payment_request allowed) ---
    def test_assert_supplier_active_inactive_po_only(self):
        with self._patch_status("Inactive"):
            # purchase_order must raise
            with self.assertRaises(self.frappe.ValidationError) as ctx:
                self.procurement._assert_supplier_active("SUP-003", "purchase_order")
            self.assertIn("Inactive", str(ctx.exception))
            # invoice and payment_request must return None (allow in-flight work)
            self.assertIsNone(self.procurement._assert_supplier_active("SUP-003", "invoice"))
            self.assertIsNone(self.procurement._assert_supplier_active("SUP-003", "payment_request"))

    # --- Test 4: Active allows all three operations ---
    def test_assert_supplier_active_active_allowed(self):
        with self._patch_status("Active"):
            for op in ("purchase_order", "invoice", "payment_request"):
                self.assertIsNone(self.procurement._assert_supplier_active("SUP-004", op))

    # --- Test 5: Missing supplier (no status row) is a no-op (caller handles) ---
    def test_assert_supplier_active_missing_supplier_is_noop(self):
        with self._patch_status(None):
            for op in ("purchase_order", "invoice", "payment_request"):
                self.assertIsNone(self.procurement._assert_supplier_active("SUP-NOEXIST", op))


if __name__ == "__main__":
    unittest.main()
