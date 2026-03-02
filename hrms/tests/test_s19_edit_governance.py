import importlib.util
import pathlib
import sys
import types
from datetime import date, datetime


def _install_common_stubs():
    frappe = types.ModuleType("frappe")

    class _DB:
        @staticmethod
        def exists(*args, **kwargs):
            return False

        @staticmethod
        def get_value(*args, **kwargs):
            return None

        @staticmethod
        def sql(*args, **kwargs):
            return []

        @staticmethod
        def get_single_value(*args, **kwargs):
            return None

    def _flt(value, precision=None):
        num = float(value or 0)
        return round(num, precision) if precision is not None else num

    def _cint(value):
        return int(value or 0)

    def _getdate(value=None):
        if value is None or value == "":
            return date(2026, 3, 2)
        if isinstance(value, date):
            return value
        return datetime.strptime(str(value), "%Y-%m-%d").date()

    frappe.db = _DB()
    frappe.session = types.SimpleNamespace(user="test.user@bebang.ph")
    frappe.PermissionError = RuntimeError
    frappe.log_error = lambda *args, **kwargs: None
    frappe.get_roles = lambda *args, **kwargs: []
    frappe.get_all = lambda *args, **kwargs: []
    frappe.parse_json = lambda payload: payload

    def _whitelist(fn=None, **kwargs):
        if fn is None:
            return lambda inner: inner
        return fn

    frappe.whitelist = _whitelist
    frappe.throw = lambda msg, *args, **kwargs: (_ for _ in ()).throw(RuntimeError(msg))
    frappe._ = lambda msg: msg

    utils = types.ModuleType("frappe.utils")
    utils.nowdate = lambda: "2026-03-02"
    utils.add_days = lambda _d, _n: "2026-03-03"
    utils.now_datetime = lambda: datetime(2026, 3, 2, 9, 0, 0)
    utils.flt = _flt
    utils.cint = _cint
    utils.getdate = _getdate

    sys.modules["frappe"] = frappe
    sys.modules["frappe.utils"] = utils

    hrms_pkg = types.ModuleType("hrms")
    hrms_pkg.__path__ = []
    utils_pkg = types.ModuleType("hrms.utils")
    utils_pkg.__path__ = []
    bei_config = types.ModuleType("hrms.utils.bei_config")
    bei_config.get_company = lambda: "Bebang Enterprise Inc."

    scm_roles = types.ModuleType("hrms.utils.scm_roles")
    scm_roles.SCM_APPROVAL_ROLES = []
    scm_roles.check_scm_permission = lambda *args, **kwargs: None

    sys.modules["hrms"] = hrms_pkg
    sys.modules["hrms.utils"] = utils_pkg
    sys.modules["hrms.utils.bei_config"] = bei_config
    sys.modules["hrms.utils.scm_roles"] = scm_roles


def _load_store_module():
    _install_common_stubs()
    file_path = pathlib.Path(__file__).resolve().parents[1] / "api" / "store.py"
    spec = importlib.util.spec_from_file_location("s19_store_under_test", file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_edited_lines_force_supervisor_review_markers():
    store_mod = _load_store_module()

    edited = store_mod._normalize_order_line(
        {
            "item_code": "ITEM-001",
            "qty_requested": 15,
            "recommended_qty": 10,
            "reason_for_edit": "higher demand",
            "lane": "Dry",
        },
        lane="Dry",
    )
    unchanged = store_mod._normalize_order_line(
        {
            "item_code": "ITEM-002",
            "qty_requested": 10,
            "recommended_qty": 10,
            "deviation_reason": "",
        },
        lane="Frozen",
    )

    assert edited["is_edited"] == 1
    assert edited["deviation_reason"] == "higher demand"
    assert unchanged["is_edited"] == 0


def test_reason_alias_normalization_accepts_reason_for_edit():
    store_mod = _load_store_module()

    line = store_mod._normalize_order_line(
        {
            "item_code": "ITEM-003",
            "qty_requested": 7,
            "suggested_qty": 5,
            "reason_for_edit": "promo week",
        }
    )

    assert line["deviation_reason"] == "promo week"
    assert line["recommended_qty"] == 5


def test_sanitize_submitted_items_drops_zero_qty_and_missing_item_code():
    store_mod = _load_store_module()

    sanitized, dropped = store_mod._sanitize_submitted_items(
        [
            {"item_code": "ITEM-001", "qty_requested": 2},
            {"item_code": "ITEM-002", "qty_requested": 0},
            {"item_code": "", "qty_requested": 3},
            {"item_code": "ITEM-003", "qty_requested": -1},
        ]
    )

    assert len(sanitized) == 1
    assert sanitized[0]["item_code"] == "ITEM-001"
    assert sanitized[0]["qty_requested"] == 2
    dropped_reasons = {row["reason"] for row in dropped}
    assert "non_positive_qty" in dropped_reasons
    assert "missing_item_code" in dropped_reasons
