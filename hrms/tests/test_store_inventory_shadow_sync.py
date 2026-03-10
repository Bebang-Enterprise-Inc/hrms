import importlib.util
import sys
import tempfile
import types
import unittest
from datetime import date
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_frappe():
	frappe = types.ModuleType("frappe")
	frappe.get_site_path = lambda *parts: str(ROOT / "tmp_test_site" / Path(*parts))
	frappe.db = types.SimpleNamespace(exists=lambda *args, **kwargs: None, commit=lambda: None)
	frappe.get_doc = lambda *args, **kwargs: None
	sys.modules["frappe"] = frappe


_install_fake_frappe()
spec = importlib.util.spec_from_file_location(
	"store_inventory_shadow_sync_under_test",
	ROOT / "hrms" / "utils" / "store_inventory_shadow_sync.py",
)
shadow_sync = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules["store_inventory_shadow_sync_under_test"] = shadow_sync
spec.loader.exec_module(shadow_sync)


class TestStoreInventoryShadowSync(unittest.TestCase):
	def test_resolve_current_qty_prefers_encode_then_history_then_blank_zero(self):
		qty, source, inventory_date, detail = shadow_sync._resolve_current_qty(
			{"encode": 7, "total": "", "whole": "", "loose": "", "wt": 1},
			[],
			date(2026, 3, 10),
		)
		self.assertEqual(qty, 7)
		self.assertEqual(source, "encode")
		self.assertEqual(inventory_date, "2026-03-10")
		self.assertEqual(detail, "")

		qty, source, inventory_date, _ = shadow_sync._resolve_current_qty(
			{"encode": "", "total": "", "whole": "", "loose": "", "wt": 1},
			[
				{"inventory_date": "2026-03-08", "end": 4},
				{"inventory_date": "2026-03-09", "end": 6},
				{"inventory_date": "2026-03-11", "end": 8},
			],
			date(2026, 3, 10),
		)
		self.assertEqual(qty, 6)
		self.assertEqual(source, "historical_end")
		self.assertEqual(inventory_date, "2026-03-09")

		qty, source, inventory_date, detail = shadow_sync._resolve_current_qty(
			{"encode": "", "total": "", "whole": "", "loose": "", "wt": 1},
			[],
			date(2026, 3, 10),
		)
		self.assertEqual(qty, 0.0)
		self.assertEqual(source, "blank_zero_policy")
		self.assertEqual(inventory_date, "2026-03-10")
		self.assertIn("zeroed", detail)

	def test_extract_store_inventory_payload_generates_payload_and_exceptions(self):
		workbook = Workbook()
		ws = workbook.active
		ws.title = "3. INVENTORY"
		ws["A1"] = "WT."
		ws["B1"] = "WHOLE"
		ws["C1"] = "LOOSE"
		ws["D1"] = "TOTAL"
		ws["E1"] = "ENCODE"
		ws["F1"] = "2026-03-09"
		ws["F2"] = "BEG"
		ws["G2"] = "IN"
		ws["H2"] = "OUT"
		ws["I2"] = "END"
		ws["J2"] = "CODE"
		ws["K2"] = "ITEMS"
		ws["L2"] = "DESCRIPTION"
		ws["M2"] = "UOM"
		ws["J3"] = "RM-ENC"
		ws["K3"] = "ENC ITEM"
		ws["M3"] = "PIECE"
		ws["A3"] = 1
		ws["E3"] = 3
		ws["J4"] = "RM-HIST"
		ws["K4"] = "HIST ITEM"
		ws["M4"] = "PIECE"
		ws["A4"] = 1
		ws["I4"] = 5
		ws["J5"] = "RM-BLANK"
		ws["K5"] = "BLANK ITEM"
		ws["M5"] = "PIECE"
		ws["A5"] = 1
		ws["J6"] = "RM-ERR"
		ws["K6"] = "ERR ITEM"
		ws["M6"] = "PIECE"
		ws["A6"] = 1
		ws["E6"] = "#REF!"

		with tempfile.TemporaryDirectory() as tmp_dir:
			workbook_path = Path(tmp_dir) / "sample.xlsx"
			workbook.save(workbook_path)

			mapping = {
				"RM-ENC": shadow_sync.ItemMapping(
					inventory_code="RM-ENC",
					inventory_items="ENC ITEM",
					inventory_description="",
					inventory_uom="PIECE",
					resolution_type="exact_live_item",
					target_item_code="RM-ENC",
					target_item_name="ENC ITEM",
					target_stock_uom="PIECE",
					target_item_group="Raw Materials",
					import_policy="import",
					notes="",
				),
				"RM-HIST": shadow_sync.ItemMapping(
					inventory_code="RM-HIST",
					inventory_items="HIST ITEM",
					inventory_description="",
					inventory_uom="PIECE",
					resolution_type="exact_live_item",
					target_item_code="RM-HIST",
					target_item_name="HIST ITEM",
					target_stock_uom="PIECE",
					target_item_group="Raw Materials",
					import_policy="import",
					notes="",
				),
				"RM-BLANK": shadow_sync.ItemMapping(
					inventory_code="RM-BLANK",
					inventory_items="BLANK ITEM",
					inventory_description="",
					inventory_uom="PIECE",
					resolution_type="exact_live_item",
					target_item_code="RM-BLANK",
					target_item_name="BLANK ITEM",
					target_stock_uom="PIECE",
					target_item_group="Raw Materials",
					import_policy="import",
					notes="",
				),
				"RM-ERR": shadow_sync.ItemMapping(
					inventory_code="RM-ERR",
					inventory_items="ERR ITEM",
					inventory_description="",
					inventory_uom="PIECE",
					resolution_type="exact_live_item",
					target_item_code="RM-ERR",
					target_item_name="ERR ITEM",
					target_stock_uom="PIECE",
					target_item_group="Raw Materials",
					import_policy="import",
					notes="",
				),
			}
			config = shadow_sync.StoreSyncConfig(
				store_code="TST",
				store_name="Test Store",
				spreadsheet_id="sheet-1",
				warehouse_name="Test Store",
				warehouse_docname="Test Store - BEI",
			)

			result = shadow_sync.extract_store_inventory_payload(
				config,
				workbook_path,
				mapping,
				date(2026, 3, 10),
			)

		self.assertEqual(len(result["payload_rows"]), 3)
		self.assertEqual(len(result["exception_rows"]), 1)
		by_code = {row["item_code"]: row for row in result["payload_rows"]}
		self.assertEqual(by_code["RM-ENC"]["qty"], 3)
		self.assertEqual(by_code["RM-ENC"]["qty_source"], "encode")
		self.assertEqual(by_code["RM-HIST"]["qty"], 5)
		self.assertEqual(by_code["RM-HIST"]["qty_source"], "historical_end")
		self.assertEqual(by_code["RM-BLANK"]["qty"], 0)
		self.assertEqual(by_code["RM-BLANK"]["qty_source"], "blank_zero_policy")
		self.assertEqual(result["exception_rows"][0]["inventory_code"], "RM-ERR")
		self.assertEqual(result["exception_rows"][0]["classification"], "formula_error")


if __name__ == "__main__":
	unittest.main()
