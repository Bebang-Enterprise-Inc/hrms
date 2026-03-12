import importlib.util
import sys
import types
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_sheets_receiver_dependencies():
	if "hrms" not in sys.modules:
		hrms_pkg = types.ModuleType("hrms")
		hrms_pkg.__path__ = []
		sys.modules["hrms"] = hrms_pkg

	if "hrms.services" not in sys.modules:
		services_pkg = types.ModuleType("hrms.services")
		services_pkg.__path__ = []
		sys.modules["hrms.services"] = services_pkg

	if "hrms.services.sheets_receiver" not in sys.modules:
		sheets_pkg = types.ModuleType("hrms.services.sheets_receiver")
		sheets_pkg.__path__ = []
		sys.modules["hrms.services.sheets_receiver"] = sheets_pkg

	config_mod = types.ModuleType("hrms.services.sheets_receiver.config")
	config_mod.get_config = lambda: types.SimpleNamespace()
	config_mod.get_watched_sheets = lambda: {}
	config_mod.get_sheet_config = lambda _sheet_key: None
	sys.modules["hrms.services.sheets_receiver.config"] = config_mod

	models_mod = types.ModuleType("hrms.services.sheets_receiver.models")
	models_mod.get_db = lambda: types.SimpleNamespace()
	sys.modules["hrms.services.sheets_receiver.models"] = models_mod

	processor_mod = types.ModuleType("hrms.services.sheets_receiver.processor")
	processor_mod.get_processor = lambda: types.SimpleNamespace()
	sys.modules["hrms.services.sheets_receiver.processor"] = processor_mod


_install_fake_sheets_receiver_dependencies()
config_mod = sys.modules["hrms.services.sheets_receiver.config"]
models_mod = sys.modules["hrms.services.sheets_receiver.models"]
webhook_spec = importlib.util.spec_from_file_location(
	"hrms.services.sheets_receiver.webhook_under_test",
	ROOT / "hrms" / "services" / "sheets_receiver" / "webhook.py",
)
webhook_mod = importlib.util.module_from_spec(webhook_spec)
webhook_spec.loader.exec_module(webhook_mod)


class _FakeSyncLog:
	def __init__(self, *, status: str, created_at: datetime, rows_failed: int = 0):
		self.id = 1
		self.trigger = "daily_baseline"
		self.status = status
		self.rows_processed = 10
		self.rows_created = 1
		self.rows_updated = 9
		self.rows_failed = rows_failed
		self.error_message = None
		self.duration_seconds = 1.2
		self.created_at = created_at.replace(tzinfo=None)


class _FakeDb:
	def __init__(self, mapping):
		self.mapping = mapping

	def get_latest_sync_since(self, spreadsheet_id, sheet_name, since, *, status=None, trigger=None):
		return self.mapping.get((sheet_name, status))


class TestSheetsReceiverMorningHealthReport(unittest.TestCase):
	def setUp(self):
		self.sheet_configs = {
			"inventory": types.SimpleNamespace(
				name="Inventory",
				spreadsheet_id="book-inventory",
				sheet_name="SUMMARY 2026",
				owner_email="ian@bebang.ph",
				enabled=True,
			),
			"ap_opening_balance": types.SimpleNamespace(
				name="AP Opening Balance",
				spreadsheet_id="book-ap",
				sheet_name="SUPPLIERS SOA",
				owner_email="alyssa@bebang.ph",
				enabled=True,
			),
			"procurement_suppliers": types.SimpleNamespace(
				name="Procurement Suppliers",
				spreadsheet_id="book-proc",
				sheet_name="Suppliers",
				owner_email="aldrin@bebang.ph",
				enabled=True,
			),
			"procurement_requisitions": types.SimpleNamespace(
				name="Procurement Requisitions",
				spreadsheet_id="book-proc",
				sheet_name="Purchase Requisitions",
				owner_email="aldrin@bebang.ph",
				enabled=True,
			),
			"procurement_purchase_orders": types.SimpleNamespace(
				name="Procurement Purchase Orders",
				spreadsheet_id="book-proc",
				sheet_name="Purchase Orders",
				owner_email="aldrin@bebang.ph",
				enabled=True,
			),
			"procurement_goods_receipts": types.SimpleNamespace(
				name="Procurement Goods Receipts",
				spreadsheet_id="book-proc",
				sheet_name="Goods Receipts",
				owner_email="aldrin@bebang.ph",
				enabled=True,
			),
		}
		config_mod.get_sheet_config = lambda sheet_key: self.sheet_configs.get(sheet_key)

	def test_report_is_yellow_when_all_lanes_ready_but_ap_has_failed_rows(self):
		fake_db = _FakeDb(
			{
				("SUMMARY 2026", None): _FakeSyncLog(
					status="success",
					created_at=datetime(2026, 3, 12, 23, 35, tzinfo=UTC),
				),
				("SUMMARY 2026", "success"): _FakeSyncLog(
					status="success",
					created_at=datetime(2026, 3, 12, 23, 35, tzinfo=UTC),
				),
				("SUPPLIERS SOA", None): _FakeSyncLog(
					status="success",
					created_at=datetime(2026, 3, 13, 0, 5, tzinfo=UTC),
					rows_failed=2,
				),
				("SUPPLIERS SOA", "success"): _FakeSyncLog(
					status="success",
					created_at=datetime(2026, 3, 13, 0, 5, tzinfo=UTC),
					rows_failed=2,
				),
				("Suppliers", None): _FakeSyncLog(
					status="success",
					created_at=datetime(2026, 3, 13, 0, 2, tzinfo=UTC),
				),
				("Suppliers", "success"): _FakeSyncLog(
					status="success",
					created_at=datetime(2026, 3, 13, 0, 2, tzinfo=UTC),
				),
				("Purchase Requisitions", None): _FakeSyncLog(
					status="success",
					created_at=datetime(2026, 3, 13, 0, 4, tzinfo=UTC),
				),
				("Purchase Requisitions", "success"): _FakeSyncLog(
					status="success",
					created_at=datetime(2026, 3, 13, 0, 4, tzinfo=UTC),
				),
				("Purchase Orders", None): _FakeSyncLog(
					status="success",
					created_at=datetime(2026, 3, 13, 0, 7, tzinfo=UTC),
				),
				("Purchase Orders", "success"): _FakeSyncLog(
					status="success",
					created_at=datetime(2026, 3, 13, 0, 7, tzinfo=UTC),
				),
				("Goods Receipts", None): _FakeSyncLog(
					status="success",
					created_at=datetime(2026, 3, 13, 0, 8, tzinfo=UTC),
				),
				("Goods Receipts", "success"): _FakeSyncLog(
					status="success",
					created_at=datetime(2026, 3, 13, 0, 8, tzinfo=UTC),
				),
			}
		)
		models_mod.get_db = lambda: fake_db

		report = webhook_mod.build_morning_health_report("2026-03-13")

		self.assertEqual(report["status"], "yellow")
		self.assertTrue(report["ready_before_deadline"])
		ap_lane = next(lane for lane in report["lanes"] if lane["sheet_key"] == "ap_opening_balance")
		self.assertEqual(ap_lane["status"], "completed_with_exceptions")
		self.assertTrue(ap_lane["ready_before_deadline"])

	def test_report_is_red_when_inventory_lane_has_no_success_today(self):
		fake_db = _FakeDb(
			{
				("SUMMARY 2026", None): _FakeSyncLog(
					status="failed",
					created_at=datetime(2026, 3, 12, 23, 10, tzinfo=UTC),
				),
			}
		)
		models_mod.get_db = lambda: fake_db

		report = webhook_mod.build_morning_health_report("2026-03-13")

		self.assertEqual(report["status"], "red")
		self.assertFalse(report["ready_before_deadline"])
		inventory_lane = next(lane for lane in report["lanes"] if lane["sheet_key"] == "inventory")
		self.assertEqual(inventory_lane["status"], "failed")
		self.assertFalse(inventory_lane["ready_before_deadline"])


if __name__ == "__main__":
	unittest.main()
