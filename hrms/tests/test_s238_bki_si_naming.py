"""S238 v2.2 — unit tests for hrms/api/bki_si_naming.py autoname hook.

4 tests verifying BKI Sales Invoice naming convention:
  Test A: BKI SI w/ valid order  -> 'BKI-SI-{YYYY}-{tail}-1'
  Test B: 2nd SI for same order  -> 'BKI-SI-{YYYY}-{tail}-2'
  Test C: BKI SI w/o order link  -> 'BKI-SI-MISC-{YYYY}-####'
  Test D: Non-BKI company SI     -> autoname no-op (Frappe naming_series fallback)
"""
from __future__ import annotations

import re
import unittest

import frappe

from hrms.api.bki_si_naming import _ORDER_PATTERN, set_bki_si_name


class _FakeDoc:
	"""Minimal stand-in for a Frappe Sales Invoice document."""

	def __init__(self, company, custom_bei_store_order=None, name=None):
		self.company = company
		self.custom_bei_store_order = custom_bei_store_order
		self.name = name


class TestS238BkiSiNaming(unittest.TestCase):
	def test_a_bki_si_with_order(self):
		"""BKI SI with valid order -> BKI-SI-2026-00903-1."""
		doc = _FakeDoc(
			company="BEBANG KITCHEN INC.",
			custom_bei_store_order="BEI-ORD-2026-00903",
			name=None,
		)
		# Stub frappe.db.count to return 0 (no existing SIs for this order)
		original_count = frappe.db.count
		try:
			frappe.db.count = lambda dt, filters: 0
			set_bki_si_name(doc)
			self.assertEqual(doc.name, "BKI-SI-2026-00903-1")
		finally:
			frappe.db.count = original_count

	def test_b_second_si_same_order(self):
		"""2nd SI for the same order -> BKI-SI-2026-00903-2."""
		doc = _FakeDoc(
			company="BEBANG KITCHEN INC.",
			custom_bei_store_order="BEI-ORD-2026-00903",
			name=None,
		)
		original_count = frappe.db.count
		try:
			frappe.db.count = lambda dt, filters: 1  # one existing SI
			set_bki_si_name(doc)
			self.assertEqual(doc.name, "BKI-SI-2026-00903-2")
		finally:
			frappe.db.count = original_count

	def test_c_bki_si_no_order(self):
		"""BKI SI without order link -> MISC fallback BKI-SI-MISC-{YYYY}-####."""
		doc = _FakeDoc(
			company="BEBANG KITCHEN INC.",
			custom_bei_store_order="",
			name=None,
		)
		set_bki_si_name(doc)
		# Frappe's make_autoname returns BKI-SI-MISC-2026-NNNN where N is the running counter
		self.assertIsNotNone(doc.name)
		self.assertRegex(doc.name, r"^BKI-SI-MISC-\d{4}-\d{4,}$")

	def test_d_non_bki_company_unaffected(self):
		"""Non-BKI company SI -> autoname is a no-op; doc.name stays None."""
		doc = _FakeDoc(
			company="ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC",
			custom_bei_store_order="BEI-ORD-2026-00903",
			name=None,
		)
		set_bki_si_name(doc)
		# Hook returns without setting name; Frappe falls back to naming_series
		self.assertIsNone(doc.name)

	def test_e_order_pattern_regex(self):
		"""Bonus: regex pattern correctness."""
		valid_cases = [
			("BEI-ORD-2026-00903", ("2026", "00903")),
			("BEI-ORD-2025-00001", ("2025", "00001")),
			("BEI-ORD-2026-12345678", ("2026", "12345678")),  # tail can grow
		]
		for order, (year, tail) in valid_cases:
			m = _ORDER_PATTERN.match(order)
			self.assertIsNotNone(m, f"Should match: {order}")
			self.assertEqual(m.group(1), year)
			self.assertEqual(m.group(2), tail)

		invalid_cases = [
			"BEI-ORD-2026-",          # empty tail
			"BEI-ORD-26-00903",       # 2-digit year
			"BEI-ORD-2026-00903 ",    # trailing space (caller strips, regex doesn't)
			"BEI-ORDER-2026-00903",   # wrong prefix
			"",                        # empty
		]
		for order in invalid_cases:
			m = _ORDER_PATTERN.match(order)
			self.assertIsNone(m, f"Should NOT match: {order!r}")
