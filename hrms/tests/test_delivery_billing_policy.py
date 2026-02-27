import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
	"delivery_billing_policy_under_test",
	ROOT / "hrms" / "utils" / "delivery_billing_policy.py",
)
policy = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(policy)


class TestDeliveryBillingPolicy(unittest.TestCase):
	def _base_exception(self):
		return {
			"name": "BEI-EXC-TEST-0001",
			"approval_tier": "CPO+CFO",
			"status": "Approved",
			"delivery_trip_reference": "TRIP-0001",
			"delivery_stop_idx": 1,
			"modified": "2026-02-27 10:00:00",
		}

	def test_trace_uses_explicit_columns(self):
		exc = self._base_exception()
		exc.update(
			{
				"cpo_approved_by": policy.CPO_APPROVER_EMAIL,
				"cpo_approved_at": "2026-02-27 09:00:00",
				"cfo_approved_by": policy.CFO_APPROVER_EMAIL,
				"cfo_approved_at": "2026-02-27 09:05:00",
				"approval_audit_log": "dual approval complete",
			}
		)

		trace = policy.get_pre_delivery_exception_trace(exc, "TRIP-0001", 1)

		self.assertEqual(trace["cpo_approved_by"], policy.CPO_APPROVER_EMAIL)
		self.assertEqual(trace["cfo_approved_by"], policy.CFO_APPROVER_EMAIL)

	def test_trace_falls_back_to_approval_comment(self):
		exc = self._base_exception()
		exc.update({"approver_comment": "CPO Approved: ok\nCFO Approved: ok"})

		trace = policy.get_pre_delivery_exception_trace(exc, "TRIP-0001", 1)

		self.assertEqual(trace["cpo_approved_by"], policy.CPO_APPROVER_EMAIL)
		self.assertEqual(trace["cfo_approved_by"], policy.CFO_APPROVER_EMAIL)
		self.assertTrue(trace["cpo_approved_at"])
		self.assertTrue(trace["cfo_approved_at"])

	def test_trace_requires_dual_approval_markers(self):
		exc = self._base_exception()
		exc.update({"approver_comment": "CPO Approved: ok"})

		with self.assertRaises(policy.DeliveryBillingPolicyError):
			policy.get_pre_delivery_exception_trace(exc, "TRIP-0001", 1)


if __name__ == "__main__":
	unittest.main()
