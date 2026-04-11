"""S181 Phase 1, Task 1.2: add 47 Company Custom Fields to the fixture.

Reads `hrms/fixtures/custom_field.json`, appends the 47 S181 Custom Fields
in the exact order the plan's 8 sections declare them, validates the result
(no duplicate fieldnames, every insert_after references a field that will
exist at migrate time), and writes back preserving the existing 4-space
indent.

Idempotent: re-running does NOT duplicate rows — if a fixture entry with
the same `name` already exists, it is left alone.

Runs offline. No bench access needed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "hrms" / "fixtures" / "custom_field.json"


def section(fieldname: str, label: str, insert_after: str, description: str) -> dict:
    return {
        "doctype": "Custom Field",
        "name": f"Company-{fieldname}",
        "dt": "Company",
        "fieldname": fieldname,
        "fieldtype": "Section Break",
        "label": label,
        "insert_after": insert_after,
        "description": description,
    }


def column(fieldname: str, insert_after: str) -> dict:
    return {
        "doctype": "Custom Field",
        "name": f"Company-{fieldname}",
        "dt": "Company",
        "fieldname": fieldname,
        "fieldtype": "Column Break",
        "insert_after": insert_after,
    }


def data(fieldname: str, label: str, insert_after: str, description: str, *,
         options: str | None = None) -> dict:
    d = {
        "doctype": "Custom Field",
        "name": f"Company-{fieldname}",
        "dt": "Company",
        "fieldname": fieldname,
        "fieldtype": "Data",
        "label": label,
        "insert_after": insert_after,
        "description": description,
    }
    if options:
        d["options"] = options
    return d


def select(fieldname: str, label: str, options: str, insert_after: str,
           description: str, *, default: str | None = None) -> dict:
    d = {
        "doctype": "Custom Field",
        "name": f"Company-{fieldname}",
        "dt": "Company",
        "fieldname": fieldname,
        "fieldtype": "Select",
        "options": options,
        "label": label,
        "insert_after": insert_after,
        "description": description,
    }
    if default is not None:
        d["default"] = default
    return d


def date_field(fieldname: str, label: str, insert_after: str, description: str) -> dict:
    return {
        "doctype": "Custom Field",
        "name": f"Company-{fieldname}",
        "dt": "Company",
        "fieldname": fieldname,
        "fieldtype": "Date",
        "label": label,
        "insert_after": insert_after,
        "description": description,
    }


def float_field(fieldname: str, label: str, insert_after: str, description: str) -> dict:
    return {
        "doctype": "Custom Field",
        "name": f"Company-{fieldname}",
        "dt": "Company",
        "fieldname": fieldname,
        "fieldtype": "Float",
        "label": label,
        "insert_after": insert_after,
        "description": description,
    }


def small_text(fieldname: str, label: str, insert_after: str, description: str) -> dict:
    return {
        "doctype": "Custom Field",
        "name": f"Company-{fieldname}",
        "dt": "Company",
        "fieldname": fieldname,
        "fieldtype": "Small Text",
        "label": label,
        "insert_after": insert_after,
        "description": description,
    }


def currency(fieldname: str, label: str, insert_after: str, description: str) -> dict:
    return {
        "doctype": "Custom Field",
        "name": f"Company-{fieldname}",
        "dt": "Company",
        "fieldname": fieldname,
        "fieldtype": "Currency",
        "label": label,
        "insert_after": insert_after,
        "description": description,
    }


def percent(fieldname: str, label: str, insert_after: str, description: str) -> dict:
    return {
        "doctype": "Custom Field",
        "name": f"Company-{fieldname}",
        "dt": "Company",
        "fieldname": fieldname,
        "fieldtype": "Percent",
        "label": label,
        "insert_after": insert_after,
        "description": description,
    }


def check(fieldname: str, label: str, insert_after: str, description: str) -> dict:
    return {
        "doctype": "Custom Field",
        "name": f"Company-{fieldname}",
        "dt": "Company",
        "fieldname": fieldname,
        "fieldtype": "Check",
        "label": label,
        "insert_after": insert_after,
        "default": "0",
        "description": description,
    }


def link(fieldname: str, label: str, options: str, insert_after: str,
         description: str) -> dict:
    return {
        "doctype": "Custom Field",
        "name": f"Company-{fieldname}",
        "dt": "Company",
        "fieldname": fieldname,
        "fieldtype": "Link",
        "options": options,
        "label": label,
        "insert_after": insert_after,
        "description": description,
    }


def phone(fieldname: str, label: str, insert_after: str, description: str) -> dict:
    return {
        "doctype": "Custom Field",
        "name": f"Company-{fieldname}",
        "dt": "Company",
        "fieldname": fieldname,
        "fieldtype": "Data",
        "options": "Phone",
        "label": label,
        "insert_after": insert_after,
        "description": description,
    }


def table(fieldname: str, label: str, options: str, insert_after: str,
          description: str) -> dict:
    return {
        "doctype": "Custom Field",
        "name": f"Company-{fieldname}",
        "dt": "Company",
        "fieldname": fieldname,
        "fieldtype": "Table",
        "options": options,
        "label": label,
        "insert_after": insert_after,
        "description": description,
    }


# ============================================================================
# The 47 S181 Custom Fields, in the exact order their insert_after chain
# requires at bench-migrate time.
# ============================================================================

S181_FIELDS: list[dict] = [
    # -------- Section 1: BIR & Legal Identity --------
    section("bir_legal_section", "BIR & Legal Identity", "stakeholders",
            "S181: BIR registration and SEC details"),
    data("branch_tin", "Branch TIN", "bir_legal_section",
         "S181: Branch-specific BIR TIN (may differ from head office tax_id)"),
    data("bir_rdo_code", "BIR RDO Code", "branch_tin",
         "S181: Revenue District Office code"),
    date_field("bir_registration_date", "BIR Registration Date", "bir_rdo_code",
               "S181: BIR Form 2303 date"),
    column("bir_legal_col1", "bir_registration_date"),
    data("sec_registration_no", "SEC Registration No.", "bir_legal_col1",
         "S181: SEC registration number"),
    date_field("sec_registration_date", "SEC Registration Date", "sec_registration_no",
               "S181: SEC registration date"),

    # -------- Section 2: Location --------
    section("location_section", "Location", "sec_registration_date",
            "S181: Physical address and GPS"),
    small_text("full_address", "Full Address", "location_section",
               "S181: Complete street address"),
    data("city", "City", "full_address", "S181"),
    data("province", "Province", "city", "S181"),
    select("region", "Region",
           "\nNCR\nLuzon\nVisayas\nMindanao",
           "province", "S181"),
    column("location_col1", "region"),
    data("mall_or_building", "Mall / Building", "location_col1",
         "S181: e.g. SM Megamall, Ayala Fairview Terraces"),
    float_field("gps_latitude", "GPS Latitude", "mall_or_building", "S181"),
    float_field("gps_longitude", "GPS Longitude", "gps_latitude", "S181"),
    data("google_maps_place_id", "Google Maps Place ID", "gps_longitude",
         "S181: For website store locator + Google Business Profile. Format: ChIJ... (Google Place ID string)"),

    # -------- Section 3: Operations --------
    section("operations_section", "Operations", "google_maps_place_id",
            "S181: Store operations metadata"),
    select("entity_category", "Entity Category",
           "\nHead Office\nCommissary\nStore\nWarehouse\nHolding Company\nFranchisor",
           "operations_section",
           "S181: Top-level classification. When 'Store' is selected, store_ownership_type becomes visible."),
    select("store_ownership_type", "Store Ownership Type",
           "\nCompany Owned\nJV\nManaged Franchise\nFull Franchise",
           "entity_category",
           "S181: Sub-classification for stores. Relevant only when entity_category == 'Store'."),
    select("operational_status", "Operational Status",
           "\nActive\nPre-Opening\nTemporarily Closed\nPermanently Closed\nPipeline",
           "store_ownership_type", "S181"),
    date_field("opening_date", "Opening Date", "operational_status",
               "S181: Date the store/entity began operations"),
    column("operations_col1", "opening_date"),
    data("operating_hours", "Operating Hours", "operations_col1",
         "S181: e.g. 10:00 AM - 9:00 PM"),
    select("pos_system", "POS System",
           "\nMosaic\nOther\nNone",
           "operating_hours", "S181"),
    data("mosaic_location_id", "Mosaic Location ID", "pos_system",
         "S181: For POS data sync"),
    section("adms_devices_section", "Biometric Devices (ADMS)", "mosaic_location_id",
            "S181: ZKTeco MB10-VL biometric devices assigned to this branch. Adding a device here auto-enrolls it in the ADMS receiver."),
    table("adms_devices", "ADMS Devices", "BEI Company ADMS Device",
          "adms_devices_section",
          "S181: Child table — one row per physical biometric device. On save, triggers ADMS auto-enrollment via the ADMS receiver API."),

    # -------- Section 4: Contacts --------
    section("contacts_section", "Contacts", "adms_devices",
            "S181: Key personnel for this entity"),
    link("store_manager", "Store Manager", "Employee", "contacts_section", "S181"),
    phone("store_manager_phone", "Store Manager Phone", "store_manager", "S181"),
    column("contacts_col1", "store_manager_phone"),
    link("area_supervisor", "Area Supervisor", "Employee", "contacts_col1", "S181"),
    link("regional_manager", "Regional Manager", "Employee", "area_supervisor", "S181"),

    # -------- Section 5: Compliance Documents --------
    section("compliance_docs_section", "Compliance Documents", "regional_manager",
            "S181: BIR forms, leases, permits — supports BOTH Frappe upload AND Google Drive link per document, with expiry tracking"),
    data("drive_folder_url", "Branch Drive Folder URL", "compliance_docs_section",
         "S181: Top-level Google Drive folder URL for this branch's corporate documents (lease, BIR, permits, fire safety, sanitary). BD pastes this once; operator UI exposes a 'Open Drive Folder' button. Format: https://drive.google.com/drive/folders/...",
         options="URL"),
    table("compliance_documents", "Compliance Documents", "BEI Company Document",
          "drive_folder_url",
          "S181: Metadata registry per document — each row tracks document_type, dates, status, and supports BOTH file upload AND per-document Drive URL"),

    # -------- Section 6: BD Pipeline --------
    section("bd_pipeline_section", "BD Pipeline", "compliance_documents",
            "S181: Business development pipeline tracking"),
    select("pipeline_status", "Pipeline Status",
           "\nProspect\nLOI Signed\nLease Signed\nUnder Construction\nPre-Opening\nOperational",
           "bd_pipeline_section", "S181"),
    date_field("target_opening_date", "Target Opening Date", "pipeline_status", "S181"),
    column("bd_pipeline_col1", "target_opening_date"),
    date_field("lease_start_date", "Lease Start Date", "bd_pipeline_col1", "S181"),
    date_field("lease_end_date", "Lease End Date", "lease_start_date", "S181"),
    currency("lease_monthly_rent", "Lease Monthly Rent", "lease_end_date", "S181"),
    percent("revenue_share_pct", "Revenue Share %", "lease_monthly_rent",
            "S181: Some malls charge a % of gross sales on top of fixed rent. Set to 0 if fixed-rent only."),

    # -------- Section 7: Provisioning State (S181 internal, collapsed by default) --------
    section("provisioning_state_section", "Provisioning State (S181)",
            "revenue_share_pct",
            "S181: Internal state for the auto-provisioning hook — collapsed by default."),
    check("first_provision_done", "S181 First Provision Done",
          "provisioning_state_section",
          "S181 sentinel (Blocker 9 fix). Set to 1 after auto_provision_company runs successfully. Prevents re-running on every save. Used as the gate for the Retry Provisioning button."),
]


def main() -> int:
    assert len(S181_FIELDS) == 47, f"expected 47 fields, got {len(S181_FIELDS)}"

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    existing_names = {f["name"] for f in fixture}

    added = 0
    skipped = 0
    for field in S181_FIELDS:
        if field["name"] in existing_names:
            skipped += 1
            continue
        fixture.append(field)
        existing_names.add(field["name"])
        added += 1

    # Validation — fieldnames unique within Company scope
    company_fieldnames = [f["fieldname"] for f in fixture if f.get("dt") == "Company"]
    if len(company_fieldnames) != len(set(company_fieldnames)):
        dupes = sorted({fn for fn in company_fieldnames if company_fieldnames.count(fn) > 1})
        print(f"FAIL: duplicate fieldnames in Company scope: {dupes}")
        return 1

    # Validation — every S181 insert_after references a field that will exist
    # at migrate time (either a standard Company field, an S178 custom field,
    # or an earlier S181 field in this same batch).
    standard_company_fields = {
        "company_name", "abbr", "tax_id", "country", "default_currency",
        "parent_company", "is_group", "default_holiday_list",
        # S178-added fields that S181 Section 1 chains onto:
        "stakeholders",
    }
    known_fieldnames = set(standard_company_fields) | {
        f["fieldname"] for f in fixture if f.get("dt") == "Company"
    }
    bad_chain = []
    for field in S181_FIELDS:
        ia = field.get("insert_after")
        if ia and ia not in known_fieldnames:
            bad_chain.append((field["fieldname"], ia))
    if bad_chain:
        print(f"FAIL: insert_after chain broken — these fields reference non-existent targets:")
        for fn, ia in bad_chain:
            print(f"  {fn} -> insert_after={ia}")
        return 1

    # Write back with 4-space indent (matches existing fixture style)
    FIXTURE.write_text(
        json.dumps(fixture, indent=4, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"OK: fixture updated")
    print(f"  added   : {added}")
    print(f"  skipped : {skipped} (already present)")
    print(f"  total S181 company fields: {added + skipped} (expected 47)")
    print(f"  fixture total rows: {len(fixture)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
