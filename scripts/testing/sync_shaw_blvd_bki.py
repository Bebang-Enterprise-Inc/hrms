"""
Populate Shaw BLVD - BKI commissary warehouse with BOM ingredient inventory.

Creates Stock Reconciliation entries via Frappe API so the commissary team
can use production and wastage forms immediately.

Usage:
    python scripts/testing/sync_shaw_blvd_bki.py [--dry-run]
"""

import argparse
import json
import sys
from datetime import date, timedelta

import requests

# ── Frappe API credentials (from Doppler bei-erp/dev) ──────────────────────
FRAPPE_KEY = "4a17c23aca83560"
FRAPPE_SECRET = "38ecc0e1054b1d2"
BASE = "https://hq.bebang.ph"
HEADERS = {"Authorization": f"token {FRAPPE_KEY}:{FRAPPE_SECRET}"}

WAREHOUSE = "Shaw BLVD - BKI"
COMPANY = "Bebang Kitchen Inc."
POSTING_DATE = date.today().isoformat()  # 2026-03-26
BATCH_PREFIX = "SYNC-S124"

# Default quantities for items that have no reference stock elsewhere
DEFAULT_QTY_RM = 100.0   # raw materials
DEFAULT_QTY_FG = 50.0    # finished goods
DEFAULT_QTY_PM = 200.0   # packaging materials
DEFAULT_VALUATION = 100.0  # fallback valuation rate


def api_get(endpoint, params=None):
    """GET from Frappe API with error handling."""
    resp = requests.get(f"{BASE}/api/{endpoint}", headers=HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def api_post(endpoint, payload):
    """POST to Frappe API."""
    resp = requests.post(
        f"{BASE}/api/{endpoint}",
        headers=HEADERS,
        json=payload,
        timeout=60,
    )
    if resp.status_code >= 400:
        print(f"  API ERROR {resp.status_code}: {resp.text[:500]}")
    resp.raise_for_status()
    return resp.json()


def api_put(endpoint, payload):
    """PUT to Frappe API."""
    resp = requests.put(
        f"{BASE}/api/{endpoint}",
        headers=HEADERS,
        json=payload,
        timeout=60,
    )
    if resp.status_code >= 400:
        print(f"  API ERROR {resp.status_code}: {resp.text[:500]}")
    resp.raise_for_status()
    return resp.json()


def get_bom_items():
    """Get all items that have at least one BOM (these are commissary items)."""
    print("Fetching BOM items...")
    # Get distinct item codes from BOM
    boms = api_get("resource/BOM", {
        "filters": json.dumps([["docstatus", "=", 1]]),
        "fields": json.dumps(["item", "name"]),
        "limit_page_length": 0,
    })
    bom_items = set()
    for b in boms.get("data", []):
        bom_items.add(b["item"])

    # Also get BOM ingredients (items used IN BOMs) by reading each BOM's items
    bom_names = [b["name"] for b in boms.get("data", [])]
    print(f"  Fetching ingredients from {len(bom_names)} BOMs...")
    for bom_name in bom_names:
        try:
            bom_doc = api_get(f"resource/BOM/{bom_name}", {
                "fields": json.dumps(["name"]),
            })
            bom_data = bom_doc.get("data", {})
            for item_row in bom_data.get("items", []):
                bom_items.add(item_row["item_code"])
        except Exception as e:
            print(f"  WARNING: Could not read BOM {bom_name}: {e}")

    print(f"  Found {len(bom_items)} unique items from BOMs")
    return bom_items


def get_all_items_with_details(item_codes):
    """Fetch item details (has_batch_no, valuation_rate, etc.) for given items."""
    print(f"Fetching details for {len(item_codes)} items...")
    items = {}
    # Fetch in batches of 50
    item_list = sorted(item_codes)
    for i in range(0, len(item_list), 50):
        batch = item_list[i:i+50]
        filters = json.dumps([["name", "in", batch]])
        result = api_get("resource/Item", {
            "filters": filters,
            "fields": json.dumps([
                "name", "item_name", "item_group", "has_batch_no", "has_serial_no",
                "valuation_rate", "last_purchase_rate", "stock_uom",
            ]),
            "limit_page_length": 0,
        })
        for item in result.get("data", []):
            items[item["name"]] = item
    print(f"  Fetched details for {len(items)} items")
    return items


def get_existing_stock_in_warehouse():
    """Get items that already have stock in Shaw BLVD - BKI."""
    print(f"Checking existing stock in {WAREHOUSE}...")
    bins = api_get("resource/Bin", {
        "filters": json.dumps([["warehouse", "=", WAREHOUSE]]),
        "fields": json.dumps(["item_code", "actual_qty", "valuation_rate"]),
        "limit_page_length": 0,
    })
    existing = {}
    for b in bins.get("data", []):
        existing[b["item_code"]] = {
            "qty": b["actual_qty"],
            "valuation_rate": b["valuation_rate"],
        }
    print(f"  Found {len(existing)} items already in {WAREHOUSE}")
    positive = {k: v for k, v in existing.items() if v["qty"] > 0}
    print(f"  Of which {len(positive)} have positive stock")
    return existing


def get_reference_stock():
    """Get stock from other warehouses to use as reference for quantities."""
    print("Fetching reference stock from other warehouses...")
    # Get bins from cold storage and other BKI warehouses
    ref_warehouses = [
        "3MD Logistics – Camangyanan",
        "Jentec Storage Inc.",
        "Royal Cold Storage – Taytay (RCS)",
        "Pinnacle Cold Storage Solutions",
    ]
    reference = {}
    for wh in ref_warehouses:
        bins = api_get("resource/Bin", {
            "filters": json.dumps([
                ["warehouse", "=", wh],
                ["actual_qty", ">", 0],
            ]),
            "fields": json.dumps(["item_code", "actual_qty", "valuation_rate"]),
            "limit_page_length": 0,
        })
        for b in bins.get("data", []):
            item = b["item_code"]
            if item not in reference or b["actual_qty"] > reference[item]["qty"]:
                reference[item] = {
                    "qty": b["actual_qty"],
                    "valuation_rate": b["valuation_rate"],
                    "warehouse": wh,
                }
    print(f"  Found reference stock for {len(reference)} items across cold storage")
    return reference


def get_valuation_from_any_bin(item_code):
    """Get valuation rate from any Bin entry for the item."""
    bins = api_get("resource/Bin", {
        "filters": json.dumps([
            ["item_code", "=", item_code],
            ["valuation_rate", ">", 0],
        ]),
        "fields": json.dumps(["valuation_rate"]),
        "limit_page_length": 1,
        "order_by": "actual_qty desc",
    })
    data = bins.get("data", [])
    if data:
        return data[0]["valuation_rate"]
    return 0


def determine_qty(item_code, item_details, reference_stock):
    """Determine a reasonable quantity for a commissary item."""
    # If we have reference stock from cold storage, use a fraction
    if item_code in reference_stock:
        ref_qty = reference_stock[item_code]["qty"]
        # Commissary holds operational stock - use 10-20% of cold storage
        suggested = max(10, round(ref_qty * 0.15, 2))
        return min(suggested, 500)  # cap at 500

    # Default based on item group / prefix
    if item_code.startswith("PM"):
        return DEFAULT_QTY_PM
    elif item_code.startswith("FG"):
        return DEFAULT_QTY_FG
    else:
        return DEFAULT_QTY_RM


def determine_valuation(item_code, item_details, existing_stock, reference_stock):
    """Determine valuation rate for an item."""
    # 1. From existing stock in Shaw BLVD - BKI
    if item_code in existing_stock and existing_stock[item_code].get("valuation_rate", 0) > 0:
        return existing_stock[item_code]["valuation_rate"]

    # 2. From reference warehouses
    if item_code in reference_stock and reference_stock[item_code].get("valuation_rate", 0) > 0:
        return reference_stock[item_code]["valuation_rate"]

    # 3. From item master
    details = item_details.get(item_code, {})
    if details.get("valuation_rate", 0) > 0:
        return details["valuation_rate"]
    if details.get("last_purchase_rate", 0) > 0:
        return details["last_purchase_rate"]

    # 4. From any Bin
    rate = get_valuation_from_any_bin(item_code)
    if rate > 0:
        return rate

    # 5. Fallback
    return DEFAULT_VALUATION


def create_batch_if_needed(item_code, has_batch_no):
    """Create a Batch for batch-tracked items if it doesn't exist."""
    if not has_batch_no:
        return None

    batch_id = f"{BATCH_PREFIX}-{item_code}"

    # Check if batch already exists
    try:
        existing = api_get(f"resource/Batch/{batch_id}")
        if existing.get("data"):
            return batch_id
    except requests.HTTPError as e:
        if e.response.status_code != 404:
            raise

    # Create the batch
    expiry = (date.today() + timedelta(days=90)).isoformat()
    batch_payload = {
        "batch_id": batch_id,
        "item": item_code,
        "manufacturing_date": POSTING_DATE,
        "expiry_date": expiry,
        "description": f"Commissary sync batch for S124 - {item_code}",
    }
    try:
        api_post("resource/Batch", batch_payload)
        return batch_id
    except requests.HTTPError as e:
        # Might already exist due to race condition
        if "DuplicateEntryError" in str(e.response.text) or e.response.status_code == 409:
            return batch_id
        print(f"  WARNING: Could not create batch for {item_code}: {e}")
        return None


def create_stock_reconciliation(items_to_sync, dry_run=False):
    """Create and submit a Stock Reconciliation for Shaw BLVD - BKI."""
    if not items_to_sync:
        print("No items to sync!")
        return

    print(f"\nCreating Stock Reconciliation with {len(items_to_sync)} items...")

    sr_items = []
    for item in items_to_sync:
        row = {
            "item_code": item["item_code"],
            "warehouse": WAREHOUSE,
            "qty": item["qty"],
            "valuation_rate": item["valuation_rate"],
        }
        if item.get("batch_no"):
            row["batch_no"] = item["batch_no"]
            row["use_serial_batch_fields"] = 1
        sr_items.append(row)

    if dry_run:
        print("\n=== DRY RUN - Would create Stock Reconciliation ===")
        print(f"Company: {COMPANY}")
        print(f"Warehouse: {WAREHOUSE}")
        print(f"Posting Date: {POSTING_DATE}")
        print(f"Items ({len(sr_items)}):")
        for row in sr_items:
            batch_info = f" [batch: {row['batch_no']}]" if row.get("batch_no") else ""
            print(f"  {row['item_code']}: qty={row['qty']}, rate={row['valuation_rate']}{batch_info}")
        print("=== END DRY RUN ===")
        return None

    # We need to chunk items because Frappe may timeout on very large reconciliations
    CHUNK_SIZE = 30
    created_names = []

    for chunk_idx in range(0, len(sr_items), CHUNK_SIZE):
        chunk = sr_items[chunk_idx:chunk_idx + CHUNK_SIZE]
        chunk_num = chunk_idx // CHUNK_SIZE + 1
        total_chunks = (len(sr_items) + CHUNK_SIZE - 1) // CHUNK_SIZE

        print(f"  Creating Stock Reconciliation chunk {chunk_num}/{total_chunks} ({len(chunk)} items)...")

        sr_payload = {
            "doctype": "Stock Reconciliation",
            "posting_date": POSTING_DATE,
            "posting_time": "08:00:00",
            "purpose": "Stock Reconciliation",
            "company": COMPANY,
            "items": chunk,
        }

        try:
            resp = api_post("resource/Stock Reconciliation", sr_payload)
            sr_name = resp["data"]["name"]
            print(f"    Created: {sr_name}")

            # Submit the Stock Reconciliation
            print(f"    Submitting {sr_name}...")
            api_put(f"resource/Stock Reconciliation/{sr_name}", {
                "docstatus": 1,
            })
            print(f"    Submitted: {sr_name}")
            created_names.append(sr_name)

        except requests.HTTPError as e:
            print(f"    FAILED chunk {chunk_num}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"    Response: {e.response.text[:1000]}")

    return created_names


def main():
    parser = argparse.ArgumentParser(description="Sync Shaw BLVD - BKI commissary inventory")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created without making changes")
    args = parser.parse_args()

    print(f"{'='*60}")
    print(f"Shaw BLVD - BKI Commissary Inventory Sync")
    print(f"Date: {POSTING_DATE}")
    print(f"Warehouse: {WAREHOUSE}")
    print(f"Company: {COMPANY}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"{'='*60}\n")

    # 1. Get BOM items (items the commissary needs)
    bom_items = get_bom_items()

    # 2. Get item details
    item_details = get_all_items_with_details(bom_items)

    # 3. Get existing stock in Shaw BLVD - BKI
    existing_stock = get_existing_stock_in_warehouse()

    # 4. Get reference stock from other warehouses
    reference_stock = get_reference_stock()

    # 5. Build the sync list
    print("\nBuilding sync list...")
    items_to_sync = []
    skipped_existing = 0
    skipped_serial = 0
    skipped_not_found = 0
    batch_created = 0

    for item_code in sorted(bom_items):
        # Skip if not found in item master
        if item_code not in item_details:
            skipped_not_found += 1
            continue

        details = item_details[item_code]

        # Skip serial-tracked items (can't do aggregate reconciliation)
        if details.get("has_serial_no"):
            skipped_serial += 1
            print(f"  SKIP (serial-tracked): {item_code}")
            continue

        # Skip items that already have positive stock
        if item_code in existing_stock and existing_stock[item_code]["qty"] > 0:
            skipped_existing += 1
            continue

        # Determine quantity and valuation
        qty = determine_qty(item_code, item_details, reference_stock)
        valuation = determine_valuation(item_code, item_details, existing_stock, reference_stock)

        # Handle batch-tracked items
        batch_no = None
        if details.get("has_batch_no"):
            batch_no = create_batch_if_needed(item_code, True) if not args.dry_run else f"{BATCH_PREFIX}-{item_code}"
            if batch_no:
                batch_created += 1
            else:
                print(f"  SKIP (batch creation failed): {item_code}")
                continue

        items_to_sync.append({
            "item_code": item_code,
            "item_name": details.get("item_name", ""),
            "qty": qty,
            "valuation_rate": valuation,
            "batch_no": batch_no,
        })

    print(f"\n{'='*60}")
    print(f"Sync Summary:")
    print(f"  Items to sync: {len(items_to_sync)}")
    print(f"  Already have stock: {skipped_existing}")
    print(f"  Serial-tracked (skipped): {skipped_serial}")
    print(f"  Not in item master: {skipped_not_found}")
    print(f"  Batches to create: {batch_created}")
    print(f"{'='*60}\n")

    if not items_to_sync:
        print("Nothing to sync - all BOM items already have stock or couldn't be processed.")
        return

    # 6. Create Stock Reconciliation
    result = create_stock_reconciliation(items_to_sync, dry_run=args.dry_run)

    if result:
        print(f"\nDONE. Created Stock Reconciliation(s): {', '.join(result)}")
    elif args.dry_run:
        print("\nDry run complete. Run without --dry-run to execute.")


if __name__ == "__main__":
    main()
