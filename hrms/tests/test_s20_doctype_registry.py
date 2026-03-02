import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def get_registered_doctypes() -> set[str]:
	doctype_root = ROOT / "hrms" / "hr" / "doctype"
	names: set[str] = set()
	for path in doctype_root.glob("*/**/*.json"):
		if path.name != f"{path.parent.name}.json":
			continue
		payload = json.loads(path.read_text(encoding="utf-8"))
		if payload.get("doctype") == "DocType" and payload.get("name"):
			names.add(payload["name"])
	return names


class TestS20DoctypeRegistry(unittest.TestCase):
	def test_s20_risk_doctypes_are_registered(self):
		expected = {
			"BEI Inventory Risk Profile",
			"BEI Inventory Risk Snapshot",
			"BEI Ingredient Risk Exposure",
			"BEI Stockout Incident",
			"BEI Stockout Incident Event",
		}
		self.assertTrue(expected.issubset(get_registered_doctypes()))

	def test_inventory_risk_module_is_wired_in_api_registry(self):
		registry_path = ROOT / "hrms" / "api" / "__init__.py"
		registry_text = registry_path.read_text(encoding="utf-8")
		self.assertIn("import hrms.api.inventory_risk", registry_text)


if __name__ == "__main__":
	unittest.main()
