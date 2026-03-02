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

    def _throw(msg, *args, **kwargs):
        raise RuntimeError(msg)

    frappe.throw = _throw
    frappe._ = lambda msg: msg

    utils = types.ModuleType("frappe.utils")
    utils.nowdate = lambda: "2026-03-02"
    utils.add_days = lambda _d, _n: "2026-03-03"
    utils.now_datetime = lambda: datetime(2026, 3, 2, 9, 0, 0)
    utils.flt = _flt
    utils.cint = _cint
    utils.getdate = _getdate
    utils.today = lambda: "2026-03-02"
    utils.now = lambda: "2026-03-02 09:00:00"
    utils.get_time = lambda _v=None: None

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


def test_orderable_items_contract_includes_recommendation_fields():
    store_mod = _load_store_module()

    contract = store_mod._build_recommendation_contract(
        last_order_qty=12,
        available_to_promise=5,
        lane="Frozen",
        order_count=9,
        signal_multiplier=1.1,
    )

    assert "recommended_qty" in contract
    assert "suggested_qty" in contract
    assert "available_to_promise" in contract
    assert "coverage_window_days" in contract
    assert "projected_sales" in contract
    assert "bom_consumption" in contract
    assert contract["suggested_qty"] == contract["recommended_qty"]
    assert contract["lane"] in {"Frozen", "Dry", "Fresh Market"}


def test_delivery_lane_resolution_defaults_to_dry():
    store_mod = _load_store_module()

    assert store_mod._resolve_delivery_lane({"item_group": "Frozen Meat"}) == "Frozen"
    assert store_mod._resolve_delivery_lane({"item_group": "Staples"}) == "Dry"
    assert (
        store_mod._resolve_delivery_lane({"item_name": "FROZEN ICE MILK (GRIFFITH POWDER)"})
        == "Frozen"
    )
    assert store_mod._resolve_delivery_lane({"item_name": "ALUMINUM PIZZA SPICE"}) == "Dry"
    assert store_mod._resolve_delivery_lane({"cargo_category": "FM"}) == "Fresh Market"
    assert (
        store_mod._resolve_delivery_lane(
            {"item_name": "FROZEN ICE MILK", "cargo_category": "DRY"}
        )
        == "Frozen"
    )
    assert (
        store_mod._resolve_delivery_lane(
            {"item_name": "FRESH LETTUCE", "cargo_category": "DRY"}
        )
        == "Fresh Market"
    )
