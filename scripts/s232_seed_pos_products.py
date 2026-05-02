"""S232 Phase 2.2 — seed pos_products from pos_order_items + apply classification overrides.

Discovers all distinct products from existing pos_order_items, computes a heuristic
is_cup_drink flag (price >= 150 AND name NOT IN packaging_list), then applies overrides
from data/POS_Extraction/POS_PRODUCT_CLASSIFICATION.csv (Phase 2.3 deliverable).

Idempotent: ON CONFLICT DO UPDATE on product_id PK.
"""
from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
CLASSIFICATION_CSV = REPO_ROOT / "data" / "POS_Extraction" / "POS_PRODUCT_CLASSIFICATION.csv"
OUT = REPO_ROOT / "output" / "s232" / "verification"
OUT.mkdir(parents=True, exist_ok=True)

PROJECT_REF = "csnniykjrychgajfrgua"
SQL_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"

# Heuristic packaging_list: never count these as cups regardless of price
packaging_list = (
    "cup 16 oz", "cup 22 oz", "lid", "straw", "spoon",
    "insulated bag", "paper bag", "plastic bag", "bag",
    "bottled water", "water",
)
# Addon list — typically priced 20-30 PHP, never cups
addon_list = (
    "ube halaya", "macapuno", "nata", "mais", "brown sugar ball",
    "rice crispies", "strawberry fruit", "red sago", "mini mallows",
    "langka", "leche flan",
)


def _doppler(name: str) -> str:
    val = os.environ.get(name, "")
    if val:
        return val
    r = subprocess.run(
        ["C:/Users/Sam/bin/doppler.exe", "secrets", "get", name,
         "--plain", "--project", "bei-erp", "--config", "dev"],
        capture_output=True, text=True, timeout=15,
    )
    return r.stdout.strip() if r.returncode == 0 else ""


MGMT_TOKEN = _doppler("SUPABASE_MGMT_TOKEN")


def sql(query: str) -> list[dict]:
    r = httpx.post(
        SQL_URL,
        headers={"Authorization": f"Bearer {MGMT_TOKEN}", "Content-Type": "application/json"},
        json={"query": query},
        timeout=300,
    )
    if r.status_code >= 400:
        print(f"SQL error {r.status_code}: {r.text[:500]}")
        sys.exit(2)
    return r.json()


def main():
    print("S232 PHASE 2.2 — Seeding pos_products")
    print("=" * 70)

    # Step 1: discover products
    print("\n[Step 1] Discovering distinct products from pos_order_items...")
    rows = sql("""
        WITH product_stats AS (
          SELECT product_id, product_name, AVG(unit_price)::numeric(10,2) AS avg_price,
                 COUNT(*)::int AS occurrences,
                 ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY COUNT(*) DESC) AS rn
          FROM pos_order_items
          WHERE product_id IS NOT NULL
            AND COALESCE(is_duplicate, false) = false
          GROUP BY product_id, product_name
        )
        SELECT product_id, product_name, avg_price AS default_price, occurrences
        FROM product_stats
        WHERE rn = 1
        ORDER BY occurrences DESC;
    """)
    print(f"  Discovered: {len(rows)} distinct products")

    # Step 2: heuristic classification
    def heuristic_is_cup(name, price):
        if not name:
            return False
        n = str(name).lower().strip()
        if n in packaging_list or n in addon_list:
            return False
        if price and float(price) >= 150:
            return True
        return False

    seeded = []
    for r in rows:
        name = r["product_name"] or ""
        price = r["default_price"] or 0
        is_cup = heuristic_is_cup(name, price)
        n_lower = name.lower().strip()
        if n_lower in packaging_list:
            category = "packaging"
        elif n_lower in addon_list:
            category = "addon"
        elif n_lower in ("bottled water", "water"):
            category = "other_beverage"
        elif price and float(price) >= 150:
            category = "cup_drink"
        else:
            category = "other"
        seeded.append({
            "product_id": r["product_id"],
            "product_name": name,
            "default_price": float(price) if price else None,
            "is_cup_drink": is_cup,
            "category": category,
            "occurrences": r["occurrences"],
        })

    # Step 3: bulk INSERT into pos_products with ON CONFLICT
    print("\n[Step 2] Inserting/updating pos_products...")
    # Build batch INSERT
    chunk_size = 200
    total_inserted = 0
    for i in range(0, len(seeded), chunk_size):
        chunk = seeded[i:i + chunk_size]
        values_sql = ",".join(
            f"({s['product_id']}, "
            f"{repr(s['product_name'].replace(chr(39), chr(39)*2)) if s['product_name'] else 'NULL'}, "
            f"{s['default_price'] if s['default_price'] is not None else 'NULL'}, "
            f"{'true' if s['is_cup_drink'] else 'false'}, "
            f"'{s['category']}')"
            for s in chunk
        )
        # Use pg-friendly value syntax
        upsert = f"""
        INSERT INTO pos_products (product_id, product_name, default_price, is_cup_drink, category)
        VALUES {values_sql}
        ON CONFLICT (product_id) DO UPDATE SET
          product_name = EXCLUDED.product_name,
          default_price = EXCLUDED.default_price,
          last_seen_at = now();
        """
        sql(upsert)
        total_inserted += len(chunk)
    print(f"  Upserted: {total_inserted} rows")

    # Step 4: apply classification overrides from CSV
    print("\n[Step 3] Applying classification overrides from POS_PRODUCT_CLASSIFICATION.csv...")
    if not CLASSIFICATION_CSV.exists():
        print(f"  WARN: override CSV not found at {CLASSIFICATION_CSV}; skipping")
    else:
        with open(CLASSIFICATION_CSV, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            overrides = list(reader)
        print(f"  Loaded {len(overrides)} override rules")

        applied = 0
        for ov in overrides:
            name = ov["product_name"].strip()
            is_cup = "true" if ov["is_cup_drink"].strip() == "1" else "false"
            # Match by case-insensitive name (Mosaic product_name)
            r = sql(f"""
            UPDATE pos_products SET is_cup_drink = {is_cup}
            WHERE LOWER(product_name) = LOWER('{name.replace("'", "''")}')
            RETURNING product_id;
            """)
            if r:
                applied += len(r)
        print(f"  Override applied to {applied} rows")

    # Step 5: dump verification CSV
    print("\n[Step 4] Writing verification CSV...")
    final = sql("""
        SELECT product_id, product_name, default_price, is_cup_drink, category
        FROM pos_products ORDER BY default_price DESC NULLS LAST, product_name;
    """)
    out_path = OUT / "pos_products_seeded.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["product_id", "product_name", "default_price", "is_cup_drink", "category"])
        w.writeheader()
        for row in final:
            w.writerow(row)
    print(f"  Verification CSV: {out_path}")

    # Step 6: summary
    summary = sql("""
        SELECT
          COUNT(*) FILTER (WHERE is_cup_drink = true)::int AS cup_drinks,
          COUNT(*) FILTER (WHERE is_cup_drink = false)::int AS non_cups,
          COUNT(*)::int AS total
        FROM pos_products;
    """)
    print(f"\nFinal classification:")
    print(f"  Cup drinks: {summary[0]['cup_drinks']}")
    print(f"  Non-cups (addons/packaging/etc.): {summary[0]['non_cups']}")
    print(f"  Total products: {summary[0]['total']}")

    print("\nPHASE 2.2 SEED: COMPLETE")


if __name__ == "__main__":
    main()
