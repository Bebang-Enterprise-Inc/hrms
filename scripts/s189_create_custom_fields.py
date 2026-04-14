"""S189: Create Custom Fields on Stock Entry for BOM consumption audit trail.

Creates:
  - bei_source (Data, read-only): source identifier (e.g., S189_POS_BOM_CONSUMPTION)
  - bei_supabase_date (Date, read-only): the business_date from Supabase

Usage:
    python scripts/s189_create_custom_fields.py
"""
import os
import sys

import requests

FRAPPE_URL = os.environ.get("FRAPPE_URL", "https://hq.bebang.ph")
API_KEY = os.environ.get("FRAPPE_API_KEY", "")
API_SECRET = os.environ.get("FRAPPE_API_SECRET", "")
AUTH = {"Authorization": f"token {API_KEY}:{API_SECRET}"}

CUSTOM_FIELDS = [
    {
        "doctype": "Custom Field",
        "dt": "Stock Entry",
        "fieldname": "bei_source",
        "label": "BEI Source",
        "fieldtype": "Data",
        "read_only": 1,
        "hidden": 0,
        "insert_after": "remarks",
        "description": "S189: source identifier for automated consumption Stock Entries",
    },
    {
        "doctype": "Custom Field",
        "dt": "Stock Entry",
        "fieldname": "bei_supabase_date",
        "label": "BEI Supabase Business Date",
        "fieldtype": "Date",
        "read_only": 1,
        "hidden": 0,
        "insert_after": "bei_source",
        "description": "S189: business_date from Supabase daily_material_consumption",
    },
]


def field_exists(dt, fieldname):
    """Check if Custom Field already exists."""
    r = requests.get(f"{FRAPPE_URL}/api/resource/Custom Field", params={
        "filters": f'[["dt","=","{dt}"],["fieldname","=","{fieldname}"]]',
        "fields": '["name"]',
        "limit_page_length": 1,
    }, headers=AUTH, timeout=30)
    if not r.ok:
        return False
    return bool(r.json().get("data"))


def main():
    created = 0
    skipped = 0
    for field in CUSTOM_FIELDS:
        if field_exists(field["dt"], field["fieldname"]):
            print(f"  SKIP: {field['dt']}.{field['fieldname']} already exists")
            skipped += 1
            continue

        r = requests.post(
            f"{FRAPPE_URL}/api/resource/Custom Field",
            json=field,
            headers=AUTH,
            timeout=30,
        )
        if r.ok:
            print(f"  CREATED: {field['dt']}.{field['fieldname']}")
            created += 1
        else:
            print(f"  FAILED: {field['dt']}.{field['fieldname']}: {r.status_code} {r.text[:200]}")
            sys.exit(1)

    print(f"\nDone. Created: {created}, Skipped: {skipped}")


if __name__ == "__main__":
    main()
