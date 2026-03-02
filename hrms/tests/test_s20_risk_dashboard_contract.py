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


class TestS20RiskDashboardContract(unittest.TestCase):
    def test_dashboard_contract_shape(self):
        inventory_risk.set_test_risk_rows(
            [
                {
                    "item_code": "RM-MILK",
                    "warehouse": "W1",
                    "available_qty": 24,
                    "avg_daily_demand": 12,
                    "lead_time_days": 4,
                    "supplier_reliability_score": 65,
                },
                {
                    "item_code": "RM-SUGAR",
                    "warehouse": "W1",
                    "available_qty": 200,
                    "avg_daily_demand": 10,
                    "lead_time_days": 1,
                    "supplier_reliability_score": 95,
                },
            ]
        )
        inventory_risk.set_test_incidents([
            {"name": "INC-001", "status": "Open"},
            {"name": "INC-002", "status": "Resolved"},
        ])

        result = inventory_risk.get_risk_dashboard(horizon_hours=72)

        self.assertIn("summary", result)
        self.assertIn("top_risks", result)
        self.assertIn("stockouts_next_72h", result["summary"])
        self.assertEqual(result["summary"]["open_incidents"], 1)

    def test_risk_items_contract_returns_sorted_rows(self):
        inventory_risk.set_test_risk_rows(
            [
                {
                    "item_code": "A",
                    "warehouse": "W1",
                    "available_qty": 10,
                    "avg_daily_demand": 10,
                    "lead_time_days": 4,
                    "supplier_reliability_score": 60,
                },
                {
                    "item_code": "B",
                    "warehouse": "W1",
                    "available_qty": 500,
                    "avg_daily_demand": 5,
                    "lead_time_days": 1,
                    "supplier_reliability_score": 95,
                },
            ]
        )

        payload = inventory_risk.get_risk_items(limit=10, horizon_hours=72)
        rows = payload["items"]

        self.assertGreaterEqual(rows[0]["risk_score"], rows[1]["risk_score"])
        self.assertIn("risk_level", rows[0])
        self.assertIn("projected_stockout_at", rows[0])


if __name__ == "__main__":
    unittest.main()
