"""S198 P1-T5: Unit tests for auto-create WR on BKI dispatch.

Tests the _create_warehouse_receiving_for_se helper and its integration
with create_stock_transfer.  Uses fake-frappe pattern (same as
test_dispatch_pre_delivery.py) — NOT FrappeTestCase.
"""

import datetime
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_fake_frappe_and_dependencies():
    """Install a minimal fake frappe + dependency tree so warehouse.py can be imported."""

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
        frappe.get_all = lambda *args, **kwargs: []
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
    "warehouse_under_test",
    ROOT / "hrms" / "api" / "warehouse.py",
)
warehouse = importlib.util.module_from_spec(warehouse_spec)
warehouse_spec.loader.exec_module(warehouse)

import frappe  # noqa: E402 — fake frappe installed above


class _FakeSEItem:
    """Simulates a Stock Entry item row."""
    def __init__(self, item_code="FG001", qty=10.0, uom="Nos"):
        self.item_code = item_code
        self.item_name = f"Item {item_code}"
        self.qty = qty
        self.uom = uom
        self.stock_uom = uom


class _FakeSE:
    """Simulates a Stock Entry doc."""
    def __init__(self, name="STE-2026-00001", from_warehouse="Shaw BLVD - BKI",
                 to_warehouse="SM-TANZA - BEI", items=None):
        self.name = name
        self.from_warehouse = from_warehouse
        self.to_warehouse = to_warehouse
        self.items = items or [_FakeSEItem("FG001", 10), _FakeSEItem("FG002", 5)]


class TestDispatchCreatesWR(unittest.TestCase):
    """P1-T5 test 1: SE submit on BKI dispatch auto-creates a WR."""

    def setUp(self):
        """Reset frappe mock state before each test."""
        frappe.log_error = MagicMock()
        frappe.db.get_value = MagicMock(return_value=None)
        frappe.db.set_value = MagicMock()
        frappe.db.get_single_value = MagicMock(return_value=None)
        frappe.get_all = MagicMock(return_value=[])

    def test_dispatch_creates_wr_alongside_se(self):
        """When a BKI-source SE is submitted, a WR is auto-created with matching items."""
        se = _FakeSE()
        contract = {
            "destination_warehouse": "SM-TANZA - BEI",
            "source_company": "Bebang Kitchen Inc.",
            "target_company": "Bebang Enterprise Inc.",
        }

        # Mock create_warehouse_receiving to return a successful result
        with patch.object(
            warehouse, "create_warehouse_receiving",
            return_value={
                "success": True,
                "data": {"name": "BEI-WHR-2026-00001"},
                "message": "created",
            },
        ) as mock_cwr:
            with patch.object(
                warehouse, "_notify_warehouse_handoff"
            ) as mock_notify:
                result = warehouse._create_warehouse_receiving_for_se(se, contract)

        self.assertEqual(result, "BEI-WHR-2026-00001")

        # Verify create_warehouse_receiving was called with correct args
        mock_cwr.assert_called_once()
        call_kwargs = mock_cwr.call_args
        self.assertEqual(call_kwargs.kwargs.get("source_warehouse") or call_kwargs[1].get("source_warehouse", call_kwargs[0][0] if call_kwargs[0] else None), "Shaw BLVD - BKI")

        # Verify stock_entry was stamped via set_value (D-11)
        frappe.db.set_value.assert_called_once_with(
            "BEI Warehouse Receiving", "BEI-WHR-2026-00001", "stock_entry", "STE-2026-00001"
        )

        # Verify notification was sent (P3-T2)
        mock_notify.assert_called_once_with(
            "BEI-WHR-2026-00001", "Shaw BLVD - BKI", "SM-TANZA - BEI"
        )


class TestIdempotentRedispatch(unittest.TestCase):
    """P1-T5 test 2: Re-dispatch for the same SE returns the existing WR."""

    def setUp(self):
        frappe.log_error = MagicMock()
        frappe.db.get_single_value = MagicMock(return_value=None)
        frappe.get_all = MagicMock(return_value=[])

    def test_idempotent_redispatch_returns_same_wr(self):
        """If a WR already exists for this SE, return its name without creating a new one."""
        se = _FakeSE()
        contract = {"destination_warehouse": "SM-TANZA - BEI"}

        # Simulate existing WR
        frappe.db.get_value = MagicMock(return_value="BEI-WHR-2026-00099")

        with patch.object(warehouse, "create_warehouse_receiving") as mock_cwr:
            result = warehouse._create_warehouse_receiving_for_se(se, contract)

        self.assertEqual(result, "BEI-WHR-2026-00099")
        # create_warehouse_receiving should NOT have been called
        mock_cwr.assert_not_called()


class TestWRFailureDoesNotRollbackSE(unittest.TestCase):
    """P1-T5 test 3: WR creation failure does not raise (SE already submitted)."""

    def setUp(self):
        frappe.log_error = MagicMock()
        frappe.db.get_value = MagicMock(return_value=None)
        frappe.db.get_single_value = MagicMock(return_value=None)
        frappe.get_all = MagicMock(return_value=[])

    def test_wr_failure_does_not_rollback_se(self):
        """If create_warehouse_receiving raises, the helper catches it and returns None."""
        se = _FakeSE()
        contract = {"destination_warehouse": "SM-TANZA - BEI"}

        with patch.object(
            warehouse, "create_warehouse_receiving",
            side_effect=Exception("BEI Warehouse Receiving insert failed"),
        ):
            result = warehouse._create_warehouse_receiving_for_se(se, contract)

        # MUST return None, NOT raise
        self.assertIsNone(result)
        # Error should have been logged
        frappe.log_error.assert_called()


class TestWRStatusStartsPendingWarehouseReceive(unittest.TestCase):
    """P1-T5 test 4: WR created by the hook has status 'Pending Warehouse Receive' (D-2)."""

    def setUp(self):
        frappe.log_error = MagicMock()
        frappe.db.get_value = MagicMock(return_value=None)
        frappe.db.set_value = MagicMock()
        frappe.db.get_single_value = MagicMock(return_value=None)
        frappe.get_all = MagicMock(return_value=[])

    def test_wr_status_starts_pending_warehouse_receive(self):
        """The WR is created via create_warehouse_receiving which sets
        the initial status to 'Pending Warehouse Receive' (the only valid initial
        status per the DocType schema). This test verifies the call goes through
        create_warehouse_receiving (which owns the status) rather than direct ORM.
        """
        se = _FakeSE()
        contract = {"destination_warehouse": "SM-TANZA - BEI"}

        with patch.object(
            warehouse, "create_warehouse_receiving",
            return_value={
                "success": True,
                "data": {"name": "BEI-WHR-2026-00005"},
                "message": "created",
            },
        ) as mock_cwr:
            with patch.object(warehouse, "_notify_warehouse_handoff"):
                result = warehouse._create_warehouse_receiving_for_se(se, contract)

        self.assertEqual(result, "BEI-WHR-2026-00005")
        # Verify that we called create_warehouse_receiving (which handles status)
        # rather than doing a raw frappe.new_doc
        mock_cwr.assert_called_once()
        # The items payload should contain the SE items
        items_arg = mock_cwr.call_args.kwargs.get("items") or mock_cwr.call_args[1].get("items")
        parsed = json.loads(items_arg) if isinstance(items_arg, str) else items_arg
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["item_code"], "FG001")
        self.assertEqual(parsed[0]["qty"], 10.0)


class TestNonBKIDispatchSkipsWR(unittest.TestCase):
    """D-1 scope guard: non-BKI dispatches skip WR auto-create."""

    def setUp(self):
        frappe.log_error = MagicMock()
        frappe.db.get_single_value = MagicMock(return_value=None)

    def test_non_bki_dispatch_returns_none(self):
        """If source warehouse is BEI (not BKI), skip WR creation."""
        se = _FakeSE(from_warehouse="SM-TANZA - BEI")
        contract = {"destination_warehouse": "SM-CALOOCAN - BEI"}

        with patch.object(warehouse, "create_warehouse_receiving") as mock_cwr:
            result = warehouse._create_warehouse_receiving_for_se(se, contract)

        self.assertIsNone(result)
        mock_cwr.assert_not_called()


if __name__ == "__main__":
    unittest.main()
