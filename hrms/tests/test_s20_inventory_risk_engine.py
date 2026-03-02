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


class TestS20InventoryRiskEngine(unittest.TestCase):
	def test_days_to_stockout_projection_is_present(self):
		row = inventory_risk.build_risk_snapshot_row(
			{
				"item_code": "RM-MILK",
				"warehouse": "TEST-COMMISSARY - BEI",
				"available_qty": 120,
				"avg_daily_demand": 30,
				"lead_time_days": 3,
				"supplier_reliability_score": 82,
			}
		)

		self.assertIn("days_to_stockout", row)
		self.assertIn("projected_stockout_at", row)
		self.assertGreaterEqual(row["risk_score"], 0)
		self.assertLessEqual(row["risk_score"], 100)

	def test_recompute_is_deterministic_for_same_inputs(self):
		rows = [
			{
				"item_code": "RM-MILK",
				"warehouse": "W1",
				"available_qty": 120,
				"avg_daily_demand": 30,
				"lead_time_days": 3,
				"supplier_reliability_score": 80,
			},
			{
				"item_code": "RM-SUGAR",
				"warehouse": "W1",
				"available_qty": 40,
				"avg_daily_demand": 20,
				"lead_time_days": 5,
				"supplier_reliability_score": 70,
			},
		]
		inventory_risk.set_test_risk_rows(rows)

		first = inventory_risk.recompute_risk_snapshots(horizon_hours=72)
		second = inventory_risk.recompute_risk_snapshots(horizon_hours=72)

		self.assertEqual(first["recomputed"], 2)
		self.assertEqual(first["rows"], second["rows"])


if __name__ == "__main__":
	unittest.main()
