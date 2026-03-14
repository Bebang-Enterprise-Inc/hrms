"""S043: Seed 12 canonical BEI Shift Types with full auto-attendance configuration.

Run via: bench execute hrms.patches.v16_0.s043_seed_shift_types.execute
"""

import frappe
from frappe.utils import now_datetime


# Auto-attendance starts from BEI's February 1, 2026 go-live.
# `process_attendance_after` is a Date field, not a Time field.
AUTO_ATTENDANCE_START_DATE = "2026-02-01"


SHIFT_TYPES = [
    # Retail Store Shifts (7)
    {
        "name": "Store - Early Opening",
        "custom_short_code": "S-8A",
        "start_time": "08:00:00",
        "end_time": "17:00:00",
        "process_attendance_after": "18:00:00",
    },
    {
        "name": "Store - Morning",
        "custom_short_code": "S-9A",
        "start_time": "09:00:00",
        "end_time": "18:00:00",
        "process_attendance_after": "19:00:00",
    },
    {
        "name": "Store - Mid Morning",
        "custom_short_code": "S-10A",
        "start_time": "10:00:00",
        "end_time": "19:00:00",
        "process_attendance_after": "20:00:00",
    },
    {
        "name": "Store - Late Morning",
        "custom_short_code": "S-11A",
        "start_time": "11:00:00",
        "end_time": "20:00:00",
        "process_attendance_after": "21:00:00",
    },
    {
        "name": "Store - Afternoon",
        "custom_short_code": "S-12P",
        "start_time": "12:00:00",
        "end_time": "21:00:00",
        "process_attendance_after": "22:00:00",
    },
    {
        "name": "Store - Mid Afternoon",
        "custom_short_code": "S-1P",
        "start_time": "13:00:00",
        "end_time": "22:00:00",
        "process_attendance_after": "23:00:00",
    },
    {
        "name": "Store - Late Afternoon",
        "custom_short_code": "S-2P",
        "start_time": "14:00:00",
        "end_time": "23:00:00",
        "process_attendance_after": "00:00:00",
    },
    # Commissary Shifts (5)
    {
        "name": "Commissary - Dawn",
        "custom_short_code": "C-4A",
        "start_time": "04:00:00",
        "end_time": "13:00:00",
        "process_attendance_after": "14:00:00",
    },
    {
        "name": "Commissary - AM",
        "custom_short_code": "C-5A",
        "start_time": "05:00:00",
        "end_time": "14:00:00",
        "process_attendance_after": "15:00:00",
    },
    {
        "name": "Commissary - AM Late",
        "custom_short_code": "C-6A",
        "start_time": "06:00:00",
        "end_time": "15:00:00",
        "process_attendance_after": "16:00:00",
    },
    {
        "name": "Commissary - PM Night",
        "custom_short_code": "C-4P",
        "start_time": "16:00:00",
        "end_time": "01:00:00",
        "process_attendance_after": "02:00:00",
    },
    {
        "name": "Commissary - Night",
        "custom_short_code": "C-5P",
        "start_time": "17:00:00",
        "end_time": "02:00:00",
        "process_attendance_after": "03:00:00",
    },
]

# Fields shared by ALL shift types
COMMON_FIELDS = {
    "enable_auto_attendance": 1,
    "late_entry_grace_period": 15,
    "early_exit_grace_period": 15,
    "working_hours_threshold_for_half_day": 4,
    "working_hours_threshold_for_absent": 1,
    "allow_check_out_after_shift_end_time": 60,
    "working_hours_calculation_based_on": "First Check-in and Last Check-out",
    "enable_late_entry_marking": 1,
    "enable_early_exit_marking": 1,
    "auto_update_last_sync": 1,
    "determine_check_in_and_check_out": "Alternating entries as IN and OUT during the same shift",
    "mark_auto_attendance_on_holidays": 0,
}


def execute():
    """Seed or update all 12 BEI canonical Shift Types."""
    created = 0
    updated = 0

    for shift_def in SHIFT_TYPES:
        name = shift_def["name"]
        fields = {**COMMON_FIELDS, **shift_def}
        fields["process_attendance_after"] = AUTO_ATTENDANCE_START_DATE
        # Seed a valid baseline immediately; the hourly scheduler keeps it fresh afterwards.
        fields["last_sync_of_checkin"] = now_datetime()

        if frappe.db.exists("Shift Type", name):
            # Update existing — ensure all auto-attendance fields are set
            doc = frappe.get_doc("Shift Type", name)
            changed = False
            for key, val in fields.items():
                if key == "name":
                    continue
                current = getattr(doc, key, None)
                if key == "custom_short_code":
                    current = getattr(doc, "custom_short_code", None)
                if str(current) != str(val):
                    setattr(doc, key, val)
                    changed = True
            if changed:
                doc.save(ignore_permissions=True)
                updated += 1
                frappe.logger().info(f"S043: Updated Shift Type {name}")
        else:
            doc = frappe.get_doc({"doctype": "Shift Type", **fields})
            doc.insert(ignore_permissions=True)
            created += 1
            frappe.logger().info(f"S043: Created Shift Type {name}")

    frappe.db.commit()
    print(f"S043 Shift Type seed: {created} created, {updated} updated, {12 - created - updated} unchanged")

    # Verify all pass has_incorrect_shift_config check
    from hrms.hr.doctype.shift_type.shift_type import has_incorrect_shift_config

    failures = []
    for shift_def in SHIFT_TYPES:
        name = shift_def["name"]
        doc = frappe.get_doc("Shift Type", name)
        if has_incorrect_shift_config(doc):
            failures.append(name)

    if failures:
        print(f"WARNING: {len(failures)} Shift Types FAIL has_incorrect_shift_config: {failures}")
    else:
        print("PASS: All 12 Shift Types pass has_incorrect_shift_config check")
