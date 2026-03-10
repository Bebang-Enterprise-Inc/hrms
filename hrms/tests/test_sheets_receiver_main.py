import importlib.util
import sys
import types
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_sheets_receiver_dependencies():
	if "schedule" not in sys.modules:
		schedule_mod = types.ModuleType("schedule")
		schedule_mod.every = lambda *_args, **_kwargs: None
		schedule_mod.run_pending = lambda: None
		sys.modules["schedule"] = schedule_mod

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

	sheets_client_mod = types.ModuleType("hrms.services.sheets_receiver.sheets_client")
	sheets_client_mod.get_sheets_client = lambda: types.SimpleNamespace()
	sys.modules["hrms.services.sheets_receiver.sheets_client"] = sheets_client_mod

	processor_mod = types.ModuleType("hrms.services.sheets_receiver.processor")
	processor_mod.get_processor = lambda: types.SimpleNamespace()
	sys.modules["hrms.services.sheets_receiver.processor"] = processor_mod

	webhook_mod = types.ModuleType("hrms.services.sheets_receiver.webhook")
	webhook_mod.run_server = lambda *_args, **_kwargs: None
	sys.modules["hrms.services.sheets_receiver.webhook"] = webhook_mod

	file_processor_mod = types.ModuleType("hrms.services.sheets_receiver.file_processor")
	file_processor_mod.get_file_processor = lambda: types.SimpleNamespace()
	sys.modules["hrms.services.sheets_receiver.file_processor"] = file_processor_mod

	folder_watcher_mod = types.ModuleType("hrms.services.sheets_receiver.folder_watcher")
	folder_watcher_mod.get_folder_watcher = lambda: types.SimpleNamespace()
	sys.modules["hrms.services.sheets_receiver.folder_watcher"] = folder_watcher_mod


_install_fake_sheets_receiver_dependencies()
main_spec = importlib.util.spec_from_file_location(
	"hrms.services.sheets_receiver.main_under_test",
	ROOT / "hrms" / "services" / "sheets_receiver" / "main.py",
)
main_mod = importlib.util.module_from_spec(main_spec)
main_spec.loader.exec_module(main_mod)


class _FakeScheduledJob:
	def __init__(self, schedule_module, interval):
		self._schedule_module = schedule_module
		self.interval = interval
		self.unit = None
		self.at_time = None

	@property
	def hour(self):
		self.unit = "hour"
		return self

	@property
	def hours(self):
		self.unit = "hours"
		return self

	@property
	def minutes(self):
		self.unit = "minutes"
		return self

	@property
	def day(self):
		self.unit = "day"
		return self

	def at(self, time_value):
		self.at_time = time_value
		return self

	def do(self, func):
		self._schedule_module.jobs.append(
			{
				"interval": self.interval,
				"unit": self.unit,
				"at": self.at_time,
				"func": func,
			}
		)
		return self


class _FakeSchedule:
	def __init__(self):
		self.jobs = []

	def every(self, interval=None):
		return _FakeScheduledJob(self, interval)


class TestSheetsReceiverDailyBaselineSync(unittest.TestCase):
	def setUp(self):
		self.processor = types.SimpleNamespace(
			sync_sheet=MagicMock(side_effect=lambda *args, **kwargs: kwargs)
		)
		self.db = types.SimpleNamespace(has_successful_sync_since=MagicMock(return_value=False))
		self.sheet_configs = {
			"ap_opening_balance": types.SimpleNamespace(
				spreadsheet_id="ap-book",
				sheet_name="05 - AP Opening Balance (PHP 24.4M)",
				enabled=True,
			),
			"supplier_soa": types.SimpleNamespace(
				spreadsheet_id="ap-book",
				sheet_name="SUPPLIERS SOA",
				enabled=True,
			),
			"procurement_suppliers": types.SimpleNamespace(
				spreadsheet_id="proc-book",
				sheet_name="Suppliers",
				enabled=True,
			),
			"procurement_requisitions": types.SimpleNamespace(
				spreadsheet_id="proc-book",
				sheet_name="Purchase Requisitions",
				enabled=True,
			),
			"procurement_purchase_orders": types.SimpleNamespace(
				spreadsheet_id="proc-book",
				sheet_name="Purchase Order",
				enabled=True,
			),
			"procurement_goods_receipts": types.SimpleNamespace(
				spreadsheet_id="proc-book",
				sheet_name="Goods Receipts",
				enabled=True,
			),
		}

		main_mod.get_db = MagicMock(return_value=self.db)
		main_mod.get_processor = MagicMock(return_value=self.processor)
		main_mod.get_sheet_config = MagicMock(side_effect=lambda sheet_key: self.sheet_configs.get(sheet_key))

	def test_daily_baseline_sync_skips_before_8am_pht(self):
		now_utc = datetime(2026, 3, 9, 23, 59, tzinfo=UTC)

		results = main_mod.run_daily_baseline_sync_if_due(now_utc=now_utc)

		self.assertEqual(results, [])
		self.processor.sync_sheet.assert_not_called()
		self.db.has_successful_sync_since.assert_not_called()

	def test_daily_baseline_sync_runs_force_sync_for_target_sheets_after_8am_pht(self):
		now_utc = datetime(2026, 3, 10, 0, 5, tzinfo=UTC)

		results = main_mod.run_daily_baseline_sync_if_due(now_utc=now_utc)

		self.assertEqual(len(results), 6)
		self.assertEqual(self.processor.sync_sheet.call_count, 6)
		for call in self.processor.sync_sheet.call_args_list:
			self.assertEqual(call.kwargs["trigger"], "daily_baseline")
			self.assertTrue(call.kwargs["force"])

	def test_daily_baseline_sync_skips_sheets_already_synced_today(self):
		now_utc = datetime(2026, 3, 10, 0, 5, tzinfo=UTC)
		self.db.has_successful_sync_since.side_effect = lambda spreadsheet_id, sheet_name, trigger, since: (
			sheet_name == "SUPPLIERS SOA"
		)

		results = main_mod.run_daily_baseline_sync_if_due(now_utc=now_utc)

		self.assertEqual(len(results), 5)
		synced_sheet_names = [call.args[0].sheet_name for call in self.processor.sync_sheet.call_args_list]
		self.assertNotIn("SUPPLIERS SOA", synced_sheet_names)

	def test_configure_scheduled_jobs_registers_daily_baseline_check(self):
		fake_schedule = _FakeSchedule()

		main_mod.configure_scheduled_jobs(schedule_module=fake_schedule)

		self.assertIn(
			main_mod.run_daily_baseline_sync_if_due,
			[job["func"] for job in fake_schedule.jobs],
		)


if __name__ == "__main__":
	unittest.main()
