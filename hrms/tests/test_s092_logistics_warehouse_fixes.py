"""S092 — Logistics & Warehouse Bug Fixes.

Tests for FIX-2 (trip role), FIX-3 (transfer guard), FIX-4 (full rejection),
FIX-5 (zero-qty display), and _run_as_system_user removal.

Uses source-code inspection since Frappe framework is not available locally.
"""

import os
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read_source(rel_path):
	with open(os.path.join(REPO_ROOT, rel_path), encoding="utf-8") as f:
		return f.read()


def _extract_function(source, func_name):
	"""Extract a function body from source text."""
	marker = f"def {func_name}("
	idx = source.find(marker)
	if idx == -1:
		return None
	end_idx = source.find("\ndef ", idx + 1)
	return source[idx : end_idx if end_idx != -1 else len(source)]


class TestTripCreationRole(unittest.TestCase):
	"""FIX-2: create_trip should use SCM_DISPATCH_ROLES, not SCM_ADMIN_ROLES."""

	def test_create_trip_uses_dispatch_roles(self):
		source = _read_source("hrms/api/dispatch.py")
		func = _extract_function(source, "create_trip")
		self.assertIsNotNone(func, "create_trip function not found")
		self.assertIn("SCM_DISPATCH_ROLES", func)
		self.assertNotIn("SCM_ADMIN_ROLES", func)


class TestTransferSourceWarehouseGuard(unittest.TestCase):
	"""FIX-3A: create_stock_transfer must reject blank source_warehouse."""

	def test_blank_source_warehouse_guard_exists(self):
		source = _read_source("hrms/api/warehouse.py")
		func = _extract_function(source, "create_stock_transfer")
		self.assertIsNotNone(func)
		self.assertIn("source warehouse", func.lower())


class TestFullRejection(unittest.TestCase):
	"""FIX-4: 100% rejected items should set 'With Issues', not throw."""

	def test_full_rejection_uses_with_issues_status(self):
		source = _read_source("hrms/api/warehouse.py")
		func = _extract_function(source, "complete_warehouse_receiving")
		self.assertIsNotNone(func)
		self.assertIn('"With Issues"', func)

	def test_full_rejection_does_not_use_rejected_status(self):
		source = _read_source("hrms/api/warehouse.py")
		func = _extract_function(source, "complete_warehouse_receiving")
		self.assertIsNotNone(func)
		# "Rejected" as a status assignment should not exist
		# (it appears in variable names like rejected_qty which is fine)
		self.assertNotIn('.status = "Rejected"', func)


class TestRunAsSystemUserRemoved(unittest.TestCase):
	"""FIX-3C/FIX-4b: _run_as_system_user removed from stock operations."""

	def test_no_run_as_system_user_in_complete_receiving(self):
		source = _read_source("hrms/api/warehouse.py")
		func = _extract_function(source, "complete_warehouse_receiving")
		self.assertIsNotNone(func)
		self.assertNotIn("_run_as_system_user", func)

	def test_no_run_as_system_user_in_create_stock_transfer(self):
		source = _read_source("hrms/api/warehouse.py")
		func = _extract_function(source, "create_stock_transfer")
		self.assertIsNotNone(func)
		self.assertNotIn("_run_as_system_user", func)


class TestZeroQuantityDisplay(unittest.TestCase):
	"""FIX-5: Blank from_warehouse should resolve via commissary warehouse fallback."""

	def test_commissary_warehouse_fallback_exists(self):
		source = _read_source("hrms/api/warehouse.py")
		func = _extract_function(source, "get_material_request_items")
		self.assertIsNotNone(func)
		self.assertIn("commissary_warehouse", func)

	def test_sum_all_warehouses_fallback(self):
		source = _read_source("hrms/api/warehouse.py")
		func = _extract_function(source, "get_material_request_items")
		self.assertIsNotNone(func)
		self.assertIn("SUM(actual_qty)", func)


if __name__ == "__main__":
	unittest.main()
