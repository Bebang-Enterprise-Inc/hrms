"""S212 DEFECT-2 regression tests — SI bills accepted qty on short-receive.

Validates `_reconcile_si_qty_from_wr` behavior via a lightweight in-memory
fake. Covers:

1. `test_full_receive_bills_dispatched` — when WR accepted_qty == dispatched
   qty on every row, SI items are unchanged (no-op, total_adjust == 0).
2. `test_partial_receive_bills_accepted` — when WR accepted_qty < dispatched
   qty on a row, the SI row's qty drops to accepted and amount is
   recomputed as qty * rate.
3. `test_wr_not_found_returns_zero` — when receiving_name doesn't exist,
   no adjustments are made (defensive short-circuit).

Uses `_FakeFrappe` pattern from `test_returns_consistency_s10.py` but
stripped down to just the surfaces _reconcile_si_qty_from_wr touches.
"""
from __future__ import annotations
import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


class _FakeSIItem:
	def __init__(self, item_code: str, qty: float, rate: float):
		self.item_code = item_code
		self.qty = qty
		self.rate = rate
		self.amount = qty * rate


class _FakeSIDoc:
	def __init__(self, name: str, items: list):
		self.doctype = "Sales Invoice"
		self.name = name
		self.items = items
		self.run_method_calls: list[str] = []

	def run_method(self, method_name: str):
		self.run_method_calls.append(method_name)


class _FakeWRItem:
	def __init__(self, item_code: str, accepted_qty: float):
		self.item_code = item_code
		self.accepted_qty = accepted_qty


class _FakeWRDoc:
	def __init__(self, name: str, items: list):
		self.doctype = "BEI Warehouse Receiving"
		self.name = name
		self.items = items


def _install_fake_modules(wr_docs: dict, exists_map: dict | None = None):
	"""Install minimal frappe.* stubs so warehouse.py imports don't blow up."""
	exists_map = exists_map or {}

	frappe_mod = types.ModuleType("frappe")
	frappe_mod.whitelist = lambda *a, **k: (lambda fn: fn)
	frappe_mod._ = lambda s: s

	class _FakeDB:
		def exists(self, doctype, name):
			return exists_map.get((doctype, name), False)

	class _FakeLogger:
		def __init__(self):
			self.messages: list[str] = []

		def info(self, msg):
			self.messages.append(msg)

	fake_db = _FakeDB()
	fake_logger = _FakeLogger()
	frappe_mod.db = fake_db
	frappe_mod.logger = lambda: fake_logger

	def _get_doc(doctype, name):
		if doctype == "BEI Warehouse Receiving" and name in wr_docs:
			return wr_docs[name]
		raise Exception(f"doc {doctype} {name} not mocked")

	frappe_mod.get_doc = _get_doc

	utils_mod = types.ModuleType("frappe.utils")
	utils_mod.cint = int
	utils_mod.flt = float
	utils_mod.now_datetime = lambda: None
	frappe_mod.utils = utils_mod

	sys.modules["frappe"] = frappe_mod
	sys.modules["frappe.utils"] = utils_mod
	return frappe_mod, fake_logger


def _load_reconcile_fn():
	"""Import ONLY the _reconcile_si_qty_from_wr function, isolated from the
	rest of hrms/api/warehouse.py (which has heavy imports).
	"""
	source_path = ROOT / "hrms" / "api" / "warehouse.py"
	text = source_path.read_text(encoding="utf-8")
	# Extract just the function + its helper imports
	import re
	m = re.search(
		r"^def _reconcile_si_qty_from_wr\(.*?(?=^def |^class |\Z)",
		text,
		re.M | re.S,
	)
	if not m:
		raise RuntimeError("_reconcile_si_qty_from_wr not found")
	fn_source = m.group(0)
	# Compile the function against the fake frappe module
	ns: dict = {
		"frappe": sys.modules["frappe"],
		"flt": float,
	}
	exec(fn_source, ns)
	return ns["_reconcile_si_qty_from_wr"]


class ReconcileSIQtyTest(unittest.TestCase):
	def setUp(self):
		# Drop any previously-imported frappe from a sibling test
		for m in ("frappe", "frappe.utils"):
			sys.modules.pop(m, None)

	def test_full_receive_bills_dispatched(self):
		"""Accepted == dispatched → no SI mutation, no adjust count."""
		wr = _FakeWRDoc("WR-001", [
			_FakeWRItem("ITEM-A", 10.0),
			_FakeWRItem("ITEM-B", 5.0),
		])
		exists = {("BEI Warehouse Receiving", "WR-001"): True}
		_install_fake_modules({"WR-001": wr}, exists)
		fn = _load_reconcile_fn()
		si = _FakeSIDoc("SI-001", [
			_FakeSIItem("ITEM-A", qty=10.0, rate=100.0),
			_FakeSIItem("ITEM-B", qty=5.0, rate=50.0),
		])
		n = fn(si, "WR-001")
		self.assertEqual(n, 0)
		self.assertEqual(si.items[0].qty, 10.0)
		self.assertEqual(si.items[0].amount, 1000.0)
		self.assertEqual(si.items[1].qty, 5.0)
		self.assertEqual(si.items[1].amount, 250.0)
		self.assertEqual(si.run_method_calls, [])

	def test_partial_receive_bills_accepted(self):
		"""Accepted = 8 < dispatched = 10 → SI qty drops to 8, amount = 8 * rate."""
		wr = _FakeWRDoc("WR-002", [
			_FakeWRItem("ITEM-A", 8.0),  # accepted 8 of dispatched 10
		])
		exists = {("BEI Warehouse Receiving", "WR-002"): True}
		_install_fake_modules({"WR-002": wr}, exists)
		fn = _load_reconcile_fn()
		si = _FakeSIDoc("SI-002", [
			_FakeSIItem("ITEM-A", qty=10.0, rate=100.0),
		])
		n = fn(si, "WR-002")
		self.assertEqual(n, 1)
		self.assertEqual(si.items[0].qty, 8.0)
		self.assertEqual(si.items[0].amount, 800.0)
		self.assertEqual(si.run_method_calls, ["calculate_taxes_and_totals"])

	def test_wr_not_found_returns_zero(self):
		"""WR doesn't exist → no mutation, return 0."""
		_install_fake_modules({}, exists_map={})
		fn = _load_reconcile_fn()
		si = _FakeSIDoc("SI-003", [
			_FakeSIItem("ITEM-A", qty=10.0, rate=100.0),
		])
		n = fn(si, "WR-MISSING")
		self.assertEqual(n, 0)
		self.assertEqual(si.items[0].qty, 10.0)


if __name__ == "__main__":
	unittest.main()
