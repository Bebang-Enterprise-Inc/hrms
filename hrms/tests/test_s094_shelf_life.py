# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Sprint S094 Phase 2 Tests — Shelf Life Hard Gate
Tests: expired batch blocking, override with supervisor, min shelf life config, wiring

Uses source-level inspection to avoid Frappe import chain in test env.
"""

import json
import os
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read_source(rel_path):
	with open(os.path.join(REPO_ROOT, rel_path), encoding="utf-8") as f:
		return f.read()


def _extract_function(source, func_name):
	marker = f"def {func_name}("
	idx = source.find(marker)
	if idx == -1:
		return None
	end_idx = source.find("\ndef ", idx + 1)
	return source[idx : end_idx if end_idx != -1 else len(source)]


def _read_json(rel_path):
	with open(os.path.join(REPO_ROOT, rel_path), encoding="utf-8") as f:
		return json.load(f)


class TestShelfLifeGateFunction(unittest.TestCase):
	"""UX-010: _validate_shelf_life_gate helper."""

	@classmethod
	def setUpClass(cls):
		cls.source = _read_source("hrms/api/commissary_dashboard.py")

	def test_validate_shelf_life_gate_exists(self):
		"""Helper function exists in commissary_dashboard.py."""
		func = _extract_function(self.source, "_validate_shelf_life_gate")
		self.assertIsNotNone(func, "_validate_shelf_life_gate not found")

	def test_gate_checks_expiry_date(self):
		"""Gate compares batch expiry_date against action_date."""
		func = _extract_function(self.source, "_validate_shelf_life_gate")
		self.assertIn("expiry_date", func)
		self.assertIn("action_date", func)

	def test_gate_reads_min_shelf_life_setting(self):
		"""Gate reads min_shelf_life_days from BEI Settings."""
		func = _extract_function(self.source, "_validate_shelf_life_gate")
		self.assertIn("min_shelf_life_days", func)
		self.assertIn("BEI Settings", func)

	def test_gate_returns_requires_override(self):
		"""Gate returns requires_override flag when blocking."""
		func = _extract_function(self.source, "_validate_shelf_life_gate")
		self.assertIn("requires_override", func)

	def test_gate_handles_no_batch(self):
		"""Gate passes when batch_no is None."""
		func = _extract_function(self.source, "_validate_shelf_life_gate")
		self.assertIn("not batch_no", func)

	def test_gate_handles_no_expiry(self):
		"""Gate passes when batch has no expiry_date."""
		func = _extract_function(self.source, "_validate_shelf_life_gate")
		self.assertIn("not batch.expiry_date", func)

	def test_date_diff_imported(self):
		"""date_diff is imported in commissary_dashboard.py."""
		# Find the import line
		for line in self.source.split("\n")[:20]:
			if "from frappe.utils import" in line and "date_diff" in line:
				return
		self.fail("date_diff not found in imports")


class TestShelfLifeOverride(unittest.TestCase):
	"""UX-010: Supervisor override for shelf life gate."""

	@classmethod
	def setUpClass(cls):
		cls.source = _read_source("hrms/api/commissary_dashboard.py")

	def test_override_function_exists(self):
		"""override_shelf_life_gate function exists."""
		func = _extract_function(self.source, "override_shelf_life_gate")
		self.assertIsNotNone(func, "override_shelf_life_gate not found")

	def test_override_requires_commissary_supervisor(self):
		"""Override checks for Commissary Supervisor role."""
		func = _extract_function(self.source, "override_shelf_life_gate")
		self.assertIn("Commissary Supervisor", func)

	def test_override_requires_reason(self):
		"""Override requires a reason string."""
		func = _extract_function(self.source, "override_shelf_life_gate")
		self.assertIn("reason", func)

	def test_override_creates_audit_trail(self):
		"""Override creates a Comment for audit."""
		func = _extract_function(self.source, "override_shelf_life_gate")
		self.assertIn("Comment", func)
		self.assertIn("Shelf life override", func)

	def test_override_is_whitelisted(self):
		"""Override function has @frappe.whitelist() decorator."""
		idx = self.source.find("def override_shelf_life_gate(")
		preceding = self.source[max(0, idx - 100) : idx]
		self.assertIn("@frappe.whitelist()", preceding)


class TestShelfLifeWiring(unittest.TestCase):
	"""UX-010: Shelf life gate wired into dispatch and receiving."""

	def test_commissary_dispatch_has_gate(self):
		"""submit_production_output includes shelf life validation."""
		source = _read_source("hrms/api/commissary_dashboard.py")
		func = _extract_function(source, "submit_production_output")
		self.assertIn("_validate_shelf_life_gate", func)

	def test_commissary_dispatch_has_override_param(self):
		"""submit_production_output accepts override_approved."""
		source = _read_source("hrms/api/commissary_dashboard.py")
		func = _extract_function(source, "submit_production_output")
		sig_lines = func.split("\n")[:8]
		sig_text = "\n".join(sig_lines)
		self.assertIn("override_approved", sig_text)

	def test_warehouse_receiving_has_gate(self):
		"""create_warehouse_receiving includes shelf life check."""
		source = _read_source("hrms/api/warehouse.py")
		func = _extract_function(source, "create_warehouse_receiving")
		self.assertIn("_validate_shelf_life_gate", func)

	def test_store_receiving_has_gate(self):
		"""complete_receiving includes shelf life check."""
		source = _read_source("hrms/api/store.py")
		func = _extract_function(source, "complete_receiving")
		self.assertIn("_validate_shelf_life_gate", func)


class TestBEISettingsField(unittest.TestCase):
	"""Phase 0: min_shelf_life_days field in BEI Settings."""

	def test_min_shelf_life_days_field_exists(self):
		"""BEI Settings has min_shelf_life_days field."""
		data = _read_json("hrms/hr/doctype/bei_settings/bei_settings.json")
		field_names = [f["fieldname"] for f in data["fields"]]
		self.assertIn("min_shelf_life_days", field_names)

	def test_min_shelf_life_days_is_int(self):
		"""min_shelf_life_days is Int type."""
		data = _read_json("hrms/hr/doctype/bei_settings/bei_settings.json")
		field = next(f for f in data["fields"] if f["fieldname"] == "min_shelf_life_days")
		self.assertEqual(field["fieldtype"], "Int")

	def test_min_shelf_life_days_default_is_7(self):
		"""min_shelf_life_days defaults to 7."""
		data = _read_json("hrms/hr/doctype/bei_settings/bei_settings.json")
		field = next(f for f in data["fields"] if f["fieldname"] == "min_shelf_life_days")
		self.assertEqual(field["default"], "7")


class TestWarehouseReceivingChildField(unittest.TestCase):
	"""Phase 0: check_expiry field in BEI Warehouse Receiving Item."""

	def test_check_expiry_field_exists(self):
		"""BEI Warehouse Receiving Item has check_expiry field."""
		data = _read_json("hrms/hr/doctype/bei_warehouse_receiving_item/bei_warehouse_receiving_item.json")
		field_names = [f["fieldname"] for f in data["fields"]]
		self.assertIn("check_expiry", field_names)

	def test_check_expiry_in_field_order(self):
		"""check_expiry is in field_order."""
		data = _read_json("hrms/hr/doctype/bei_warehouse_receiving_item/bei_warehouse_receiving_item.json")
		self.assertIn("check_expiry", data["field_order"])


if __name__ == "__main__":
	unittest.main()
