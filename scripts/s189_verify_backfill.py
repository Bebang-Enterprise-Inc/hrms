"""S189: Verify backfill accuracy by comparing direct BOM computation vs stored data.

Two modes:
  --generate-expected: Compute expected consumption from source data, save to JSON.
  --compare: Compare stored daily_material_consumption against expected.

Usage:
    python scripts/s189_verify_backfill.py --generate-expected --from 2026-03-14 --to 2026-04-13
    python scripts/s189_verify_backfill.py --compare --dates 2026-04-07,2026-04-08,2026-04-11,2026-04-12
"""
import argparse
import json
import os
import sys
from pathlib import Path

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://csnniykjrychgajfrgua.supabase.co")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
MGMT_TOKEN = os.environ.get("SUPABASE_MGMT_TOKEN", "")
MGMT_URL = "https://api.supabase.com/v1/projects/csnniykjrychgajfrgua/database/query"

OUTPUT_PATH = Path("tmp/s189_expected_consumption.json")


def mgmt_headers():
    return {"Authorization": f"Bearer {MGMT_TOKEN}", "Content-Type": "application/json"}


def run_sql(sql):
    r = requests.post(MGMT_URL, headers=mgmt_headers(), json={"query": sql}, timeout=120)
    r.raise_for_status()
    return r.json()


def generate_expected(date_from, date_to):
    """Compute expected consumption directly from pos_order_items x product_bom."""
    print(f"Generating expected consumption from {date_from} to {date_to}...")

    # Direct SQL join: order_items x product_bom, grouped by date + material
    sql = f"""
    SELECT
        o.business_date,
        pb.material_code,
        pb.material_name,
        'POS' AS channel,
        SUM(COALESCE(i.quantity, 1)) AS total_cups,
        SUM(COALESCE(i.quantity, 1) * pb.grams_per_serving) AS total_grams
    FROM pos_order_items i
    JOIN pos_orders o ON o.id = i.order_id
    JOIN product_bom pb ON pb.product_name = i.product_name AND pb.is_active = TRUE
    WHERE o.business_date >= '{date_from}' AND o.business_date <= '{date_to}'
    GROUP BY o.business_date, pb.material_code, pb.material_name
    UNION ALL
    SELECT
        o.business_date,
        pb.material_code,
        pb.material_name,
        'Web' AS channel,
        SUM(COALESCE(i.quantity, 1)) AS total_cups,
        SUM(COALESCE(i.quantity, 1) * pb.grams_per_serving) AS total_grams
    FROM web_order_items i
    JOIN web_orders o ON o.id = i.order_id
    JOIN product_bom pb ON pb.product_name = i.product_name AND pb.is_active = TRUE
    WHERE o.business_date >= '{date_from}' AND o.business_date <= '{date_to}'
    GROUP BY o.business_date, pb.material_code, pb.material_name
    ORDER BY business_date, material_code
    """

    rows = run_sql(sql)
    print(f"  Got {len(rows)} expected consumption rows")

    # Aggregate by (date, material_code) across channels
    expected = {}
    for row in rows:
        key = f"{row['business_date']}|{row['material_code']}"
        if key not in expected:
            expected[key] = {
                "business_date": row["business_date"],
                "material_code": row["material_code"],
                "material_name": row["material_name"],
                "total_cups": 0,
                "total_grams": 0.0,
            }
        expected[key]["total_cups"] += int(row["total_cups"])
        expected[key]["total_grams"] += float(row["total_grams"])

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(expected, indent=2, default=str))
    print(f"  Saved to {OUTPUT_PATH}")
    return expected


def compare(dates_str):
    """Compare stored daily_material_consumption against expected for spot-check dates."""
    dates = [d.strip() for d in dates_str.split(",")]
    print(f"Comparing for dates: {dates}")

    if not OUTPUT_PATH.exists():
        print(f"ERROR: Expected data not found at {OUTPUT_PATH}. Run --generate-expected first.")
        sys.exit(1)

    expected = json.loads(OUTPUT_PATH.read_text())

    all_pass = True
    for date in dates:
        print(f"\n--- {date} ---")

        # Get stored consumption for this date
        sql = f"""
        SELECT material_code, SUM(total_cups) AS total_cups, SUM(total_grams) AS total_grams
        FROM daily_material_consumption
        WHERE business_date = '{date}'
        GROUP BY material_code
        ORDER BY material_code
        """
        stored_rows = run_sql(sql)
        stored = {r["material_code"]: r for r in stored_rows}

        # Get expected for this date
        date_expected = {
            v["material_code"]: v
            for k, v in expected.items()
            if v["business_date"] == date
        }

        if not date_expected:
            print(f"  WARNING: No expected data for {date}")
            continue

        mismatches = 0
        for mat_code, exp in date_expected.items():
            actual = stored.get(mat_code)
            if not actual:
                print(f"  MISSING: {mat_code} (expected {exp['total_grams']:.2f}g)")
                mismatches += 1
                continue

            exp_grams = float(exp["total_grams"])
            act_grams = float(actual["total_grams"])
            if exp_grams == 0:
                continue
            pct_diff = abs(act_grams - exp_grams) / exp_grams * 100

            if pct_diff > 5:
                print(f"  FAIL: {mat_code} expected={exp_grams:.2f}g actual={act_grams:.2f}g diff={pct_diff:.1f}%")
                mismatches += 1
            elif pct_diff > 2:
                print(f"  WARN: {mat_code} diff={pct_diff:.1f}%")

        if mismatches == 0:
            print(f"  PASS: {len(date_expected)} materials within tolerance")
        else:
            print(f"  FAIL: {mismatches} materials out of tolerance")
            all_pass = False

    if all_pass:
        print("\nALL DATES PASS")
    else:
        print("\nSOME DATES FAILED — investigate before proceeding")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Verify backfill accuracy")
    parser.add_argument("--generate-expected", action="store_true")
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--from", dest="date_from")
    parser.add_argument("--to", dest="date_to")
    parser.add_argument("--dates", help="Comma-separated dates for spot-check")
    args = parser.parse_args()

    if args.generate_expected:
        if not args.date_from or not args.date_to:
            print("ERROR: --from and --to required with --generate-expected")
            sys.exit(1)
        generate_expected(args.date_from, args.date_to)
    elif args.compare:
        if not args.dates:
            print("ERROR: --dates required with --compare")
            sys.exit(1)
        compare(args.dates)
    else:
        print("Specify --generate-expected or --compare")
        sys.exit(1)


if __name__ == "__main__":
    main()
