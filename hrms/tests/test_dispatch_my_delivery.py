# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Unit tests for Delivery Trip Tracking enhancements (Phase 1A)
"""

import frappe
from frappe.utils import today, add_days, now_datetime, add_to_date, get_datetime
import unittest


class TestDispatchMyDelivery(unittest.TestCase):
    """Test get_my_delivery endpoint and ETA calculations"""

    @classmethod
    def setUpClass(cls):
        """Create test data once for all tests"""
        # Create test warehouse
        if not frappe.db.exists("Warehouse", "Test Store Delivery - BEI"):
            warehouse = frappe.get_doc({
                "doctype": "Warehouse",
                "warehouse_name": "Test Store Delivery",
                "company": "BEI",
                "is_group": 0
            })
            warehouse.insert(ignore_permissions=True)

        # Create test employee linked to test user
        if not frappe.db.exists("Employee", {"user_id": "test.delivery@bebang.ph"}):
            employee = frappe.get_doc({
                "doctype": "Employee",
                "employee_name": "Test Delivery User",
                "user_id": "test.delivery@bebang.ph",
                "status": "Active",
                "branch": "Test Store Delivery - BEI"
            })
            employee.insert(ignore_permissions=True)

        frappe.db.commit()

    def tearDown(self):
        """Clean up test trips after each test"""
        frappe.db.sql("DELETE FROM `tabBEI Distribution Trip` WHERE route_name LIKE 'TEST-%'")
        frappe.db.commit()

    def _create_test_trip(self, status="In Transit", include_my_store=True, departure_time=None):
        """Helper to create a test trip"""
        trip = frappe.get_doc({
            "doctype": "BEI Distribution Trip",
            "trip_date": today(),
            "route_name": "TEST-ROUTE-001",
            "driver": "Test Driver",
            "vehicle_plate": "TEST 123",
            "status": status,
            "departure_time": departure_time or now_datetime()
        })

        # Add stops
        if include_my_store:
            trip.append("stops", {
                "store": "Test Store Delivery - BEI",
                "stop_order": 3,
                "items_count": 10,
                "status": "Pending"
            })

        # Add other stops
        trip.append("stops", {
            "store": "Other Store - BEI",
            "stop_order": 1,
            "items_count": 5,
            "status": "Delivered"
        })

        trip.append("stops", {
            "store": "Another Store - BEI",
            "stop_order": 2,
            "items_count": 8,
            "status": "Delivered"
        })

        trip.insert(ignore_permissions=True)
        frappe.db.commit()
        return trip

    def test_get_my_delivery_returns_correct_structure(self):
        """Test that get_my_delivery returns the expected data structure"""
        # Create trip with my store
        self._create_test_trip()

        # Set user
        frappe.set_user("test.delivery@bebang.ph")

        # Call endpoint
        from hrms.api.dispatch import get_my_delivery
        result = get_my_delivery()

        # Verify structure
        self.assertTrue(result.get("ok"))
        self.assertIn("trip", result)
        trip = result["trip"]
        self.assertEqual(trip["driver"], "Test Driver")
        self.assertEqual(trip["vehicle_plate"], "TEST 123")
        self.assertEqual(trip["status"], "In Transit")
        self.assertIn("my_stop", trip)

        my_stop = trip["my_stop"]
        self.assertEqual(my_stop["stop_order"], 3)
        self.assertEqual(my_stop["status"], "Pending")
        self.assertIsNotNone(my_stop["eta_minutes"])
        self.assertIn("items_preview", my_stop)

        # Verify cs_phone is present
        self.assertIn("cs_phone", result)

    def test_eta_calculation_with_departure(self):
        """Test ETA calculation when trip has departed"""
        # Create trip that departed 30 minutes ago
        departure = add_to_date(now_datetime(), minutes=-30)
        trip = self._create_test_trip(departure_time=departure)

        frappe.set_user("test.delivery@bebang.ph")

        from hrms.api.dispatch import get_my_delivery
        result = get_my_delivery()

        # My stop is #3, stops #1 and #2 are delivered
        # So 1 stop remaining * 20 min = 20 min ETA
        my_stop = result["trip"]["my_stop"]
        self.assertEqual(my_stop["eta_minutes"], 20)
        self.assertIsNotNone(my_stop["eta_window"])
        self.assertIn("min", my_stop["eta_window"])
        self.assertIn("max", my_stop["eta_window"])

    def test_eta_calculation_without_departure(self):
        """Test ETA is null when trip hasn't departed"""
        trip = self._create_test_trip(status="Preparing", departure_time=None)

        frappe.set_user("test.delivery@bebang.ph")

        from hrms.api.dispatch import get_my_delivery
        result = get_my_delivery()

        my_stop = result["trip"]["my_stop"]
        self.assertIsNone(my_stop["eta_minutes"])
        self.assertIsNone(my_stop["eta_window"])

    def test_no_delivery_scheduled(self):
        """Test response when no delivery is scheduled for user's store"""
        # Don't create any trip
        frappe.set_user("test.delivery@bebang.ph")

        from hrms.api.dispatch import get_my_delivery
        result = get_my_delivery()

        self.assertFalse(result.get("ok"))
        self.assertIn("message", result)
        self.assertEqual(result["message"], "No delivery scheduled")

    def test_items_preview_empty_when_no_order(self):
        """Test items_preview returns empty list when no store order linked"""
        trip = self._create_test_trip()

        frappe.set_user("test.delivery@bebang.ph")

        from hrms.api.dispatch import get_my_delivery
        result = get_my_delivery()

        my_stop = result["trip"]["my_stop"]
        self.assertEqual(my_stop["items_preview"], [])

    def test_user_without_store_assignment(self):
        """Test error handling when user has no store assigned"""
        # Create user without Employee record
        frappe.set_user("Administrator")

        from hrms.api.dispatch import get_my_delivery
        result = get_my_delivery()

        self.assertFalse(result.get("ok"))
        self.assertIn("message", result)


# Allow running tests directly
if __name__ == "__main__":
    unittest.main()
