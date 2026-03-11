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


if __name__ == "__main__":
	unittest.main()
