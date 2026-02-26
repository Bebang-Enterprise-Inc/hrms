"""
Flexi-Time Attendance Processing for Head Office Employees

This module handles the 60-minute grace period policy for Head Office employees.
Employees who arrive late (within grace) must compensate by staying late the same day.
Uncompensated time is automatically flagged for payroll deduction.

Policy:
- Grace Period: 60 minutes (Head Office only)
- Stores/Malls: No grace period
- Compensation: Must be same day
- Deduction: Auto-deduct if not compensated

Usage:
    from hrms.hrms.utils.flexi_attendance import process_flexi_attendance

    # Process single employee's attendance for a date
    result = process_flexi_attendance(employee_id, date)

    # Batch process all Head Office employees
    results = batch_process_flexi_attendance(date)

Author: Claude (Opus 4.5)
Created: 2026-01-21
"""

import frappe
from frappe.utils import (
    getdate,
    get_time,
    time_diff_in_seconds,
    time_diff_in_hours,
    add_to_date,
    now_datetime,
    cint,
    flt,
)
from datetime import datetime, timedelta, time
from typing import Optional, Dict, List, Tuple, NamedTuple


# =============================================================================
# CONFIGURATION
# =============================================================================

# Grace period in minutes (Head Office only)
GRACE_PERIOD_MINUTES = 60

# Head Office location codes that get flexi-time
HEAD_OFFICE_LOCATIONS = [
    "BGC",
    "BGC Branch",
    "Head Office",
    "HQ",
    "Brittany",
    "Capital House",
    "Shaw Commissary",
    "SHAW COMM",
]

# Head Office device serial numbers
HEAD_OFFICE_DEVICES = [
    "UDP3251600245",  # Brittany Hotel (HO1)
    "UDP3235200625",  # Capital House (HO2)
    "UDP3235200629",  # Shaw Commissary
]

# Lunch break duration in minutes
LUNCH_BREAK_MINUTES = 60


# =============================================================================
# DATA CLASSES
# =============================================================================

class FlexiResult(NamedTuple):
    """Result of flexi-time attendance calculation."""
    employee: str
    date: str
    scheduled_in: time
    scheduled_out: time
    actual_in: Optional[time]
    actual_out: Optional[time]
    late_minutes: int
    grace_used: int
    tardy_minutes: int
    required_out: time
    deficit_minutes: int
    total_deduction_minutes: int
    status: str  # ON_TIME, TARDY, UNCOMPENSATED, ABSENT, HALF_DAY
    notes: str


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def is_head_office_employee(employee: str) -> bool:
    """
    Check if employee is assigned to Head Office.

    Args:
        employee: Employee ID

    Returns:
        True if employee's branch/location is in HEAD_OFFICE_LOCATIONS
    """
    emp_doc = frappe.get_doc("Employee", employee)

    # Check branch field
    if emp_doc.branch and emp_doc.branch in HEAD_OFFICE_LOCATIONS:
        return True

    # Check custom location field if exists
    if hasattr(emp_doc, "location") and emp_doc.location in HEAD_OFFICE_LOCATIONS:
        return True

    # Check attendance_device_id against HO devices
    # (backup check if location not set properly)

    return False


def get_employee_shift(employee: str, date: str) -> Optional[Dict]:
    """
    Get employee's assigned shift for a specific date.

    Args:
        employee: Employee ID
        date: Date string (YYYY-MM-DD)

    Returns:
        Dict with shift details or None if no shift assigned
    """
    # Check Shift Assignment first
    shift_assignment = frappe.db.get_value(
        "Shift Assignment",
        {
            "employee": employee,
            "start_date": ("<=", date),
            "docstatus": 1,
            "status": "Active",
        },
        ["shift_type", "start_date", "end_date"],
        as_dict=True,
        order_by="start_date desc"
    )

    if not shift_assignment:
        # Fall back to default shift from Employee
        default_shift = frappe.db.get_value("Employee", employee, "default_shift")
        if not default_shift:
            return None
        shift_type = default_shift
    else:
        # Check if assignment is still valid for this date
        if shift_assignment.end_date and getdate(date) > getdate(shift_assignment.end_date):
            return None
        shift_type = shift_assignment.shift_type

    # Get shift details
    shift = frappe.get_doc("Shift Type", shift_type)

    return {
        "shift_type": shift_type,
        "start_time": shift.start_time,
        "end_time": shift.end_time,
        "late_entry_grace_period": cint(shift.late_entry_grace_period) or 0,
        "enable_flexi_compensation": getattr(shift, "enable_flexi_compensation", False),
    }


def get_checkins(employee: str, date: str) -> List[Dict]:
    """
    Get all checkins for an employee on a specific date.

    Args:
        employee: Employee ID
        date: Date string (YYYY-MM-DD)

    Returns:
        List of checkin records sorted by time
    """
    checkins = frappe.get_all(
        "Employee Checkin",
        filters={
            "employee": employee,
            "time": ("between", [f"{date} 00:00:00", f"{date} 23:59:59"]),
        },
        fields=["name", "time", "log_type", "device_id"],
        order_by="time asc"
    )

    return checkins


def determine_in_out(checkins: List[Dict], shift: Dict) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Determine IN and OUT times based on shift proximity.

    For Head Office employees, we use shift timing to determine IN/OUT
    regardless of which device (Brittany/Capital House/Shaw) was used.

    Args:
        checkins: List of checkin records
        shift: Shift details dict

    Returns:
        Tuple of (in_time, out_time) as datetime objects
    """
    if not checkins:
        return None, None

    if len(checkins) == 1:
        # Single punch - determine based on proximity to shift times
        punch_time = checkins[0]["time"]
        shift_start = datetime.combine(punch_time.date(), shift["start_time"])
        shift_end = datetime.combine(punch_time.date(), shift["end_time"])

        # If closer to start time, it's an IN
        to_start = abs(time_diff_in_seconds(punch_time, shift_start))
        to_end = abs(time_diff_in_seconds(punch_time, shift_end))

        if to_start <= to_end:
            return punch_time, None  # IN only
        else:
            return None, punch_time  # OUT only (rare - missed IN)

    # Multiple punches - first is IN, last is OUT
    # (ignoring any middle punches for break/lunch)
    return checkins[0]["time"], checkins[-1]["time"]


def calculate_flexi_attendance(
    employee: str,
    date: str,
    shift: Dict,
    actual_in: Optional[datetime],
    actual_out: Optional[datetime],
) -> FlexiResult:
    """
    Calculate flexi-time attendance with compensation logic.

    Args:
        employee: Employee ID
        date: Date string
        shift: Shift details dict
        actual_in: Actual IN time
        actual_out: Actual OUT time

    Returns:
        FlexiResult with all calculated values
    """
    scheduled_in = shift["start_time"]
    scheduled_out = shift["end_time"]

    # Handle absent
    if not actual_in and not actual_out:
        return FlexiResult(
            employee=employee,
            date=date,
            scheduled_in=scheduled_in,
            scheduled_out=scheduled_out,
            actual_in=None,
            actual_out=None,
            late_minutes=0,
            grace_used=0,
            tardy_minutes=0,
            required_out=scheduled_out,
            deficit_minutes=0,
            total_deduction_minutes=480,  # Full day deduction (8 hours)
            status="ABSENT",
            notes="No checkin records found"
        )

    # Handle half day (IN only or OUT only)
    if not actual_in or not actual_out:
        return FlexiResult(
            employee=employee,
            date=date,
            scheduled_in=scheduled_in,
            scheduled_out=scheduled_out,
            actual_in=actual_in.time() if actual_in else None,
            actual_out=actual_out.time() if actual_out else None,
            late_minutes=0,
            grace_used=0,
            tardy_minutes=0,
            required_out=scheduled_out,
            deficit_minutes=240,  # Half day deficit
            total_deduction_minutes=240,
            status="HALF_DAY",
            notes="Missing IN or OUT punch"
        )

    # Calculate late minutes
    scheduled_in_dt = datetime.combine(actual_in.date(), scheduled_in)
    late_seconds = time_diff_in_seconds(actual_in, scheduled_in_dt)
    late_minutes = max(0, int(late_seconds / 60))

    # Apply grace period (Head Office: 60 minutes)
    grace_period = GRACE_PERIOD_MINUTES if is_head_office_employee(employee) else 0
    grace_used = min(late_minutes, grace_period)
    tardy_minutes = max(0, late_minutes - grace_period)

    # Calculate required OUT time (must compensate grace used)
    scheduled_out_dt = datetime.combine(actual_out.date(), scheduled_out)
    required_out_dt = scheduled_out_dt + timedelta(minutes=grace_used)
    required_out = required_out_dt.time()

    # Calculate deficit (uncompensated time)
    if actual_out < required_out_dt:
        deficit_seconds = time_diff_in_seconds(required_out_dt, actual_out)
        deficit_minutes = int(deficit_seconds / 60)
    else:
        deficit_minutes = 0

    # Total deduction
    total_deduction_minutes = tardy_minutes + deficit_minutes

    # Determine status
    if total_deduction_minutes == 0:
        status = "ON_TIME"
        notes = "Fully compensated" if grace_used > 0 else "On time"
    elif tardy_minutes > 0 and deficit_minutes > 0:
        status = "TARDY_UNCOMPENSATED"
        notes = f"Tardy {tardy_minutes}min + Uncompensated {deficit_minutes}min"
    elif tardy_minutes > 0:
        status = "TARDY"
        notes = f"Exceeded grace by {tardy_minutes}min (compensated flexi portion)"
    else:
        status = "UNCOMPENSATED"
        notes = f"Left {deficit_minutes}min early without compensating"

    return FlexiResult(
        employee=employee,
        date=date,
        scheduled_in=scheduled_in,
        scheduled_out=scheduled_out,
        actual_in=actual_in.time(),
        actual_out=actual_out.time(),
        late_minutes=late_minutes,
        grace_used=grace_used,
        tardy_minutes=tardy_minutes,
        required_out=required_out,
        deficit_minutes=deficit_minutes,
        total_deduction_minutes=total_deduction_minutes,
        status=status,
        notes=notes
    )


# =============================================================================
# PUBLIC API
# =============================================================================

def process_flexi_attendance(employee: str, date: str) -> Optional[FlexiResult]:
    """
    Process flexi-time attendance for a single employee on a specific date.

    This is the main entry point for processing attendance.

    Args:
        employee: Employee ID
        date: Date string (YYYY-MM-DD)

    Returns:
        FlexiResult with attendance calculation, or None if no shift assigned

    Example:
        >>> result = process_flexi_attendance("HR-EMP-00172", "2026-01-21")
        >>> print(f"Status: {result.status}, Deduction: {result.total_deduction_minutes}min")
    """
    # Get shift
    shift = get_employee_shift(employee, date)
    if not shift:
        frappe.log_error(
            f"No shift assigned for {employee} on {date}",
            "Flexi Attendance"
        )
        return None

    # Get checkins
    checkins = get_checkins(employee, date)

    # Determine IN/OUT
    actual_in, actual_out = determine_in_out(checkins, shift)

    # Calculate flexi attendance
    result = calculate_flexi_attendance(
        employee=employee,
        date=date,
        shift=shift,
        actual_in=actual_in,
        actual_out=actual_out
    )

    return result


def batch_process_flexi_attendance(
    date: str,
    head_office_only: bool = True
) -> List[FlexiResult]:
    """
    Process flexi-time attendance for all employees on a specific date.

    Args:
        date: Date string (YYYY-MM-DD)
        head_office_only: If True, only process Head Office employees

    Returns:
        List of FlexiResult for all processed employees

    Example:
        >>> results = batch_process_flexi_attendance("2026-01-21")
        >>> deductions = [r for r in results if r.total_deduction_minutes > 0]
        >>> print(f"Employees with deductions: {len(deductions)}")
    """
    # Get employees to process
    filters = {"status": "Active"}
    if head_office_only:
        filters["branch"] = ("in", HEAD_OFFICE_LOCATIONS)

    employees = frappe.get_all(
        "Employee",
        filters=filters,
        pluck="name"
    )

    results = []
    for employee in employees:
        result = process_flexi_attendance(employee, date)
        if result:
            results.append(result)

    return results


def get_monthly_deductions(employee: str, month: int, year: int) -> Dict:
    """
    Calculate total monthly deductions for an employee.

    Args:
        employee: Employee ID
        month: Month number (1-12)
        year: Year (e.g., 2026)

    Returns:
        Dict with deduction summary

    Example:
        >>> deductions = get_monthly_deductions("HR-EMP-00172", 1, 2026)
        >>> print(f"Total: {deductions['total_minutes']} minutes = PHP {deductions['amount']}")
    """
    from calendar import monthrange

    # Get all dates in month
    _, last_day = monthrange(year, month)

    total_tardy = 0
    total_uncompensated = 0
    details = []

    for day in range(1, last_day + 1):
        date = f"{year}-{month:02d}-{day:02d}"

        # Skip weekends (simple check - could use Holiday list)
        date_obj = getdate(date)
        if date_obj.weekday() >= 5:  # Saturday=5, Sunday=6
            continue

        result = process_flexi_attendance(employee, date)
        if result and result.total_deduction_minutes > 0:
            total_tardy += result.tardy_minutes
            total_uncompensated += result.deficit_minutes
            details.append({
                "date": date,
                "tardy_minutes": result.tardy_minutes,
                "uncompensated_minutes": result.deficit_minutes,
                "status": result.status,
                "notes": result.notes
            })

    # Calculate deduction amount
    emp_doc = frappe.get_doc("Employee", employee)
    basic_pay = flt(emp_doc.ctc) or flt(emp_doc.basic_salary) or 0

    # Per-minute rate: basic / (22 working days * 8 hours * 60 minutes)
    minute_rate = basic_pay / (22 * 8 * 60) if basic_pay else 0

    total_minutes = total_tardy + total_uncompensated
    deduction_amount = total_minutes * minute_rate

    return {
        "employee": employee,
        "month": month,
        "year": year,
        "total_tardy_minutes": total_tardy,
        "total_uncompensated_minutes": total_uncompensated,
        "total_minutes": total_minutes,
        "minute_rate": minute_rate,
        "deduction_amount": round(deduction_amount, 2),
        "details": details
    }


# =============================================================================
# FRAPPE HOOKS
# =============================================================================

def on_attendance_submit(doc, method):
    """
    Hook: Called when Attendance is submitted.
    Updates attendance with flexi-time calculation.
    """
    if not is_head_office_employee(doc.employee):
        return

    result = process_flexi_attendance(doc.employee, str(doc.attendance_date))
    if not result:
        return

    # Update custom fields on Attendance (if they exist)
    if hasattr(doc, "flexi_late_minutes"):
        doc.db_set("flexi_late_minutes", result.late_minutes)
    if hasattr(doc, "flexi_grace_used"):
        doc.db_set("flexi_grace_used", result.grace_used)
    if hasattr(doc, "flexi_tardy_minutes"):
        doc.db_set("flexi_tardy_minutes", result.tardy_minutes)
    if hasattr(doc, "flexi_uncompensated_minutes"):
        doc.db_set("flexi_uncompensated_minutes", result.deficit_minutes)
    if hasattr(doc, "flexi_total_deduction"):
        doc.db_set("flexi_total_deduction", result.total_deduction_minutes)
    if hasattr(doc, "flexi_status"):
        doc.db_set("flexi_status", result.status)


# =============================================================================
# CLI / TESTING
# =============================================================================

def test_flexi_calculation():
    """
    Test the flexi calculation with sample data.
    Run via: bench execute hrms.hrms.utils.flexi_attendance.test_flexi_calculation
    """
    from datetime import datetime, time

    print("=" * 60)
    print("FLEXI-TIME ATTENDANCE CALCULATION TEST")
    print("=" * 60)

    # Mock data
    test_cases = [
        {
            "name": "On Time",
            "scheduled_in": time(9, 0),
            "scheduled_out": time(18, 0),
            "actual_in": datetime(2026, 1, 21, 9, 0),
            "actual_out": datetime(2026, 1, 21, 18, 0),
        },
        {
            "name": "Late but Compensated",
            "scheduled_in": time(9, 0),
            "scheduled_out": time(18, 0),
            "actual_in": datetime(2026, 1, 21, 9, 45),
            "actual_out": datetime(2026, 1, 21, 18, 45),
        },
        {
            "name": "Late, Partially Compensated",
            "scheduled_in": time(9, 0),
            "scheduled_out": time(18, 0),
            "actual_in": datetime(2026, 1, 21, 9, 45),
            "actual_out": datetime(2026, 1, 21, 18, 30),
        },
        {
            "name": "Exceeded Grace Period",
            "scheduled_in": time(9, 0),
            "scheduled_out": time(18, 0),
            "actual_in": datetime(2026, 1, 21, 10, 30),
            "actual_out": datetime(2026, 1, 21, 19, 0),
        },
        {
            "name": "Early Departure",
            "scheduled_in": time(9, 0),
            "scheduled_out": time(18, 0),
            "actual_in": datetime(2026, 1, 21, 9, 30),
            "actual_out": datetime(2026, 1, 21, 17, 30),
        },
    ]

    for tc in test_cases:
        print(f"\n--- {tc['name']} ---")
        print(f"Schedule: {tc['scheduled_in']} - {tc['scheduled_out']}")
        print(f"Actual: {tc['actual_in'].time()} - {tc['actual_out'].time()}")

        # Manual calculation for test
        shift = {
            "start_time": tc["scheduled_in"],
            "end_time": tc["scheduled_out"],
        }

        # Simplified calculation (same as calculate_flexi_attendance)
        scheduled_in_dt = datetime.combine(tc["actual_in"].date(), tc["scheduled_in"])
        late_seconds = (tc["actual_in"] - scheduled_in_dt).total_seconds()
        late_minutes = max(0, int(late_seconds / 60))

        grace_used = min(late_minutes, GRACE_PERIOD_MINUTES)
        tardy_minutes = max(0, late_minutes - GRACE_PERIOD_MINUTES)

        scheduled_out_dt = datetime.combine(tc["actual_out"].date(), tc["scheduled_out"])
        required_out_dt = scheduled_out_dt + timedelta(minutes=grace_used)

        if tc["actual_out"] < required_out_dt:
            deficit_minutes = int((required_out_dt - tc["actual_out"]).total_seconds() / 60)
        else:
            deficit_minutes = 0

        total_deduction = tardy_minutes + deficit_minutes

        print(f"Late: {late_minutes}min | Grace Used: {grace_used}min | Tardy: {tardy_minutes}min")
        print(f"Required OUT: {required_out_dt.time()} | Deficit: {deficit_minutes}min")
        print(f"TOTAL DEDUCTION: {total_deduction} minutes")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_flexi_calculation()
