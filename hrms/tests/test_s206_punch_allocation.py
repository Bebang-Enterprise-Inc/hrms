"""S206 Phase 1 — punch_allocation unit tests."""

import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

from hrms.utils import punch_allocation
from hrms.utils.punch_allocation import (
	_pair_punches,
	compute_shift_share,
	compute_shifts_by_store,
)


class PunchPairingTests(unittest.TestCase):
	"""Test the _pair_punches helper — no Frappe DB needed."""

	def test_clean_in_out_pair_one_shift(self):
		checkins = [
			{"device_id": "UDP1", "time": datetime(2026, 4, 15, 8, 0), "log_type": "IN"},
			{"device_id": "UDP1", "time": datetime(2026, 4, 15, 17, 0), "log_type": "OUT"},
		]
		shifts = _pair_punches(checkins)
		self.assertEqual(len(shifts), 1)
		self.assertEqual(shifts[0]["device_id"], "UDP1")
		self.assertEqual(shifts[0]["weight"], 1.0)

	def test_orphan_in_counts_half_shift(self):
		checkins = [
			{"device_id": "UDP1", "time": datetime(2026, 4, 15, 8, 0), "log_type": "IN"},
		]
		shifts = _pair_punches(checkins)
		self.assertEqual(len(shifts), 1)
		self.assertEqual(shifts[0]["weight"], 0.5)

	def test_orphan_out_dropped(self):
		checkins = [
			{"device_id": "UDP1", "time": datetime(2026, 4, 15, 17, 0), "log_type": "OUT"},
		]
		shifts = _pair_punches(checkins)
		self.assertEqual(shifts, [])

	def test_multi_day_separate_shifts(self):
		checkins = [
			{"device_id": "UDP1", "time": datetime(2026, 4, 15, 8, 0), "log_type": "IN"},
			{"device_id": "UDP1", "time": datetime(2026, 4, 15, 17, 0), "log_type": "OUT"},
			{"device_id": "UDP1", "time": datetime(2026, 4, 16, 8, 0), "log_type": "IN"},
			{"device_id": "UDP1", "time": datetime(2026, 4, 16, 17, 0), "log_type": "OUT"},
		]
		shifts = _pair_punches(checkins)
		self.assertEqual(len(shifts), 2)
		self.assertEqual(sum(s["weight"] for s in shifts), 2.0)

	def test_multi_device_separate_tracks(self):
		checkins = [
			{"device_id": "UDP1", "time": datetime(2026, 4, 15, 8, 0), "log_type": "IN"},
			{"device_id": "UDP1", "time": datetime(2026, 4, 15, 17, 0), "log_type": "OUT"},
			{"device_id": "UDP2", "time": datetime(2026, 4, 15, 10, 0), "log_type": "IN"},
			{"device_id": "UDP2", "time": datetime(2026, 4, 15, 19, 0), "log_type": "OUT"},
		]
		shifts = _pair_punches(checkins)
		by_device = {s["device_id"]: s["weight"] for s in shifts}
		self.assertEqual(by_device, {"UDP1": 1.0, "UDP2": 1.0})

	def test_two_ins_in_a_row_counts_first_as_half(self):
		checkins = [
			{"device_id": "UDP1", "time": datetime(2026, 4, 15, 8, 0), "log_type": "IN"},
			{"device_id": "UDP1", "time": datetime(2026, 4, 15, 10, 0), "log_type": "IN"},
			{"device_id": "UDP1", "time": datetime(2026, 4, 15, 17, 0), "log_type": "OUT"},
		]
		shifts = _pair_punches(checkins)
		# 1 half (orphan) + 1 full = 1.5 total
		total = sum(s["weight"] for s in shifts)
		self.assertEqual(total, 1.5)


class ComputeShiftShareTests(unittest.TestCase):
	"""Test compute_shift_share with mocked Frappe DB."""

	def _fake_fetch(self, checkins):
		"""Factory to patch _fetch_checkins return."""
		return patch.object(punch_allocation, "_fetch_checkins", return_value=checkins)

	def _fake_resolve(self, device_to_company):
		"""Factory to patch resolve_device_company."""

		def fake(sn, department=None):
			if sn not in device_to_company:
				from hrms.utils.device_store_bridge import UnknownDeviceCompany

				raise UnknownDeviceCompany(f"Unknown {sn}")
			return device_to_company[sn]

		return patch.object(punch_allocation, "resolve_device_company", side_effect=fake)

	def test_all_home_store_returns_single_share(self):
		checkins = [
			{"device_id": "UDP_MEGA", "time": datetime(2026, 4, 15, 8, 0), "log_type": "IN"},
			{"device_id": "UDP_MEGA", "time": datetime(2026, 4, 15, 17, 0), "log_type": "OUT"},
			{"device_id": "UDP_MEGA", "time": datetime(2026, 4, 16, 8, 0), "log_type": "IN"},
			{"device_id": "UDP_MEGA", "time": datetime(2026, 4, 16, 17, 0), "log_type": "OUT"},
		]
		with (
			self._fake_fetch(checkins),
			self._fake_resolve(
				{
					"UDP_MEGA": "SM MEGAMALL - BEI",
				}
			),
		):
			shares = compute_shift_share("EMP-001", date(2026, 4, 1), date(2026, 4, 30))
		self.assertEqual(shares, {"SM MEGAMALL - BEI": 1.0})

	def test_50_50_split_across_two_stores(self):
		checkins = [
			{"device_id": "UDP_MEGA", "time": datetime(2026, 4, 15, 8, 0), "log_type": "IN"},
			{"device_id": "UDP_MEGA", "time": datetime(2026, 4, 15, 17, 0), "log_type": "OUT"},
			{"device_id": "UDP_TANZA", "time": datetime(2026, 4, 16, 8, 0), "log_type": "IN"},
			{"device_id": "UDP_TANZA", "time": datetime(2026, 4, 16, 17, 0), "log_type": "OUT"},
		]
		with (
			self._fake_fetch(checkins),
			self._fake_resolve(
				{
					"UDP_MEGA": "SM MEGAMALL - BEI",
					"UDP_TANZA": "SM TANZA - BMI",
				}
			),
		):
			shares = compute_shift_share("EMP-001", date(2026, 4, 1), date(2026, 4, 30))
		self.assertEqual(shares, {"SM MEGAMALL - BEI": 0.5, "SM TANZA - BMI": 0.5})

	def test_zero_punches_returns_empty(self):
		with self._fake_fetch([]):
			shares = compute_shift_share("EMP-001", date(2026, 4, 1), date(2026, 4, 30))
		self.assertEqual(shares, {})

	def test_unknown_device_is_skipped_not_errored(self):
		checkins = [
			{"device_id": "UDP_KNOWN", "time": datetime(2026, 4, 15, 8, 0), "log_type": "IN"},
			{"device_id": "UDP_KNOWN", "time": datetime(2026, 4, 15, 17, 0), "log_type": "OUT"},
			{"device_id": "UDP_BAD", "time": datetime(2026, 4, 16, 8, 0), "log_type": "IN"},
			{"device_id": "UDP_BAD", "time": datetime(2026, 4, 16, 17, 0), "log_type": "OUT"},
		]
		with (
			self._fake_fetch(checkins),
			self._fake_resolve(
				{
					"UDP_KNOWN": "SM MEGAMALL - BEI",
				}
			),
		):
			shares = compute_shift_share("EMP-001", date(2026, 4, 1), date(2026, 4, 30))
		# Unknown device shifts skipped → known-only = 1.0
		self.assertEqual(shares, {"SM MEGAMALL - BEI": 1.0})


if __name__ == "__main__":
	unittest.main()
