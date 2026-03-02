import importlib.util
import pathlib
import sys
import types
from datetime import datetime


def _install_common_stubs():
    frappe = types.ModuleType("frappe")

    def _whitelist(fn=None, **kwargs):
        if fn is None:
            return lambda inner: inner
        return fn

    frappe.whitelist = _whitelist
    frappe.throw = lambda msg, *args, **kwargs: (_ for _ in ()).throw(RuntimeError(msg))
    frappe._ = lambda msg: msg
    frappe.log_error = lambda *args, **kwargs: None

    utils = types.ModuleType("frappe.utils")
    utils.nowdate = lambda: "2026-03-02"
    utils.flt = lambda value, precision=None: round(float(value or 0), precision) if precision is not None else float(value or 0)
    utils.add_days = lambda _d, _n: "2026-03-03"
    utils.now_datetime = lambda: datetime(2026, 3, 2, 9, 0, 0)

    sys.modules["frappe"] = frappe
    sys.modules["frappe.utils"] = utils

    hrms_pkg = types.ModuleType("hrms")
    hrms_pkg.__path__ = []
    utils_pkg = types.ModuleType("hrms.utils")
    utils_pkg.__path__ = []
    bei_config = types.ModuleType("hrms.utils.bei_config")
    bei_config.get_company = lambda: "Bebang Enterprise Inc."
    scm_roles = types.ModuleType("hrms.utils.scm_roles")
    scm_roles.SCM_INVENTORY_ROLES = []
    scm_roles.SCM_STOCK_UPDATE_ROLES = []
    scm_roles.check_scm_permission = lambda *args, **kwargs: None

    sys.modules["hrms"] = hrms_pkg
    sys.modules["hrms.utils"] = utils_pkg
    sys.modules["hrms.utils.bei_config"] = bei_config
    sys.modules["hrms.utils.scm_roles"] = scm_roles


def _load_inventory_module():
    _install_common_stubs()
    file_path = pathlib.Path(__file__).resolve().parents[1] / "api" / "inventory.py"
    spec = importlib.util.spec_from_file_location("s19_inventory_under_test", file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_adaptive_tuning_clamps_upper_bound():
    inventory_mod = _load_inventory_module()
    assert inventory_mod.apply_adaptive_tuning(1.45, 0.20) == 1.5


def test_adaptive_tuning_clamps_lower_bound():
    inventory_mod = _load_inventory_module()
    assert inventory_mod.apply_adaptive_tuning(0.75, -0.20) == 0.7


def test_preview_multiplier_returns_before_and_after():
    inventory_mod = _load_inventory_module()
    payload = inventory_mod.preview_adaptive_multiplier(1.0, 0.05)
    assert payload["multiplier_before"] == 1.0
    assert payload["multiplier_after"] == 1.05
