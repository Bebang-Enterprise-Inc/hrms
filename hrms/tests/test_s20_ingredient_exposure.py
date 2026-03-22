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
	frappe.local = types.SimpleNamespace(session=types.SimpleNamespace(user="Administrator"))

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


class TestS20IngredientExposure(unittest.TestCase):
	def test_build_ingredient_exposure_computes_shortage(self):
		rows = inventory_risk.build_ingredient_exposure(
			parent_item_code="FG-HALO",
			demand_qty=10,
			bom_rows=[
				{"ingredient_item_code": "RM-MILK", "qty_per_unit": 2},
				{"ingredient_item_code": "RM-SUGAR", "qty_per_unit": 1},
			],
			stock_map={"RM-MILK": 5, "RM-SUGAR": 20},
		)

		milk = next(row for row in rows if row["ingredient_item_code"] == "RM-MILK")
		self.assertEqual(milk["required_qty"], 20.0)
		self.assertEqual(milk["shortage_qty"], 15.0)
		self.assertEqual(milk["exposure_status"], "Watch")

	def test_get_item_exposure_returns_seeded_edges(self):
		inventory_risk.set_test_exposure_map(
			{
				"FG-HALO": [
					{
						"parent_item_code": "FG-HALO",
						"ingredient_item_code": "RM-MILK",
						"required_qty": 20,
						"available_qty": 5,
						"shortage_qty": 15,
						"days_cover": 0.25,
						"exposure_status": "Watch",
					}
				]
			}
		)

		payload = inventory_risk.get_item_exposure("FG-HALO")
		self.assertEqual(payload["item_code"], "FG-HALO")
		self.assertEqual(len(payload["exposure"]), 1)


if __name__ == "__main__":
	unittest.main()
