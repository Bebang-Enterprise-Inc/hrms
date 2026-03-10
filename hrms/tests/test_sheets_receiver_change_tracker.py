import importlib.util
import sqlite3
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

change_tracker_spec = importlib.util.spec_from_file_location(
	"sheets_receiver_change_tracker_under_test",
	ROOT / "hrms" / "services" / "sheets_receiver" / "change_tracker.py",
)
change_tracker = importlib.util.module_from_spec(change_tracker_spec)
change_tracker_spec.loader.exec_module(change_tracker)
ChangeTracker = change_tracker.ChangeTracker


class _FakeDB:
	def __init__(self):
		self.conn = sqlite3.connect(":memory:")
		self.conn.row_factory = sqlite3.Row

	@contextmanager
	def _connection(self):
		try:
			yield self.conn
			self.conn.commit()
		except Exception:
			self.conn.rollback()
			raise


class TestSheetsReceiverChangeTracker(unittest.TestCase):
	def test_compute_changes_handles_duplicate_and_blank_keys(self):
		db = _FakeDB()
		tracker = ChangeTracker(db)
		rows = [
			{"invoice_no.": "", "supplier_name": "ALYANA CHUA", "amount": 20300},
			{"invoice_no.": "16538", "supplier_name": "FORWARD DYNAMIC", "amount": 10500},
			{"invoice_no.": "16538", "supplier_name": "FORWARD DYNAMIC", "amount": 8500},
		]

		first = tracker.compute_changes(
			spreadsheet_id="sheet-1",
			spreadsheet_name="Supplier SOA",
			sheet_name="SUPPLIERS SOA",
			new_data=rows,
			key_column="invoice_no.",
		)
		second = tracker.compute_changes(
			spreadsheet_id="sheet-1",
			spreadsheet_name="Supplier SOA",
			sheet_name="SUPPLIERS SOA",
			new_data=rows,
			key_column="invoice_no.",
		)

		self.assertEqual(first.rows_added, 3)
		self.assertEqual(second.rows_added, 0)
		self.assertEqual(second.rows_modified, 0)
		self.assertEqual(second.rows_unchanged, 3)

		with db._connection() as conn:
			stored_keys = [
				row["row_key"]
				for row in conn.execute(
					"SELECT row_key FROM data_snapshots WHERE spreadsheet_id = ? AND sheet_name = ? ORDER BY row_number",
					("sheet-1", "SUPPLIERS SOA"),
				).fetchall()
			]

		self.assertEqual(stored_keys, ["__row_2", "16538__row_3", "16538__row_4"])


if __name__ == "__main__":
	unittest.main()
