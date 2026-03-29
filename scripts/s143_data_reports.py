"""S143 Phase B: Generate supplier compliance and item price reports.

Queries hq.bebang.ph Frappe API with session auth, generates CSVs.
"""
import csv
import json
import os
import sys
import requests

FRAPPE_URL = "https://hq.bebang.ph"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "s143")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def login(username: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{FRAPPE_URL}/api/method/login", data={"usr": username, "pwd": password})
    r.raise_for_status()
    print(f"Logged in as {username}")
    return s


def get_all(session: requests.Session, doctype: str, fields: list[str], filters: list | None = None, limit: int = 500) -> list[dict]:
    """Frappe get_all via REST API."""
    params = {
        "doctype": doctype,
        "fields": json.dumps(fields),
        "limit_page_length": limit,
    }
    if filters:
        params["filters"] = json.dumps(filters)
    r = session.get(f"{FRAPPE_URL}/api/resource/{doctype}", params={
        "fields": json.dumps(fields),
        "filters": json.dumps(filters or []),
        "limit_page_length": limit,
    })
    r.raise_for_status()
    return r.json().get("data", [])


def b1_supplier_compliance(session: requests.Session):
    """DEF-003: Generate supplier compliance CSV."""
    print("\n=== B1: Supplier Compliance Report ===")
    suppliers = get_all(session, "BEI Supplier",
        fields=["supplier_name", "supplier_code", "status", "tin", "bir_2307", "sec_certificate", "business_permit"],
        filters=[["status", "=", "Active"]],
        limit=500
    )
    print(f"Found {len(suppliers)} active suppliers")

    out_path = os.path.join(OUTPUT_DIR, "suppliers_missing_compliance.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "supplier_name", "supplier_code", "status",
            "tin_present", "bir_2307_present", "sec_cert_present", "business_permit_present",
            "docs_complete"
        ])
        writer.writeheader()

        complete = 0
        missing = 0
        for s in suppliers:
            tin_ok = bool(s.get("tin") and str(s["tin"]).strip())
            bir_ok = bool(s.get("bir_2307") and str(s["bir_2307"]).strip())
            sec_ok = bool(s.get("sec_certificate") and str(s["sec_certificate"]).strip())
            bp_ok = bool(s.get("business_permit") and str(s["business_permit"]).strip())
            all_ok = tin_ok and bir_ok and sec_ok and bp_ok

            if all_ok:
                complete += 1
            else:
                missing += 1

            writer.writerow({
                "supplier_name": s.get("supplier_name", ""),
                "supplier_code": s.get("supplier_code", ""),
                "status": s.get("status", ""),
                "tin_present": "Yes" if tin_ok else "No",
                "bir_2307_present": "Yes" if bir_ok else "No",
                "sec_cert_present": "Yes" if sec_ok else "No",
                "business_permit_present": "Yes" if bp_ok else "No",
                "docs_complete": "Yes" if all_ok else "No",
            })

    print(f"Complete: {complete}, Missing docs: {missing}")
    print(f"Output: {out_path}")
    return out_path


def b2_item_price_backfill(session: requests.Session):
    """DEF-004: Generate item price backfill and SKU crossref CSVs."""
    print("\n=== B2: Item Price Backfill ===")

    # Get all items with standard_rate
    items = get_all(session, "Item",
        fields=["name", "item_name", "item_code", "standard_rate", "item_group", "stock_uom"],
        limit=500
    )
    print(f"Found {len(items)} items total")

    zero_price = [i for i in items if not i.get("standard_rate") or float(i.get("standard_rate", 0)) == 0]
    print(f"Items with zero/null price: {len(zero_price)}")

    # Get POs with their items via full doc fetch
    pos_list = get_all(session, "BEI Purchase Order",
        fields=["name", "po_no", "po_date", "status"],
        filters=[["status", "not in", ["Draft", "Cancelled"]]],
        limit=2000
    )
    print(f"Found {len(pos_list)} non-draft POs")

    # Fetch items from each PO (batch via individual doc gets)
    po_items: list[dict] = []
    po_date_map: dict[str, dict] = {}
    for i, po in enumerate(pos_list):
        po_name = po["name"]
        po_date_map[po_name] = {
            "po_no": po.get("po_no", ""),
            "po_date": po.get("po_date", ""),
            "status": po.get("status", ""),
        }
        # Get full PO doc with items
        try:
            r = session.get(f"{FRAPPE_URL}/api/resource/BEI Purchase Order/{po_name}")
            if r.ok:
                doc = r.json().get("data", {})
                for item in doc.get("items", []):
                    po_items.append({
                        "item_code": item.get("item_code", ""),
                        "item_name": item.get("item_name", ""),
                        "rate": item.get("rate", 0),
                        "uom": item.get("uom", ""),
                        "parent": po_name,
                    })
        except Exception as e:
            print(f"  Error fetching {po_name}: {e}")
        if (i + 1) % 50 == 0:
            print(f"  Fetched {i + 1}/{len(pos_list)} POs ({len(po_items)} items)")

    print(f"Found {len(po_items)} PO line items from {len(pos_list)} POs")

    # Build latest price per item from PO data
    latest_price: dict[str, dict] = {}
    for pi in po_items:
        ic = pi.get("item_code", "")
        if not ic:
            continue
        po_info = po_date_map.get(pi.get("parent", ""), {})
        po_date = po_info.get("po_date", "")
        if po_info.get("status") in ("Draft", "Cancelled"):
            continue
        existing = latest_price.get(ic)
        if not existing or (po_date and po_date > existing.get("po_date", "")):
            latest_price[ic] = {
                "item_code": ic,
                "item_name": pi.get("item_name", ""),
                "suggested_rate": pi.get("rate", 0),
                "uom": pi.get("uom", ""),
                "source_po": po_info.get("po_no", pi.get("parent", "")),
                "po_date": po_date,
            }

    # Write price backfill CSV
    out_path = os.path.join(OUTPUT_DIR, "item_price_backfill.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "item_code", "item_name", "current_rate", "suggested_rate", "uom",
            "source_po", "po_date", "needs_update"
        ])
        writer.writeheader()

        needs_update = 0
        for item in items:
            ic = item.get("name", "")
            current = float(item.get("standard_rate", 0) or 0)
            suggestion = latest_price.get(ic, {})
            suggested = float(suggestion.get("suggested_rate", 0) or 0)
            needs = current == 0 and suggested > 0
            if needs:
                needs_update += 1

            writer.writerow({
                "item_code": ic,
                "item_name": item.get("item_name", ""),
                "current_rate": current,
                "suggested_rate": suggested if suggested else "",
                "uom": item.get("stock_uom", ""),
                "source_po": suggestion.get("source_po", ""),
                "po_date": suggestion.get("po_date", ""),
                "needs_update": "Yes" if needs else "",
            })

    print(f"Items needing price update: {needs_update}")
    print(f"Output: {out_path}")

    # SKU Master crossref
    sku_csv = os.path.join(os.path.dirname(os.path.dirname(__file__)),
        "data", "Procurement_Database", "FORENSIC_EXTRACTION",
        "Copy of Compliance App Database__SKU_Master.csv")

    out_sku = os.path.join(OUTPUT_DIR, "sku_master_crossref.csv")
    item_codes_set = {i.get("name", "").strip().upper() for i in items}
    item_names_map = {i.get("item_name", "").strip().upper(): i.get("name", "") for i in items if i.get("item_name")}

    if os.path.exists(sku_csv):
        print(f"\nReading SKU Master: {sku_csv}")
        with open(sku_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            sku_rows = list(reader)
        print(f"Found {len(sku_rows)} SKU Master rows")

        with open(out_sku, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "csv_item_code", "csv_item_name", "frappe_match", "frappe_item_code", "match_method"
            ])
            writer.writeheader()

            matched = 0
            for row in sku_rows:
                csv_code = str(row.get("Item Code", row.get("item_code", ""))).strip()
                csv_name = str(row.get("Item Name", row.get("item_name", ""))).strip()

                frappe_match = ""
                frappe_code = ""
                method = ""

                # Try exact code match
                if csv_code.upper() in item_codes_set:
                    frappe_match = "EXACT_CODE"
                    frappe_code = csv_code
                    method = "code"
                    matched += 1
                # Try name match
                elif csv_name.upper() in item_names_map:
                    frappe_match = "NAME_MATCH"
                    frappe_code = item_names_map[csv_name.upper()]
                    method = "name"
                    matched += 1
                else:
                    frappe_match = "NO_MATCH"
                    method = ""

                writer.writerow({
                    "csv_item_code": csv_code,
                    "csv_item_name": csv_name,
                    "frappe_match": frappe_match,
                    "frappe_item_code": frappe_code,
                    "match_method": method,
                })

            print(f"SKU matches: {matched}/{len(sku_rows)}")
            print(f"Output: {out_sku}")
    else:
        print(f"SKU Master CSV not found: {sku_csv}")

    # Check for orphan items (PO line items referencing non-existent Item Master codes)
    orphans = []
    for pi in po_items:
        ic = pi.get("item_code", "")
        if ic and ic not in {i.get("name", "") for i in items}:
            orphans.append({
                "item_code": ic,
                "item_name": pi.get("item_name", ""),
                "source_po": pi.get("parent", ""),
            })

    if orphans:
        unique_orphans = {o["item_code"]: o for o in orphans}
        print(f"\nOrphan items (in POs but not in Item Master): {len(unique_orphans)}")
        for code, o in unique_orphans.items():
            print(f"  - {code}: {o['item_name']} (PO: {o['source_po']})")

    return out_path, out_sku


if __name__ == "__main__":
    # CEO credentials from plan
    session = login("sam@bebang.ph", "2289454")

    b1_supplier_compliance(session)
    b2_item_price_backfill(session)

    print("\n=== Done ===")
