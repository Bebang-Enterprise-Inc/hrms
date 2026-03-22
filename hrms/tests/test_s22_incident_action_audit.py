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


class TestS22IncidentActionAudit(unittest.TestCase):
    def test_incident_event_records_action_context(self):
        inventory_risk.set_test_incidents([])
        incident = inventory_risk.create_stockout_incident(
            item_code="test-item-005",
            warehouse="test-warehouse-west",
        )

        result = inventory_risk.add_incident_mitigation_action(
            incident_name=incident["name"],
            action_owner="test.scm@bebang.ph",
            action_text="Expedite supplier commitment",
            due_at="2026-03-03 12:00:00",
            department="SCM",
            source_page="/dashboard/scm/delayed-deliveries",
            action_id="escalate_supplier_delay",
        )

        self.assertIn("action_context", result)
        self.assertEqual(result["action_context"]["department"], "SCM")
        self.assertEqual(result["action_context"]["action_id"], "escalate_supplier_delay")

        events = inventory_risk.get_incident_events(incident["name"])
        mitigation_events = [row for row in events if row["event_type"] == "Mitigation Added"]
        self.assertEqual(len(mitigation_events), 1)
        self.assertEqual(mitigation_events[0]["action_context"]["source_page"], "/dashboard/scm/delayed-deliveries")


if __name__ == "__main__":
    unittest.main()
