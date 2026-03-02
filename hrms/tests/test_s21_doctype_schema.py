import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCTYPE_ROOT = ROOT / "hrms" / "hr" / "doctype"


def get_doctype_fields(doctype_dir: str) -> dict[str, dict]:
    path = DOCTYPE_ROOT / doctype_dir / f"{doctype_dir}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {row["fieldname"]: row for row in payload.get("fields", [])}


class TestS21DoctypeSchema(unittest.TestCase):
    def test_stockout_incident_has_command_fields(self):
        fields = get_doctype_fields("bei_stockout_incident")
        self.assertIn("target_resolution_at", fields)
        self.assertIn("root_cause", fields)
        self.assertIn("escalation_level", fields)
        self.assertIn("mitigation_plan", fields)

    def test_risk_snapshot_has_pipeline_metrics(self):
        fields = get_doctype_fields("bei_inventory_risk_snapshot")
        self.assertIn("available_qty", fields)
        self.assertIn("avg_daily_demand", fields)
        self.assertIn("inbound_qty", fields)
        self.assertIn("delayed_po_count", fields)
        self.assertIn("next_eta", fields)

    def test_incident_event_supports_escalation_timeline(self):
        fields = get_doctype_fields("bei_stockout_incident_event")
        options = fields["event_type"]["options"]
        self.assertIn("Escalated", options)
        self.assertIn("Mitigation Added", options)


if __name__ == "__main__":
    unittest.main()
