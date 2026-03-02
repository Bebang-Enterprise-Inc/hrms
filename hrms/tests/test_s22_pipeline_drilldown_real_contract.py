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


class TestS22PipelineDrilldownRealContract(unittest.TestCase):
    def setUp(self):
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
        inventory_risk.set_test_pipeline_source_map(
            {
                "test-item-005::test-warehouse-west": [
                    {
                        "source_doctype": "Purchase Order",
                        "source_name": "PO-TEST-0001",
                        "po_number": "PO-TEST-0001",
                        "supplier": "test-supplier-01",
                        "item_code": "test-item-005",
                        "warehouse": "test-warehouse-west",
                        "ordered_qty": 5.0,
                        "received_qty": 0.0,
                        "expected_eta": "2026-03-08 08:00:00",
                        "status": "Delayed",
                        "delayed_days": 2,
                        "delivery_id": "DTL-TEST-0001",
                        "delay_reason": "Port congestion",
                        "link_route": "/app/purchase-order/PO-TEST-0001",
                    },
                    {
                        "source_doctype": "Purchase Order",
                        "source_name": "PO-TEST-0002",
                        "po_number": "PO-TEST-0002",
                        "supplier": "test-supplier-02",
                        "item_code": "test-item-005",
                        "warehouse": "test-warehouse-west",
                        "ordered_qty": 4.35,
                        "received_qty": 0.0,
                        "expected_eta": "2026-03-09 08:00:00",
                        "status": "Pending",
                        "link_route": "/app/purchase-order/PO-TEST-0002",
                    },
                ]
            }
        )

    def test_pending_pos_returns_source_docs_for_item_warehouse(self):
        payload = inventory_risk.get_item_pending_pos("test-item-005", "test-warehouse-west", 72)
        self.assertEqual(payload["totals"]["pending_po_count"], 2)
        self.assertEqual(payload["pending_pos"][0]["source_doctype"], "Purchase Order")
        self.assertTrue(payload["pending_pos"][0]["source_name"])
        self.assertTrue(payload["pending_pos"][0]["link_route"])

    def test_delayed_deliveries_include_traceability_contract(self):
        payload = inventory_risk.get_item_delayed_deliveries("test-item-005", "test-warehouse-west", 72)
        self.assertEqual(payload["totals"]["delayed_delivery_count"], 1)
        line = payload["delayed_deliveries"][0]
        self.assertEqual(line["delivery_id"], "DTL-TEST-0001")
        self.assertIn("po_number", line)
        self.assertIn("supplier", line)
        self.assertIn("item_code", line)
        self.assertIn("warehouse", line)
        self.assertIn("delayed_qty", line)
        self.assertIn("expected_eta", line)
        self.assertIn("delayed_days", line)
        self.assertIn("delay_reason", line)
        self.assertIn("source_doctype", line)
        self.assertIn("source_name", line)
        self.assertIn("link_route", line)


if __name__ == "__main__":
    unittest.main()
