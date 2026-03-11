import datetime
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_hrms():
	if "hrms" in sys.modules:
		return

	hrms_pkg = types.ModuleType("hrms")
	hrms_pkg.__path__ = []
	sys.modules["hrms"] = hrms_pkg

	utils_pkg = types.ModuleType("hrms.utils")
	utils_pkg.__path__ = []
	sys.modules["hrms.utils"] = utils_pkg

	store_snapshot_mod = types.ModuleType("hrms.utils.store_order_demand_snapshot")
	store_snapshot_mod.DEFAULT_DESTINATION_DIR = ROOT / "tmp"
	store_snapshot_mod.run_snapshot = lambda *args, **kwargs: {}
	sys.modules["hrms.utils.store_order_demand_snapshot"] = store_snapshot_mod
	utils_pkg.store_order_demand_snapshot = store_snapshot_mod

	store_inventory_mod = types.ModuleType("hrms.utils.store_inventory_shadow_sync")
	store_inventory_mod.DEFAULT_OUTPUT_ROOT = ROOT / "tmp"
	store_inventory_mod.run_shadow_sync = lambda *args, **kwargs: {}
	store_inventory_mod.get_runtime_state_path = lambda: (
		ROOT / "tmp" / "store_inventory_shadow_sync_state.json"
	)
	store_inventory_mod.get_runtime_registry_path = lambda: (
		ROOT / "tmp" / "store_inventory_shadow_sync_registry.csv"
	)
	store_inventory_mod.load_runtime_state = lambda *args, **kwargs: {"stores": {}, "last_run": {}}
	store_inventory_mod.load_store_registry = lambda *args, **kwargs: []
	store_inventory_mod.save_store_registry = lambda *args, **kwargs: None
	store_inventory_mod.save_runtime_state = lambda *args, **kwargs: None
	sys.modules["hrms.utils.store_inventory_shadow_sync"] = store_inventory_mod
	utils_pkg.store_inventory_shadow_sync = store_inventory_mod

	standard_buying_bridge_mod = types.ModuleType("hrms.utils.standard_buying_bridge")

	def apply_standard_buying_context(doc, *, store_label=None, legal_entity=None):
		if legal_entity:
			doc.set("bei_legal_entity", legal_entity)
		doc.set("bei_store_label", store_label or "Stores - BEI")

	standard_buying_bridge_mod.apply_standard_buying_context = apply_standard_buying_context
	sys.modules["hrms.utils.standard_buying_bridge"] = standard_buying_bridge_mod
	utils_pkg.standard_buying_bridge = standard_buying_bridge_mod


def _install_fake_frappe():
	frappe = types.ModuleType("frappe")
	utils = types.ModuleType("frappe.utils")

	def whitelist(*_args, **_kwargs):
		def decorator(fn):
			return fn

		return decorator

	class PermissionError(Exception):
		pass

	def _throw(message, exc=None):
		if isinstance(exc, type) and issubclass(exc, Exception):
			raise exc(message)
		raise Exception(message)

	frappe.whitelist = whitelist
	frappe._ = lambda text: text
	frappe.throw = _throw
	frappe.PermissionError = PermissionError
	frappe.log_error = lambda *args, **kwargs: None
	frappe.logger = lambda: types.SimpleNamespace(info=lambda *args, **kwargs: None)
	frappe.get_traceback = lambda: "traceback"
	frappe.__dict__["session"] = types.SimpleNamespace(user="Administrator")
	frappe.get_roles = lambda user=None: ["System Manager"] if user and user != "Guest" else []
	frappe.__dict__["db"] = types.SimpleNamespace(
		exists=lambda *args, **kwargs: None,
		get_value=lambda *args, **kwargs: None,
		set_value=lambda *args, **kwargs: None,
		savepoint=lambda *args, **kwargs: None,
		release_savepoint=lambda *args, **kwargs: None,
		rollback=lambda *args, **kwargs: None,
	)
	frappe.get_meta = lambda *args, **kwargs: types.SimpleNamespace(has_field=lambda *_: True)

	utils.now_datetime = lambda: datetime.datetime(2026, 1, 1, 8, 0, 0)
	utils.nowdate = lambda: "2026-01-01"
	utils.flt = lambda value: float(value or 0)
	utils.cint = lambda value: int(float(value or 0))
	utils.getdate = lambda value=None: (
		datetime.date.fromisoformat(str(value)) if value else datetime.date(2026, 1, 1)
	)

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils


_install_fake_frappe()
_install_fake_hrms()
erp_sync_spec = importlib.util.spec_from_file_location(
	"erp_sync_runtime_under_test",
	ROOT / "hrms" / "api" / "erp_sync.py",
)
erp_sync = importlib.util.module_from_spec(erp_sync_spec)
erp_sync_spec.loader.exec_module(erp_sync)


class TestErpSyncRuntime(unittest.TestCase):
	def setUp(self):
		erp_sync._FIELD_CACHE.clear()
		erp_sync.frappe.__dict__["session"] = types.SimpleNamespace(user="Administrator")
		erp_sync.frappe.get_roles = MagicMock(return_value=["System Manager"])
		erp_sync.frappe.db.savepoint = MagicMock(return_value="sp_sync")
		erp_sync.frappe.db.release_savepoint = MagicMock()
		erp_sync.frappe.db.rollback = MagicMock()
		erp_sync.frappe.db.exists = MagicMock(return_value="SINV-0001")
		erp_sync.frappe.db.get_value = MagicMock(return_value=1)
		erp_sync.frappe.db.set_value = MagicMock()
		erp_sync.frappe.get_meta = MagicMock(return_value=types.SimpleNamespace(has_field=lambda *_: True))

	def test_allowed_roles_cover_finance_and_hr(self):
		self.assertTrue(
			{"Accounts Manager", "Accounts User", "HR Manager"}.issubset(erp_sync.SYNC_ALLOWED_ROLES)
		)

	def test_successful_sync_releases_savepoint(self):
		result = erp_sync.sync_ar_aging(
			sheet_name="AR Aging",
			data=[{"invoice_no": "SINV-0001", "outstanding": 1200, "due_date": "2026-01-31"}],
			checksum="runtime-1",
		)

		self.assertEqual(result["rows_failed"], 0)
		erp_sync.frappe.db.savepoint.assert_called_once()
		erp_sync.frappe.db.release_savepoint.assert_called_once()
		erp_sync.frappe.db.rollback.assert_not_called()

	def test_supplier_soa_alias_preserves_payload(self):
		rows = [{"supplier": "Acme", "invoice_no": "INV-001", "amount": 1500}]
		expected = {"rows_processed": 1, "rows_created": 1, "rows_updated": 0, "rows_failed": 0, "errors": []}

		with patch.object(erp_sync, "sync_ap_opening", return_value=expected) as sync_ap_opening:
			result = erp_sync.sync_supplier_soa("Supplier SOA", rows, "runtime-2")

		sync_ap_opening.assert_called_once_with(sheet_name="Supplier SOA", data=rows, checksum="runtime-2")
		self.assertEqual(result, expected)

	def test_watch_store_inventory_shadow_sync_health_queues_recovery_for_stale_run(self):
		runtime_state = {
			"stores": {},
			"last_run": {
				"status": "in_progress",
				"run_date": "2026-01-01",
				"generated_at": "2026-01-01T07:30:00",
				"updated_at": "2026-01-01T07:35:00",
			},
		}
		erp_sync.frappe.enqueue = MagicMock()
		erp_sync.frappe.log_error = MagicMock()

		with (
			patch.object(
				erp_sync.store_inventory_shadow_sync_builder,
				"load_runtime_state",
				return_value=runtime_state,
			),
			patch.object(
				erp_sync.store_inventory_shadow_sync_builder,
				"save_runtime_state",
				MagicMock(),
			) as save_state_mock,
		):
			result = erp_sync.watch_store_inventory_shadow_sync_health(
				run_date="2026-01-01",
				stale_after_minutes=20,
				cooldown_minutes=20,
				state_path=str(ROOT / "tmp" / "shadow-state.json"),
			)

		self.assertTrue(result["queued"])
		self.assertEqual(result["job_id"], "scheduled_store_inventory_shadow_sync_recovery:2026-01-01")
		erp_sync.frappe.enqueue.assert_called_once_with(
			"hrms.api.erp_sync.run_scheduled_store_inventory_shadow_sync",
			queue="long",
			job_id="scheduled_store_inventory_shadow_sync_recovery:2026-01-01",
			deduplicate=True,
			run_date="2026-01-01",
			force=False,
		)
		self.assertIn("recovery_enqueued_at", runtime_state["last_run"])
		save_state_mock.assert_called_once()

	def test_watch_store_inventory_shadow_sync_health_skips_fresh_run(self):
		runtime_state = {
			"stores": {},
			"last_run": {
				"status": "in_progress",
				"run_date": "2026-01-01",
				"generated_at": "2026-01-01T07:55:00",
				"updated_at": "2026-01-01T07:55:00",
			},
		}
		erp_sync.frappe.enqueue = MagicMock()

		with patch.object(
			erp_sync.store_inventory_shadow_sync_builder,
			"load_runtime_state",
			return_value=runtime_state,
		):
			result = erp_sync.watch_store_inventory_shadow_sync_health(
				run_date="2026-01-01",
				stale_after_minutes=20,
				cooldown_minutes=20,
			)

		self.assertFalse(result["queued"])
		self.assertEqual(result["reason"], "not_stale")
		erp_sync.frappe.enqueue.assert_not_called()

	def test_watch_store_inventory_shadow_sync_health_marks_completed_when_registry_already_synced(self):
		runtime_state = {
			"stores": {},
			"last_run": {
				"status": "in_progress",
				"run_date": "2026-01-01",
				"generated_at": "2026-01-01T07:00:00",
				"updated_at": "2026-01-01T07:10:00",
				"recovery_enqueued_at": "2026-01-01T07:20:00",
			},
		}
		registry_rows = [
			types.SimpleNamespace(
				store_code="AFT",
				sheet_sync_enabled=True,
				state="shadow_sync",
				last_inventory_date="2026-01-01",
				last_success_at="2026-01-01T07:30:00",
			),
			types.SimpleNamespace(
				store_code="AMM",
				sheet_sync_enabled=True,
				state="shadow_sync",
				last_inventory_date="2026-01-01",
				last_success_at="2026-01-01T07:31:00",
			),
		]
		erp_sync.frappe.enqueue = MagicMock()

		with (
			patch.object(
				erp_sync.store_inventory_shadow_sync_builder,
				"load_runtime_state",
				return_value=runtime_state,
			),
			patch.object(
				erp_sync.store_inventory_shadow_sync_builder,
				"load_store_registry",
				return_value=registry_rows,
			),
			patch.object(
				erp_sync.store_inventory_shadow_sync_builder,
				"save_runtime_state",
				MagicMock(),
			) as save_state_mock,
			patch.object(
				erp_sync.store_inventory_shadow_sync_builder,
				"save_store_registry",
				MagicMock(),
			) as save_registry_mock,
		):
			result = erp_sync.watch_store_inventory_shadow_sync_health(
				run_date="2026-01-01",
				stale_after_minutes=20,
				cooldown_minutes=20,
			)

		self.assertFalse(result["queued"])
		self.assertEqual(result["reason"], "already_complete")
		self.assertEqual(runtime_state["last_run"]["status"], "completed")
		self.assertEqual(runtime_state["last_run"]["failed_stores"], 0)
		self.assertEqual(runtime_state["last_run"]["current_stage"], "completed")
		erp_sync.frappe.enqueue.assert_not_called()
		save_registry_mock.assert_called_once()
		save_state_mock.assert_called_once()


if __name__ == "__main__":
	unittest.main()
