import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


config_spec = importlib.util.spec_from_file_location(
	"sheets_receiver_config_under_test",
	ROOT / "hrms" / "services" / "sheets_receiver" / "config.py",
)
config = importlib.util.module_from_spec(config_spec)
config_spec.loader.exec_module(config)


class TestSheetsReceiverConfig(unittest.TestCase):
	def test_ap_opening_balance_uses_supplier_soa_tab(self):
		ap_config = config.get_sheet_config("ap_opening_balance")
		supplier_soa_config = config.get_sheet_config("supplier_soa")

		self.assertIsNotNone(ap_config)
		self.assertIsNotNone(supplier_soa_config)
		self.assertEqual(ap_config.sheet_name, "SUPPLIERS SOA")
		self.assertEqual(ap_config.sheet_name, supplier_soa_config.sheet_name)
		self.assertEqual(ap_config.range, "A2:Z")
		self.assertEqual(supplier_soa_config.range, "A2:Z")
		self.assertEqual(ap_config.key_column, "invoice_no.")
		self.assertEqual(supplier_soa_config.key_column, "invoice_no.")
		self.assertTrue(ap_config.enabled)
		self.assertFalse(supplier_soa_config.enabled)

	def test_inventory_uses_active_march_workbook_and_matrix_transformer(self):
		inventory_config = config.get_sheet_config("inventory")

		self.assertIsNotNone(inventory_config)
		self.assertEqual(
			inventory_config.spreadsheet_id,
			"19Hm25vaj9gD8p6z_M6-4CPWvcXaPzAeOFKlUZ298V4s",
		)
		self.assertEqual(inventory_config.sheet_name, "SUMMARY 2026")
		self.assertEqual(inventory_config.key_column, "inventory_key")
		self.assertEqual(inventory_config.data_transformer, "inventory_summary_matrix")
		self.assertEqual(inventory_config.sync_mode, "replace")


if __name__ == "__main__":
	unittest.main()
