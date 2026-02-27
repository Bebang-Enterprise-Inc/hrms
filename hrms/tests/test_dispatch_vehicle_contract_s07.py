# Copyright (c) 2026, Frappe Technologies Pvt. Ltd.
# For license information, please see license.txt

"""Sprint 07 contract checks for warehouse vehicle + variance APIs."""

from unittest import TestCase
from unittest.mock import patch


class TestDispatchVehicleContractS07(TestCase):
    """Lock contract shape used by trip/warehouse UI flows."""

    @patch("hrms.api.dispatch.frappe.get_all")
    @patch("hrms.api.dispatch._check_scm_permission")
    def test_get_vehicles_returns_object_and_flat_contract(self, _mock_perm, mock_get_all):
        from hrms.api.dispatch import get_vehicles

        mock_get_all.return_value = [
            {"name": "VEH-001", "vehicle_plate": "ABC 123"},
            {"name": "VEH-002", "vehicle_plate": "XYZ 789"},
        ]

        result = get_vehicles()

        self.assertIn("vehicles", result)
        self.assertIn("vehicle_names", result)
        self.assertIn("data", result)
        self.assertEqual(result["vehicle_names"], ["VEH-001", "VEH-002"])
        self.assertEqual(result["data"], ["VEH-001", "VEH-002"])
        self.assertEqual(len(result["vehicles"]), 2)

    def test_inventory_variance_resolution_contract_is_explicit(self):
        from hrms.api.inventory import get_variance_resolution_contract

        result = get_variance_resolution_contract()
        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "resolve_variance")
        self.assertIn("variance_name", result["required_fields"])
        self.assertIn("resolution_type", result["required_fields"])
        self.assertIn("resolution_notes", result["required_fields"])
        self.assertIn("System Error", result["resolution_types"])
