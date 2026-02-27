import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


class _Row(dict):
	def __getattr__(self, item):
		return self.get(item)


def _install_fake_modules():
	if "frappe" not in sys.modules:
		frappe = types.ModuleType("frappe")
		utils = types.ModuleType("frappe.utils")

		def whitelist(*_args, **_kwargs):
			def decorator(fn):
				return fn

			return decorator

		frappe.whitelist = whitelist
		frappe._ = lambda text: text
		frappe.throw = lambda message, exc=None: (_ for _ in ()).throw(Exception(message))
		frappe.ValidationError = type("ValidationError", (Exception,), {})
		frappe.PermissionError = type("PermissionError", (Exception,), {})
		frappe.parse_json = lambda x: x
		frappe.has_permission = lambda *_args, **_kwargs: True
		local_db = types.SimpleNamespace(sql=lambda *args, **kwargs: [])
		frappe.local = types.SimpleNamespace(db=local_db)
		frappe.__dict__["db"] = frappe.local.db

		utils.flt = lambda value, precision=None: round(float(value or 0), precision or 2)
		utils.cint = lambda value: int(float(value or 0))
		utils.getdate = lambda value=None: value
		utils.nowdate = lambda: "2026-02-27"
		utils.add_days = lambda d, n: d
		utils.get_first_day = lambda d: d
		utils.get_last_day = lambda d: d

		sys.modules["frappe"] = frappe
		sys.modules["frappe.utils"] = utils

	if "hrms" not in sys.modules:
		hrms_mod = types.ModuleType("hrms")
		hrms_mod.__path__ = []
		sys.modules["hrms"] = hrms_mod

	if "hrms.utils" not in sys.modules:
		hrms_utils_mod = types.ModuleType("hrms.utils")
		hrms_utils_mod.__path__ = []
		sys.modules["hrms.utils"] = hrms_utils_mod

	if "hrms.utils.bei_config" not in sys.modules:
		bei_config_mod = types.ModuleType("hrms.utils.bei_config")
		bei_config_mod.get_company = lambda: "BEI"
		sys.modules["hrms.utils.bei_config"] = bei_config_mod

	if "hrms.utils.delivery_billing_policy" not in sys.modules:
		policy_mod = types.ModuleType("hrms.utils.delivery_billing_policy")
		policy_mod.CPO_APPROVER_EMAIL = "mae@bebang.ph"
		policy_mod.CFO_APPROVER_EMAIL = "butch@bebang.ph"
		policy_mod.append_approval_audit_log = lambda existing, actor, action: existing
		sys.modules["hrms.utils.delivery_billing_policy"] = policy_mod


_install_fake_modules()
spec = importlib.util.spec_from_file_location(
	"procurement_under_test",
	ROOT / "hrms" / "api" / "procurement.py",
)
procurement = importlib.util.module_from_spec(spec)
spec.loader.exec_module(procurement)


class TestProcurementSingleSource(unittest.TestCase):
	def test_returns_supplier_summary_and_totals(self):
		rows = [
			_Row(
				item_code="ITM-001",
				item_name="Item One",
				supplier="SUP-001",
				supplier_name="Supplier A",
				total_value=1000,
				po_count=2,
				item_total_value=1200,
				concentration_pct=83.3,
			),
			_Row(
				item_code="ITM-002",
				item_name="Item Two",
				supplier="SUP-001",
				supplier_name="Supplier A",
				total_value=800,
				po_count=1,
				item_total_value=800,
				concentration_pct=100.0,
			),
			_Row(
				item_code="ITM-003",
				item_name="Item Three",
				supplier="SUP-002",
				supplier_name="Supplier B",
				total_value=500,
				po_count=1,
				item_total_value=600,
				concentration_pct=83.3,
			),
		]
		procurement.frappe.db.sql = MagicMock(return_value=rows)

		result = procurement.get_single_source_suppliers()

		self.assertEqual(len(result["data"]), 3)
		self.assertEqual(result["summary"]["total_single_source_items"], 3)
		self.assertEqual(result["summary"]["suppliers_with_concentration"], 2)
		self.assertEqual(result["summary"]["total_at_risk_value"], 2300.0)
		self.assertEqual(result["supplier_summary"][0]["supplier"], "SUP-001")
		self.assertEqual(result["supplier_summary"][0]["single_source_items"], 2)

	def test_handles_empty_dataset(self):
		procurement.frappe.db.sql = MagicMock(return_value=[])

		result = procurement.get_single_source_suppliers()

		self.assertEqual(result["data"], [])
		self.assertEqual(result["supplier_summary"], [])
		self.assertEqual(
			result["summary"],
			{
				"total_single_source_items": 0,
				"total_at_risk_value": 0.0,
				"suppliers_with_concentration": 0,
			},
		)


if __name__ == "__main__":
	unittest.main()
