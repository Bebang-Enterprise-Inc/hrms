#!/usr/bin/env python3
"""S143: Delete test/E2E suppliers from BEI Supplier DocType.

Runs inside Frappe Docker container via SSM.
54 test suppliers identified by code patterns + explicit names.
"""
import os, sys, re

# Step 0: Create log directories
for d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(d, exist_ok=True)

import frappe

frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# === Test supplier patterns ===
TEST_PATTERNS = [
    r'^API-TEST',
    r'^CURL-',
    r'^CUTOVER-',
    r'^E2E-',
    r'^CYCLE-',
    r'^QA-',
    r'^S062',
    r'^S063',
    r'^JS-TEST',
    r'^NOTERMS',
    r'^UI-CREATED',
]

EXPLICIT_CODES = [
    'GR-TEST-001',
    'SUPP-20260326224326',
    'SUPP-20260326224428',
    'TC1',
]

# === Before snapshot ===
total_before = frappe.db.count('BEI Supplier')
active_before = frappe.db.count('BEI Supplier', {'status': 'Active'})
print(f"BEFORE: {total_before} total suppliers, {active_before} active")

# === Find test suppliers ===
all_suppliers = frappe.get_all('BEI Supplier',
    fields=['name', 'supplier_name', 'supplier_code', 'status'],
    limit_page_length=500
)

to_delete = []
for sup in all_suppliers:
    code = sup.get('supplier_code', '')
    is_test = any(re.search(pat, code, re.IGNORECASE) for pat in TEST_PATTERNS)
    is_explicit = code in EXPLICIT_CODES
    if is_test or is_explicit:
        to_delete.append(sup)

print(f"\nFound {len(to_delete)} test suppliers to delete:")
for sup in to_delete:
    print(f"  {sup['supplier_code']:40s} | {sup['supplier_name']}")

# === Check for POs referencing these suppliers ===
test_names_frappe = [s['name'] for s in to_delete]

# Check BEI Purchase Order references via the supplier Link field
po_refs = []
for sup_name in test_names_frappe:
    count = frappe.db.count('BEI Purchase Order', {'supplier': sup_name})
    if count > 0:
        po_refs.append({'name': sup_name, 'count': count})

if po_refs:
    print(f"\nWARNING: {len(po_refs)} test suppliers have POs:")
    blocked_names = set()
    for ref in po_refs:
        print(f"  {ref['name']}: {ref['count']} POs")
        blocked_names.add(ref['name'])
    blocked = [s for s in to_delete if s['name'] in blocked_names]
    to_delete = [s for s in to_delete if s['name'] not in blocked_names]
    print(f"\n  Will SET INACTIVE (have POs): {len(blocked)}")
    print(f"  Will DELETE (no POs): {len(to_delete)}")

    for sup in blocked:
        frappe.db.set_value('BEI Supplier', sup['name'], 'status', 'Inactive')
        print(f"  Set Inactive: {sup['supplier_code']}")
    frappe.db.commit()
else:
    print("\nNo test suppliers have POs — safe to delete all.")

# === Delete test suppliers ===
print(f"\nDeleting {len(to_delete)} test suppliers...")
deleted = 0
failed = 0
for sup in to_delete:
    try:
        frappe.delete_doc('BEI Supplier', sup['name'], force=True, ignore_permissions=True)
        deleted += 1
    except Exception as e:
        # Fallback: set inactive
        try:
            frappe.db.set_value('BEI Supplier', sup['name'], 'status', 'Inactive')
            print(f"  Could not delete {sup['supplier_code']}, set Inactive: {str(e)[:60]}")
        except:
            print(f"  FAILED: {sup['supplier_code']}: {str(e)[:80]}")
            failed += 1
    if deleted % 10 == 0:
        frappe.db.commit()

frappe.db.commit()

# === After snapshot ===
total_after = frappe.db.count('BEI Supplier')
active_after = frappe.db.count('BEI Supplier', {'status': 'Active'})
inactive_after = frappe.db.count('BEI Supplier', {'status': 'Inactive'})
pending_after = frappe.db.count('BEI Supplier', {'status': 'Pending Verification'})

print(f"\nRESULTS:")
print(f"  Deleted: {deleted}")
print(f"  Failed: {failed}")
print(f"  BEFORE: {total_before} total, {active_before} active")
print(f"  AFTER:  {total_after} total, {active_after} active, {inactive_after} inactive, {pending_after} pending")
print("CLEANUP-DONE")

frappe.destroy()
