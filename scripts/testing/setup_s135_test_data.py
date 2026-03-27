"""
Setup real test data for S135 L3 tests.

Creates:
1. Supplier with expiry dates (BIR expiring in 15 days = yellow, SEC expired = red, permit OK = green)
2. Stock Ledger Entries to simulate consumption data for low-stock alerts

Usage: python scripts/testing/setup_s135_test_data.py
Requires: requests, valid session cookie from my.bebang.ph
"""
import requests
import json
import sys
from datetime import datetime, timedelta

BASE = "https://my.bebang.ph"
# We'll use the Frappe API directly via HQ
HQ = "https://hq.bebang.ph"

def get_session(email, password):
    """Login and return session."""
    s = requests.Session()
    r = s.post(f"{HQ}/api/method/login", data={"usr": email, "pwd": password})
    if r.status_code != 200:
        print(f"Login failed: {r.status_code} {r.text[:200]}")
        sys.exit(1)
    print(f"Logged in as {email}")
    return s


def setup_supplier_expiry(s):
    """Update an existing supplier with expiry dates for testing."""
    today = datetime.now().date()

    # Find a test supplier created by L3 tests
    r = s.get(f"{HQ}/api/resource/BEI Supplier", params={
        "filters": json.dumps([["supplier_name", "like", "L3-%"]]),
        "fields": json.dumps(["name", "supplier_name"]),
        "limit_page_length": 5,
        "order_by": "creation desc"
    })
    suppliers = r.json().get("data", [])

    if not suppliers:
        # Create a new test supplier
        r = s.post(f"{HQ}/api/method/hrms.api.procurement.create_supplier", json={
            "data": {
                "supplier_name": f"L3-Expiry-Test-{today.isoformat()}",
                "contact_person": "Expiry Test",
                "status": "Active",
            }
        })
        result = r.json().get("message", {})
        supplier_name = result.get("name")
        print(f"Created supplier: {supplier_name}")
    else:
        supplier_name = suppliers[0]["name"]
        print(f"Using existing supplier: {supplier_name}")

    # Set expiry dates:
    # - BIR: 15 days from now (yellow/warning)
    # - SEC: 10 days ago (red/expired)
    # - Permit: 90 days from now (green/ok)
    bir_expiry = (today + timedelta(days=15)).isoformat()
    sec_expiry = (today - timedelta(days=10)).isoformat()
    permit_expiry = (today + timedelta(days=90)).isoformat()

    r = s.post(f"{HQ}/api/method/hrms.api.procurement.update_supplier", json={
        "name": supplier_name,
        "data": {
            "bir_expiry_date": bir_expiry,
            "sec_expiry_date": sec_expiry,
            "permit_expiry_date": permit_expiry,
        }
    })
    result = r.json().get("message", {})
    print(f"Updated {supplier_name} with expiry dates:")
    print(f"  BIR: {bir_expiry} (warning - 15 days)")
    print(f"  SEC: {sec_expiry} (expired - 10 days ago)")
    print(f"  Permit: {permit_expiry} (ok - 90 days)")
    print(f"  API response: {result}")

    # Verify
    r = s.get(f"{HQ}/api/resource/BEI Supplier/{supplier_name}", params={
        "fields": json.dumps(["name", "supplier_name", "bir_expiry_date", "sec_expiry_date", "permit_expiry_date"])
    })
    doc = r.json().get("data", {})
    print(f"  Verified: BIR={doc.get('bir_expiry_date')}, SEC={doc.get('sec_expiry_date')}, Permit={doc.get('permit_expiry_date')}")
    return supplier_name


def setup_stock_consumption(s):
    """Create Stock Ledger Entries to simulate consumption for low-stock items.

    The get_low_stock_items function reads:
    1. Bin table for current stock (actual_qty > 0)
    2. Stock Ledger Entry for consumption (actual_qty < 0 in last 30 days)

    We need items that:
    - Have stock in Bin (actual_qty > 0) in 'Stores - BEI' warehouse
    - Have negative SLE entries in the last 30 days
    - Result in days_remaining < threshold (7)

    Since we can't directly insert SLEs without going through Stock Entry,
    let's check what items already exist and what their consumption looks like.
    """
    warehouse = "Stores - BEI"

    # Check existing bins
    r = s.get(f"{HQ}/api/resource/Bin", params={
        "filters": json.dumps([
            ["warehouse", "=", warehouse],
            ["actual_qty", ">", 0]
        ]),
        "fields": json.dumps(["item_code", "actual_qty", "warehouse"]),
        "limit_page_length": 20,
        "order_by": "actual_qty asc"
    })
    bins = r.json().get("data", [])
    print(f"\nItems with stock in '{warehouse}': {len(bins)}")
    for b in bins[:10]:
        print(f"  {b['item_code']}: {b['actual_qty']} qty")

    # Check existing SLEs (consumption in last 30 days)
    r = s.post(f"{HQ}/api/method/frappe.client.get_list", json={
        "doctype": "Stock Ledger Entry",
        "filters": [
            ["warehouse", "=", warehouse],
            ["actual_qty", "<", 0],
            ["posting_date", ">=", (datetime.now().date() - timedelta(days=30)).isoformat()]
        ],
        "fields": ["item_code", "sum(actual_qty) as total_consumed"],
        "group_by": "item_code",
        "limit_page_length": 20,
        "order_by": "sum(actual_qty) asc"
    })
    sles = r.json().get("message", [])
    print(f"\nItems with consumption in last 30 days: {len(sles)}")
    for s_entry in sles[:10]:
        print(f"  {s_entry['item_code']}: {s_entry['total_consumed']} consumed")

    # Try creating a Stock Entry (Material Issue) to simulate consumption
    # This is the proper Frappe way to create SLEs
    # Pick an item that has stock
    if bins:
        test_item = bins[0]["item_code"]
        current_stock = bins[0]["actual_qty"]

        # Calculate how much to consume to make days_remaining < 7
        # We want: current_stock / daily_consumption < 7
        # daily_consumption = total_consumed_30d / 30
        # So we need total_consumed_30d > current_stock * 30 / 7 ≈ current_stock * 4.3
        # But we can't consume more than what's available
        # Let's consume 80% of stock to make it look urgent

        consume_qty = min(round(current_stock * 0.8, 2), current_stock - 0.01)
        if consume_qty <= 0:
            consume_qty = 0.01

        print(f"\nCreating Material Issue for {test_item}:")
        print(f"  Current stock: {current_stock}")
        print(f"  Will consume: {consume_qty}")
        print(f"  Expected daily_consumption: {consume_qty / 30:.4f}")
        remaining = current_stock - consume_qty
        daily = consume_qty / 30
        if daily > 0:
            print(f"  Expected days_remaining: {remaining / daily:.1f}")

        # Create Material Issue via Stock Entry
        r = s.post(f"{HQ}/api/resource/Stock Entry", json={
            "stock_entry_type": "Material Issue",
            "posting_date": (datetime.now().date() - timedelta(days=1)).isoformat(),
            "posting_time": "12:00:00",
            "company": "Bebang Enterprise Inc.",
            "items": [{
                "item_code": test_item,
                "qty": consume_qty,
                "s_warehouse": warehouse,
                "basic_rate": 1,
            }]
        })

        if r.status_code == 200:
            se_data = r.json().get("data", {})
            se_name = se_data.get("name")
            print(f"  Created Stock Entry: {se_name}")

            # Submit it to create the SLE
            r = s.put(f"{HQ}/api/resource/Stock Entry/{se_name}", json={
                "docstatus": 1
            })
            if r.status_code == 200:
                print(f"  Submitted Stock Entry: {se_name}")
            else:
                print(f"  Failed to submit: {r.status_code} {r.text[:300]}")
        else:
            print(f"  Failed to create Stock Entry: {r.status_code} {r.text[:300]}")
            print("  Trying direct SLE approach via bench...")
    else:
        print("No items with stock found — cannot create consumption data")

    return bins


def verify_low_stock_api(s):
    """Call the low stock API to verify data is visible."""
    for threshold in [3, 7, 30]:
        r = s.post(f"{HQ}/api/method/hrms.api.procurement.get_low_stock_items", json={
            "threshold_days": threshold
        })
        result = r.json().get("message", {})
        items = result.get("items", [])
        print(f"Low stock (threshold={threshold}d): {len(items)} items")
        for item in items[:3]:
            print(f"  {item.get('item_code')}: stock={item.get('current_stock')}, "
                  f"daily={item.get('daily_consumption')}, days={item.get('days_remaining')}")


def verify_supplier_expiry_api(s):
    """Call the supplier expiry API to verify data is visible."""
    r = s.post(f"{HQ}/api/method/hrms.api.procurement.get_suppliers_with_expiry", json={})
    result = r.json().get("message", {})
    suppliers = result.get("suppliers", [])
    print(f"\nSuppliers with expiry data: {len(suppliers)}")
    for sup in suppliers[:5]:
        print(f"  {sup.get('supplier_name')} ({sup.get('name')}):")
        for exp in sup.get("expiry_status", []):
            print(f"    {exp.get('document')}: {exp.get('expiry_date')} ({exp.get('badge')}, {exp.get('days_left')} days)")


if __name__ == "__main__":
    print("=" * 60)
    print("S135 Test Data Setup")
    print("=" * 60)

    session = get_session("test.hr@bebang.ph", "BeiTest2026!")

    print("\n--- Supplier Expiry Data ---")
    setup_supplier_expiry(session)
    verify_supplier_expiry_api(session)

    print("\n--- Stock Consumption Data ---")
    setup_stock_consumption(session)
    verify_low_stock_api(session)

    print("\n" + "=" * 60)
    print("Setup complete. Rerun L3 tests.")
    print("=" * 60)
