"""S150 Payroll Data Quality — SSM Execution Script.

Run this on the Frappe server (inside Docker container) via bench console or SSM.
It performs ALL Phase 1 + Phase 2 operations in sequence with verification.

Usage:
    bench --site hq.bebang.ph execute scripts.s150_payroll_data_quality.execute_all

Or step-by-step:
    bench --site hq.bebang.ph execute scripts.s150_payroll_data_quality.p1_1_submit_payroll_period
    bench --site hq.bebang.ph execute scripts.s150_payroll_data_quality.p1_2_link_tax_slabs
    ...etc

Each function prints before/after counts and is idempotent.
"""

import csv
import io
import os
import re
from collections import defaultdict

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


# ============================================================================
# Helpers
# ============================================================================

PAYROLL_RATES_CSV = "data/_FINAL/Payroll_RatesData_Mar25_AllBatches.csv"
PAYROLL_COMPRE_CSV = "data/_FINAL/Payroll_Feb25_Mar10_Mar25.csv"
EMPLOYEE_MASTER_CSV = "data/_FINAL/EMPLOYEE_MASTER.csv"


def load_csv(path):
    """Load a CSV file from the repo root."""
    # Resolve relative to bench site or absolute
    if not os.path.isabs(path):
        # Try relative to current dir, then common locations
        for base in [os.getcwd(), "/home/frappe/frappe-bench", "F:/Dropbox/Projects/BEI-ERP"]:
            full = os.path.join(base, path)
            if os.path.exists(full):
                path = full
                break

    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def extract_lastname_firstname(name):
    """Extract (LASTNAME, FIRSTNAME) tuple for matching."""
    n = name.upper().strip()
    n = re.sub(r"\b(JR\.?|SR\.?|III|IV|II)\b", "", n)
    n = re.sub(r"[.,]", " ", n)
    tokens = [t for t in n.split() if t]
    if not tokens:
        return ("", "")
    if "," in name:
        parts = name.upper().split(",", 1)
        last = re.sub(r"[^A-Z\s]", "", parts[0]).strip()
        first_tokens = re.sub(r"[^A-Z\s]", "", parts[1]).strip().split()
        firstname = first_tokens[0] if first_tokens else ""
        return (last, firstname)
    else:
        return (tokens[-1] if len(tokens) > 1 else tokens[0], tokens[0])


def build_payroll_to_frappe_map():
    """Build EmployeeNo -> Frappe employee name mapping using 3-tier strategy.

    Returns: dict[payroll_emp_no -> frappe_employee_id], list[unmatched]
    """
    em_rows = load_csv(EMPLOYEE_MASTER_CSV)
    rates_rows = load_csv(PAYROLL_RATES_CSV)

    active = [r for r in em_rows if r.get("status", "").strip() == "Active"]

    # Tier 1: payroll_emp_no direct match
    emp_no_map = {}
    for r in active:
        pno = r.get("payroll_emp_no", "").strip()
        bio_id = r.get("new_attendance_device_id", "").strip()
        if pno and bio_id:
            emp_no_map[pno] = bio_id

    # Tier 2: lastname+firstname index
    lf_idx = defaultdict(list)
    for r in active:
        bio_id = r.get("new_attendance_device_id", "").strip()
        if not bio_id:
            continue
        for raw in [r.get("employee_name", ""), r.get("payroll_name", "")]:
            raw = raw.strip()
            if raw:
                lf = extract_lastname_firstname(raw)
                if lf[0] and lf[1]:
                    lf_idx[lf].append(bio_id)

    # Match each RatesData employee
    matched = {}  # payroll_emp_no -> frappe_employee_id (HR-XXXXX format)
    unmatched = []

    for rd in rates_rows:
        eno = rd["EmployeeNo"].strip()
        fn = rd["FullName"].strip()
        basic = float(rd.get("BasicPay_Monthly", 0) or 0)

        # Tier 1
        if eno in emp_no_map:
            # Now find the Frappe Employee docname (HR-XXXXX)
            frappe_id = _bio_id_to_employee(emp_no_map[eno])
            if frappe_id:
                matched[eno] = frappe_id
                continue

        # Tier 2
        lf = extract_lastname_firstname(fn)
        if lf in lf_idx:
            bio_ids = list(set(lf_idx[lf]))
            if len(bio_ids) == 1:
                frappe_id = _bio_id_to_employee(bio_ids[0])
                if frappe_id:
                    matched[eno] = frappe_id
                    continue

        unmatched.append({"payroll_emp_no": eno, "fullname": fn, "basic_monthly": basic})

    return matched, unmatched


def _bio_id_to_employee(bio_id):
    """Convert bio device ID (9xxxxxx) to Frappe Employee name (HR-XXXXX)."""
    result = frappe.db.get_value(
        "Employee",
        {"attendance_device_id": bio_id, "status": "Active"},
        "name",
    )
    return result


# ============================================================================
# Phase 1 — Fix 5 Blockers
# ============================================================================


def p1_1_submit_payroll_period():
    """P1-1: Submit the 2026 Payroll Period."""
    pp_name = frappe.db.get_value(
        "Payroll Period",
        {"company": "Bebang Enterprise Inc."},
        "name",
    )
    if not pp_name:
        print("ERROR: No Payroll Period found for Bebang Enterprise Inc.")
        return

    docstatus = frappe.db.get_value("Payroll Period", pp_name, "docstatus")
    print(f"BEFORE: Payroll Period '{pp_name}' docstatus={docstatus}")

    if docstatus == 1:
        print("Already submitted. Skipping.")
        return

    pp = frappe.get_doc("Payroll Period", pp_name)
    pp.submit()
    frappe.db.commit()

    docstatus_after = frappe.db.get_value("Payroll Period", pp_name, "docstatus")
    print(f"AFTER: Payroll Period '{pp_name}' docstatus={docstatus_after}")


def p1_2_link_tax_slabs():
    """P1-2: Link Income Tax Slab to all SSAs."""
    # Verify slab exists
    slab_name = frappe.db.get_value("Income Tax Slab", {"name": ("like", "%TRAIN%Philippines%")}, "name")
    if not slab_name:
        all_slabs = frappe.get_all("Income Tax Slab", pluck="name")
        print(f"ERROR: TRAIN Law slab not found! Available slabs: {all_slabs}")
        return

    print(f"Using tax slab: {slab_name}")

    # Count before
    no_slab = frappe.db.count("Salary Structure Assignment", {"docstatus": 1, "income_tax_slab": ("is", "not set")})
    has_slab = frappe.db.count("Salary Structure Assignment", {"docstatus": 1, "income_tax_slab": ("is", "set")})
    print(f"BEFORE: {no_slab} SSAs without slab, {has_slab} with slab")

    # Update using frappe.db.set_value (NOT raw SQL — submitted doc safety)
    ssas_to_update = frappe.get_all(
        "Salary Structure Assignment",
        filters={"docstatus": 1, "income_tax_slab": ("is", "not set")},
        pluck="name",
    )

    for i, ssa_name in enumerate(ssas_to_update):
        frappe.db.set_value(
            "Salary Structure Assignment", ssa_name,
            "income_tax_slab", slab_name,
            update_modified=True,
        )
        if (i + 1) % 100 == 0:
            frappe.db.commit()
            print(f"  Updated {i + 1}/{len(ssas_to_update)}...")

    frappe.db.commit()

    # Count after
    no_slab_after = frappe.db.count("Salary Structure Assignment", {"docstatus": 1, "income_tax_slab": ("is", "not set")})
    print(f"AFTER: {no_slab_after} SSAs without slab (should be 0)")
    print(f"Updated {len(ssas_to_update)} SSAs")


def p1_3_set_salary_mode():
    """P1-3: Set salary_mode on all active employees."""
    # Count before
    no_mode = frappe.db.sql(
        "SELECT COUNT(*) FROM tabEmployee WHERE status='Active' AND (salary_mode IS NULL OR salary_mode='')"
    )[0][0]
    print(f"BEFORE: {no_mode} active employees without salary_mode")

    # Bank mode for those with bank details
    bank_updated = frappe.db.sql("""
        UPDATE tabEmployee
        SET salary_mode = 'Bank'
        WHERE status = 'Active'
          AND (salary_mode IS NULL OR salary_mode = '')
          AND bank_name IS NOT NULL AND bank_name != ''
          AND bank_ac_no IS NOT NULL AND bank_ac_no != ''
    """)
    bank_count = frappe.db.sql("SELECT ROW_COUNT()")[0][0]

    # Cash mode for the rest
    cash_updated = frappe.db.sql("""
        UPDATE tabEmployee
        SET salary_mode = 'Cash'
        WHERE status = 'Active'
          AND (salary_mode IS NULL OR salary_mode = '')
    """)
    cash_count = frappe.db.sql("SELECT ROW_COUNT()")[0][0]

    frappe.db.commit()

    no_mode_after = frappe.db.sql(
        "SELECT COUNT(*) FROM tabEmployee WHERE status='Active' AND (salary_mode IS NULL OR salary_mode='')"
    )[0][0]
    print(f"AFTER: {no_mode_after} active employees without salary_mode")
    print(f"Set Bank: {bank_count}, Cash: {cash_count}")


def p1_4_update_ssa_base_salaries():
    """P1-4: Update SSA base salaries from actual payroll data."""
    matched, unmatched = build_payroll_to_frappe_map()
    rates_rows = load_csv(PAYROLL_RATES_CSV)

    # Build EmployeeNo -> BasicPay_Monthly
    rates_by_eno = {}
    for rd in rates_rows:
        eno = rd["EmployeeNo"].strip()
        basic = float(rd.get("BasicPay_Monthly", 0) or 0)
        rates_by_eno[eno] = basic

    updated = 0
    skipped_zero = 0
    skipped_no_ssa = 0
    skipped_match_ok = 0

    for eno, frappe_emp in matched.items():
        basic = rates_by_eno.get(eno, 0)
        if basic <= 0:
            skipped_zero += 1
            continue

        # Get current SSA
        ssa = frappe.db.sql("""
            SELECT name, base FROM `tabSalary Structure Assignment`
            WHERE employee = %s AND docstatus = 1
            ORDER BY from_date DESC LIMIT 1
        """, frappe_emp, as_dict=True)

        if not ssa:
            skipped_no_ssa += 1
            continue

        current_base = float(ssa[0]["base"] or 0)
        if abs(current_base - basic) < 1:  # Already correct
            skipped_match_ok += 1
            continue

        # Update using frappe.db.set_value
        frappe.db.set_value(
            "Salary Structure Assignment", ssa[0]["name"],
            "base", basic,
            update_modified=True,
        )
        updated += 1
        if updated % 100 == 0:
            frappe.db.commit()

    frappe.db.commit()

    # Count zero-base SSAs remaining
    zero_base = frappe.db.sql(
        "SELECT COUNT(*) FROM `tabSalary Structure Assignment` WHERE docstatus=1 AND (base IS NULL OR base=0)"
    )[0][0]

    print(f"RESULTS:")
    print(f"  Payroll employees matched to Frappe: {len(matched)}/{len(rates_rows)}")
    print(f"  SSA bases updated: {updated}")
    print(f"  Already correct: {skipped_match_ok}")
    print(f"  Skipped (zero payroll): {skipped_zero}")
    print(f"  Skipped (no SSA): {skipped_no_ssa}")
    print(f"  Unmatched employees: {len(unmatched)}")
    print(f"  Zero-base SSAs remaining: {zero_base}")

    # Save unmatched report
    if unmatched:
        print(f"\nUnmatched employees ({len(unmatched)}):")
        for u in unmatched[:20]:
            print(f"  PayrollNo={u['payroll_emp_no']}: {u['fullname']} (₱{u['basic_monthly']:,.2f}/mo)")


def p1_5_create_salary_structures_and_ssas():
    """P1-5: Create 2 new salary structures + SSAs for employees missing them."""

    # --- Create Supervisory and Executive salary structures ---
    structures_to_create = {
        "Supervisory Staff - Regular": "Store Staff - Regular",
        "Executive Staff - Regular": "HO Staff - Regular",
    }

    for new_name, source_name in structures_to_create.items():
        if frappe.db.exists("Salary Structure", new_name):
            print(f"Structure '{new_name}' already exists. Skipping creation.")
            continue

        source = frappe.get_doc("Salary Structure", source_name)
        new_doc = frappe.copy_doc(source)
        new_doc.name = None
        new_doc.__newname = new_name
        new_doc.is_active = "Yes"
        new_doc.company = "Bebang Enterprise Inc."
        new_doc.currency = "PHP"
        new_doc.insert(ignore_permissions=True)
        new_doc.submit()
        frappe.db.commit()
        print(f"Created and submitted: {new_name}")

    # --- Re-map existing SSAs by designation ---
    designation_map = {
        # Executive keywords
        "CEO": "Executive Staff - Regular",
        "CFO": "Executive Staff - Regular",
        "COO": "Executive Staff - Regular",
        "VP": "Executive Staff - Regular",
        "DIRECTOR": "Executive Staff - Regular",
        "PRESIDENT": "Executive Staff - Regular",
        # Supervisory keywords
        "SUPERVISOR": "Supervisory Staff - Regular",
        "AREA SUPERVISOR": "Supervisory Staff - Regular",
        "AREA SUP": "Supervisory Staff - Regular",
        "TEAM LEAD": "Supervisory Staff - Regular",
        "ASST. MANAGER": "Supervisory Staff - Regular",
        "ASSISTANT MANAGER": "Supervisory Staff - Regular",
    }

    # Get all active SSAs with employee designation
    ssas = frappe.db.sql("""
        SELECT ssa.name, ssa.employee, ssa.salary_structure, e.designation
        FROM `tabSalary Structure Assignment` ssa
        JOIN tabEmployee e ON e.name = ssa.employee
        WHERE ssa.docstatus = 1 AND e.status = 'Active'
    """, as_dict=True)

    remapped = 0
    for ssa in ssas:
        desig = (ssa.get("designation") or "").upper().strip()
        new_structure = None
        for keyword, structure in designation_map.items():
            if keyword in desig:
                new_structure = structure
                break

        if not new_structure:
            # Keep HO Staff for HO designations, Store Staff for others
            if any(kw in desig for kw in ["MANAGER", "OFFICER", "ANALYST", "SPECIALIST", "ACCOUNTANT", "COORDINATOR"]):
                new_structure = "HO Staff - Regular"
            else:
                continue  # Store Staff stays as-is

        if ssa["salary_structure"] != new_structure:
            frappe.db.set_value(
                "Salary Structure Assignment", ssa["name"],
                "salary_structure", new_structure,
                update_modified=True,
            )
            remapped += 1

    frappe.db.commit()
    print(f"Re-mapped {remapped} SSAs by designation")

    # --- Create SSAs for active employees without one ---
    no_ssa = frappe.db.sql("""
        SELECT e.name, e.employee_name, e.designation, e.department
        FROM tabEmployee e
        LEFT JOIN `tabSalary Structure Assignment` ssa
            ON ssa.employee = e.name AND ssa.docstatus = 1
        WHERE e.status = 'Active'
          AND ssa.name IS NULL
          AND e.name NOT LIKE 'test%%'
    """, as_dict=True)

    print(f"\nActive employees without SSA: {len(no_ssa)}")

    # Try to get salary from payroll data
    matched, _ = build_payroll_to_frappe_map()
    rates_rows = load_csv(PAYROLL_RATES_CSV)
    rates_by_eno = {rd["EmployeeNo"].strip(): float(rd.get("BasicPay_Monthly", 0) or 0) for rd in rates_rows}

    # Reverse map: frappe_emp -> payroll_emp_no
    frappe_to_payroll = {v: k for k, v in matched.items()}

    # Get slab name
    slab_name = frappe.db.get_value("Income Tax Slab", {"name": ("like", "%TRAIN%Philippines%")}, "name")

    created = 0
    skipped = 0
    for emp in no_ssa:
        desig = (emp.get("designation") or "").upper().strip()

        # Determine salary structure
        structure = "Store Staff - Regular"
        for keyword, struct in designation_map.items():
            if keyword in desig:
                structure = struct
                break
        if not structure.startswith(("Executive", "Supervisory")):
            if any(kw in desig for kw in ["MANAGER", "OFFICER", "ANALYST", "SPECIALIST", "ACCOUNTANT", "COORDINATOR"]):
                structure = "HO Staff - Regular"

        # Get base salary from payroll
        peno = frappe_to_payroll.get(emp["name"])
        base = rates_by_eno.get(peno, 0) if peno else 0

        if base <= 0:
            # Try Employee Master monthly_rate
            base = float(frappe.db.get_value("Employee", emp["name"], "ctc") or 0)
            if base <= 0:
                skipped += 1
                continue

        # Create SSA
        try:
            ssa_doc = frappe.get_doc({
                "doctype": "Salary Structure Assignment",
                "employee": emp["name"],
                "employee_name": emp["employee_name"],
                "salary_structure": structure,
                "from_date": "2026-02-01",
                "base": base,
                "currency": "PHP",
                "company": "Bebang Enterprise Inc.",
                "income_tax_slab": slab_name or "",
            })
            ssa_doc.insert(ignore_permissions=True)
            ssa_doc.submit()
            created += 1
        except Exception as e:
            print(f"  Failed to create SSA for {emp['name']} ({emp['employee_name']}): {e}")

        if created % 50 == 0:
            frappe.db.commit()

    frappe.db.commit()
    print(f"Created {created} new SSAs, skipped {skipped} (no salary data)")


# ============================================================================
# Phase 2 — Import Allowance Data
# ============================================================================


def p2_1_create_salary_components():
    """P2-1: Create missing salary components."""
    components = [
        {"name1": "Communication Allowance", "type": "Earning", "is_tax_applicable": 1},
        {"name1": "De Minimis Allowance", "type": "Earning", "is_tax_applicable": 0},
        {"name1": "Honorarium Allowance", "type": "Earning", "is_tax_applicable": 1},  # DQ-4: taxable per actual payroll
        {"name1": "Meal Allowance", "type": "Earning", "is_tax_applicable": 0},
        {"name1": "Gasoline Allowance", "type": "Earning", "is_tax_applicable": 0},
        {"name1": "Other Fixed Allowance", "type": "Earning", "is_tax_applicable": 0},
    ]

    created = 0
    existing = 0
    for comp in components:
        if frappe.db.exists("Salary Component", comp["name1"]):
            existing += 1
            continue

        doc = frappe.get_doc({
            "doctype": "Salary Component",
            "salary_component": comp["name1"],
            "salary_component_abbr": comp["name1"][:4].upper(),
            "type": comp["type"],
            "is_tax_applicable": comp["is_tax_applicable"],
            "company": "Bebang Enterprise Inc.",
        })
        doc.insert(ignore_permissions=True)
        created += 1

    frappe.db.commit()
    print(f"Salary Components: {created} created, {existing} already existed")

    # Add components to all 4 salary structures
    structures = frappe.get_all(
        "Salary Structure",
        filters={"docstatus": 1, "is_active": "Yes"},
        pluck="name",
    )
    for struct_name in structures:
        struct = frappe.get_doc("Salary Structure", struct_name)
        existing_components = {d.salary_component for d in struct.earnings}
        added = 0
        for comp in components:
            if comp["name1"] not in existing_components:
                struct.append("earnings", {
                    "salary_component": comp["name1"],
                    "amount": 0,
                    "amount_based_on_formula": 0,
                })
                added += 1
        if added:
            struct.save(ignore_permissions=True)
            print(f"  Added {added} components to {struct_name}")

    frappe.db.commit()


def p2_2_create_custom_fields_and_import():
    """P2-2: Create custom fields on Employee + import allowance data."""

    # --- Create Custom Fields ---
    custom_fields = {
        "Employee": [
            {
                "fieldname": "bei_payroll_allowances_section",
                "fieldtype": "Section Break",
                "label": "Payroll Allowances (from Mar 2026 payroll)",
                "insert_after": "ctc",
                "collapsible": 1,
            },
            {
                "fieldname": "bei_comm_allow_monthly",
                "fieldtype": "Currency",
                "label": "Communication Allowance (Monthly)",
                "insert_after": "bei_payroll_allowances_section",
                "options": "PHP",
            },
            {
                "fieldname": "bei_deminimis_monthly",
                "fieldtype": "Currency",
                "label": "De Minimis Allowance (Monthly)",
                "insert_after": "bei_comm_allow_monthly",
                "options": "PHP",
            },
            {
                "fieldname": "bei_honorarium_monthly",
                "fieldtype": "Currency",
                "label": "Honorarium (Monthly)",
                "insert_after": "bei_deminimis_monthly",
                "options": "PHP",
            },
            {
                "fieldname": "bei_allowances_col_break",
                "fieldtype": "Column Break",
                "insert_after": "bei_honorarium_monthly",
            },
            {
                "fieldname": "bei_meal_allow_monthly",
                "fieldtype": "Currency",
                "label": "Meal Allowance (Monthly)",
                "insert_after": "bei_allowances_col_break",
                "options": "PHP",
            },
            {
                "fieldname": "bei_gasoline_allow_monthly",
                "fieldtype": "Currency",
                "label": "Gasoline Allowance (Monthly)",
                "insert_after": "bei_meal_allow_monthly",
                "options": "PHP",
            },
            {
                "fieldname": "bei_other_fixed_monthly",
                "fieldtype": "Currency",
                "label": "Other Fixed Allowance (Monthly)",
                "insert_after": "bei_gasoline_allow_monthly",
                "options": "PHP",
            },
        ]
    }

    create_custom_fields(custom_fields)
    frappe.db.commit()
    print("Custom fields created. Run 'bench migrate' + 'bench clear-cache' next.")

    # Verify columns exist
    cols = frappe.db.sql("SHOW COLUMNS FROM tabEmployee LIKE 'bei_%'")
    print(f"V-09: {len(cols)} bei_* columns found in tabEmployee (expected 6+)")

    if len(cols) < 6:
        print("WARNING: Not all columns created. Run 'bench migrate' first!")
        return

    _import_allowances()


def _import_allowances():
    """Import allowance data from payroll CSVs into Employee custom fields."""
    matched, unmatched = build_payroll_to_frappe_map()

    # Load RatesData for CommAllow, DeMinimis, Honorarium, OtherFixed
    rates_rows = load_csv(PAYROLL_RATES_CSV)
    rates_by_eno = {}
    for rd in rates_rows:
        eno = rd["EmployeeNo"].strip()
        rates_by_eno[eno] = {
            "bei_comm_allow_monthly": float(rd.get("CommAllow_Monthly", 0) or 0),
            "bei_deminimis_monthly": float(rd.get("DeMinimis_Monthly", 0) or 0),
            "bei_honorarium_monthly": float(rd.get("Honorarium_Monthly", 0) or 0),
            "bei_other_fixed_monthly": float(rd.get("OtherFixed_Monthly", 0) or 0),
        }

    # Load ComprePayRun for Meal and Gasoline (latest cutoff only, × 2 for monthly)
    compre_rows = load_csv(PAYROLL_COMPRE_CSV)
    meal_gas_by_eno = {}
    for cr in compre_rows:
        if cr.get("cutoff_date", "").strip() != "2026-03-25":
            continue
        eno = cr["EmployeeNo"].strip()
        meal = float(cr.get("MealAllow_NonTax", 0) or 0)
        gasoline = float(cr.get("GasolineAllow", 0) or 0)
        meal_gas_by_eno[eno] = {
            "bei_meal_allow_monthly": round(meal * 2, 2),  # semi-monthly -> monthly
            "bei_gasoline_allow_monthly": round(gasoline * 2, 2),
        }

    # Reverse map: frappe_emp -> payroll_emp_no
    frappe_to_payroll = {v: k for k, v in matched.items()}

    updated = 0
    for frappe_emp, payroll_eno in frappe_to_payroll.items():
        allowances = {}

        # From RatesData
        if payroll_eno in rates_by_eno:
            allowances.update(rates_by_eno[payroll_eno])

        # From ComprePayRun (Meal + Gasoline)
        # Need to find the ComprePayRun EmployeeNo format (has leading zeros)
        # RatesData uses bare numbers, ComprePayRun uses zero-padded
        padded_eno = payroll_eno.zfill(5)
        if padded_eno in meal_gas_by_eno:
            allowances.update(meal_gas_by_eno[padded_eno])
        elif payroll_eno in meal_gas_by_eno:
            allowances.update(meal_gas_by_eno[payroll_eno])

        # Only update if there's any non-zero allowance
        non_zero = {k: v for k, v in allowances.items() if v > 0}
        if non_zero:
            for field, value in non_zero.items():
                frappe.db.set_value("Employee", frappe_emp, field, value, update_modified=False)
            updated += 1

        if updated % 100 == 0 and updated > 0:
            frappe.db.commit()

    frappe.db.commit()

    # Verify
    for field, label in [
        ("bei_comm_allow_monthly", "Communication"),
        ("bei_deminimis_monthly", "De Minimis"),
        ("bei_honorarium_monthly", "Honorarium"),
        ("bei_meal_allow_monthly", "Meal"),
        ("bei_gasoline_allow_monthly", "Gasoline"),
        ("bei_other_fixed_monthly", "Other Fixed"),
    ]:
        count = frappe.db.sql(f"SELECT COUNT(*) FROM tabEmployee WHERE {field} > 0")[0][0]
        total = frappe.db.sql(f"SELECT COALESCE(SUM({field}), 0) FROM tabEmployee WHERE {field} > 0")[0][0]
        print(f"  {label}: {count} employees, total ₱{total:,.2f}/mo")

    print(f"\nTotal employees updated with allowances: {updated}")


def p2_3_cleanup_duplicates():
    """P2-3: Disable duplicate salary components + fix typos."""
    # Disable "Basic" (keep "Basic Pay")
    for comp_name in ["Basic", "Income Tax"]:
        if frappe.db.exists("Salary Component", comp_name):
            frappe.db.set_value("Salary Component", comp_name, "disabled", 1)
            print(f"Disabled: {comp_name}")

    # Fix "Probitionary" typo
    fixed = frappe.db.sql("""
        UPDATE tabEmployee
        SET employment_type = 'Probationary'
        WHERE employment_type = 'Probitionary'
    """)
    count = frappe.db.sql("SELECT ROW_COUNT()")[0][0]
    frappe.db.commit()
    print(f"Fixed 'Probitionary' typo: {count} employees")


# ============================================================================
# Phase 2-4: Produce matching report
# ============================================================================


def p2_4_produce_matching_report():
    """P2-4: Save employee-payroll matching report."""
    matched, unmatched = build_payroll_to_frappe_map()
    rates_rows = load_csv(PAYROLL_RATES_CSV)
    rates_by_eno = {rd["EmployeeNo"].strip(): rd for rd in rates_rows}

    output_path = "output/s150_employee_payroll_match.csv"
    os.makedirs("output", exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "frappe_employee_id", "frappe_name", "payroll_employee_no",
            "payroll_name", "match_tier", "basic_monthly",
            "comm_allow", "deminimis", "honorarium", "meal", "gasoline", "other_fixed",
        ])

        for eno, frappe_emp in matched.items():
            rd = rates_by_eno.get(eno, {})
            emp_name = frappe.db.get_value("Employee", frappe_emp, "employee_name") or ""
            writer.writerow([
                frappe_emp, emp_name, eno,
                rd.get("FullName", ""), "MATCHED",
                rd.get("BasicPay_Monthly", 0),
                rd.get("CommAllow_Monthly", 0),
                rd.get("DeMinimis_Monthly", 0),
                rd.get("Honorarium_Monthly", 0),
                0,  # Meal from ComprePayRun
                0,  # Gasoline from ComprePayRun
                rd.get("OtherFixed_Monthly", 0),
            ])

        for u in unmatched:
            writer.writerow([
                "", "", u["payroll_emp_no"],
                u["fullname"], "UNMATCHED",
                u["basic_monthly"],
                "", "", "", "", "", "",
            ])

    print(f"Report saved: {output_path}")
    print(f"  Matched: {len(matched)}, Unmatched: {len(unmatched)}")


# ============================================================================
# Verification
# ============================================================================


def verify_all():
    """Phase 5 verification queries."""
    checks = {
        "V-01 Payroll Period submitted": (
            "SELECT docstatus FROM `tabPayroll Period` WHERE company='Bebang Enterprise Inc.' LIMIT 1",
            lambda r: r and r[0][0] == 1,
        ),
        "V-02 SSAs with NULL tax slab": (
            "SELECT COUNT(*) FROM `tabSalary Structure Assignment` WHERE docstatus=1 AND (income_tax_slab IS NULL OR income_tax_slab='')",
            lambda r: r[0][0] == 0,
        ),
        "V-03 Active emps without salary_mode": (
            "SELECT COUNT(*) FROM tabEmployee WHERE status='Active' AND (salary_mode IS NULL OR salary_mode='')",
            lambda r: r[0][0] == 0,
        ),
        "V-04 SSAs with base=0": (
            "SELECT COUNT(*) FROM `tabSalary Structure Assignment` WHERE docstatus=1 AND (base IS NULL OR base=0)",
            lambda r: True,  # Just report
        ),
        "V-05 Active emps without SSA": (
            """SELECT COUNT(*) FROM tabEmployee e
               LEFT JOIN `tabSalary Structure Assignment` ssa ON ssa.employee=e.name AND ssa.docstatus=1
               WHERE e.status='Active' AND ssa.name IS NULL AND e.name NOT LIKE 'test%%'""",
            lambda r: r[0][0] < 10,
        ),
        "V-06 Salary Structures count": (
            "SELECT COUNT(*) FROM `tabSalary Structure` WHERE docstatus=1 AND is_active='Yes'",
            lambda r: r[0][0] >= 4,
        ),
        "V-07 Employees with other_fixed > 0": (
            "SELECT COUNT(*) FROM tabEmployee WHERE bei_other_fixed_monthly > 0",
            lambda r: True,  # Just report
        ),
        "V-08 Disabled components": (
            "SELECT name FROM `tabSalary Component` WHERE disabled=1",
            lambda r: True,  # Just report
        ),
        "V-09 bei_* columns in tabEmployee": (
            "SHOW COLUMNS FROM tabEmployee LIKE 'bei_%'",
            lambda r: len(r) >= 6,
        ),
    }

    all_pass = True
    for name, (sql, check_fn) in checks.items():
        result = frappe.db.sql(sql)
        passed = check_fn(result)
        value = result[0][0] if result and len(result[0]) == 1 else len(result)
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{status}] {name}: {value}")

    return all_pass


# ============================================================================
# Master orchestrator
# ============================================================================


def execute_all():
    """Run all phases in sequence."""
    print("=" * 60)
    print("S150 PAYROLL DATA QUALITY — FULL EXECUTION")
    print("=" * 60)

    print("\n--- Phase 1: Fix 5 Blockers ---")
    print("\nP1-1: Submit Payroll Period")
    p1_1_submit_payroll_period()

    print("\nP1-2: Link Tax Slabs")
    p1_2_link_tax_slabs()

    print("\nP1-3: Set Salary Mode")
    p1_3_set_salary_mode()

    print("\nP1-4: Update SSA Base Salaries")
    p1_4_update_ssa_base_salaries()

    print("\nP1-5: Create Salary Structures + Missing SSAs")
    p1_5_create_salary_structures_and_ssas()

    print("\n--- Phase 2: Import Allowances ---")
    print("\nP2-1: Create Salary Components")
    p2_1_create_salary_components()

    print("\nP2-2: Create Custom Fields + Import Allowances")
    p2_2_create_custom_fields_and_import()

    print("\nP2-3: Cleanup Duplicates")
    p2_3_cleanup_duplicates()

    print("\nP2-4: Matching Report")
    p2_4_produce_matching_report()

    print("\n--- Verification ---")
    verify_all()

    print("\n" + "=" * 60)
    print("S150 Phase 1-2 COMPLETE. Run bench migrate + bench clear-cache next.")
    print("=" * 60)
