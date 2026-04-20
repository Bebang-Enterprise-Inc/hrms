"""S207 Phase 7 — Bimonthly cadence + preview_scheduled day-guard tests.

Uses ``freezegun.freeze_time()`` to mock ``datetime.now()`` for UTC/PHT
boundary cases. See LD-2, LD-16, LD-17 in the S207 plan.

Install: ``pip install -r hrms/requirements-dev.txt`` (freezegun>=1.4.0).

Run:
    pytest hrms/tests/test_s207_bimonthly_cadence.py -v
"""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

try:
	from freezegun import freeze_time
	HAS_FREEZEGUN = True
except ImportError:
	HAS_FREEZEGUN = False


@unittest.skipUnless(HAS_FREEZEGUN, "freezegun>=1.4.0 required — see hrms/requirements-dev.txt")
class PreviewScheduledDayGuardTests(unittest.TestCase):
	"""LD-17 regression: pht_date comes from datetime.now(utc).astimezone(PHT) directly.

	Scenario: cron fires at UTC 22:00 which is PHT 06:00 the NEXT calendar day.
	Day-guard must use the PHT calendar date (NOT UTC calendar date, NOT
	UTC-plus-one-day). v2 plan had an off-by-one where `+ timedelta(days=1)`
	was added to UTC; this test proves the v3/v4 fix stays in place.
	"""

	@freeze_time("2026-04-30T22:30:00+00:00")
	def test_april_30_utc_2230_is_pht_may_1_fires_day1(self):
		"""UTC 2026-04-30 22:30 -> PHT 2026-05-01 06:30 -> day=1, should fire."""
		from hrms.api.labor_allocation import PHT
		from datetime import datetime, timezone
		pht_now = datetime.now(timezone.utc).astimezone(PHT)
		self.assertEqual(pht_now.date(), date(2026, 5, 1))
		self.assertEqual(pht_now.date().day, 1)

	@freeze_time("2026-04-15T22:30:00+00:00")
	def test_april_15_utc_2230_is_pht_april_16_fires_day16(self):
		"""UTC 2026-04-15 22:30 -> PHT 2026-04-16 06:30 -> day=16, should fire."""
		from hrms.api.labor_allocation import PHT
		from datetime import datetime, timezone
		pht_now = datetime.now(timezone.utc).astimezone(PHT)
		self.assertEqual(pht_now.date(), date(2026, 4, 16))
		self.assertEqual(pht_now.date().day, 16)

	@freeze_time("2026-04-07T22:30:00+00:00")
	def test_april_7_utc_2230_is_pht_april_8_no_fire(self):
		"""UTC 2026-04-07 22:30 -> PHT 2026-04-08 06:30 -> day=8, should NOT fire."""
		from hrms.api.labor_allocation import PHT
		from datetime import datetime, timezone
		pht_now = datetime.now(timezone.utc).astimezone(PHT)
		self.assertEqual(pht_now.date(), date(2026, 4, 8))
		self.assertNotIn(pht_now.date().day, (1, 16))


@unittest.skipUnless(HAS_FREEZEGUN, "freezegun>=1.4.0 required")
class PreviewScheduledBehaviourTests(unittest.TestCase):
	"""End-to-end behaviour of preview_scheduled — mock frappe.sendmail to isolate."""

	@freeze_time("2026-04-30T22:30:00+00:00")
	def test_day1_period_is_second_half_of_previous_month(self):
		"""PHT May 1 fire -> preview covers April 16..April 30."""
		from hrms.api import labor_allocation
		captured = {}

		def fake_preview(start, end):
			captured["start"] = start
			captured["end"] = end
			return {
				"period": {"start": str(start), "end": str(end)},
				"total_slips": 0,
				"planned_count": 0,
				"skipped_count": 0,
				"errors_count": 0,
			}

		def fake_sendmail(**kwargs):
			captured["email_subject"] = kwargs.get("subject")
			captured["email_recipients"] = kwargs.get("recipients")

		with (
			patch.object(labor_allocation, "preview_allocation", side_effect=fake_preview),
			patch.object(labor_allocation, "set_backend_observability_context"),
			patch.object(labor_allocation.frappe, "sendmail", side_effect=fake_sendmail),
		):
			labor_allocation.preview_scheduled()

		self.assertEqual(captured["start"], date(2026, 4, 16))
		self.assertEqual(captured["end"], date(2026, 4, 30))
		self.assertIn("2026-04-16", captured["email_subject"])
		self.assertIn("2026-04-30", captured["email_subject"])
		self.assertEqual(captured["email_recipients"], ["sam@bebang.ph", "denise@bebang.ph"])

	@freeze_time("2026-04-15T22:30:00+00:00")
	def test_day16_period_is_first_half_of_current_month(self):
		"""PHT April 16 fire -> preview covers April 1..April 15."""
		from hrms.api import labor_allocation
		captured = {}

		def fake_preview(start, end):
			captured["start"] = start
			captured["end"] = end
			return {
				"period": {"start": str(start), "end": str(end)},
				"total_slips": 0,
				"planned_count": 0,
				"skipped_count": 0,
				"errors_count": 0,
			}

		with (
			patch.object(labor_allocation, "preview_allocation", side_effect=fake_preview),
			patch.object(labor_allocation, "set_backend_observability_context"),
			patch.object(labor_allocation.frappe, "sendmail"),
		):
			labor_allocation.preview_scheduled()

		self.assertEqual(captured["start"], date(2026, 4, 1))
		self.assertEqual(captured["end"], date(2026, 4, 15))

	@freeze_time("2026-04-07T22:30:00+00:00")
	def test_noop_day_does_not_call_preview(self):
		"""PHT day 8 -> function returns early; preview_allocation never called."""
		from hrms.api import labor_allocation
		call_count = {"n": 0}

		def fake_preview(*_args, **_kwargs):
			call_count["n"] += 1
			return {}

		with (
			patch.object(labor_allocation, "preview_allocation", side_effect=fake_preview),
			patch.object(labor_allocation, "set_backend_observability_context") as obs,
		):
			labor_allocation.preview_scheduled()

		self.assertEqual(call_count["n"], 0)
		# Observability context also not set on no-op days
		self.assertEqual(obs.call_count, 0)


if __name__ == "__main__":
	unittest.main()
