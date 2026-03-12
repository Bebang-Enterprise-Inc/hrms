import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


class _FakeDB:
	def __init__(self, existing: set[str], stocked: set[str]):
		self.existing = existing
		self.stocked = stocked

	def exists(self, doctype, value):
		return doctype == "Warehouse" and value in self.existing

	def sql(self, query, warehouse_name):
		return [(1 if warehouse_name in self.stocked else 0,)]


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


class TestS37CommissaryWarehouseResolution(unittest.TestCase):
	def test_prefers_bki_warehouse_even_when_legacy_has_stock(self):
		module = _load_module(
			_FakeDB(
				existing={"Shaw BLVD - BKI", "TEST-COMMISSARY - BEI"},
				stocked={"TEST-COMMISSARY - BEI"},
			)
		)
		self.assertEqual(module.get_commissary_warehouse(), "Shaw BLVD - BKI")

	def test_falls_back_to_legacy_when_bki_missing(self):
		module = _load_module(
			_FakeDB(
				existing={"TEST-COMMISSARY - BEI"},
				stocked={"TEST-COMMISSARY - BEI"},
			)
		)
		self.assertEqual(module.get_commissary_warehouse(), "TEST-COMMISSARY - BEI")


if __name__ == "__main__":
	unittest.main()
