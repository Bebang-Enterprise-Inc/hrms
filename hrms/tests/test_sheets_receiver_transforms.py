import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


transforms_spec = importlib.util.spec_from_file_location(
	"sheets_receiver_transforms_under_test",
	ROOT / "hrms" / "services" / "sheets_receiver" / "transforms.py",
)
transforms = importlib.util.module_from_spec(transforms_spec)
assert transforms_spec and transforms_spec.loader
transforms_spec.loader.exec_module(transforms)


class TestSheetsReceiverTransforms(unittest.TestCase):
	def test_inventory_summary_matrix_pivots_warehouse_columns_and_zero_fills_blanks(self):
		raw_rows = [
			["SOH AS OF", "3/11"],
			[
				"CATEGORY",
				"ITEM DESCRIPTION",
				"MATERIAL CODE",
				"UOM",
				"3MD",
				"JENTEC",
				"RCS",
				"PINNACLE",
				"SHAW",
				"TOTAL",
			],
			[
				"",
				"",
				"",
				"",
				"REMAINING SOH",
				"REMAINING SOH",
				"REMAINING SOH",
				"REMAINING SOH",
				"REMAINING SOH",
			],
			["", "DRY"],
			["PACKAGING", "16OZ CUP WITH LOGO", "PM001", "BOX", 73, "", "", 23, "", 96],
			["RAW MATERIAL", "BLUEBERRY SYRUP", "RM015", "BOTTLE", 220, "", "-", 116, "", 336],
		]

		rows = transforms.transform_sheet_rows("inventory_summary_matrix", raw_rows)

		self.assertEqual(len(rows), 10)
		self.assertEqual(rows[0]["inventory_key"], "3MD::PM001")
		self.assertEqual(rows[0]["warehouse"], "3MD Logistics – Camangyanan")
		self.assertEqual(rows[0]["qty"], 73.0)
		self.assertEqual(rows[1]["warehouse"], "Jentec Storage Inc.")
		self.assertEqual(rows[1]["qty"], 0.0)
		self.assertEqual(rows[3]["warehouse"], "Pinnacle Cold Storage Solutions")
		self.assertEqual(rows[3]["qty"], 23.0)
		self.assertEqual(rows[4]["warehouse"], "Shaw BLVD")
		self.assertEqual(rows[4]["qty"], 0.0)
		self.assertEqual(rows[5]["inventory_key"], "3MD::RM015")
		self.assertEqual(rows[7]["warehouse"], "Royal Cold Storage – Taytay (RCS)")
		self.assertEqual(rows[7]["qty"], 0.0)

	def test_inventory_summary_matrix_raises_when_expected_warehouses_are_missing(self):
		raw_rows = [
			["SOH AS OF", "3/11"],
			["CATEGORY", "ITEM DESCRIPTION", "MATERIAL CODE", "UOM", "3MD", "JENTEC"],
			["", "", "", "", "REMAINING SOH", "REMAINING SOH"],
			["PACKAGING", "16OZ CUP WITH LOGO", "PM001", "BOX", 73, ""],
		]

		with self.assertRaisesRegex(ValueError, "missing expected warehouse columns"):
			transforms.transform_sheet_rows("inventory_summary_matrix", raw_rows)

	def test_ar_aging_table_normalizes_receivables_rows_and_generates_stable_keys(self):
		raw_rows = [
			["TOTAL BALANCE", 12345],
			[
				"BILLED BY:",
				"DATE BILLED",
				"",
				"TYPE BILLINGS",
				"PARTICULARS",
				"PERIOD",
				"BILLED AMOUNT",
				"AMOUNT PAID",
				"NET RECEIVABLES",
				"STATUS",
				"overdue",
				"AGING (days)",
				"REMARKS",
				"0-30",
				"31-60",
				"61-90",
				"91-120",
				"over 120",
			],
			[
				"IVY",
				"January 20, 2026",
				"BF Homes",
				"OTHERS",
				"Event Billing",
				"",
				"1000",
				"250",
				"750",
				"OPEN",
				"YES",
				"15",
				"",
				"750",
				"",
				"",
				"",
				"",
			],
		]

		rows = transforms.transform_sheet_rows("ar_aging_table", raw_rows)

		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["store"], "BF Homes")
		self.assertEqual(rows[0]["net_receivables"], 750.0)
		self.assertEqual(rows[0]["aging_days"], 15)
		self.assertEqual(
			rows[0]["ar_entry_key"],
			"January 20, 2026::BF Homes::OTHERS::Event Billing::1000.0",
		)

	def test_ar_aging_table_raises_when_receivables_header_is_missing(self):
		raw_rows = [["TOTAL BALANCE", 12345], ["wrong", "headers"]]

		with self.assertRaisesRegex(ValueError, "missing the expected receivables header row"):
			transforms.transform_sheet_rows("ar_aging_table", raw_rows)


if __name__ == "__main__":
	unittest.main()
