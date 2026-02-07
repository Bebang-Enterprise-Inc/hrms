"""
Sprint 2 Test Data Seeder
Run via: bench --site hq.bebang.ph console < seed_sprint2_test_data.py

Creates test data for sprint 2 features:
- Attendance records (last 2 weeks) for test employees
- Salary Slips for test employees
- 1 BEI Announcement (Published)
- Stock Bin records (5 items) for test warehouse
- 1 BEI Distribution Trip with stops
- 7 BEI Shift Template records
- Sets custom_area_supervisor on test warehouses
"""

import frappe
from frappe.utils import nowdate, add_days, now_datetime
import datetime

def run():
    print("=== Sprint 2 Test Data Seeder ===")

    # Test employee IDs from canonical list
    TEST_EMPLOYEES = {
        "TEST-AREA-001": {"name": "Test Area Supervisor", "user": "test.area@bebang.ph"},
        "TEST-SUPERVISOR-001": {"name": "Test Store Supervisor", "user": "test.supervisor@bebang.ph"},
        "TEST-STAFF-001": {"name": "Test Store Staff", "user": "test.staff@bebang.ph"},
        "TEST-CREW-001": {"name": "Test Crew 1", "user": "test.crew1@bebang.ph"},
        "TEST-HR-001": {"name": "Test HR Officer", "user": "test.hr@bebang.ph"},
    }

    # Use a known test warehouse
    TEST_WAREHOUSE = "BGC Stopover - BEI"
    TEST_WAREHOUSE_2 = "Tagaytay Rotonda - BEI"
    COMPANY = "Bebang Enterprise Inc."

    today = nowdate()

    # ===== 1. Attendance Records (last 2 weeks) =====
    print("\n--- Creating Attendance Records ---")
    att_count = 0
    for emp_id, emp_info in TEST_EMPLOYEES.items():
        for day_offset in range(-13, 1):  # 14 days back to today
            att_date = add_days(today, day_offset)
            # Skip weekends for realism
            dt = datetime.datetime.strptime(str(att_date), "%Y-%m-%d")
            if dt.weekday() >= 6:  # Sunday only (PH retail works Sat)
                continue

            # Check if already exists
            exists = frappe.db.exists("Attendance", {
                "employee": emp_id,
                "attendance_date": att_date
            })
            if exists:
                continue

            try:
                frappe.db.sql("""
                    INSERT INTO `tabAttendance`
                    (name, employee, employee_name, attendance_date, status, company,
                     docstatus, creation, modified, modified_by, owner)
                    VALUES (%s, %s, %s, %s, %s, %s,
                            1, NOW(), NOW(), 'Administrator', 'Administrator')
                """, (
                    f"ATT-TEST-{emp_id}-{att_date}",
                    emp_id,
                    emp_info["name"],
                    att_date,
                    "Present",
                    COMPANY
                ))
                att_count += 1
            except Exception as e:
                if "Duplicate" in str(e):
                    pass
                else:
                    print(f"  WARN: Attendance {emp_id} {att_date}: {e}")

    frappe.db.commit()
    print(f"  Created {att_count} attendance records")

    # ===== 2. Salary Slips =====
    print("\n--- Creating Salary Slips ---")
    ss_count = 0
    for emp_id, emp_info in TEST_EMPLOYEES.items():
        slip_name = f"SS-TEST-{emp_id}-2026-01"
        if frappe.db.exists("Salary Slip", slip_name):
            print(f"  Skip {slip_name} (exists)")
            continue

        try:
            frappe.db.sql("""
                INSERT INTO `tabSalary Slip`
                (name, employee, employee_name, company, posting_date,
                 start_date, end_date, gross_pay, net_pay, total_deduction,
                 docstatus, creation, modified, modified_by, owner)
                VALUES (%s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        0, NOW(), NOW(), 'Administrator', 'Administrator')
            """, (
                slip_name, emp_id, emp_info["name"], COMPANY, "2026-01-31",
                "2026-01-01", "2026-01-31", 25000, 22000, 3000
            ))
            ss_count += 1
        except Exception as e:
            if "Duplicate" in str(e):
                pass
            else:
                print(f"  WARN: Salary Slip {emp_id}: {e}")

    frappe.db.commit()
    print(f"  Created {ss_count} salary slips")

    # ===== 3. BEI Announcement =====
    print("\n--- Creating BEI Announcement ---")
    ann_name = "BEI-ANN-2026-00001"
    if not frappe.db.exists("BEI Announcement", ann_name):
        try:
            frappe.db.sql("""
                INSERT INTO `tabBEI Announcement`
                (name, title, announcement_type, priority, status,
                 publish_date, content, target_audience, published_by,
                 requires_acknowledgment,
                 creation, modified, modified_by, owner)
                VALUES (%s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        NOW(), NOW(), 'Administrator', 'Administrator')
            """, (
                ann_name,
                "Welcome to Sprint 2 Testing",
                "General",
                "Normal",
                "Published",
                now_datetime(),
                "<p>This is a test announcement for Sprint 2. All store operations features are now live for testing.</p>",
                "All",
                "Administrator",
                0
            ))
            frappe.db.commit()
            print(f"  Created announcement: {ann_name}")
        except Exception as e:
            print(f"  WARN: Announcement: {e}")
    else:
        print(f"  Skip {ann_name} (exists)")

    # ===== 4. Stock Bin Records =====
    print("\n--- Creating Stock Bin Records ---")
    test_items = [
        ("ITEM-CHICKEN-001", "Chicken Breast", 50),
        ("ITEM-RICE-001", "Premium Rice 25kg", 20),
        ("ITEM-OIL-001", "Cooking Oil 1L", 30),
        ("ITEM-SAUCE-001", "Soy Sauce 1L", 40),
        ("ITEM-CUPS-001", "Paper Cups 12oz", 100),
    ]
    bin_count = 0
    for item_code, item_name, qty in test_items:
        # Ensure Item exists first
        if not frappe.db.exists("Item", item_code):
            try:
                frappe.db.sql("""
                    INSERT INTO `tabItem`
                    (name, item_code, item_name, item_group, stock_uom,
                     is_stock_item, valuation_rate, disabled,
                     creation, modified, modified_by, owner)
                    VALUES (%s, %s, %s, %s, %s,
                            1, %s, 0,
                            NOW(), NOW(), 'Administrator', 'Administrator')
                """, (
                    item_code, item_code, item_name, "Products", "Nos",
                    100.0
                ))
                print(f"  Created item: {item_code}")
            except Exception as e:
                if "Duplicate" not in str(e):
                    print(f"  WARN: Item {item_code}: {e}")

        # Create or update Bin
        bin_exists = frappe.db.exists("Bin", {"item_code": item_code, "warehouse": TEST_WAREHOUSE})
        if not bin_exists:
            try:
                frappe.db.sql("""
                    INSERT INTO `tabBin`
                    (name, item_code, warehouse, actual_qty, valuation_rate,
                     stock_value, creation, modified, modified_by, owner)
                    VALUES (%s, %s, %s, %s, %s,
                            %s, NOW(), NOW(), 'Administrator', 'Administrator')
                """, (
                    f"BIN-{item_code}-TEST",
                    item_code,
                    TEST_WAREHOUSE,
                    qty,
                    100.0,
                    qty * 100.0
                ))
                bin_count += 1
            except Exception as e:
                if "Duplicate" not in str(e):
                    print(f"  WARN: Bin {item_code}: {e}")
        else:
            print(f"  Skip bin {item_code} (exists)")

    frappe.db.commit()
    print(f"  Created {bin_count} stock bins")

    # ===== 5. BEI Distribution Trip =====
    print("\n--- Creating BEI Distribution Trip ---")
    trip_name = "BEI-TRIP-2026-00001"
    if not frappe.db.exists("BEI Distribution Trip", trip_name):
        try:
            frappe.db.sql("""
                INSERT INTO `tabBEI Distribution Trip`
                (name, naming_series, trip_date, route_name, status,
                 driver, vehicle, vehicle_plate,
                 creation, modified, modified_by, owner)
                VALUES (%s, %s, %s, %s, %s,
                        %s, %s, %s,
                        NOW(), NOW(), 'Administrator', 'Administrator')
            """, (
                trip_name,
                "BEI-TRIP-.YYYY.-.#####",
                today,
                "North Route - BGC + Tagaytay",
                "Preparing",
                "Administrator",
                "Isuzu Elf",
                "ABC 1234"
            ))
            # Add stops (child table rows)
            for idx, (store, order) in enumerate([
                (TEST_WAREHOUSE, 1),
                (TEST_WAREHOUSE_2, 2),
            ], 1):
                if frappe.db.exists("Warehouse", store):
                    frappe.db.sql("""
                        INSERT INTO `tabBEI Trip Stop`
                        (name, parent, parentfield, parenttype, idx,
                         store, stop_order, items_count, status,
                         creation, modified, modified_by, owner)
                        VALUES (%s, %s, 'stops', 'BEI Distribution Trip', %s,
                                %s, %s, %s, 'Pending',
                                NOW(), NOW(), 'Administrator', 'Administrator')
                    """, (
                        f"STOP-TEST-{idx}",
                        trip_name,
                        idx,
                        store,
                        order,
                        10 * idx
                    ))
            frappe.db.commit()
            print(f"  Created trip: {trip_name}")
        except Exception as e:
            print(f"  WARN: Trip: {e}")
    else:
        print(f"  Skip {trip_name} (exists)")

    # ===== 6. BEI Shift Templates =====
    print("\n--- Creating BEI Shift Templates ---")
    templates = [
        ("Opening Shift", "06:00:00", "14:00:00", "Opening crew arrives before mall opens", "All Stores"),
        ("Mid Shift", "10:00:00", "18:00:00", "Mid-day coverage shift", "All Stores"),
        ("Closing Shift", "14:00:00", "22:00:00", "Closing crew handles end-of-day", "All Stores"),
        ("Split Shift", "06:00:00", "22:00:00", "Split shift for supervisors", "All Stores"),
        ("Graveyard Shift", "22:00:00", "06:00:00", "Overnight commissary production", "All Stores"),
        ("Early Bird", "05:00:00", "13:00:00", "Early morning prep shift", "Mall Stores"),
        ("Late Night", "15:00:00", "23:00:00", "Late evening shift for mall stores", "Mall Stores"),
    ]
    tmpl_count = 0
    for tname, opening, closing, desc, applies_to in templates:
        if not frappe.db.exists("BEI Shift Template", tname):
            try:
                frappe.db.sql("""
                    INSERT INTO `tabBEI Shift Template`
                    (name, template_name, is_active, description, applies_to,
                     opening_time, closing_time, max_daily_hours, min_break_minutes,
                     require_two_person_close, prep_time_minutes, cleanup_time_minutes,
                     creation, modified, modified_by, owner)
                    VALUES (%s, %s, 1, %s, %s,
                            %s, %s, 8, 60,
                            1, 30, 30,
                            NOW(), NOW(), 'Administrator', 'Administrator')
                """, (
                    tname, tname, desc, applies_to,
                    opening, closing
                ))
                tmpl_count += 1
            except Exception as e:
                if "Duplicate" not in str(e):
                    print(f"  WARN: Template {tname}: {e}")
        else:
            print(f"  Skip template {tname} (exists)")

    frappe.db.commit()
    print(f"  Created {tmpl_count} shift templates")

    # ===== 7. Set custom_area_supervisor on test warehouses =====
    print("\n--- Setting Area Supervisor on Warehouses ---")
    area_sup = "test.area@bebang.ph"  # Must be user email, not Employee ID
    test_warehouses = [TEST_WAREHOUSE, TEST_WAREHOUSE_2]
    for wh in test_warehouses:
        if frappe.db.exists("Warehouse", wh):
            try:
                # Check if custom field exists
                has_field = frappe.db.sql("""
                    SELECT 1 FROM `tabCustom Field`
                    WHERE dt='Warehouse' AND fieldname='custom_area_supervisor'
                """)
                if has_field:
                    frappe.db.sql("""
                        UPDATE `tabWarehouse`
                        SET custom_area_supervisor = %s, modified = NOW()
                        WHERE name = %s
                    """, (area_sup, wh))
                    print(f"  Set area supervisor on {wh}")
                else:
                    print(f"  WARN: custom_area_supervisor field not found on Warehouse")
                    break
            except Exception as e:
                print(f"  WARN: {wh}: {e}")
        else:
            print(f"  Skip {wh} (warehouse not found)")

    frappe.db.commit()
    print("\n=== Seed Complete ===")


run()
