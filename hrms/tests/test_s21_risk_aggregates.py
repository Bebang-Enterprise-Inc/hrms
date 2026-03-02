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


class TestS21RiskAggregates(unittest.TestCase):
    def test_risk_row_has_supply_pipeline_metrics(self):
        inventory_risk.set_test_risk_rows(
            [
                {
                    "item_code": "test-item-001",
                    "warehouse": "test-warehouse-main",
                    "available_qty": 8,
                    "avg_daily_demand": 10,
                    "lead_time_days": 3,
                    "supplier_reliability_score": 75,
                    "pending_po_count": 2,
                    "inbound_po_qty": 5,
                    "delayed_po_count": 1,
                    "in_transit_qty": 4,
                    "next_eta": "2026-03-04 09:00:00",
                }
            ]
        )

        row = inventory_risk.get_risk_items(limit=1, horizon_hours=72)["items"][0]
        self.assertIn("inbound_qty", row)
        self.assertIn("delayed_po_count", row)
        self.assertIn("next_eta", row)
        self.assertEqual(row["pending_po_count"], 2)

    def test_dashboard_summary_contains_pipeline_totals(self):
        inventory_risk.set_test_risk_rows(
            [
                {
                    "item_code": "test-item-002",
                    "warehouse": "test-warehouse-main",
                    "available_qty": 12,
                    "avg_daily_demand": 7,
                    "pending_po_count": 1,
                    "inbound_po_qty": 3,
                    "delayed_po_count": 1,
                    "in_transit_qty": 2,
                }
            ]
        )

        summary = inventory_risk.get_risk_dashboard(horizon_hours=72)["summary"]
        self.assertIn("total_inbound_qty", summary)
        self.assertIn("total_delayed_pos", summary)


if __name__ == "__main__":
    unittest.main()
