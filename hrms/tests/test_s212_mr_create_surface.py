"""S212 DEFECT-1 regression tests — MR-create error surfacing + commit visibility.

Validates three behaviors against hrms/api/store.py source:

1. `_create_mr_for_store_order` re-raises from its except block (does NOT
   return None silently). Set by S163 audit fix; locked in here so a later
   refactor cannot silently undo it.
2. `_create_mr_for_store_order` calls `frappe.db.commit()` after `mr.submit()`
   and before `return mr.name`. S212 fix — forces MariaDB commit visibility
   before whitelist returns so REST readers don't race the insert on a
   separate connection.
3. `approve_order` verifies the MR row exists via `frappe.db.exists` after
   `_create_mr_for_store_order` returns a name. S212 fix — guards against
   savepoint/commit drift where the function returns a name but the row
   never materialized.

Tests inspect source directly because `_create_mr_for_store_order` and
`approve_order` depend on a large import graph; full live-Frappe mocking
yields no additional coverage over source verification for these
particular defects.
"""
from __future__ import annotations
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STORE_PY = ROOT / "hrms" / "api" / "store.py"


def _read_source() -> str:
	return STORE_PY.read_text(encoding="utf-8")


def _find_function(src: str, name: str) -> str:
	"""Extract the source of function `name` up to the next top-level def/class."""
	pattern = re.compile(
		rf"^(def {re.escape(name)}\b.*?)(?=^def |^class |\Z)",
		re.M | re.S,
	)
	m = pattern.search(src)
	return m.group(1) if m else ""


class MRCreateReRaiseTest(unittest.TestCase):
	"""Re-raise + commit-visibility for _create_mr_for_store_order."""

	def setUp(self):
		src = _read_source()
		self.fn = _find_function(src, "_create_mr_for_store_order")
		self.assertTrue(self.fn, "could not locate _create_mr_for_store_order")

	def test_mr_insert_raises_propagates(self):
		self.assertIn("except Exception as e:", self.fn)
		except_block = self.fn.split("except Exception as e:", 1)[1]
		self.assertIn(
			"raise",
			except_block,
			"S212 regression: except block must re-raise, not swallow",
		)
		self.assertNotIn(
			"return None",
			except_block,
			"S212 regression: except block must not return None silently",
		)

	def test_mr_submit_commits_before_return(self):
		try_body = self.fn.split("mr.submit()", 1)[1]
		return_idx = try_body.find("return mr.name")
		self.assertGreater(return_idx, 0, "could not locate 'return mr.name' after submit")
		head = try_body[:return_idx]
		self.assertIn(
			"frappe.db.commit()",
			head,
			"S212 DEFECT-1: expected frappe.db.commit() after mr.submit() and before return",
		)


class ApproveOrderVerifiesMRTest(unittest.TestCase):
	"""approve_order asserts MR row exists after _create_mr_for_store_order."""

	def setUp(self):
		src = _read_source()
		self.fn = _find_function(src, "approve_order")
		self.assertTrue(self.fn, "could not locate approve_order")

	def test_approve_order_verifies_mr_exists(self):
		self.assertRegex(
			self.fn,
			r"frappe\.db\.exists\(\s*[\"']Material Request[\"']",
			"S212 DEFECT-1: expected frappe.db.exists('Material Request', ...) check in approve_order",
		)
		create_idx = self.fn.find("_create_mr_for_store_order(order)")
		exists_idx = self.fn.find('frappe.db.exists("Material Request"')
		if exists_idx < 0:
			exists_idx = self.fn.find("frappe.db.exists('Material Request'")
		self.assertGreater(create_idx, 0, "callsite _create_mr_for_store_order(order) missing")
		self.assertGreater(
			exists_idx,
			create_idx,
			"S212: exists() check must come AFTER the MR creation call",
		)


if __name__ == "__main__":
	unittest.main()
