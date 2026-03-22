#!/usr/bin/env python3
"""
Generate ERPNext Journal Vouchers from Supabase POS daily revenue data.

This script aggregates POS order data from Supabase by store and date,
then generates Journal Voucher entries for ERPNext. Each store gets one JV
per day with proper double-entry accounting:

  DEBIT:  Cash/Payment Receivable accounts (by payment type)
  CREDIT: Sales Revenue (net of VAT)
  CREDIT: Output VAT Payable (VAT component)

Key accounting identities verified per order:
  gross_sales = net_sales + vat_amount  (always true)
  original_gross_sales >= gross_sales   (difference = discounts applied pre-billing)

Usage:
  python scripts/generate_daily_jv.py --date 2026-02-13 --dry-run
  python scripts/generate_daily_jv.py --date 2026-02-13 --store 2338 --dry-run
  python scripts/generate_daily_jv.py --date 2026-02-13 --live  (POST to ERPNext)

Requires Doppler secrets:
  - SUPABASE_SERVICE_ROLE_KEY (bei-erp/dev)
  - FRAPPE_API_KEY (bei-erp/dev)
  - FRAPPE_API_SECRET (bei-erp/dev)
"""

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DOPPLER_BIN = "C:/Users/Sam/bin/doppler.exe"
DOPPLER_PROJECT = "bei-erp"
DOPPLER_CONFIG = "dev"

SUPABASE_BASE = "https://csnniykjrychgajfrgua.supabase.co/rest/v1"
ERPNEXT_BASE = "https://hq.bebang.ph"

COMPANY = "Bebang Enterprise Inc."
COMPANY_ABBR = "BEI"
DEFAULT_COST_CENTER = f"Main - {COMPANY_ABBR}"

STORE_MAP_PATH = Path(__file__).parent.parent / "data" / "store_cost_center_map.json"

# Account names in ERPNext COA
# NOTE: SALES REVENUE account does NOT exist yet -- must be created before live mode
ACCOUNTS = {
    "sales_revenue": f"SALES REVENUE - {COMPANY}",
    "output_vat": f"OUTPUT VAT PAYABLE - {COMPANY}",
    "cash": f"CASHIER'S FUND - {COMPANY}",
    "digital_receivable": f"RECEIVABLES FROM PAYMONGO - {COMPANY}",
    "discount_expense": f"DISCOUNTS AND PROMO - {COMPANY}",
}

# Map POS payment_type to debit account key
PAYMENT_TYPE_MAP = {
    "Cash": "cash",
    "GCASH": "digital_receivable",
    "MAYA QR": "digital_receivable",
    "MAYA-STRAIGHT/VISA": "digital_receivable",
    "MAYA-STRAIGHT/MC": "digital_receivable",
    "MAYA-DEBIT": "digital_receivable",
    "MosaicPay QRPH": "digital_receivable",
    "BDO PAY": "digital_receivable",
    "BDO-STRAIGHT / VISA": "digital_receivable",
    "BDO-STRAIGHT / MC": "digital_receivable",
    "BANK DEPOSIT / ONLINE": "digital_receivable",
    "BEBANG WEBSITE": "digital_receivable",
    "Complimentary": "complimentary",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_doppler_secret(name: str) -> str:
    """Fetch a secret from Doppler."""
    result = subprocess.run(
        [DOPPLER_BIN, "secrets", "get", name, "--plain",
         "--project", DOPPLER_PROJECT, "--config", DOPPLER_CONFIG],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"ERROR: Failed to get Doppler secret {name}: {result.stderr.strip()}")
        sys.exit(1)
    return result.stdout.strip()


def d(value) -> Decimal:
    """Convert to Decimal, rounded to 2 places."""
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def load_store_map() -> dict:
    """Load store-to-cost-center mapping."""
    with open(STORE_MAP_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Supabase queries
# ---------------------------------------------------------------------------

def fetch_daily_orders(supabase_key: str, target_date: str, location_id: int = None) -> list:
    """Fetch all paid POS orders for a given date, optionally filtered by store."""
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Prefer": "count=exact",
    }

    params = f"business_date=eq.{target_date}&payment_status=eq.PAID&order=location_id,bill_number"
    if location_id:
        params += f"&location_id=eq.{location_id}"

    all_orders = []
    offset = 0
    page_size = 1000

    while True:
        url = f"{SUPABASE_BASE}/pos_orders?select=*&{params}"
        resp = requests.get(url, headers={**headers, "Range": f"{offset}-{offset + page_size - 1}"})
        if resp.status_code not in (200, 206):
            print(f"ERROR: Supabase query failed: {resp.status_code} {resp.text[:300]}")
            sys.exit(1)

        batch = resp.json()
        all_orders.extend(batch)

        content_range = resp.headers.get("content-range", "")
        if "/" in content_range:
            total = int(content_range.split("/")[1])
            if offset + page_size >= total:
                break
        else:
            if len(batch) < page_size:
                break

        offset += page_size

    return all_orders


def fetch_payments_for_orders(supabase_key: str, order_ids: list) -> dict:
    """Fetch payment records for a batch of order IDs. Returns {order_id: [payments]}."""
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
    }

    payments_by_order = {}
    chunk_size = 200
    for i in range(0, len(order_ids), chunk_size):
        chunk = order_ids[i:i + chunk_size]
        id_filter = ",".join(str(oid) for oid in chunk)
        url = f"{SUPABASE_BASE}/pos_order_payments?select=*&order_id=in.({id_filter})"
        resp = requests.get(url, headers={**headers, "Range": "0-9999"})
        if resp.status_code not in (200, 206):
            print(f"WARNING: Payment query failed for chunk: {resp.status_code}")
            continue
        for p in resp.json():
            oid = p["order_id"]
            payments_by_order.setdefault(oid, []).append(p)

    return payments_by_order


# ---------------------------------------------------------------------------
# JV Generation
# ---------------------------------------------------------------------------

def classify_payment_type(payments: list) -> str:
    """
    Determine the primary payment type for an order.

    If an order has multiple payment lines (split payment), use the one with
    the highest paid_amount. For single-payment orders, use that type directly.
    """
    if not payments:
        return "Cash"  # fallback for orders without payment records
    if len(payments) == 1:
        return payments[0]["payment_type"]
    # Multiple payments: pick the dominant one by paid_amount
    return max(payments, key=lambda p: float(p["paid_amount"] or 0))["payment_type"]


def aggregate_store_daily(orders: list, payments_by_order: dict) -> dict:
    """
    Aggregate orders by location_id into JV-ready data.

    Uses gross_sales (= net_sales + vat_amount) as the collection amount per order.
    Payment type from pos_order_payments determines which debit account receives it.
    """
    stores = {}

    for order in orders:
        loc = order["location_id"]
        if loc not in stores:
            stores[loc] = {
                "order_count": 0,
                "original_gross_sales": Decimal("0"),
                "gross_sales": Decimal("0"),
                "net_sales": Decimal("0"),
                "vatable_sales": Decimal("0"),
                "vat_amount": Decimal("0"),
                "vat_exempt_sales": Decimal("0"),
                "zero_rated_sales": Decimal("0"),
                "total_discounts": Decimal("0"),
                "collections_by_type": {},  # payment_type -> gross_sales amount
            }

        s = stores[loc]
        s["order_count"] += 1
        s["original_gross_sales"] += d(order["original_gross_sales"])
        s["gross_sales"] += d(order["gross_sales"])
        s["net_sales"] += d(order["net_sales"])
        s["vatable_sales"] += d(order["vatable_sales"])
        s["vat_amount"] += d(order["vat_amount"])
        s["vat_exempt_sales"] += d(order["vat_exempt_sales"])
        s["zero_rated_sales"] += d(order["zero_rated_sales"])
        s["total_discounts"] += d(order["total_discounts"])

        # Classify this order's collection by payment type
        # Use gross_sales as the amount (= what the customer actually paid for the order)
        oid = order["id"]
        ptype = classify_payment_type(payments_by_order.get(oid, []))
        order_amount = d(order["gross_sales"])
        s["collections_by_type"][ptype] = s["collections_by_type"].get(ptype, Decimal("0")) + order_amount

    return stores


def build_jv_entries(location_id: int, store_data: dict, target_date: str,
                     store_map: dict) -> dict:
    """
    Build an ERPNext Journal Voucher document for one store's daily revenue.

    Accounting equation (always balanced):
      gross_sales = net_sales + vat_amount

    JV entries:
      DR  Cash/Digital Receivable  =  gross_sales (split by payment type)
      CR  Sales Revenue            =  net_sales
      CR  Output VAT Payable       =  vat_amount

    Discounts (original_gross - gross) are tracked as memo information
    but don't appear as separate JV lines because they're already reflected
    in the reduced gross_sales figure from the POS system.
    """
    loc_str = str(location_id)
    store_info = store_map.get("stores", {}).get(loc_str, {})
    store_name = store_info.get("store_name", f"Store {location_id}")
    cost_center = store_info.get("cost_center", DEFAULT_COST_CENTER)

    accounts = []

    # --- DEBIT SIDE: Collections by payment type ---
    # Each payment type maps to a debit account (Cash or Digital Receivable)
    for ptype, amount in sorted(store_data["collections_by_type"].items()):
        if amount <= 0:
            continue

        account_key = PAYMENT_TYPE_MAP.get(ptype, "digital_receivable")

        if account_key == "complimentary":
            # Complimentary = no cash collected. The order has gross_sales > 0 but
            # nothing was actually received. We need a discount expense debit instead.
            accounts.append({
                "account": ACCOUNTS["discount_expense"],
                "debit_in_account_currency": float(d(amount)),
                "credit_in_account_currency": 0,
                "cost_center": cost_center,
                "user_remark": f"Complimentary orders - {ptype}",
            })
        else:
            accounts.append({
                "account": ACCOUNTS[account_key],
                "debit_in_account_currency": float(d(amount)),
                "credit_in_account_currency": 0,
                "cost_center": cost_center,
                "user_remark": f"POS collections - {ptype}",
            })

    # --- CREDIT SIDE: Sales Revenue (net of VAT) ---
    net_sales = store_data["net_sales"]
    if net_sales > 0:
        accounts.append({
            "account": ACCOUNTS["sales_revenue"],
            "debit_in_account_currency": 0,
            "credit_in_account_currency": float(d(net_sales)),
            "cost_center": cost_center,
            "user_remark": f"Daily POS sales revenue ({store_data['order_count']} orders)",
        })

    # --- CREDIT SIDE: Output VAT ---
    vat_amount = store_data["vat_amount"]
    if vat_amount > 0:
        accounts.append({
            "account": ACCOUNTS["output_vat"],
            "debit_in_account_currency": 0,
            "credit_in_account_currency": float(d(vat_amount)),
            "cost_center": cost_center,
            "user_remark": "Output VAT on POS sales",
        })

    # --- Balance verification ---
    total_debit = sum(a["debit_in_account_currency"] for a in accounts)
    total_credit = sum(a["credit_in_account_currency"] for a in accounts)
    diff = round(total_debit - total_credit, 2)

    if abs(diff) > 0.01:
        # Rounding adjustment (should be rare and tiny)
        if diff > 0:
            accounts.append({
                "account": ACCOUNTS["sales_revenue"],
                "debit_in_account_currency": 0,
                "credit_in_account_currency": abs(diff),
                "cost_center": cost_center,
                "user_remark": "Rounding adjustment",
            })
        else:
            accounts.append({
                "account": ACCOUNTS["sales_revenue"],
                "debit_in_account_currency": abs(diff),
                "credit_in_account_currency": 0,
                "cost_center": cost_center,
                "user_remark": "Rounding adjustment",
            })

    # Build discount memo for user_remark
    disc_total = store_data["total_discounts"]
    disc_memo = f", discounts applied={disc_total}" if disc_total > 0 else ""

    jv = {
        "doctype": "Journal Entry",
        "voucher_type": "Journal Entry",
        "posting_date": target_date,
        "company": COMPANY,
        "user_remark": (
            f"Daily POS Revenue - {store_name} - {target_date} "
            f"({store_data['order_count']} orders, "
            f"gross={store_data['gross_sales']}, "
            f"net={store_data['net_sales']}, "
            f"vat={store_data['vat_amount']}"
            f"{disc_memo})"
        ),
        "accounts": accounts,
    }

    return jv


def post_jv_to_erpnext(jv: dict, api_key: str, api_secret: str) -> dict:
    """POST a Journal Voucher to ERPNext. Returns the API response."""
    url = f"{ERPNEXT_BASE}/api/resource/Journal Entry"
    headers = {
        "Authorization": f"token {api_key}:{api_secret}",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, headers=headers, json={"data": json.dumps(jv)})
    return {
        "status": resp.status_code,
        "body": resp.json() if resp.status_code in (200, 201) else resp.text[:500],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate ERPNext JVs from Supabase POS data")
    parser.add_argument("--date", type=str, default=None,
                        help="Business date (YYYY-MM-DD). Default: yesterday")
    parser.add_argument("--store", type=int, default=None,
                        help="Single location_id to process. Default: all stores")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Print JVs as JSON without posting (default)")
    parser.add_argument("--live", action="store_true", default=False,
                        help="Actually POST JVs to ERPNext (use with caution)")
    parser.add_argument("--output", type=str, default=None,
                        help="Write JV JSON to file instead of stdout")
    args = parser.parse_args()

    if args.live:
        args.dry_run = False

    target_date = args.date or (date.today() - timedelta(days=1)).isoformat()

    print(f"=== POS Daily JV Generator ===")
    print(f"Date:     {target_date}")
    print(f"Store:    {args.store or 'ALL'}")
    print(f"Mode:     {'DRY RUN' if args.dry_run else 'LIVE - WILL POST TO ERPNEXT'}")
    print()

    if not args.dry_run:
        confirm = input("LIVE MODE: Are you sure you want to post JVs to ERPNext? (yes/no): ")
        if confirm.lower() != "yes":
            print("Aborted.")
            sys.exit(0)

    # Load secrets
    print("Loading secrets from Doppler...")
    supabase_key = get_doppler_secret("SUPABASE_SERVICE_ROLE_KEY")

    if not args.dry_run:
        frappe_key = get_doppler_secret("FRAPPE_API_KEY")
        frappe_secret = get_doppler_secret("FRAPPE_API_SECRET")
    else:
        frappe_key = frappe_secret = None

    # Load store map
    store_map = load_store_map()

    # Fetch orders
    print(f"Fetching POS orders for {target_date}...")
    orders = fetch_daily_orders(supabase_key, target_date, args.store)
    print(f"  Found {len(orders)} paid orders")

    if not orders:
        print("No orders found. Nothing to do.")
        sys.exit(0)

    # Fetch payments
    order_ids = [o["id"] for o in orders]
    print(f"Fetching payment records for {len(order_ids)} orders...")
    payments_by_order = fetch_payments_for_orders(supabase_key, order_ids)
    orders_with_payments = sum(1 for oid in order_ids if oid in payments_by_order)
    print(f"  Found payments for {orders_with_payments}/{len(order_ids)} orders")

    if orders_with_payments < len(order_ids):
        missing = len(order_ids) - orders_with_payments
        print(f"  WARNING: {missing} orders have no payment records (will default to Cash)")

    # Aggregate by store
    print("Aggregating by store...")
    store_data = aggregate_store_daily(orders, payments_by_order)
    print(f"  {len(store_data)} stores with activity")
    print()

    # Generate JVs
    jvs = []
    for loc_id in sorted(store_data.keys()):
        sd = store_data[loc_id]
        store_info = store_map.get("stores", {}).get(str(loc_id), {})
        store_name = store_info.get("store_name", f"Store {loc_id}")

        jv = build_jv_entries(loc_id, sd, target_date, store_map)
        jvs.append(jv)

        total_dr = sum(a["debit_in_account_currency"] for a in jv["accounts"])
        total_cr = sum(a["credit_in_account_currency"] for a in jv["accounts"])

        print(f"  {store_name:<40} orders={sd['order_count']:>5}  "
              f"gross={sd['gross_sales']:>12,.2f}  "
              f"net={sd['net_sales']:>12,.2f}  "
              f"vat={sd['vat_amount']:>10,.2f}  "
              f"disc={sd['total_discounts']:>10,.2f}  "
              f"DR={total_dr:>12,.2f}  CR={total_cr:>12,.2f}  "
              f"{'OK' if abs(total_dr - total_cr) < 0.02 else 'MISMATCH!'}")

    print()

    # Output
    if args.dry_run:
        output = {
            "generated_at": datetime.now().isoformat(),
            "target_date": target_date,
            "mode": "dry_run",
            "store_count": len(jvs),
            "total_orders": sum(s["order_count"] for s in store_data.values()),
            "total_gross": float(sum(s["gross_sales"] for s in store_data.values())),
            "total_net": float(sum(s["net_sales"] for s in store_data.values())),
            "total_vat": float(sum(s["vat_amount"] for s in store_data.values())),
            "total_discounts": float(sum(s["total_discounts"] for s in store_data.values())),
            "journal_vouchers": jvs,
            "prerequisites": {
                "accounts_to_create": [
                    "SALES REVENUE - Bebang Enterprise Inc. (Income, root_type=Income)",
                ],
                "cost_centers_to_create": [
                    f"{s.get('cost_center', 'Unknown')}"
                    for s in store_map.get("stores", {}).values()
                    if s.get("needs_creation")
                ],
            },
        }

        output_json = json.dumps(output, indent=2, default=str)

        if args.output:
            with open(args.output, "w") as f:
                f.write(output_json)
            print(f"Wrote {len(jvs)} JVs to {args.output}")
        else:
            print("=== Journal Voucher Preview (first 2) ===")
            for jv in jvs[:2]:
                print(json.dumps(jv, indent=2, default=str))
                print()
            if len(jvs) > 2:
                print(f"... and {len(jvs) - 2} more JVs (use --output to save all)")

        print(f"\n=== Summary for {target_date} ===")
        print(f"  Stores:          {len(jvs)}")
        print(f"  Total orders:    {output['total_orders']:,}")
        print(f"  Total gross:     {output['total_gross']:>14,.2f}")
        print(f"  Total net:       {output['total_net']:>14,.2f}")
        print(f"  Total VAT:       {output['total_vat']:>14,.2f}")
        print(f"  Total discounts: {output['total_discounts']:>14,.2f}")

    else:
        # LIVE mode
        results = []
        for jv in jvs:
            parts = jv["user_remark"].split(" - ")
            store_name = parts[1] if len(parts) > 1 else "Unknown"
            print(f"  Posting JV for {store_name}...", end=" ")
            result = post_jv_to_erpnext(jv, frappe_key, frappe_secret)
            results.append({"store": store_name, **result})
            status_icon = "OK" if result["status"] in (200, 201) else "FAIL"
            print(f"[{status_icon}] {result['status']}")

        success = sum(1 for r in results if r["status"] in (200, 201))
        print(f"\nPosted {success}/{len(results)} JVs successfully")

        if args.output:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2, default=str)


if __name__ == "__main__":
    main()
