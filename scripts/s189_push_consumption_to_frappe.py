"""S189: Push daily consumption from Supabase to Frappe as Stock Entry (Material Issue).

Hourly: create/update Draft Stock Entries per material per day.
Daily at 1 AM PHT: submit all Draft SEs for yesterday (--mode finalize).

Usage:
    python scripts/s189_push_consumption_to_frappe.py --date 2026-04-13
    python scripts/s189_push_consumption_to_frappe.py --date yesterday
    python scripts/s189_push_consumption_to_frappe.py --date yesterday --mode finalize
    python scripts/s189_push_consumption_to_frappe.py --date today --mode delta
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta

import requests

# ── Credentials ──────────────────────────────────────────────────────────────

FRAPPE_URL = os.environ.get("FRAPPE_URL", "https://hq.bebang.ph")
FRAPPE_API_KEY = os.environ.get("FRAPPE_API_KEY", "")
FRAPPE_API_SECRET = os.environ.get("FRAPPE_API_SECRET", "")
FRAPPE_AUTH = {"Authorization": f"token {FRAPPE_API_KEY}:{FRAPPE_API_SECRET}"}

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://csnniykjrychgajfrgua.supabase.co")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SB_HEADERS = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}

BEI_SOURCE = "S189_POS_BOM_CONSUMPTION"
DEFAULT_WAREHOUSE = "Stores - BEI"

# UOM mapping: Supabase material_code prefix -> Frappe UOM + conversion
# RM/FG items: grams -> KG (divide by 1000)
# PM items: count -> Nos (cups sold as pieces)
PACKAGING_PREFIXES = ("PM",)


def resolve_date(date_str):
    """Resolve 'today', 'yesterday', or YYYY-MM-DD to a date string."""
    if date_str == "today":
        return datetime.utcnow().strftime("%Y-%m-%d")
    elif date_str == "yesterday":
        return (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    return date_str


def get_consumption(date):
    """Get aggregated consumption from Supabase for a date."""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/v_daily_material_consumption",
        params={"business_date": f"eq.{date}", "select": "*"},
        headers=SB_HEADERS,
    )
    r.raise_for_status()
    return r.json()


def get_7day_avg():
    """Get 7-day average from Supabase for inventory risk update."""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/v_material_7day_avg",
        params={"select": "*"},
        headers=SB_HEADERS,
    )
    r.raise_for_status()
    return {row["material_code"]: row for row in r.json()}


def frappe_get(endpoint, params=None):
    r = requests.get(f"{FRAPPE_URL}{endpoint}", params=params, headers=FRAPPE_AUTH, timeout=30)
    r.raise_for_status()
    return r.json()


def frappe_post(endpoint, data):
    r = requests.post(f"{FRAPPE_URL}{endpoint}", json=data, headers=FRAPPE_AUTH, timeout=30)
    if not r.ok:
        print(f"  Frappe POST error: {r.status_code} {r.text[:300]}")
    r.raise_for_status()
    return r.json()


def frappe_put(endpoint, data):
    r = requests.put(f"{FRAPPE_URL}{endpoint}", json=data, headers=FRAPPE_AUTH, timeout=30)
    if not r.ok:
        print(f"  Frappe PUT error: {r.status_code} {r.text[:300]}")
    r.raise_for_status()
    return r.json()


def find_existing_draft(date, material_code):
    """Find existing Draft SE for this date+material."""
    result = frappe_get("/api/resource/Stock Entry", params={
        "filters": json.dumps([
            ["bei_source", "=", BEI_SOURCE],
            ["bei_supabase_date", "=", date],
            ["docstatus", "=", 0],
        ]),
        "fields": '["name"]',
        "limit_page_length": 500,
    })
    return result.get("data", [])


def find_submitted_se(date):
    """Find submitted SEs for this date."""
    result = frappe_get("/api/resource/Stock Entry", params={
        "filters": json.dumps([
            ["bei_source", "=", BEI_SOURCE],
            ["bei_supabase_date", "=", date],
            ["docstatus", "=", 1],
        ]),
        "fields": '["name"]',
        "limit_page_length": 500,
    })
    return result.get("data", [])


def convert_to_frappe_uom(material_code, total_grams, total_cups):
    """Convert Supabase units to Frappe Stock Entry units."""
    if material_code.startswith(PACKAGING_PREFIXES):
        return total_cups, "Nos"
    else:
        return round(total_grams / 1000, 4), "Kg"


def create_or_update_draft_se(date, consumption_rows):
    """Create a single Draft Stock Entry with all materials for this date."""
    # Check for existing submitted SE — skip if already finalized
    submitted = find_submitted_se(date)
    if submitted:
        print(f"  SKIPPED: {len(submitted)} submitted SEs already exist for {date}")
        return "SKIPPED", None

    # Check for existing draft
    drafts = find_existing_draft(date, None)

    items = []
    for row in consumption_rows:
        qty, uom = convert_to_frappe_uom(
            row["material_code"],
            float(row.get("total_grams", 0)),
            int(row.get("total_cups", 0)),
        )
        if qty <= 0:
            continue
        items.append({
            "item_code": row["material_code"],
            "qty": qty,
            "uom": uom,
            "s_warehouse": DEFAULT_WAREHOUSE,
        })

    if not items:
        print(f"  No items with qty > 0 for {date}")
        return "SKIPPED", None

    if drafts:
        # Update existing draft
        se_name = drafts[0]["name"]
        print(f"  Updating existing draft {se_name} with {len(items)} items")
        frappe_put(f"/api/resource/Stock Entry/{se_name}", {
            "items": items,
        })
        return "UPDATED", se_name
    else:
        # Create new draft
        print(f"  Creating new draft SE for {date} with {len(items)} items")
        result = frappe_post("/api/resource/Stock Entry", {
            "stock_entry_type": "Material Issue",
            "posting_date": date,
            "bei_source": BEI_SOURCE,
            "bei_supabase_date": date,
            "items": items,
        })
        se_name = result.get("data", {}).get("name")
        print(f"  Created: {se_name}")
        return "CREATED", se_name


def finalize_drafts(date):
    """Submit all Draft SEs for the given date."""
    drafts = find_existing_draft(date, None)
    if not drafts:
        print(f"  No drafts to finalize for {date}")
        return 0

    submitted = 0
    for draft in drafts:
        se_name = draft["name"]
        try:
            frappe_put(f"/api/resource/Stock Entry/{se_name}", {"docstatus": 1})
            print(f"  Submitted: {se_name}")
            submitted += 1
        except Exception as e:
            print(f"  FAILED to submit {se_name}: {e}")
    return submitted


def update_inventory_risk_snapshots(avg_data):
    """Update BEI Inventory Risk Snapshot with real consumption data."""
    snapshots = frappe_get("/api/resource/BEI Inventory Risk Snapshot", params={
        "fields": '["name","item_code","source_reference"]',
        "limit_page_length": 0,
    })
    updated = 0
    for snap in snapshots.get("data", []):
        item_code = snap.get("item_code")
        avg_row = avg_data.get(item_code)
        if not avg_row:
            continue

        source_ref = json.loads(snap.get("source_reference") or "{}")
        source_ref["bom_consumption"] = {
            "daily_avg_kg": float(avg_row.get("avg_kg_per_day", 0)),
            "last_7d_total_kg": float(avg_row.get("total_kg_7d", 0)),
            "updated_at": datetime.utcnow().isoformat(),
            "source": "S189_REALTIME",
        }
        try:
            frappe_put(f"/api/resource/BEI Inventory Risk Snapshot/{snap['name']}", {
                "source_reference": json.dumps(source_ref),
            })
            updated += 1
        except Exception as e:
            print(f"  Failed to update snapshot {snap['name']}: {e}")
    print(f"  Updated {updated} Inventory Risk Snapshots")


def log_sync(date, material_code, total_kg, se_name, status, error=None):
    """Log sync result to Supabase."""
    row = {
        "business_date": date,
        "material_code": material_code,
        "total_kg": total_kg,
        "frappe_stock_entry_name": se_name,
        "sync_status": status,
        "error_message": error,
        "synced_at": datetime.utcnow().isoformat(),
    }
    requests.post(
        f"{SUPABASE_URL}/rest/v1/daily_material_consumption_frappe_sync",
        headers={
            "apikey": SB_KEY,
            "Authorization": f"Bearer {SB_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
        json=row,
    )


def main():
    parser = argparse.ArgumentParser(description="Push consumption to Frappe")
    parser.add_argument("--date", required=True, help="Business date or 'today'/'yesterday'")
    parser.add_argument("--mode", default="delta", choices=["delta", "finalize"],
                        help="delta=create/update drafts, finalize=submit drafts")
    args = parser.parse_args()

    date = resolve_date(args.date)
    print(f"S189 Consumption Push: date={date} mode={args.mode}")

    if args.mode == "finalize":
        count = finalize_drafts(date)
        print(f"Finalized {count} Stock Entries for {date}")
        # Also update inventory risk snapshots
        avg_data = get_7day_avg()
        if avg_data:
            update_inventory_risk_snapshots(avg_data)
        return

    # Delta mode: create/update drafts
    consumption = get_consumption(date)
    if not consumption:
        print(f"No consumption data for {date}")
        return

    print(f"Got {len(consumption)} material rows for {date}")

    status, se_name = create_or_update_draft_se(date, consumption)
    print(f"Result: {status} SE={se_name}")

    # Log sync results
    for row in consumption:
        total_kg = float(row.get("total_grams", 0)) / 1000
        log_sync(date, row["material_code"], total_kg, se_name, status)

    # Update inventory risk snapshots
    avg_data = get_7day_avg()
    if avg_data:
        update_inventory_risk_snapshots(avg_data)


if __name__ == "__main__":
    main()
