import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


class _FakeDB:
	def __init__(self):
		self.last_inventory_warehouse = None

	def exists(self, doctype, value):
		return doctype == "Warehouse" and value == "Shaw BLVD - BKI"

	def sql(self, query, params=None, as_dict=False):
		if "COUNT(*)" in query:
			return [(1,)]

		if "FROM `tabBin` b" in query and "Finished Goods" in query:
			self.last_inventory_warehouse = params
			rows = [
				{
					"item_code": "FG002-A",
					"item_name": "BANANA CINNAMON",
					"item_group": "Finished Goods",
					"actual_qty": 3,
					"reserved_qty": 0,
					"available_qty": 3,
					"stock_uom": "BOX",
					"warehouse": "Shaw BLVD - BKI",
				}
			]
			return rows if as_dict else [tuple(row.values()) for row in rows]

		raise AssertionError(f"Unexpected SQL in test fake: {query}")

	def get_value(self, doctype, name, fieldname=None):
		if doctype == "Warehouse" and fieldname == "company" and name == "Shaw BLVD - BKI":
			return "Bebang Kitchen Inc."
		return None


class _FakeFrappe(types.ModuleType):
	@property
	def db(self):
		return self.local.db


def _install_fake_modules(db):
	frappe = _FakeFrappe("frappe")
	utils = types.ModuleType("frappe.utils")
	frappe.local = types.SimpleNamespace(db=db)
	frappe._ = lambda text: text
	frappe.throw = lambda message, exc=None, title=None: (_ for _ in ()).throw(Exception(message))
	frappe.whitelist = lambda *args, **kwargs: (lambda fn: fn)
	utils.add_days = lambda value, days: value
	utils.flt = lambda value, precision=None: float(value or 0)
	utils.today = lambda: "2026-03-12"

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils

	if "hrms" not in sys.modules:
		hrms_pkg = types.ModuleType("hrms")
		hrms_pkg.__path__ = []
		sys.modules["hrms"] = hrms_pkg

	if "hrms.api" not in sys.modules:
		hrms_api_pkg = types.ModuleType("hrms.api")
		hrms_api_pkg.__path__ = []
		sys.modules["hrms.api"] = hrms_api_pkg

	store_mod = types.ModuleType("hrms.api.store")
	store_mod._get_store_customer = lambda *args, **kwargs: None
	sys.modules["hrms.api.store"] = store_mod

	def _stub_module(name, exports):
		mod = types.ModuleType(name)
		for export in exports:
			setattr(mod, export, lambda *args, **kwargs: None)
		sys.modules[name] = mod

	_stub_module(
		"hrms.api.commissary_bom",
		["check_production_feasibility", "create_bom", "get_bom_detail", "update_bom"],
	)
	_stub_module(
		"hrms.api.commissary_dashboard",
		[
			"get_commissary_dashboard",
			"get_or_create_batch",
			"get_production_history",
			"get_production_items",
			"submit_production_output",
			"get_logistics_architecture_mode",
			"get_production_cost_per_batch",
		],
	)
	_stub_module(
		"hrms.api.commissary_quality",
		[
			"create_quality_inspection",
			"enable_batch_tracking_for_fg",
			"get_expiring_batches",
			"get_fefo_picking_list",
			"get_inspection_details",
			"get_inspection_history",
			"get_pending_inspections",
			"get_qc_form_detail",
			"get_qc_form_templates",
			"get_qc_forms",
			"get_wastage_history",
			"get_wastage_reasons",
			"get_wastage_trends",
			"log_wastage",
			"submit_qc_form",
		],
	)
	_stub_module(
		"hrms.api.commissary_requisition",
		[
			"approve_requisition",
			"complete_work_order",
			"cancel_requisition",
			"create_rm_requisition",
			"create_work_order",
			"get_my_requisitions",
			"get_production_suggestions",
			"get_production_plans",
			"get_requisition_detail",
			"get_rm_for_requisition",
			"get_rm_reorder_alerts",
			"get_work_order_detail",
			"get_work_orders",
			"start_work_order",
		],
	)

	bei_config_mod = types.ModuleType("hrms.utils.bei_config")
	bei_config_mod.get_company = lambda: "Bebang Enterprise Inc."
	sys.modules["hrms.utils.bei_config"] = bei_config_mod

	contracts_spec = importlib.util.spec_from_file_location(
		"hrms.utils.supply_chain_contracts",
		ROOT / "hrms" / "utils" / "supply_chain_contracts.py",
	)
	contracts_mod = importlib.util.module_from_spec(contracts_spec)
	contracts_spec.loader.exec_module(contracts_mod)
	sys.modules["hrms.utils.supply_chain_contracts"] = contracts_mod


def _load_module(db):
	_install_fake_modules(db)
	module_spec = importlib.util.spec_from_file_location(
		"commissary_under_test",
		ROOT / "hrms" / "api" / "commissary.py",
	)
	module = importlib.util.module_from_spec(module_spec)
	module_spec.loader.exec_module(module)
	return module


class TestS37TransferReadyInventoryContract(unittest.TestCase):
	def test_transfer_ready_inventory_uses_active_commissary_warehouse(self):
		db = _FakeDB()
		module = _load_module(db)

		result = module.get_transfer_ready_inventory()

		self.assertTrue(result["success"])
		self.assertEqual(db.last_inventory_warehouse, "Shaw BLVD - BKI")
		self.assertEqual(len(result["data"]), 1)
		self.assertEqual(result["data"][0]["item_code"], "FG002-A")
		self.assertEqual(result["data"][0]["warehouse"], "Shaw BLVD - BKI")


if __name__ == "__main__":
	unittest.main()
