import datetime
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

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
	config_mod.SheetConfig = types.SimpleNamespace
	config_mod.get_config = lambda: types.SimpleNamespace()
	config_mod.get_all_sheet_configs = lambda: {}
	config_mod.get_sheet_by_spreadsheet_id = lambda *_args, **_kwargs: None
	config_mod.get_sheets_by_spreadsheet_id = lambda *_args, **_kwargs: {}
	config_mod.get_watched_sheets = lambda: {}
	sys.modules["hrms.services.sheets_receiver.config"] = config_mod

	models_mod = types.ModuleType("hrms.services.sheets_receiver.models")

	class SyncLog:
		def __init__(self, **kwargs):
			self.id = kwargs.get("id")
			self.spreadsheet_id = kwargs.get("spreadsheet_id")
			self.spreadsheet_name = kwargs.get("spreadsheet_name")
			self.sheet_name = kwargs.get("sheet_name")
			self.trigger = kwargs.get("trigger")
			self.status = kwargs.get("status")
			self.rows_processed = kwargs.get("rows_processed", 0)
			self.rows_created = kwargs.get("rows_created", 0)
			self.rows_updated = kwargs.get("rows_updated", 0)
			self.rows_failed = kwargs.get("rows_failed", 0)
			self.error_message = kwargs.get("error_message")
			self.duration_seconds = kwargs.get("duration_seconds", 0)
			self.data_checksum = kwargs.get("data_checksum")
			self.created_at = kwargs.get("created_at", datetime.datetime.now(datetime.UTC))

	models_mod.SyncLog = SyncLog
	models_mod.get_db = lambda: types.SimpleNamespace()
	sys.modules["hrms.services.sheets_receiver.models"] = models_mod

	sheets_client_mod = types.ModuleType("hrms.services.sheets_receiver.sheets_client")
	sheets_client_mod.get_sheets_client = lambda: types.SimpleNamespace()
	sys.modules["hrms.services.sheets_receiver.sheets_client"] = sheets_client_mod

	frappe_client_mod = types.ModuleType("hrms.services.sheets_receiver.frappe_client")

	class SyncResult:
		def __init__(
			self,
			success: bool,
			rows_processed: int = 0,
			rows_created: int = 0,
			rows_updated: int = 0,
			rows_failed: int = 0,
			errors=None,
		):
			self.success = success
			self.rows_processed = rows_processed
			self.rows_created = rows_created
			self.rows_updated = rows_updated
			self.rows_failed = rows_failed
			self.errors = errors or []

	frappe_client_mod.SyncResult = SyncResult
	frappe_client_mod.get_frappe_client = lambda: types.SimpleNamespace()
	sys.modules["hrms.services.sheets_receiver.frappe_client"] = frappe_client_mod

	transforms_mod = types.ModuleType("hrms.services.sheets_receiver.transforms")
	transforms_mod.transform_sheet_rows = lambda _name, rows: rows
	sys.modules["hrms.services.sheets_receiver.transforms"] = transforms_mod

	change_tracker_mod = types.ModuleType("hrms.services.sheets_receiver.change_tracker")
	change_tracker_mod.ChangeTracker = lambda _db: types.SimpleNamespace()
	change_tracker_mod.ChangeReport = types.SimpleNamespace
	change_tracker_mod.ChangeType = types.SimpleNamespace
	sys.modules["hrms.services.sheets_receiver.change_tracker"] = change_tracker_mod


_install_fake_sheets_receiver_dependencies()
processor_spec = importlib.util.spec_from_file_location(
	"hrms.services.sheets_receiver.processor_under_test",
	ROOT / "hrms" / "services" / "sheets_receiver" / "processor.py",
)
processor_mod = importlib.util.module_from_spec(processor_spec)
processor_spec.loader.exec_module(processor_mod)
ChangeProcessor = processor_mod.ChangeProcessor
SyncResult = processor_mod.SyncResult


class TestSheetsReceiverProcessorCriticalAlerts(unittest.TestCase):
	def _make_sheet_config(self):
		return types.SimpleNamespace(
			name="AR Aging",
			spreadsheet_id="sheet-001",
			sheet_name="AR",
			range="A:Z",
			key_column="invoice_no",
			related_sheet_keys=[],
		)

	def _make_processor(self):
		processor = ChangeProcessor.__new__(ChangeProcessor)
		processor.config = types.SimpleNamespace(
			suppress_critical_alert_triggers=("startup", "manual", "interval_baseline")
		)
		processor.db = types.SimpleNamespace(
			has_changed=MagicMock(return_value=True),
			save_checksum=MagicMock(),
			log_sync=MagicMock(),
		)
		processor.sheets = types.SimpleNamespace(
			fetch_sheet_values=MagicMock(return_value=([["header"], ["row"]], "raw-001")),
			compute_checksum=MagicMock(return_value="chk-001"),
			fetch_sheet_data=MagicMock(
				return_value=([{"invoice_no": "SINV-0001", "outstanding": 1200}], "chk-001")
			),
		)
		processor.frappe = types.SimpleNamespace(
			sync_sheet_data=MagicMock(
				return_value=SyncResult(
					success=True,
					rows_processed=1,
					rows_created=0,
					rows_updated=1,
					rows_failed=0,
					errors=[],
				)
			)
		)
		processor.change_tracker = types.SimpleNamespace(
			compute_changes=MagicMock(
				return_value=types.SimpleNamespace(
					rows_added=0,
					rows_modified=0,
					rows_deleted=0,
					rows_unchanged=1,
					alerts=[],
				)
			)
		)
		processor._send_critical_sync_alert = MagicMock()
		return processor

	def test_critical_alerts_suppressed_for_interval_baseline_trigger(self):
		processor = self._make_processor()

		self.assertTrue(processor._critical_alerts_suppressed_for_trigger("interval_baseline"))
		self.assertTrue(processor._critical_alerts_suppressed_for_trigger("manual"))
		self.assertFalse(processor._critical_alerts_suppressed_for_trigger("scheduled"))

	def test_sync_sheet_emits_alert_for_critical_change_pattern(self):
		processor = self._make_processor()
		sheet_config = self._make_sheet_config()
		alert = (
			"⚠️ MASS EDIT: 12 rows (24%) modified in AR Aging/AR. "
			"Expected new rows, but existing data was changed."
		)
		processor.change_tracker.compute_changes.return_value = types.SimpleNamespace(
			rows_added=0,
			rows_modified=12,
			rows_deleted=0,
			rows_unchanged=1,
			alerts=[alert],
		)

		log = processor.sync_sheet(sheet_config, trigger="webhook")

		self.assertEqual(log.status, "success")
		processor._send_critical_sync_alert.assert_called_once()
		call = processor._send_critical_sync_alert.call_args
		self.assertIn("suspicious_change_alert", call.kwargs["reasons"])
		self.assertIn(alert, call.kwargs["critical_alerts"])

	def test_sync_sheet_emits_alert_when_rows_fail(self):
		processor = self._make_processor()
		sheet_config = self._make_sheet_config()
		processor.frappe.sync_sheet_data.return_value = SyncResult(
			success=True,
			rows_processed=2,
			rows_created=1,
			rows_updated=0,
			rows_failed=1,
			errors=["Missing supplier on row 2"],
		)

		log = processor.sync_sheet(sheet_config, trigger="scheduled")

		self.assertEqual(log.status, "success")
		processor._send_critical_sync_alert.assert_called_once()
		call = processor._send_critical_sync_alert.call_args
		self.assertIn("rows_failed", call.kwargs["reasons"])
		self.assertIn("sync_errors_reported", call.kwargs["reasons"])

	def test_sync_sheet_emits_alert_when_exception_occurs(self):
		processor = self._make_processor()
		sheet_config = self._make_sheet_config()
		processor.sheets.fetch_sheet_data.side_effect = RuntimeError("receiver timeout")

		log = processor.sync_sheet(sheet_config, trigger="manual")

		self.assertEqual(log.status, "failed")
		self.assertIn("receiver timeout", log.error_message or "")
		processor._send_critical_sync_alert.assert_called_once()
		call = processor._send_critical_sync_alert.call_args
		self.assertEqual(call.kwargs["reasons"], ["sync_exception"])
		self.assertIn("receiver timeout", call.kwargs["errors"][0])
		processor.db.log_sync.assert_called_once()

	def test_process_webhook_syncs_all_matching_sheet_configs_for_workbook(self):
		processor = self._make_processor()
		sheet_a = self._make_sheet_config()
		sheet_b = types.SimpleNamespace(
			**{**sheet_a.__dict__, "name": "Supplier SOA", "sheet_name": "SUPPLIERS SOA"}
		)
		processor.sync_sheet = MagicMock(side_effect=["log-a", "log-b"])

		processor_mod.get_sheets_by_spreadsheet_id = MagicMock(
			return_value={"ap_opening_balance": sheet_a, "supplier_soa": sheet_b}
		)

		result = processor.process_webhook("sheet-001", "change")

		self.assertEqual(result, "log-b")
		self.assertEqual(processor.sync_sheet.call_count, 2)

	def test_sync_sheet_fetches_related_tabs_and_passes_bundle_payload(self):
		processor = self._make_processor()
		sheet_config = types.SimpleNamespace(
			name="Procurement Requisitions",
			spreadsheet_id="sheet-002",
			sheet_name="Purchase Requisitions",
			range="A:Z",
			key_column="pr_no",
			related_sheet_keys=["procurement_pr_items"],
		)
		related_config = types.SimpleNamespace(
			name="Procurement PR Items",
			spreadsheet_id="sheet-002",
			sheet_name="PR Items",
			range="A:Z",
		)
		processor.sheets.fetch_sheet_data = MagicMock(
			side_effect=[
				([{"pr_no": "PR202510"}], "chk-parent"),
				([{"pr_no": "PR202510", "item_code": "CM34"}], "chk-child"),
			]
		)

		processor_mod.get_all_sheet_configs = MagicMock(return_value={"procurement_pr_items": related_config})

		log = processor.sync_sheet(sheet_config, trigger="manual")

		self.assertEqual(log.status, "success")
		self.assertNotEqual(log.data_checksum, "chk-parent")
		call = processor.frappe.sync_sheet_data.call_args
		self.assertEqual(call.args[0], sheet_config)
		self.assertEqual(
			call.kwargs["related_data"],
			{"procurement_pr_items": [{"pr_no": "PR202510", "item_code": "CM34"}]},
		)

	def test_sync_sheet_uses_data_transformer_before_change_tracking(self):
		processor = self._make_processor()
		sheet_config = types.SimpleNamespace(
			name="Inventory",
			spreadsheet_id="sheet-003",
			sheet_name="SUMMARY 2026",
			range="A:Z",
			key_column="inventory_key",
			related_sheet_keys=[],
			data_transformer="inventory_summary_matrix",
		)
		raw_rows = [
			["SOH AS OF", "3/11"],
			["CATEGORY", "ITEM DESCRIPTION", "MATERIAL CODE", "UOM", "3MD", "JENTEC"],
			["", "", "", "", "REMAINING SOH", "REMAINING SOH"],
			["PACKAGING", "16OZ CUP WITH LOGO", "PM001", "BOX", 73, ""],
		]
		transformed_rows = [
			{
				"inventory_key": "3MD::PM001",
				"item_code": "PM001",
				"warehouse": "3MD Logistics - Camangyanan - BEI",
				"qty": 73.0,
			}
		]
		processor.sheets.fetch_sheet_values = MagicMock(return_value=(raw_rows, "raw-001"))
		processor.sheets.compute_checksum = MagicMock(return_value="chk-inventory")
		processor_mod.transform_sheet_rows = MagicMock(return_value=transformed_rows)

		log = processor.sync_sheet(sheet_config, trigger="manual")

		self.assertEqual(log.status, "success")
		processor.sheets.fetch_sheet_values.assert_called_once_with("sheet-003", "SUMMARY 2026!A:Z")
		processor.sheets.fetch_sheet_data.assert_not_called()
		processor_mod.transform_sheet_rows.assert_called_once_with("inventory_summary_matrix", raw_rows)
		processor.change_tracker.compute_changes.assert_called_once()
		self.assertEqual(
			processor.change_tracker.compute_changes.call_args.kwargs["new_data"],
			transformed_rows,
		)
		self.assertEqual(log.data_checksum, "chk-inventory")

	def test_sync_sheet_chunks_inventory_payload_by_warehouse_source_code(self):
		processor = self._make_processor()
		sheet_config = types.SimpleNamespace(
			name="Inventory",
			spreadsheet_id="sheet-003",
			sheet_name="SUMMARY 2026",
			range="A:Z",
			key_column="inventory_key",
			related_sheet_keys=[],
			sync_chunk_field="warehouse_source_code",
		)
		rows = [
			{
				"inventory_key": "3MD::PM001",
				"item_code": "PM001",
				"warehouse_source_code": "3MD",
				"qty": 73.0,
			},
			{
				"inventory_key": "JENTEC::PM001",
				"item_code": "PM001",
				"warehouse_source_code": "JENTEC",
				"qty": 12.0,
			},
			{
				"inventory_key": "3MD::RM015",
				"item_code": "RM015",
				"warehouse_source_code": "3MD",
				"qty": 18.0,
			},
		]
		processor.sheets.fetch_sheet_data = MagicMock(return_value=(rows, "chk-inventory"))
		processor.frappe.sync_sheet_data = MagicMock(
			side_effect=[
				processor_mod.SyncResult(success=True, rows_processed=2, rows_created=2),
				processor_mod.SyncResult(success=True, rows_processed=1, rows_created=1),
			]
		)

		log = processor.sync_sheet(sheet_config, trigger="manual")

		self.assertEqual(log.status, "success")
		self.assertEqual(log.rows_created, 3)
		self.assertEqual(processor.frappe.sync_sheet_data.call_count, 2)
		first_call = processor.frappe.sync_sheet_data.call_args_list[0]
		second_call = processor.frappe.sync_sheet_data.call_args_list[1]
		self.assertEqual(
			[row["warehouse_source_code"] for row in first_call.args[1]],
			["3MD", "3MD"],
		)
		self.assertEqual(
			[row["warehouse_source_code"] for row in second_call.args[1]],
			["JENTEC"],
		)


if __name__ == "__main__":
	unittest.main()
