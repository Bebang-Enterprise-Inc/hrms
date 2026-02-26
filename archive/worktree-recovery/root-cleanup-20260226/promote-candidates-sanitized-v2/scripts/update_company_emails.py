"""Update company_email field in Frappe tabEmployee for 32 employees.

Usage: Run inside Docker container with bench env Python:
  /home/frappe/frappe-bench/env/bin/python /tmp/update_company_emails.py

Reads from Employee Master CSV mappings. Updates tabEmployee.company_email
matching on attendance_device_id (Bio ID).
"""
import frappe

frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()

# Bio ID -> company_email mappings (from Employee Master)
MAPPINGS = {
    "9000040": "admin@bebang.ph",
    "9000115": "aldrin@bebang.ph",
    "9000740": "alyssa@bebang.ph",
    "9000897": "amelia@bebang.ph",
    "9000099": "ana@bebang.ph",
    "9000899": "angela@bebang.ph",
    "9001790": "angelamel@bebang.ph",
    "9001791": "anthony@bebang.ph",
    "9000114": "arnoldjames@bebang.ph",
    "9001548": "arshier@bebang.ph",
    "9000650": "avislyndelle@bebang.ph",
    "9000559": "butch@bebang.ph",
    "9000102": "dan@bebang.ph",
    "9000816": "denise@bebang.ph",
    "9000142": "ian@bebang.ph",
    "9001771": "ian@bebang.ph",
    "9000896": "ivy@bebang.ph",
    "9001788": "izza@bebang.ph",
    "9000560": "jay@bebang.ph",
    "9000817": "je-ann@bebang.ph",
    "9000810": "jeffrey@bebang.ph",
    "9001710": "jeffrey@bebang.ph",
    "9000043": "jenna@bebang.ph",
    "9001805": "jeson@bebang.ph",
    "9000050": "jojo@bebang.ph",
    "9001787": "juanna@bebang.ph",
    "9001794": "liezel@bebang.ph",
    "9001804": "marialuisa@bebang.ph",
    "9000189": "melissa@bebang.ph",
    "9001677": "reels@bebang.ph",
    "9000103": "ronald@bebang.ph",
    "9000651": "ronni@bebang.ph",
}

updated = 0
not_found = 0
already_set = 0
errors = 0

for bio_id, email in MAPPINGS.items():
    try:
        # Find employee by attendance_device_id
        employees = frappe.db.sql(
            "SELECT name, employee_name, company_email, attendance_device_id "
            "FROM tabEmployee WHERE attendance_device_id = %s",
            (bio_id,),
            as_dict=True
        )

        if not employees:
            print(f"  NOT FOUND: Bio ID {bio_id} -> {email}")
            not_found += 1
            continue

        for emp in employees:
            current = (emp.company_email or "").strip()
            if current == email:
                print(f"  SKIP: {emp.name} ({emp.employee_name}) already has {email}")
                already_set += 1
                continue

            frappe.db.sql(
                "UPDATE tabEmployee SET company_email = %s, modified = NOW() "
                "WHERE name = %s",
                (email, emp.name)
            )
            old_display = f" (was: {current})" if current else ""
            print(f"  SET: {emp.name} ({emp.employee_name}) -> {email}{old_display}")
            updated += 1

    except Exception as e:
        print(f"  ERROR: Bio ID {bio_id} -> {email}: {e}")
        errors += 1

frappe.db.commit()
print(f"\nSUMMARY: {updated} updated, {already_set} already set, {not_found} not found, {errors} errors")
print(f"Total processed: {len(MAPPINGS)} Bio IDs")
