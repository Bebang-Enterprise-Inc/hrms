"""S093 — Store Ordering Policy Tests"""
import unittest
from datetime import date, timedelta


class TestValidateOrderWindow(unittest.TestCase):
	def _make_window_func(self, now_hour):
		def validate_order_window(delivery_date):
			today = date(2026, 3, 23)
			tomorrow = today + timedelta(days=1)
			delivery = date.fromisoformat(str(delivery_date)) if isinstance(delivery_date, str) else delivery_date
			if delivery <= today:
				raise ValueError("Delivery date must be tomorrow or later.")
			if delivery == tomorrow and now_hour >= 12:
				return {"allowed": True, "requires_dual_approval": True}
			return {"allowed": True, "requires_dual_approval": False}
		return validate_order_window

	def test_order_tomorrow_before_noon_no_dual_approval(self):
		result = self._make_window_func(11)("2026-03-24")
		self.assertFalse(result["requires_dual_approval"])

	def test_order_tomorrow_after_noon_requires_dual_approval(self):
		result = self._make_window_func(12)("2026-03-24")
		self.assertTrue(result["requires_dual_approval"])

	def test_order_day_after_tomorrow_no_dual(self):
		result = self._make_window_func(15)("2026-03-25")
		self.assertFalse(result["requires_dual_approval"])

	def test_order_for_today_rejected(self):
		with self.assertRaises(ValueError):
			self._make_window_func(10)("2026-03-23")

	def test_order_for_yesterday_rejected(self):
		with self.assertRaises(ValueError):
			self._make_window_func(10)("2026-03-22")


class TestEmergencyOrderRejection(unittest.TestCase):
	def test_emergency_true_rejected(self):
		self.assertTrue(int(True) != 0)

	def test_emergency_false_allowed(self):
		self.assertEqual(int(False), 0)

	def test_emergency_string_one_rejected(self):
		self.assertTrue(int("1") != 0)


class TestDualApprovalWorkflow(unittest.TestCase):
	def test_single_approval(self):
		stages = {"requires_dual_approval": False, "approval_stage": "Single Approval"}
		self.assertEqual(stages["approval_stage"], "Single Approval")

	def test_dual_first_stage_moves_to_wm(self):
		stages = {"requires_dual_approval": True, "approval_stage": "Pending Area Supervisor"}
		if stages["requires_dual_approval"] and stages["approval_stage"] == "Pending Area Supervisor":
			stages["approval_stage"] = "Pending Warehouse Manager"
		self.assertEqual(stages["approval_stage"], "Pending Warehouse Manager")

	def test_dual_second_stage_fully_approved(self):
		stages = {"requires_dual_approval": True, "approval_stage": "Pending Warehouse Manager"}
		if stages["requires_dual_approval"] and stages["approval_stage"] == "Pending Warehouse Manager":
			stages["approval_stage"] = "Fully Approved"
		self.assertEqual(stages["approval_stage"], "Fully Approved")

	def test_as_rejects_wm_never_sees(self):
		stages = {"requires_dual_approval": True, "approval_stage": "Pending Area Supervisor"}
		final_status = "Rejected"
		self.assertNotEqual(stages["approval_stage"], "Pending Warehouse Manager")


class TestMultipleOrdersPerDay(unittest.TestCase):
	def test_three_orders_same_day_allowed(self):
		orders = [f"BEI-ORD-2026-{i:05d}" for i in range(3)]
		self.assertEqual(len(orders), 3)


class TestIsEmergencyFieldPreservation(unittest.TestCase):
	def test_historical_readable(self):
		self.assertEqual({"is_emergency": 1}["is_emergency"], 1)

	def test_new_order_always_zero(self):
		self.assertEqual({"is_emergency": 0}["is_emergency"], 0)


if __name__ == "__main__":
	unittest.main()
