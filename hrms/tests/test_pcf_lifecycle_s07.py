# Copyright (c) 2026, Frappe Technologies Pvt. Ltd.
# For license information, please see license.txt

"""Sprint 07 lifecycle checks for PCF replenishment + classifier health."""

import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_fake_runtime():
    if "frappe" not in sys.modules:
        frappe = types.ModuleType("frappe")
        utils = types.ModuleType("frappe.utils")

        def whitelist(*args, **kwargs):
            if args and callable(args[0]) and len(args) == 1 and not kwargs:
                return args[0]

            def decorator(fn):
                return fn

            return decorator

        frappe.whitelist = whitelist
        frappe._ = lambda text: text
        frappe.throw = lambda message, exc=None: (_ for _ in ()).throw(Exception(message))
        frappe.log_error = lambda *args, **kwargs: None
        frappe.get_roles = lambda *_args, **_kwargs: ["System Manager", "Accounts Manager"]
        frappe.session = types.SimpleNamespace(user="test.accounting@bebang.ph")
        frappe.conf = types.SimpleNamespace(get=lambda *_args, **_kwargs: None)
        frappe.db = types.SimpleNamespace(
            has_column=lambda *args, **kwargs: True,
            get_value=lambda *args, **kwargs: None,
            get_single_value=lambda *args, **kwargs: None,
            set_value=lambda *args, **kwargs: None,
            exists=lambda *args, **kwargs: None,
            sql=lambda *args, **kwargs: [],
            count=lambda *args, **kwargs: 0,
            commit=lambda: None,
        )
        frappe.get_all = lambda *args, **kwargs: []
        frappe.get_doc = lambda *args, **kwargs: types.SimpleNamespace(
            name="DOC-0001",
            store="TEST STORE - BEI",
            status="Approved",
            total_amount=1000,
            review_notes="",
            save=lambda **kw: None,
        )
        frappe.new_doc = lambda *args, **kwargs: types.SimpleNamespace(
            name="DOC-NEW",
            append=lambda *a, **k: None,
            insert=lambda **kw: None,
            save=lambda **kw: None,
        )
        frappe.parse_json = json.loads
        frappe.logger = lambda *args, **kwargs: types.SimpleNamespace(
            info=lambda *a, **k: None, warning=lambda *a, **k: None, error=lambda *a, **k: None
        )

        utils.flt = lambda value, precision=None: float(value or 0)
        utils.now_datetime = lambda: "2026-02-27 00:00:00"
        utils.nowdate = lambda: "2026-02-27"
        utils.today = lambda: "2026-02-27"
        utils.getdate = lambda value=None: value
        utils.get_url = lambda path="": f"https://hq.bebang.ph{path}"

        sys.modules["frappe"] = frappe
        sys.modules["frappe.utils"] = utils

    frappe = sys.modules["frappe"]
    utils = sys.modules["frappe.utils"]
    if not hasattr(frappe, "conf") or not hasattr(frappe.conf, "get"):
        frappe.conf = types.SimpleNamespace(get=lambda *_args, **_kwargs: None)
    if not hasattr(utils, "get_url"):
        utils.get_url = lambda path="": f"https://hq.bebang.ph{path}"
    if not hasattr(utils, "getdate"):
        utils.getdate = lambda value=None: value

    if "hrms" not in sys.modules:
        hrms_pkg = types.ModuleType("hrms")
        hrms_pkg.__path__ = []
        sys.modules["hrms"] = hrms_pkg

    if "hrms.api" not in sys.modules:
        api_pkg = types.ModuleType("hrms.api")
        api_pkg.__path__ = []
        sys.modules["hrms.api"] = api_pkg

    if "hrms.utils" not in sys.modules:
        utils_pkg = types.ModuleType("hrms.utils")
        utils_pkg.__path__ = []
        sys.modules["hrms.utils"] = utils_pkg

    if "hrms.utils.bei_config" not in sys.modules:
        bei_config = types.ModuleType("hrms.utils.bei_config")
        bei_config.get_company = lambda: "BEI"
        sys.modules["hrms.utils.bei_config"] = bei_config

    if "hrms.api.store" not in sys.modules:
        store_mod = types.ModuleType("hrms.api.store")
        store_mod.save_base64_image = lambda payload, *_args, **_kwargs: payload or "/files/test.png"
        sys.modules["hrms.api.store"] = store_mod

    if "hrms.api.expense_classifier" not in sys.modules:
        _load_module("hrms.api.expense_classifier", "hrms/api/expense_classifier.py")


def _load_module(module_name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_install_fake_runtime()
expense = _load_module("hrms.api.expense", "hrms/api/expense.py")
pcf = _load_module("hrms.api.pcf", "hrms/api/pcf.py")


class TestPCFLifecycleS07(unittest.TestCase):
    @patch.object(expense.os.path, "exists", return_value=False)
    @patch.object(expense.frappe.conf, "get", return_value=None)
    @patch("hrms.api.expense_classifier.JOBLIB_AVAILABLE", False)
    def test_classification_runtime_health_critical_when_no_ml_and_no_openai(self, *_mocks):
        result = expense.get_classification_runtime_health()
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "critical")
        self.assertFalse(result["ml_model_available"])
        self.assertFalse(result["openai_available"])

    @patch.object(pcf.frappe.db, "has_column", return_value=False)
    @patch.object(pcf, "_get_account_by_number", return_value=None)
    @patch.object(pcf, "_get_replenishment_source_account", return_value=None)
    def test_replenishment_jv_skips_when_accounts_missing(self, *_mocks):
        class DummyBatch:
            name = "PCF-BATCH-TEST-0001"
            store = "TEST STORE - BEI"

        je_name, err = pcf._create_replenishment_journal_entry(DummyBatch(), 1000)
        self.assertIsNone(je_name)
        self.assertIn("missing_account_mapping", err)


if __name__ == "__main__":
    unittest.main()
