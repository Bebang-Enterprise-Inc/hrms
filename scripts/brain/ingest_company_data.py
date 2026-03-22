"""
BEI Brain S023A Phase 1B: Company Data Ingestion
Reads all _FINAL CSVs, generates embeddings, upserts to company_data table.

Usage: python scripts/brain/ingest_company_data.py [--skip-embeddings] [--limit N]
"""
import csv
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import requests

# ─── Config ───
DATA_DIR = Path("F:/Dropbox/Projects/BEI-ERP/data/_FINAL")
BATCH_SIZE = 100  # embeddings per OpenAI call
UPSERT_BATCH = 50  # rows per Supabase upsert

def get_doppler_secret(key):
    result = subprocess.run(
        ["C:/Users/Sam/bin/doppler.exe", "secrets", "get", key, "--plain",
         "--project", "bei-erp", "--config", "dev"],
        capture_output=True, text=True
    )
    return result.stdout.strip()

SUPABASE_URL = get_doppler_secret("SUPABASE_URL")
SUPABASE_KEY = get_doppler_secret("SUPABASE_SERVICE_ROLE_KEY")
OPENAI_KEY = get_doppler_secret("OPENAI_API_KEY")

HEADERS_SB = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates",
}


# ─── Content generators (human-readable summaries for semantic search) ───

def employee_content(row):
    name = row.get("employee_name", "")
    desg = row.get("designation", "")
    store = row.get("store_location", "")
    bio = row.get("new_attendance_device_id", "")
    dept = row.get("department", "")
    status = row.get("status", "")
    joined = row.get("date_of_joining", "")
    emp_type = row.get("employment_type", "")
    return (f"{name} — {desg} at {store}. Bio ID: {bio}. "
            f"Department: {dept}. Status: {status}. Type: {emp_type}. Joined: {joined}.")


def store_content(row):
    name = row.get("Official_Store_Name", "")
    addr = row.get("Store_Address", "")
    city = row.get("City", "")
    pos = row.get("POS_Entity", "")
    sid = row.get("Superadmin_ID", "")
    return (f"Store: {name}. Address: {addr}. City: {city}. "
            f"POS Entity: {pos}. Superadmin ID: {sid}.")


def item_content(row):
    code = row.get("Item Code", "")
    name = row.get("Item Name", "")
    uom = row.get("Default Unit of Measure", "")
    group = row.get("Item Group", "")
    rate = row.get("Valuation Rate", "")
    return f"Item {code}: {name}. UOM: {uom}. Group: {group}. Valuation rate: {rate}."


def supplier_content(row):
    code = row.get("supplier_code", "")
    name = row.get("supplier_name", "")
    status = row.get("status", "Active")
    contact = row.get("contact_person", "")
    terms = row.get("payment_terms", "")
    cat = row.get("category", "")
    return (f"Supplier {code}: {name}. Status: {status}. Contact: {contact}. "
            f"Payment terms: {terms}. Category: {cat}.")


def coa_content(row):
    code = row.get("GL Code", "")
    desc = row.get("GL Description", "")
    atype = row.get("AccountType", "")
    nature = row.get("Account Nature", "")
    cls = row.get("Class", "")
    return f"GL Account {code}: {desc}. Type: {atype}. Nature: {nature}. Class: {cls}."


def warehouse_content(row):
    wid = row.get("warehouse_id", "")
    name = row.get("warehouse_name", "")
    city = row.get("city", "")
    addr = row.get("address", "")
    kind = row.get("node_kind", "")
    return f"Warehouse {wid}: {name}. City: {city}. Type: {kind}. Address: {addr}."


def ap_content(row):
    supplier = row.get("supplier", "")
    amt = row.get("outstanding_amount", "")
    bill_no = row.get("bill_no", "")
    terms = row.get("payment_terms", "")
    return f"AP Balance: {supplier}. Bill #{bill_no}. Outstanding: PHP {amt}. Terms: {terms}."


def bank_content(row):
    branch = row.get("Branch Name", "")
    bank = row.get("Bank Name", "")
    acct_type = row.get("Account Type", "")
    acct_name = row.get("Account Name", "")
    acct_no = row.get("Account Number", "")
    gl = row.get("GL Account", "")
    return f"Bank: {bank} ({branch}). Account: {acct_name} #{acct_no}. Type: {acct_type}. GL: {gl}."


def po_content(row):
    po_no = row.get("PO No", "")
    supplier = row.get("Supplier Name", "")
    date = row.get("PO Date", "")
    approval = row.get("Approval", "")
    pr = row.get("PR No", "")
    return (f"Purchase Order {po_no}. Supplier: {supplier}. Date: {date}. "
            f"Status: {approval}. PR: {pr}.")


def pr_content(row):
    pr_no = row.get("PR No", "")
    purpose = row.get("Purpose", "")
    delivery = row.get("Delivery to", "")
    requested = row.get("Requested By", "")
    approval = row.get("Approval", "")
    return (f"Purchase Requisition {pr_no}. Purpose: {purpose}. "
            f"Deliver to: {delivery}. Requested by: {requested}. Status: {approval}.")


def gr_content(row):
    gr_no = row.get("GR No", "")
    po_no = row.get("PO No", "")
    supplier = row.get("Name", "")
    date = row.get("Date", "")
    return f"Goods Receipt {gr_no}. PO: {po_no}. Supplier: {supplier}. Date: {date}."


def approval_content(row):
    approval_for = row.get("Approval For", "")
    criteria = row.get("Criteria", "")
    approver = row.get("Approver's Name", "")
    return f"Approval Rule: {approval_for} — {criteria}. Approver: {approver}."


def ar_content(row):
    customer = row.get("CUSTOMER", "")
    billed = row.get("BILLED AMOUNT", "")
    net = row.get("NET RECEIVABLES", "")
    status = row.get("STATUS", "")
    period = row.get("PERIOD", "")
    return f"AR: {customer}. Billed: {billed}. Net receivable: {net}. Status: {status}. Period: {period}."


def ar_summary_content(row):
    customer = row.get("CUSTOMER", "")
    d30 = row.get("SUM of 0-30", "0")
    d60 = row.get("SUM of 31-60", "0")
    d90 = row.get("SUM of 61-90", "0")
    d120 = row.get("SUM of 91-120", "0")
    over = row.get("SUM of over 120 ", "0")
    return (f"AR Aging Summary: {customer}. 0-30d: {d30}. 31-60d: {d60}. "
            f"61-90d: {d90}. 91-120d: {d120}. >120d: {over}.")


def procurement_item_content(row):
    code = row.get("Item Code", "")
    name = row.get("Item Name", "")
    uom = row.get("UOM", "")
    cat = row.get("Category", "")
    price_inc = row.get("Unit Price (Vat Inc)", "")
    return f"Procurement Item {code}: {name}. UOM: {uom}. Category: {cat}. Price (VAT inc): {price_inc}."


def procurement_supplier_content(row):
    code = row.get("Supplier Code", "")
    name = row.get("Supplier Name", "")
    contact = row.get("Contact Person", "")
    email = row.get("Email ID", "")
    return f"Procurement App Supplier {code}: {name}. Contact: {contact}. Email: {email}."


# ─── Data source registry ───

SOURCES = [
    {
        "file": "EMPLOYEE_MASTER.csv",
        "domain": "hr",
        "entity_type": "employee",
        "entity_id_field": "new_attendance_device_id",
        "content_fn": employee_content,
    },
    {
        "file": "STORE_MAPPING.csv",
        "domain": "stores",
        "entity_type": "store",
        "entity_id_field": "Superadmin_ID",
        "content_fn": store_content,
    },
    {
        "file": "ITEM_MASTER.csv",
        "domain": "inventory",
        "entity_type": "item",
        "entity_id_field": "Item Code",
        "content_fn": item_content,
    },
    {
        "file": "SUPPLIER_MASTER.csv",
        "domain": "procurement",
        "entity_type": "supplier",
        "entity_id_field": "supplier_code",
        "content_fn": supplier_content,
    },
    {
        "file": "SUPPLIER_MASTER_INACTIVE.csv",
        "domain": "procurement",
        "entity_type": "supplier",
        "entity_id_field": "supplier_code",
        "content_fn": supplier_content,
    },
    {
        "file": "COA.csv",
        "domain": "finance",
        "entity_type": "gl_account",
        "entity_id_field": "GL Code",
        "content_fn": coa_content,
    },
    {
        "file": "WAREHOUSE_TREE.csv",
        "domain": "inventory",
        "entity_type": "warehouse",
        "entity_id_field": "warehouse_id",
        "content_fn": warehouse_content,
    },
    {
        "file": "AP_OPENING.csv",
        "domain": "finance",
        "entity_type": "ap_balance",
        "entity_id_field": "bill_no",
        "content_fn": ap_content,
    },
    {
        "file": "BANK_DIRECTORY.csv",
        "domain": "finance",
        "entity_type": "bank_account",
        "entity_id_field": "Account Number",
        "content_fn": bank_content,
    },
    {
        "file": "procurement/Purchase_Order.csv",
        "domain": "procurement",
        "entity_type": "po",
        "entity_id_field": "PO No",
        "content_fn": po_content,
    },
    {
        "file": "procurement/Purchase_Requisitions.csv",
        "domain": "procurement",
        "entity_type": "pr",
        "entity_id_field": "PR No",
        "content_fn": pr_content,
    },
    {
        "file": "procurement/Goods_Receipts.csv",
        "domain": "procurement",
        "entity_type": "gr",
        "entity_id_field": "GR No",
        "content_fn": gr_content,
    },
    {
        "file": "procurement/Approval_Matrix.csv",
        "domain": "procurement",
        "entity_type": "approval_rule",
        "entity_id_field": None,
        "content_fn": approval_content,
    },
    {
        "file": "procurement/Suppliers.csv",
        "domain": "procurement",
        "entity_type": "supplier_app",
        "entity_id_field": "Supplier Code",
        "content_fn": procurement_supplier_content,
    },
    {
        "file": "procurement/Item_List.csv",
        "domain": "procurement",
        "entity_type": "item_procurement",
        "entity_id_field": "Item Code",
        "content_fn": procurement_item_content,
    },
    {
        "file": "ar_aging/AR_AGING_DETAILS.csv",
        "domain": "finance",
        "entity_type": "ar_aging",
        "entity_id_field": None,
        "content_fn": ar_content,
    },
    {
        "file": "ar_aging/SUMMARY_AGING.csv",
        "domain": "finance",
        "entity_type": "ar_summary",
        "entity_id_field": "CUSTOMER",
        "content_fn": ar_summary_content,
    },
]


def read_csv(filepath):
    """Read CSV, handling BOM and encoding."""
    rows = []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip completely empty rows
            if all(v.strip() == "" for v in row.values()):
                continue
            rows.append(dict(row))
    return rows


def row_hash(data):
    """SHA-256 hash of structured data for change detection."""
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def batch_embed(texts):
    """Generate embeddings via OpenAI API in batches."""
    resp = requests.post(
        "https://api.openai.com/v1/embeddings",
        headers={
            "Authorization": f"Bearer {OPENAI_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "input": texts,
            "model": "text-embedding-3-small",
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    return [d["embedding"] for d in sorted(data, key=lambda x: x["index"])]


def upsert_batch(rows):
    """Upsert rows to company_data via Supabase REST API (service role bypasses RLS)."""
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/company_data?on_conflict=entity_type,entity_id",
        headers=HEADERS_SB,
        json=rows,
        timeout=60,
    )
    if resp.status_code not in (200, 201):
        print(f"  Upsert error ({resp.status_code}): {resp.text[:200]}")
        return False
    return True


def process_source(source, skip_embeddings=False, limit=None):
    """Process a single data source: read CSV, embed, upsert."""
    filepath = DATA_DIR / source["file"]
    if not filepath.exists():
        print(f"  SKIP: {source['file']} not found")
        return 0

    rows = read_csv(filepath)
    if limit:
        rows = rows[:limit]

    if not rows:
        print(f"  SKIP: {source['file']} empty")
        return 0

    # Build records
    records = []
    for i, row in enumerate(rows):
        # Generate entity_id
        eid_field = source["entity_id_field"]
        if eid_field and eid_field in row:
            eid = str(row[eid_field]).strip()
        else:
            eid = f"{source['entity_type']}_{i:04d}"

        if not eid or eid == "":
            eid = f"{source['entity_type']}_{i:04d}"

        content = source["content_fn"](row)
        if not content or content.strip() == "":
            continue

        structured = {k: v for k, v in row.items() if v and str(v).strip()}
        rhash = row_hash(structured)

        records.append({
            "domain": source["domain"],
            "entity_type": source["entity_type"],
            "entity_id": eid,
            "content": content[:2000],  # cap content length
            "structured_data": structured,
            "source_file": f"data/_FINAL/{source['file']}",
            "row_hash": rhash,
        })

    if not records:
        return 0

    # Deduplicate by entity_type+entity_id (keep last occurrence)
    seen = {}
    for rec in records:
        key = (rec["entity_type"], rec["entity_id"])
        seen[key] = rec
    records = list(seen.values())

    # Generate embeddings in batches
    if not skip_embeddings:
        texts = [r["content"] for r in records]
        all_embeddings = []
        for batch_start in range(0, len(texts), BATCH_SIZE):
            batch = texts[batch_start:batch_start + BATCH_SIZE]
            embeddings = batch_embed(batch)
            all_embeddings.extend(embeddings)
            if batch_start + BATCH_SIZE < len(texts):
                time.sleep(0.5)  # rate limit courtesy

        for rec, emb in zip(records, all_embeddings):
            rec["embedding"] = emb
    else:
        for rec in records:
            rec["embedding"] = None

    # Upsert in batches
    success = 0
    for batch_start in range(0, len(records), UPSERT_BATCH):
        batch = records[batch_start:batch_start + UPSERT_BATCH]
        if upsert_batch(batch):
            success += len(batch)

    return success


def main():
    skip_embeddings = "--skip-embeddings" in sys.argv
    limit = None
    for i, arg in enumerate(sys.argv):
        if arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    print(f"=== BEI Brain Company Data Ingestion ===")
    print(f"  Skip embeddings: {skip_embeddings}")
    print(f"  Limit per source: {limit or 'all'}")
    print()

    total = 0
    for source in SOURCES:
        print(f"Processing: {source['file']} ({source['entity_type']})...")
        count = process_source(source, skip_embeddings, limit)
        print(f"  Ingested: {count} rows")
        total += count

    print(f"\n=== TOTAL INGESTED: {total} rows ===")

    # Verify
    print("\n=== VERIFICATION ===")
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/company_data?select=entity_type,count",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        },
        params={"select": "entity_type"},
        timeout=30,
    )
    if resp.status_code == 200:
        print(f"  Total rows in company_data: {len(resp.json())}")


if __name__ == "__main__":
    main()
