"""
Create a test batch with near-expiry stock in Shaw BLVD - BKI warehouse.

Steps:
1. Find an FG item that has has_batch_no=1 (or enable batch tracking on one)
2. Create a Batch record with expiry_date = tomorrow
3. Create a Stock Reconciliation to add stock for that batch
4. Verify the batch shows up on the expiring page
"""
import os
import json
import urllib.request
from datetime import date, timedelta

FK = os.environ.get("FK")
FS = os.environ.get("FS")
BASE = "https://hq.bebang.ph"

def frappe_call(method, data=None):
    """Call Frappe API method (POST)."""
    url = f"{BASE}/api/method/{method}"
    payload = json.dumps(data or {}).encode()
    req = urllib.request.Request(url, data=payload, headers={
        "Authorization": f"token {FK}:{FS}",
        "Content-Type": "application/json",
    })
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())

def frappe_get(resource, filters=None, fields=None, limit=5):
    """GET a Frappe resource list."""
    params = urllib.parse.urlencode({
        "filters": json.dumps(filters or []),
        "fields": json.dumps(fields or ["name"]),
        "limit_page_length": str(limit),
    })
    url = f"{BASE}/api/resource/{urllib.parse.quote(resource)}?{params}"
    req = urllib.request.Request(url, headers={"Authorization": f"token {FK}:{FS}"})
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read()).get("data", [])

def frappe_put(resource, name, data):
    """Update a Frappe resource."""
    url = f"{BASE}/api/resource/{urllib.parse.quote(resource)}/{urllib.parse.quote(name)}"
    payload = json.dumps(data).encode()
    req = urllib.request.Request(url, data=payload, method="PUT", headers={
        "Authorization": f"token {FK}:{FS}",
        "Content-Type": "application/json",
    })
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())

import urllib.parse

# Step 1: Find an FG item. Check if any have has_batch_no=1
print("Step 1: Finding batch-tracked FG items...")
fg_items = frappe_get("Item",
    filters=[["item_code", "like", "FG%"], ["has_batch_no", "=", 1], ["disabled", "=", 0]],
    fields=["item_code", "item_name", "has_batch_no", "create_new_batch"],
    limit=5
)

if fg_items:
    test_item = fg_items[0]["item_code"]
    print(f"  Found batch-tracked: {test_item}")
else:
    # Enable batch tracking on FG006 (Coconut Jelly — previously had batches)
    test_item = "FG006"
    print(f"  No batch-tracked FG items. Enabling batch tracking on {test_item}...")
    try:
        frappe_put("Item", test_item, {
            "has_batch_no": 1,
            "create_new_batch": 1,
        })
        print(f"  Enabled batch tracking on {test_item}")
    except Exception as e:
        print(f"  Failed to enable: {e}")
        exit(1)

# Step 2: Create a Batch with expiry = tomorrow
tomorrow = (date.today() + timedelta(days=1)).isoformat()
batch_name = f"TEST-EXPIRY-{date.today().isoformat()}"
print(f"\nStep 2: Creating batch {batch_name} with expiry {tomorrow}...")

try:
    result = frappe_call("frappe.client.insert", {
        "doc": {
            "doctype": "Batch",
            "batch_id": batch_name,
            "item": test_item,
            "expiry_date": tomorrow,
            "manufacturing_date": date.today().isoformat(),
        }
    })
    actual_batch = result.get("message", {}).get("name", batch_name)
    print(f"  Created batch: {actual_batch}")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    if "already exists" in body or "DuplicateEntry" in body:
        actual_batch = batch_name
        print(f"  Batch {batch_name} already exists, reusing")
    else:
        print(f"  Failed: {body[:300]}")
        exit(1)

# Step 3: Create Stock Reconciliation to add 5 units of test_item with this batch
print(f"\nStep 3: Creating Stock Reconciliation for {test_item} batch={actual_batch} qty=5...")

try:
    result = frappe_call("frappe.client.insert", {
        "doc": {
            "doctype": "Stock Reconciliation",
            "company": "Bebang Kitchen Inc.",
            "purpose": "Stock Reconciliation",
            "posting_date": date.today().isoformat(),
            "items": [{
                "item_code": test_item,
                "warehouse": "Shaw BLVD - BKI",
                "qty": 5,
                "batch_no": actual_batch,
                "valuation_rate": 100,
            }],
        }
    })
    sr_name = result.get("message", {}).get("name")
    print(f"  Created: {sr_name}")

    # Submit it
    frappe_call("frappe.client.submit", {"doc": {"doctype": "Stock Reconciliation", "name": sr_name}})
    print(f"  Submitted: {sr_name}")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"  Failed: {body[:500]}")
    exit(1)

# Step 4: Verify batch shows in SLE
print(f"\nStep 4: Verifying SLE for {test_item} batch={actual_batch}...")
sles = frappe_get("Stock Ledger Entry",
    filters=[["item_code", "=", test_item], ["warehouse", "=", "Shaw BLVD - BKI"],
             ["batch_no", "=", actual_batch], ["is_cancelled", "=", 0]],
    fields=["voucher_no", "actual_qty", "qty_after_transaction"],
    limit=5
)
for sle in sles:
    print(f"  SLE: {sle['voucher_no']} qty={sle['actual_qty']} after={sle['qty_after_transaction']}")

print(f"\n✓ Test batch ready: item={test_item}, batch={actual_batch}, expiry={tomorrow}")
print(f"  The expiring page should now show this batch with 1 day to expiry.")
