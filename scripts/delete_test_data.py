#!/usr/bin/env python3
"""
Delete test custom data from BEI-HRMS
Deletion order handles dependencies and circular references
"""

import frappe
import sys
from collections import defaultdict

def log_deletion(doctype, name, success, error=None):
    """Log deletion result"""
    if success:
        print(f"✓ {doctype}: {name}")
    else:
        print(f"✗ {doctype}: {name} - ERROR: {error}")

def delete_records(doctype, filters, force=False):
    """Delete records matching filters"""
    deleted = []
    failed = []

    try:
        records = frappe.get_list(doctype, filters=filters)
        print(f"\nFound {len(records)} {doctype} record(s) to delete...")

        for record in records:
            try:
                frappe.delete_doc(doctype, record.name, force=force)
                frappe.db.commit()
                deleted.append(record.name)
                log_deletion(doctype, record.name, True)
            except Exception as e:
                error_msg = str(e)
                failed.append((record.name, error_msg))
                log_deletion(doctype, record.name, False, error_msg)

    except Exception as e:
        print(f"ERROR querying {doctype}: {e}")
        return deleted, failed

    return deleted, failed

def main():
    """Main deletion workflow"""

    # Initialize Frappe
    frappe.init(user='Administrator')
    frappe.connect()

    results = defaultdict(lambda: {"deleted": [], "failed": []})

    try:
        # Step 1: BEI Route - clear Distribution Trip references first
        print("\n" + "="*60)
        print("STEP 1: Clearing BEI Route references from Distribution Trip")
        print("="*60)

        try:
            trips = frappe.get_list("Distribution Trip", fields=["name", "bei_route"])
            for trip in trips:
                if trip.bei_route:
                    doc = frappe.get_doc("Distribution Trip", trip.name)
                    doc.bei_route = None
                    doc.save()
                    print(f"✓ Cleared route from Distribution Trip: {trip.name}")
        except Exception as e:
            print(f"Warning: Could not clear route references: {e}")

        # Step 2: Delete Distribution Trip records (with force for circular refs)
        print("\n" + "="*60)
        print("STEP 2: Deleting Distribution Trip records (test records)")
        print("="*60)

        deleted, failed = delete_records(
            "Distribution Trip",
            [["name", "like", "TEST%"]],
            force=True
        )
        results["Distribution Trip"]["deleted"].extend(deleted)
        results["Distribution Trip"]["failed"].extend(failed)

        # Step 3: Delete BEI Route records
        print("\n" + "="*60)
        print("STEP 3: Deleting BEI Route records (test records)")
        print("="*60)

        deleted, failed = delete_records(
            "BEI Route",
            [["name", "like", "TEST%"]],
            force=False
        )
        results["BEI Route"]["deleted"].extend(deleted)
        results["BEI Route"]["failed"].extend(failed)

        # Step 4: Delete Store Order test records
        print("\n" + "="*60)
        print("STEP 4: Deleting Store Order test records")
        print("="*60)

        deleted, failed = delete_records(
            "Store Order",
            [["name", "like", "TEST%"]],
            force=False
        )
        results["Store Order"]["deleted"].extend(deleted)
        results["Store Order"]["failed"].extend(failed)

        # Step 5: Delete test Suppliers (TEST-*)
        print("\n" + "="*60)
        print("STEP 5: Deleting test Suppliers (starting with TEST-)")
        print("="*60)

        deleted, failed = delete_records(
            "Supplier",
            [["name", "like", "TEST-%"]],
            force=False
        )
        results["Supplier"]["deleted"].extend(deleted)
        results["Supplier"]["failed"].extend(failed)

        # Step 6: Delete test Items (TEST-*)
        print("\n" + "="*60)
        print("STEP 6: Deleting test Items (starting with TEST-)")
        print("="*60)

        deleted, failed = delete_records(
            "Item",
            [["name", "like", "TEST-%"]],
            force=False
        )
        results["Item"]["deleted"].extend(deleted)
        results["Item"]["failed"].extend(failed)

        # Step 7: Delete BEI Cycle Count test records
        print("\n" + "="*60)
        print("STEP 7: Deleting BEI Cycle Count test records")
        print("="*60)

        # Try to find cycle count records marked as test
        # Check for records with "TEST" in name or marked with test flag if it exists
        try:
            deleted, failed = delete_records(
                "BEI Cycle Count",
                [["name", "like", "TEST%"]],
                force=False
            )
            results["BEI Cycle Count"]["deleted"].extend(deleted)
            results["BEI Cycle Count"]["failed"].extend(failed)
        except Exception as e:
            print(f"Note: BEI Cycle Count DocType may not exist or is inaccessible: {e}")

    finally:
        frappe.close()

    # Print summary
    print("\n" + "="*60)
    print("DELETION SUMMARY")
    print("="*60)

    total_deleted = 0
    total_failed = 0

    for doctype in sorted(results.keys()):
        deleted_count = len(results[doctype]["deleted"])
        failed_count = len(results[doctype]["failed"])
        total_deleted += deleted_count
        total_failed += failed_count

        print(f"\n{doctype}:")
        print(f"  Deleted: {deleted_count}")
        if deleted_count > 0:
            for name in results[doctype]["deleted"]:
                print(f"    - {name}")

        if failed_count > 0:
            print(f"  Failed: {failed_count}")
            for name, error in results[doctype]["failed"]:
                print(f"    - {name}: {error}")

    print(f"\n{'='*60}")
    print(f"TOTAL DELETED: {total_deleted}")
    print(f"TOTAL FAILED: {total_failed}")
    print(f"{'='*60}")

    return 0 if total_failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
