"""BEI-specific payroll formula helpers.

These functions are called FROM Salary Component formulas during Salary Slip generation.
They provide calculations for 13th month, night differential, holiday pay, overtime, etc.

Usage in Salary Component formula field:
    hrms.payroll.ph_payroll_formulas.get_ytd_basic_salary(employee, payroll_period)
"""

import frappe
from frappe import _
from frappe.utils import date_diff, flt, get_datetime, getdate


def get_ytd_basic_salary(employee, payroll_period):
	"""Sum basic pay from all submitted Salary Slips in current payroll period.

	Used by 13th Month Pay calculation:
	    13th_month = get_ytd_basic_salary(employee, payroll_period) / 12

	Args:
	    employee: Employee ID (string)
	    payroll_period: Payroll Period name (string, e.g., "2025")

	Returns:
	    float: Total basic salary year-to-date
	"""
	if not employee or not payroll_period:
		return 0.0

	# Get payroll period dates
	period = frappe.db.get_value("Payroll Period", payroll_period, ["start_date", "end_date"], as_dict=True)

	if not period:
		return 0.0

	# Sum gross_pay from all submitted salary slips in period
	result = frappe.db.sql(
		"""
        SELECT SUM(ss.gross_pay) as total_basic
        FROM `tabSalary Slip` ss
        WHERE ss.employee = %(employee)s
          AND ss.docstatus = 1
          AND ss.start_date >= %(period_start)s
          AND ss.end_date <= %(period_end)s
    """,
		{"employee": employee, "period_start": period.start_date, "period_end": period.end_date},
		as_dict=True,
	)

	return flt(result[0].total_basic) if result and result[0].total_basic else 0.0


def get_night_diff_hours(employee, start_date, end_date):
	"""Count hours worked between 10pm-6am from Employee Checkin records.

	Used by Night Differential formula:
	    night_diff_pay = hourly_rate * 0.1 * get_night_diff_hours(employee, start_date, end_date)

	Args:
	    employee: Employee ID (string)
	    start_date: Period start date (string or date)
	    end_date: Period end date (string or date)

	Returns:
	    float: Total night differential hours
	"""
	if not employee or not start_date or not end_date:
		return 0.0

	start = getdate(start_date)
	end = getdate(end_date)

	# Query Employee Checkin records for the period
	checkins = frappe.db.sql(
		"""
        SELECT
            ec.time as checkin_time,
            ec.log_type
        FROM `tabEmployee Checkin` ec
        WHERE ec.employee = %(employee)s
          AND DATE(ec.time) BETWEEN %(start_date)s AND %(end_date)s
          AND ec.log_type IN ('IN', 'OUT')
        ORDER BY ec.time
    """,
		{"employee": employee, "start_date": start, "end_date": end},
		as_dict=True,
	)

	if not checkins:
		return 0.0

	night_hours = 0.0
	current_in = None

	# Process checkin/checkout pairs
	for checkin in checkins:
		if checkin.log_type == "IN":
			current_in = get_datetime(checkin.checkin_time)
		elif checkin.log_type == "OUT" and current_in:
			checkout_time = get_datetime(checkin.checkin_time)
			night_hours += _calculate_night_hours(current_in, checkout_time)
			current_in = None

	return flt(night_hours, 2)


def _calculate_night_hours(checkin_time, checkout_time):
	"""Calculate hours between 10pm-6am within a single checkin/checkout pair.

	Args:
	    checkin_time: Check-in datetime
	    checkout_time: Check-out datetime

	Returns:
	    float: Night differential hours
	"""
	from datetime import datetime, time, timedelta

	# Night shift is 10pm (22:00) to 6am (06:00)
	night_start = time(22, 0)  # 10pm
	night_end = time(6, 0)  # 6am

	total_night_hours = 0.0
	current = checkin_time

	while current < checkout_time:
		current_time = current.time()

		# Check if current hour is within night shift
		if night_start <= current_time or current_time < night_end:
			# Calculate hours in this segment (max 1 hour)
			next_hour = min(current + timedelta(hours=1), checkout_time)
			hours = (next_hour - current).total_seconds() / 3600
			total_night_hours += hours
			current = next_hour
		else:
			# Move to next hour
			current += timedelta(hours=1)

	return total_night_hours


def get_holiday_premium_days(employee, start_date, end_date, holiday_type="Regular Holiday"):
	"""Count days employee worked on holidays (from Attendance + Holiday List).

	Args:
	    employee: Employee ID (string)
	    start_date: Period start date (string or date)
	    end_date: Period end date (string or date)
	    holiday_type: "Regular Holiday" (200% premium) or "Special Holiday" (130% premium)

	Returns:
	    float: Number of holiday days worked
	"""
	if not employee or not start_date or not end_date:
		return 0.0

	start = getdate(start_date)
	end = getdate(end_date)

	# Get employee's holiday list
	holiday_list = frappe.db.get_value("Employee", employee, "holiday_list")
	if not holiday_list:
		return 0.0

	# Get holidays in the period
	holidays = frappe.db.sql(
		"""
        SELECT h.holiday_date
        FROM `tabHoliday` h
        WHERE h.parent = %(holiday_list)s
          AND h.holiday_date BETWEEN %(start_date)s AND %(end_date)s
          AND h.weekly_off = 0
          AND (%(holiday_type)s = '' OR h.description LIKE %(holiday_type_pattern)s)
    """,
		{
			"holiday_list": holiday_list,
			"start_date": start,
			"end_date": end,
			"holiday_type": holiday_type,
			"holiday_type_pattern": f"%{holiday_type}%",
		},
		as_dict=True,
	)

	if not holidays:
		return 0.0

	# Check attendance on those holidays
	worked_holidays = 0
	for holiday in holidays:
		attendance = frappe.db.get_value(
			"Attendance",
			{
				"employee": employee,
				"attendance_date": holiday.holiday_date,
				"status": "Present",
				"docstatus": 1,
			},
			"name",
		)
		if attendance:
			worked_holidays += 1

	return flt(worked_holidays, 1)


def get_approved_ot_hours(employee, start_date, end_date, ot_type="regular"):
	"""Query approved standard Overtime Slip records.

	Args:
	    employee: Employee ID (string)
	    start_date: Period start date (string or date)
	    end_date: Period end date (string or date)
	    ot_type: "regular" (1.25x), "rest_day" (1.30x), "holiday" (2.6x)

	Returns:
	    float: Total approved overtime hours
	"""
	if not employee or not start_date or not end_date:
		return 0.0

	start = getdate(start_date)
	end = getdate(end_date)

	ot_type_filter = ""
	if ot_type == "regular":
		ot_type_filter = (
			"AND od.overtime_type NOT LIKE '%Rest Day%' AND od.overtime_type NOT LIKE '%Holiday%'"
		)
	elif ot_type == "rest_day":
		ot_type_filter = "AND od.overtime_type LIKE '%Rest Day%'"
	elif ot_type == "holiday":
		ot_type_filter = "AND od.overtime_type LIKE '%Holiday%'"

	result = frappe.db.sql(
		f"""
        SELECT SUM(od.overtime_duration) as total_hours
        FROM `tabOvertime Slip` os
        INNER JOIN `tabOvertime Details` od ON od.parent = os.name
        WHERE os.employee = %(employee)s
          AND os.docstatus = 1
          AND od.date BETWEEN %(start_date)s AND %(end_date)s
          {ot_type_filter}
    """,
		{{"employee": employee, "start_date": start, "end_date": end}},
		as_dict=True,
	)

	return flt(result[0].total_hours) if result and result[0].total_hours else 0.0
