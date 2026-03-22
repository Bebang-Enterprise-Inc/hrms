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


class TestS21IncidentEventAudit(unittest.TestCase):
    def test_command_actions_append_timeline_events(self):
        inventory_risk.set_test_incidents([])
        incident = inventory_risk.create_stockout_incident(
            item_code="test-item-020",
            warehouse="test-warehouse-main",
        )

        inventory_risk.assign_incident_owner(incident["name"], "test.warehouse@bebang.ph")
        inventory_risk.set_incident_sla(incident["name"], "2026-03-04 18:00:00")
        inventory_risk.escalate_stockout_incident(incident["name"], "Executive")
        inventory_risk.add_incident_mitigation_action(
            incident_name=incident["name"],
            action_owner="test.scm@bebang.ph",
            action_text="Reallocate inbound truck from nearby hub",
        )

        events = inventory_risk.get_incident_events(incident["name"])
        event_types = [row["event_type"] for row in events]
        self.assertIn("Assigned", event_types)
        self.assertIn("Updated", event_types)
        self.assertIn("Escalated", event_types)
        self.assertIn("Mitigation Added", event_types)


if __name__ == "__main__":
    unittest.main()
