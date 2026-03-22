import datetime
import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_fake_frappe():
    if "frappe" in sys.modules:
        return

    frappe = types.ModuleType("frappe")
    utils = types.ModuleType("frappe.utils")

    def whitelist(*args, **kwargs):
        def decorator(fn):
            return fn

        return decorator

    def throw(message, exc=None):
        if isinstance(exc, type) and issubclass(exc, Exception):
            raise exc(message)
        raise Exception(message)

    def add_to_date(dt, days=0, as_string=False):
        base = dt if isinstance(dt, datetime.datetime) else datetime.datetime(2026, 3, 2, 10, 0, 0)
        shifted = base + datetime.timedelta(days=float(days or 0))
        return shifted.strftime("%Y-%m-%d %H:%M:%S") if as_string else shifted

    frappe.whitelist = whitelist
    frappe._ = lambda text: text
    frappe.throw = throw
    frappe.session = types.SimpleNamespace(user="Administrator")

    utils.flt = lambda value: float(value or 0)
    utils.cint = lambda value: int(float(value or 0))
    utils.now_datetime = lambda: datetime.datetime(2026, 3, 2, 10, 0, 0)
    utils.add_to_date = add_to_date

    sys.modules["frappe"] = frappe
    sys.modules["frappe.utils"] = utils


_install_fake_frappe()

spec = importlib.util.spec_from_file_location(
    "inventory_risk_under_test",
    ROOT / "hrms" / "api" / "inventory_risk.py",
)
inventory_risk = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(inventory_risk)


class TestS21FinanceRiskImpact(unittest.TestCase):
    def test_finance_risk_impact_contains_value_metrics(self):
        inventory_risk.set_test_risk_rows(
            [
                {
                    "item_code": "test-item-001",
                    "warehouse": "test-warehouse-main",
                    "available_qty": 2,
                    "avg_daily_demand": 8,
                    "inbound_po_qty": 1,
                    "delayed_po_count": 1,
                    "latest_cost": 35,
                    "selling_price": 72,
                }
            ]
        )

        payload = inventory_risk.get_finance_risk_impact(
            item_code="test-item-001",
            warehouse="test-warehouse-main",
        )
        self.assertGreaterEqual(payload["value_at_risk"], 0)
        self.assertIn("urgent_payment_required", payload)
        self.assertIn("margin_at_risk", payload)


if __name__ == "__main__":
    unittest.main()
