import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]


def _install_fake_dependencies():
	frappe = sys.modules.get("frappe") or types.ModuleType("frappe")
	utils = sys.modules.get("frappe.utils") or types.ModuleType("frappe.utils")

	def whitelist(*args, **kwargs):
		def decorator(fn):
			return fn

		return decorator

	frappe.whitelist = getattr(frappe, "whitelist", whitelist)
	frappe._ = getattr(frappe, "_", lambda text: text)
	frappe.throw = getattr(
		frappe, "throw", lambda message, exc=None: (_ for _ in ()).throw(Exception(message))
	)
	frappe.__dict__.setdefault("local", types.SimpleNamespace())
	if not getattr(frappe.local, "db", None):
		frappe.local.db = types.SimpleNamespace(
			get_value=lambda *args, **kwargs: None,
			exists=lambda *args, **kwargs: False,
			table_exists=lambda *args, **kwargs: False,
			sql=lambda *args, **kwargs: [],
			has_column=lambda *args, **kwargs: False,
		)
	if not getattr(frappe.local, "session", None):
		frappe.local.session = types.SimpleNamespace(user="commissary.team@bebang.ph")
	frappe.db = frappe.local.db
	frappe.session = frappe.local.session
	frappe.get_doc = getattr(frappe, "get_doc", lambda *args, **kwargs: None)
	frappe.delete_doc = getattr(frappe, "delete_doc", lambda *args, **kwargs: None)
	frappe.get_all = getattr(frappe, "get_all", lambda *args, **kwargs: [])
	frappe.get_roles = getattr(frappe, "get_roles", lambda *args, **kwargs: [])

	utils.add_days = getattr(utils, "add_days", lambda value, days: value)
	utils.cint = getattr(utils, "cint", lambda value: int(float(value or 0)))
	utils.flt = getattr(utils, "flt", lambda value: float(value or 0))
	utils.get_datetime = getattr(utils, "get_datetime", lambda value=None: value)
	utils.getdate = getattr(utils, "getdate", lambda value=None: value)
	utils.now_datetime = getattr(utils, "now_datetime", lambda: "2026-03-20 12:00:00")
	utils.nowdate = getattr(utils, "nowdate", lambda: "2026-03-20")

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils

	if "hrms" not in sys.modules:
		hrms_pkg = types.ModuleType("hrms")
		hrms_pkg.__path__ = []
		sys.modules["hrms"] = hrms_pkg

	if "hrms.api" not in sys.modules:
		hrms_api_pkg = types.ModuleType("hrms.api")
		hrms_api_pkg.__path__ = [str(ROOT / "hrms" / "api")]
		sys.modules["hrms.api"] = hrms_api_pkg

	if "hrms.utils" not in sys.modules:
		hrms_utils_pkg = types.ModuleType("hrms.utils")
		hrms_utils_pkg.__path__ = [str(ROOT / "hrms" / "utils")]
		sys.modules["hrms.utils"] = hrms_utils_pkg

	bei_config = types.ModuleType("hrms.utils.bei_config")
	bei_config.SPACE_OPS = "ops"
	bei_config.get_chat_space = lambda *args, **kwargs: "space"
	bei_config.get_company = lambda *args, **kwargs: "Bebang Enterprise Inc."
	sys.modules["hrms.utils.bei_config"] = bei_config

	scm_roles = types.ModuleType("hrms.utils.scm_roles")
	scm_roles.SCM_APPROVAL_ROLES = set()
	scm_roles.check_scm_permission = lambda *args, **kwargs: True
	sys.modules["hrms.utils.scm_roles"] = scm_roles

	contracts = types.ModuleType("hrms.utils.supply_chain_contracts")
	contracts.FINANCE_TREATMENT_INTERCOMPANY = "intercompany"
	contracts.FINANCE_TREATMENT_SAME_COMPANY = "same_company"
	contracts.REQUEST_SOURCE_STORE_DISPOSAL = "store_disposal"
	contracts.REQUEST_SOURCE_STORE_ORDER = "store_order"
	contracts.REQUEST_SOURCE_STORE_RETURN = "store_return"
	contracts.get_preferred_commissary_warehouses = lambda include_legacy=True: ("Shaw BLVD - BKI",)
	contracts.infer_finance_treatment = lambda *args, **kwargs: "same_company"
	contracts.resolve_material_request_contract = lambda *args, **kwargs: {}
	contracts.resolve_route_source_warehouse = lambda *args, **kwargs: None
	contracts.resolve_store_buyer_entity = lambda *args, **kwargs: {}
	contracts.resolve_warehouse_company = lambda *args, **kwargs: "Bebang Kitchen Inc."
	contracts.stamp_material_request_contract = lambda *args, **kwargs: None
	contracts.stamp_stock_entry_contract = lambda *args, **kwargs: None
	sys.modules["hrms.utils.supply_chain_contracts"] = contracts


_install_fake_dependencies()
spec = importlib.util.spec_from_file_location("store_under_test_s084", ROOT / "hrms" / "api" / "store.py")
store = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(store)


class TestS084CommissaryUserStoreResolution(unittest.TestCase):
	def setUp(self):
		store.frappe.session.user = "commissary.team@bebang.ph"
		store.frappe.get_roles = MagicMock(return_value=["Warehouse User"])
		store.frappe.db.get_value = MagicMock(return_value=None)
		store.frappe.get_all = MagicMock(return_value=[])

	def test_get_user_store_commissary_schedule_falls_back_to_commissary_location_for_warehouse_user(self):
		with patch.object(
			store,
			"_get_commissary_schedule_locations",
			return_value=[{"name": "Shaw BLVD - BKI", "warehouse_name": "Shaw BLVD"}],
		):
			result = store.get_user_store(surface="commissary_schedule")

		self.assertEqual(result["role"], "Warehouse User")
		self.assertEqual(result["default_store"], "Shaw BLVD - BKI")
		self.assertEqual(result["stores"], [{"name": "Shaw BLVD - BKI", "warehouse_name": "Shaw BLVD"}])


if __name__ == "__main__":
	unittest.main()
