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


class TestS20StockoutIncidentWorkflow(unittest.TestCase):
    def test_incident_status_transition_writes_timeline_event(self):
        inventory_risk.set_test_incidents([])
        incident = inventory_risk.create_stockout_incident(
            item_code="RM-MILK",
            warehouse="TEST-COMMISSARY - BEI",
        )

        inventory_risk.update_stockout_incident_status(
            incident_name=incident["name"],
            new_status="Mitigating",
            note="Owner assigned",
            owner_user="ian@bebang.ph",
        )

        events = inventory_risk.get_incident_events(incident["name"])
        self.assertEqual(events[-1]["event_type"], "Assigned")

    def test_resolved_requires_resolution_notes(self):
        inventory_risk.set_test_incidents([])
        incident = inventory_risk.create_stockout_incident(
            item_code="RM-SUGAR",
            warehouse="TEST-COMMISSARY - BEI",
        )

        with self.assertRaises(Exception):
            inventory_risk.update_stockout_incident_status(
                incident_name=incident["name"],
                new_status="Resolved",
                note="",
                resolution_notes="",
            )


if __name__ == "__main__":
    unittest.main()
