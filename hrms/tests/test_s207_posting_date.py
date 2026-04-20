"""S207 P3-T2: unit tests for posting_date_for_slip (CFO PNL-001).

Pure / deterministic. No Frappe / DB dependency — can run under plain pytest.
"""

from __future__ import annotations

from datetime import date

from hrms.utils.labor_allocation import posting_date_for_slip


def test_first_half_pays_on_25th_same_month():
	# Slip ending on the 15th (first-half boundary) -> 25th of same month
	assert posting_date_for_slip(date(2026, 4, 15)) == date(2026, 4, 25)
	assert posting_date_for_slip(date(2026, 4, 1)) == date(2026, 4, 25)
	assert posting_date_for_slip(date(2026, 4, 10)) == date(2026, 4, 25)


def test_second_half_pays_on_10th_next_month():
	# Slip ending on the 30th (end-of-month for 30-day months) -> 10th next month
	assert posting_date_for_slip(date(2026, 4, 30)) == date(2026, 5, 10)
	# 31-day month
	assert posting_date_for_slip(date(2026, 3, 31)) == date(2026, 4, 10)
	# 28-day February
	assert posting_date_for_slip(date(2026, 2, 28)) == date(2026, 3, 10)
	# 29-day February (leap year)
	assert posting_date_for_slip(date(2024, 2, 29)) == date(2024, 3, 10)


def test_second_half_december_rolls_to_january():
	# Year rollover — 16th of Dec onward pays January 10th next year
	assert posting_date_for_slip(date(2026, 12, 31)) == date(2027, 1, 10)
	assert posting_date_for_slip(date(2026, 12, 16)) == date(2027, 1, 10)


def test_boundary_day_16_is_second_half():
	# First day of the second half
	assert posting_date_for_slip(date(2026, 4, 16)) == date(2026, 5, 10)
	assert posting_date_for_slip(date(2026, 1, 16)) == date(2026, 2, 10)
