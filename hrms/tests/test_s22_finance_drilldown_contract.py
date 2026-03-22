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


class TestS22FinanceDrilldownContract(unittest.TestCase):
    def test_finance_queue_returns_supplier_filtered_rows(self):
        inventory_risk.set_test_risk_rows(
            [
                {
                    "item_code": "test-item-005",
                    "warehouse": "test-warehouse-west",
                    "available_qty": 6.05,
                    "avg_daily_demand": 11,
                    "pending_po_count": 3,
                    "inbound_po_qty": 9.35,
                    "delayed_po_count": 2,
                    "in_transit_qty": 2.2,
                    "next_eta": "2026-03-08 08:00:00",
                    "latest_cost": 28,
                    "selling_price": 45,
                }
            ]
        )

        payload = inventory_risk.get_item_finance_queue("test-item-005", "test-warehouse-west", 72)

        self.assertGreaterEqual(payload["totals"]["pending_payment_count"], 0)
        self.assertIn("pending_payments", payload)
        self.assertTrue(all("supplier" in row for row in payload["pending_payments"]))
        self.assertTrue(all(row["item_code"] == "test-item-005" for row in payload["pending_payments"]))
        self.assertTrue(all(row["warehouse"] == "test-warehouse-west" for row in payload["pending_payments"]))


if __name__ == "__main__":
    unittest.main()
