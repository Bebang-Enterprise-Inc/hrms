"""S198 P3-T4: Unit tests for dispatch notification via GChat.

Tests _get_store_crew_recipients and verifies that notification failures
do not roll back the SE/WR.  Uses fake-frappe pattern.
"""

import datetime
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_fake_frappe_and_dependencies():
    """Install a minimal fake frappe so warehouse.py can be imported."""

    if "frappe" not in sys.modules:
        frappe = types.ModuleType("frappe")
        utils = types.ModuleType("frappe.utils")

        def whitelist(*args, **kwargs):
            def decorator(fn):
                return fn
            return decorator

        def _throw(message, exc=None, title=None):
            if isinstance(exc, type) and issubclass(exc, Exception):
                raise exc(message)
            raise Exception(message)

        frappe.whitelist = whitelist
        frappe._ = lambda text: text
        frappe.throw = _throw
        frappe.PermissionError = type("PermissionError", (Exception,), {})
        frappe.ValidationError = type("ValidationError", (Exception,), {})
        frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
        frappe.DuplicateEntryError = type("DuplicateEntryError", (Exception,), {})
        frappe.log_error = MagicMock()
        frappe.logger = lambda: types.SimpleNamespace(info=lambda *args, **kwargs: None)
        frappe.get_traceback = lambda: "traceback"
        frappe.enqueue = lambda *args, **kwargs: None
        frappe.parse_json = json.loads
        frappe.__dict__["session"] = types.SimpleNamespace(user="Administrator")
        frappe.__dict__["flags"] = types.SimpleNamespace()

        frappe.__dict__["db"] = types.SimpleNamespace(
            get_single_value=lambda *args, **kwargs: None,
            exists=lambda *args, **kwargs: None,
            get_value=lambda *args, **kwargs: None,
            set_value=lambda *args, **kwargs: None,
            sql=lambda *args, **kwargs: [],
            savepoint=lambda name: name,
            release_savepoint=lambda name: None,
            rollback=lambda **kwargs: None,
            commit=lambda: None,
        )
        frappe.get_doc = MagicMock(return_value=types.SimpleNamespace(
            name="DOC-0001",
            items=[],
            save=lambda **kw: None,
            reload=lambda: None,
        ))
        frappe.get_all = MagicMock(return_value=[])
        frappe.new_doc = MagicMock(return_value=types.SimpleNamespace(
            update=lambda *a, **k: None,
            insert=lambda **k: None,
            append=lambda *a, **k: None,
            name="BEI-WHR-2026-00001",
            items=[],
            flags=types.SimpleNamespace(ignore_permissions=False),
        ))

        utils.nowdate = lambda: "2026-04-16"
        utils.today = lambda: "2026-04-16"
        utils.nowtime = lambda: "10:00:00"
        utils.now_datetime = lambda: datetime.datetime(2026, 4, 16, 10, 0, 0)
        utils.flt = lambda value, precision=None: float(value or 0)
        utils.cint = lambda value: int(float(value or 0))

        sys.modules["frappe"] = frappe
        sys.modules["frappe.utils"] = utils

    exceptions = types.ModuleType("frappe.exceptions")
    exceptions.TimestampMismatchError = type("TimestampMismatchError", (Exception,), {})
    sys.modules["frappe.exceptions"] = exceptions

    if "hrms" not in sys.modules:
        hrms_pkg = types.ModuleType("hrms")
        hrms_pkg.__path__ = []
        sys.modules["hrms"] = hrms_pkg

    if "hrms.utils" not in sys.modules:
        hrms_utils_pkg = types.ModuleType("hrms.utils")
        hrms_utils_pkg.__path__ = []
        sys.modules["hrms.utils"] = hrms_utils_pkg

    if "hrms.api" not in sys.modules:
        hrms_api_pkg = types.ModuleType("hrms.api")
        hrms_api_pkg.__path__ = []
        sys.modules["hrms.api"] = hrms_api_pkg

    if "hrms.utils.scm_roles" not in sys.modules:
        scm_roles_mod = types.ModuleType("hrms.utils.scm_roles")
        scm_roles_mod.SCM_ADMIN_ROLES = ["System Manager"]
        scm_roles_mod.SCM_APPROVAL_ROLES = ["System Manager"]
        scm_roles_mod.SCM_DISPATCH_ROLES = ["System Manager"]
        scm_roles_mod.SCM_RECEIVING_ROLES = ["System Manager"]
        scm_roles_mod.SCM_ROUTE_MANAGEMENT_ROLES = ["System Manager"]
        scm_roles_mod.SCM_STORE_ROLES = ["Store User"]
        scm_roles_mod.check_scm_permission = lambda roles, action: None
        sys.modules["hrms.utils.scm_roles"] = scm_roles_mod

    if "hrms.utils.sentry" not in sys.modules:
        sentry_mod = types.ModuleType("hrms.utils.sentry")
        sentry_mod.set_backend_observability_context = lambda *args, **kwargs: None
        sys.modules["hrms.utils.sentry"] = sentry_mod

    if "hrms.utils.bei_config" not in sys.modules:
        bei_config_mod = types.ModuleType("hrms.utils.bei_config")
        bei_config_mod.get_company = lambda: "Bebang Enterprise Inc."
        bei_config_mod.SPACE_OPS = "SPACE_OPS"
        bei_config_mod.get_chat_space = lambda key: None
        sys.modules["hrms.utils.bei_config"] = bei_config_mod

    if "hrms.utils.standard_buying_bridge" not in sys.modules:
        bridge_mod = types.ModuleType("hrms.utils.standard_buying_bridge")
        bridge_mod.apply_standard_buying_context = lambda *args, **kwargs: None
        sys.modules["hrms.utils.standard_buying_bridge"] = bridge_mod

    if "hrms.utils.supply_chain_contracts" not in sys.modules:
        contracts_mod = types.ModuleType("hrms.utils.supply_chain_contracts")
        contracts_mod.CANONICAL_COMMISSARY_OPERATION_WAREHOUSE = "BKI Operations"
        contracts_mod.TEST_COMMISSARY_OPERATION_WAREHOUSE = "Test BKI Operations"
        contracts_mod.FINANCE_TREATMENT_INTERCOMPANY = "Intercompany"
        contracts_mod.FINANCE_TREATMENT_SAME_COMPANY = "Same Company"
        contracts_mod.REQUEST_SOURCE_COMMISSARY_FG_TRANSFER = "Commissary FG Transfer"
        contracts_mod.REQUEST_SOURCE_STORE_ORDER = "Store Order"
        contracts_mod.get_preferred_commissary_warehouses = lambda **kwargs: []
        contracts_mod.get_request_source_label = lambda src: src
        contracts_mod.infer_finance_treatment = lambda src, tgt: "Intercompany" if src != tgt else "Same Company"
        contracts_mod.resolve_material_request_contract = lambda mr: {
            "request_source": "Store Order",
            "cargo_lane": None,
            "source_company": "Bebang Kitchen Inc.",
            "target_company": "Bebang Enterprise Inc.",
            "finance_treatment": "Intercompany",
            "destination_warehouse": "SM-TANZA - BEI",
            "destination_label": "SM Tanza",
        }
        contracts_mod.resolve_warehouse_company = lambda wh: (
            "Bebang Kitchen Inc." if "BKI" in (wh or "") else "Bebang Enterprise Inc."
        )
        contracts_mod.stamp_stock_entry_contract = lambda *args, **kwargs: None
        contracts_mod.strip_company_suffix = lambda name: (name or "").rsplit(" - ", 1)[0]
        sys.modules["hrms.utils.supply_chain_contracts"] = contracts_mod

    if "hrms.api.google_chat" not in sys.modules:
        gchat_mod = types.ModuleType("hrms.api.google_chat")
        gchat_mod.send_message_to_space = MagicMock()
        sys.modules["hrms.api.google_chat"] = gchat_mod

    if "hrms.api.commissary_dashboard" not in sys.modules:
        cd_mod = types.ModuleType("hrms.api.commissary_dashboard")
        cd_mod._validate_shelf_life_gate = lambda *args, **kwargs: {"valid": True}
        sys.modules["hrms.api.commissary_dashboard"] = cd_mod

    if "hrms.api.commissary" not in sys.modules:
        comm_mod = types.ModuleType("hrms.api.commissary")
        comm_mod.get_commissary_warehouse = lambda: "BKI Operations"
        sys.modules["hrms.api.commissary"] = comm_mod


_install_fake_frappe_and_dependencies()

# Load warehouse module under test
warehouse_spec = importlib.util.spec_from_file_location(
    "warehouse_under_test_notif",
    ROOT / "hrms" / "api" / "warehouse.py",
)
warehouse = importlib.util.module_from_spec(warehouse_spec)
warehouse_spec.loader.exec_module(warehouse)

import frappe  # noqa: E402 — fake frappe installed above


class _FakeSEItem:
    def __init__(self, item_code="FG001", qty=10.0, uom="Nos"):
        self.item_code = item_code
        self.item_name = f"Item {item_code}"
        self.qty = qty
        self.uom = uom
        self.stock_uom = uom


class _FakeSE:
    def __init__(self, name="STE-2026-00001", from_warehouse="Shaw BLVD - BKI",
                 to_warehouse="SM-TANZA - BEI", items=None):
        self.name = name
        self.from_warehouse = from_warehouse
        self.to_warehouse = to_warehouse
        self.items = items or [_FakeSEItem("FG001", 10)]


class TestGetStoreCrewRecipients(unittest.TestCase):
    """P3-T1: _get_store_crew_recipients resolves area supervisor + branch employees."""

    def setUp(self):
        frappe.log_error = MagicMock()

    def test_returns_area_supervisor_email(self):
        """Area supervisor from Warehouse.custom_area_supervisor is included."""
        frappe.db.get_value = MagicMock(return_value="test.area@bebang.ph")
        frappe.get_all = MagicMock(return_value=[])

        result = warehouse._get_store_crew_recipients("SM-TANZA - BEI")

        self.assertIn("test.area@bebang.ph", result)

    def test_returns_branch_employees(self):
        """Employees with branch = target_warehouse are included."""
        frappe.db.get_value = MagicMock(return_value=None)
        frappe.get_all = MagicMock(return_value=[
            {"user_id": "crew1@bebang.ph"},
            {"user_id": "crew2@bebang.ph"},
        ])

        result = warehouse._get_store_crew_recipients("SM-TANZA - BEI")

        self.assertIn("crew1@bebang.ph", result)
        self.assertIn("crew2@bebang.ph", result)

    def test_deduplicates_supervisor_and_employee(self):
        """If area supervisor is also an employee, they appear only once."""
        frappe.db.get_value = MagicMock(return_value="test.area@bebang.ph")
        frappe.get_all = MagicMock(return_value=[
            {"user_id": "test.area@bebang.ph"},
            {"user_id": "crew1@bebang.ph"},
        ])

        result = warehouse._get_store_crew_recipients("SM-TANZA - BEI")

        self.assertEqual(result.count("test.area@bebang.ph"), 1)
        self.assertEqual(len(result), 2)

    def test_returns_empty_for_no_warehouse(self):
        """If target_warehouse is empty, return empty list."""
        result = warehouse._get_store_crew_recipients("")
        self.assertEqual(result, [])

    def test_caps_at_20_recipients(self):
        """Result is capped at 20 even if more employees exist."""
        frappe.db.get_value = MagicMock(return_value="supervisor@bebang.ph")
        frappe.get_all = MagicMock(return_value=[
            {"user_id": f"crew{i}@bebang.ph"} for i in range(25)
        ])

        result = warehouse._get_store_crew_recipients("SM-TANZA - BEI")

        self.assertLessEqual(len(result), 20)

    def test_exception_returns_empty_list(self):
        """If DB query fails, return empty list (don't raise)."""
        frappe.db.get_value = MagicMock(side_effect=Exception("DB down"))
        frappe.get_all = MagicMock(side_effect=Exception("DB down"))

        result = warehouse._get_store_crew_recipients("SM-TANZA - BEI")

        self.assertEqual(result, [])
        frappe.log_error.assert_called()


class TestDispatchCreatesNotification(unittest.TestCase):
    """P3-T4 test 1: dispatch triggers GChat notification via _notify_warehouse_handoff."""

    def setUp(self):
        frappe.log_error = MagicMock()
        frappe.db.get_value = MagicMock(return_value=None)
        frappe.db.set_value = MagicMock()
        frappe.db.get_single_value = MagicMock(return_value=None)
        frappe.get_all = MagicMock(return_value=[])

    def test_dispatch_creates_notification_log_for_recipients(self):
        """After WR is created, _notify_warehouse_handoff is called with the WR details."""
        se = _FakeSE()
        contract = {"destination_warehouse": "SM-TANZA - BEI"}

        with patch.object(
            warehouse, "create_warehouse_receiving",
            return_value={"success": True, "data": {"name": "BEI-WHR-2026-00010"}, "message": "ok"},
        ):
            with patch.object(warehouse, "_notify_warehouse_handoff") as mock_notify:
                result = warehouse._create_warehouse_receiving_for_se(se, contract)

        self.assertEqual(result, "BEI-WHR-2026-00010")
        mock_notify.assert_called_once_with(
            "BEI-WHR-2026-00010", "Shaw BLVD - BKI", "SM-TANZA - BEI"
        )


class TestNotificationFailureDoesNotRollbackDispatch(unittest.TestCase):
    """P3-T4 test 2: GChat notification failure does not prevent WR creation."""

    def setUp(self):
        frappe.log_error = MagicMock()
        frappe.db.get_value = MagicMock(return_value=None)
        frappe.db.set_value = MagicMock()
        frappe.db.get_single_value = MagicMock(return_value=None)
        frappe.get_all = MagicMock(return_value=[])

    def test_notification_failure_does_not_rollback_dispatch(self):
        """If _notify_warehouse_handoff raises, the WR is still returned."""
        se = _FakeSE()
        contract = {"destination_warehouse": "SM-TANZA - BEI"}

        with patch.object(
            warehouse, "create_warehouse_receiving",
            return_value={"success": True, "data": {"name": "BEI-WHR-2026-00020"}, "message": "ok"},
        ):
            with patch.object(
                warehouse, "_notify_warehouse_handoff",
                side_effect=Exception("GChat API timeout"),
            ):
                result = warehouse._create_warehouse_receiving_for_se(se, contract)

        # WR should still be returned despite notification failure
        self.assertEqual(result, "BEI-WHR-2026-00020")
        # stock_entry should still have been stamped
        frappe.db.set_value.assert_called_once_with(
            "BEI Warehouse Receiving", "BEI-WHR-2026-00020", "stock_entry", "STE-2026-00001"
        )


if __name__ == "__main__":
    unittest.main()
