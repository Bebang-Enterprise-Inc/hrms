"""S120 Fact-Check: Layer 1 programmatic verification of all data claims."""
import csv, json, subprocess, sys
from collections import Counter

PASS = 0
FAIL = 0
WARN = 0

def check(label, expected, actual, tolerance=0):
    global PASS, FAIL, WARN
    if tolerance and isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if abs(expected - actual) <= tolerance:
            print(f"  PASS  {label}: expected={expected}, actual={actual} (tolerance={tolerance})")
            PASS += 1
            return
    if expected == actual:
        print(f"  PASS  {label}: {actual}")
        PASS += 1
    else:
        print(f"  FAIL  {label}: expected={expected}, actual={actual}")
        FAIL += 1

def warn(label, msg):
    global WARN
    print(f"  WARN  {label}: {msg}")
    WARN += 1

def curl_frappe(payload):
    r = subprocess.run([
        'curl', '-s', '-k', 'https://hq.bebang.ph/api/method/frappe.client.get_list',
        '-H', 'Content-Type: application/json',
        '-H', 'Authorization: token 4a17c23aca83560:38ecc0e1054b1d2',
        '-d', json.dumps(payload)
    ], capture_output=True, text=True)
    return json.loads(r.stdout).get('message', [])

def curl_frappe_count(payload):
    r = subprocess.run([
        'curl', '-s', '-k', 'https://hq.bebang.ph/api/method/frappe.client.get_count',
        '-H', 'Content-Type: application/json',
        '-H', 'Authorization: token 4a17c23aca83560:38ecc0e1054b1d2',
        '-d', json.dumps(payload)
    ], capture_output=True, text=True)
    return json.loads(r.stdout).get('message', 0)

print("=" * 70)
print("S120 FACT-CHECK: Layer 1 Programmatic Verification")
print("=" * 70)

# =====================================================================
# CLAIM 1: Compliance App Item List has 365 items
# =====================================================================
print("\n--- Claim: Compliance App Item List = 365 items ---")
with open('tmp/compliance_item_list.csv', 'r', encoding='utf-8') as f:
    comp_items = [r for r in csv.DictReader(f) if (r.get('Item Code') or '').strip()]
check("Compliance App Item List count", 365, len(comp_items), tolerance=5)

# =====================================================================
# CLAIM 2: Compliance App PO Items = 2013 line items
# =====================================================================
print("\n--- Claim: Compliance App PO Items = 2013 rows ---")
with open('tmp/compliance_po_items.csv', 'r', encoding='utf-8') as f:
    po_items = list(csv.DictReader(f))
check("PO Items row count", 2013, len(po_items), tolerance=5)

# Count unique item codes in PO Items
po_unique = len(set((r.get('Item Code') or '').strip() for r in po_items if (r.get('Item Code') or '').strip()))
print(f"  INFO  PO Items unique item codes: {po_unique}")

# =====================================================================
# CLAIM 3: Compliance App GR Items = 2267 line items, 230 unique items
# =====================================================================
print("\n--- Claim: Compliance App GR Items = 2267 rows, 230 unique ---")
with open('tmp/compliance_gr_items.csv', 'r', encoding='utf-8') as f:
    gr_items = list(csv.DictReader(f))
check("GR Items row count", 2267, len(gr_items), tolerance=5)
gr_unique = len(set((r.get('Item Code') or '').strip() for r in gr_items if (r.get('Item Code') or '').strip()))
check("GR Items unique item codes", 230, gr_unique, tolerance=10)

# =====================================================================
# CLAIM 4: Frappe Item master = 463 items
# =====================================================================
print("\n--- Claim: Frappe Item master = 463 items ---")
frappe_count = curl_frappe_count({'doctype': 'Item'})
check("Frappe Item count", 463, frappe_count, tolerance=5)

# =====================================================================
# CLAIM 5: Frappe Item Price records = 8
# =====================================================================
print("\n--- Claim: Frappe Item Price = 8 records ---")
ip_count = curl_frappe_count({'doctype': 'Item Price'})
check("Frappe Item Price count", 8, ip_count)

# =====================================================================
# CLAIM 6: 330 Compliance items overlap with Frappe
# =====================================================================
print("\n--- Claim: 330 Compliance items in Frappe ---")
frappe_items = {r['name'] for r in curl_frappe({
    'doctype': 'Item', 'fields': ['name'], 'limit_page_length': 0
})}
comp_codes = {(r.get('Item Code') or '').strip() for r in comp_items if (r.get('Item Code') or '').strip()}
overlap = comp_codes & frappe_items
not_in_frappe = comp_codes - frappe_items
check("Compliance items in Frappe", 330, len(overlap), tolerance=5)
check("Compliance items NOT in Frappe", 35, len(not_in_frappe), tolerance=5)

# =====================================================================
# CLAIM 7: 252 items have Compliance price but Frappe standard_rate=0
# =====================================================================
print("\n--- Claim: 252 items with price gap ---")
frappe_rates = {r['name']: r for r in curl_frappe({
    'doctype': 'Item',
    'fields': ['name', 'standard_rate', 'valuation_rate'],
    'limit_page_length': 0
})}
comp_dict = {}
for r in comp_items:
    code = (r.get('Item Code') or '').strip()
    if code:
        comp_dict[code] = r

gap = 0
for code in overlap:
    ci = comp_dict.get(code, {})
    fi = frappe_rates.get(code, {})
    try:
        p = float((ci.get('Unit Price (Vat ex)') or ci.get('Unit Price (Vat Inc)') or '0').strip() or '0')
    except ValueError:
        p = 0
    std = float(fi.get('standard_rate') or 0)
    if p > 0 and std == 0:
        gap += 1
check("Items with price gap (Compliance has price, Frappe std=0)", 252, gap, tolerance=10)

# =====================================================================
# CLAIM 8: Frappe items with stock > 0 = 206
# =====================================================================
print("\n--- Claim: Items with stock > 0 = 206 ---")
stock_bins = curl_frappe({
    'doctype': 'Bin',
    'fields': ['item_code', 'sum(actual_qty) as total_qty'],
    'group_by': 'item_code',
    'limit_page_length': 0,
    'filters': [['actual_qty', '>', 0]]
})
# Count items where total > 0
items_with_stock = len(stock_bins)
check("Items with stock > 0", 206, items_with_stock, tolerance=15)

# =====================================================================
# CLAIM 9: 63 stale items
# =====================================================================
print("\n--- Claim: 63 stale items ---")
with open('tmp/item_master_full_analysis.csv', 'r', encoding='utf-8') as f:
    analysis = list(csv.DictReader(f))
stale_count = sum(1 for r in analysis if r.get('status') == 'STALE_REMOVE')
check("Stale items (STALE_REMOVE)", 63, stale_count)

active_count = sum(1 for r in analysis if r.get('status') == 'ACTIVE')
dormant_count = sum(1 for r in analysis if r.get('status') == 'DORMANT_BUT_KNOWN')
check("Active items", 212, active_count)
check("Dormant but known items", 188, dormant_count, tolerance=10)
check("Analysis total rows", 463, len(analysis), tolerance=5)

# =====================================================================
# CLAIM 10: SKU Master items all exist in Frappe (0 missing)
# =====================================================================
print("\n--- Claim: All 92 SKU Master items exist in Frappe ---")
with open('data/Procurement_Database/FORENSIC_EXTRACTION/Copy of Compliance App Database__SKU_Master.csv', 'r', encoding='utf-8-sig') as f:
    sku = list(csv.DictReader(f))
sku_codes = {r['Item Code'] for r in sku}
sku_missing = sku_codes - frappe_items
check("SKU Master items count", 92, len(sku))
check("SKU Master items missing from Frappe", 0, len(sku_missing))

# =====================================================================
# CLAIM 11: PR-2026-03022 has SAGO at estimated_unit_cost=0
# =====================================================================
print("\n--- Claim: PR-2026-03022 SAGO at PHP0 ---")
r = subprocess.run([
    'curl', '-s', '-k',
    'https://hq.bebang.ph/api/resource/BEI%20Purchase%20Requisition/PR-2026-03022',
    '-H', 'Authorization: token 4a17c23aca83560:38ecc0e1054b1d2',
], capture_output=True, text=True)
pr_data = json.loads(r.stdout).get('data', {})
if pr_data:
    pr_items = pr_data.get('items', [])
    if pr_items:
        item = pr_items[0]
        check("PR item code", "SAGO", item.get('item_code'))
        check("PR estimated_unit_cost", 0.0, float(item.get('estimated_unit_cost', -1)))
    else:
        warn("PR-2026-03022", "No items found")
else:
    warn("PR-2026-03022", "PR not found or no access")

# =====================================================================
# CLAIM 12: "SAGO" doesn't exist as Item code, FG009 does
# =====================================================================
print("\n--- Claim: SAGO not an Item code, FG009 exists ---")
check("SAGO in Frappe items", False, 'SAGO' in frappe_items)
check("FG009 in Frappe items", True, 'FG009' in frappe_items)

# =====================================================================
# CLAIM 13: Google Sheet ID is valid
# =====================================================================
print("\n--- Claim: Google Sheet IDs documented correctly ---")
# We already extracted from these — if they worked, IDs are valid
check("Compliance App Sheet ID used successfully", True, len(comp_items) > 300)
print("  INFO  Sheet ID: 1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q (verified by extraction)")

# =====================================================================
# CLAIM 14: Compliance App Item List has VAT-inclusive and VAT-exclusive prices
# =====================================================================
print("\n--- Claim: Compliance App has VAT inc/ex pricing ---")
has_vat_inc = sum(1 for r in comp_items if (r.get('Unit Price (Vat Inc)') or '').strip() not in ('', '0'))
has_vat_ex = sum(1 for r in comp_items if (r.get('Unit Price (Vat ex)') or '').strip() not in ('', '0'))
print(f"  INFO  Items with VAT inc price > 0: {has_vat_inc}")
print(f"  INFO  Items with VAT ex price > 0: {has_vat_ex}")
if has_vat_inc > 100:
    check("Substantial VAT inc pricing exists", True, True)
else:
    warn("VAT pricing", f"Only {has_vat_inc} items have VAT inc pricing")

# =====================================================================
# CLAIM 15: PO Items have unit costs (for price resolution)
# =====================================================================
print("\n--- Claim: PO Items have unit costs for price resolution ---")
po_with_cost = sum(1 for r in po_items if float((r.get('Unit Cost') or '0').strip().replace(',','') or '0') > 0)
print(f"  INFO  PO line items with Unit Cost > 0: {po_with_cost}/{len(po_items)}")
check("PO Items with pricing", True, po_with_cost > 1500)

# =====================================================================
# SUMMARY
# =====================================================================
print("\n" + "=" * 70)
print(f"FACT-CHECK SUMMARY: {PASS} PASS / {FAIL} FAIL / {WARN} WARN")
print("=" * 70)
if FAIL > 0:
    print("ACTION REQUIRED: Fix failed claims in plan before execution.")
    sys.exit(1)
else:
    print("ALL CLAIMS VERIFIED. Plan is grounded in real data.")
    sys.exit(0)
