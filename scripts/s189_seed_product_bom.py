"""S189: Seed product_bom table from Frappe BOM DocType + Tikim recipes.

Reads BOMs via Frappe REST API, maps FG names to POS product_names,
upserts into Supabase product_bom table.

Usage:
    python scripts/s189_seed_product_bom.py
    python scripts/s189_seed_product_bom.py --dry-run
"""
import argparse
import csv
import json
import os
import sys
from pathlib import Path

import requests

# ── Credentials ──────────────────────────────────────────────────────────────

FRAPPE_URL = os.environ.get("FRAPPE_URL", "https://hq.bebang.ph")
FRAPPE_API_KEY = os.environ.get("FRAPPE_API_KEY", "")
FRAPPE_API_SECRET = os.environ.get("FRAPPE_API_SECRET", "")
FRAPPE_AUTH = {"Authorization": f"token {FRAPPE_API_KEY}:{FRAPPE_API_SECRET}"}

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://csnniykjrychgajfrgua.supabase.co")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def sb_headers(prefer="return=minimal"):
    return {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


# ── BOM FG Name -> POS product_name mapping ──────────────────────────────────
# Verified against live SELECT DISTINCT product_name FROM pos_order_items.
# Keys = Frappe BOM item_name (uppercased), Values = POS product_name.

VERIFIED_MAPPINGS = {
    "PRESIDENTIAL": "Presidential",
    "SPECIAL": "Special",
    "MELON": "Melon-ial",
    "MATCHARAP": "Matcharap",
    "HALOKAY UBE": "Halokay Ube",
    "BUKO PANDAN": "Buko Pandan",
    "MANGO GRAHAM CARAMEL": "Mango Graham",
    "BANANA CINNAMON": "Banana Cinnamon",
    "BUKO FRUIT SALAD": "Buko Fruit Salad",
    "STRAWBERRY PISTACHIO": "Berry Good (Strawberry)",
    "BLUEBERRY PISTACHIO": "Berry Good (Blueberry)",
    "COOKIE CRUMBLE": "Cookie Crumble",
    "SO CORNY": "So Corny",
    "MANGO CLASSIC": "Mango Classic",
    "CHOCO BROWNIE": "Brownie Overload",
    "POP LAMIG": "Pop Lamig",
    "ISKRAMBOL": "Iskrambol",
    "GINATAANG HALO-HALO": "Ginataang Halo Halo",
    # Tikim variants
    "TIKIM PRESIDENTIAL": "Presidential (Tikim)",
    "TIKIM MANGO GRAHAM": "Mango Graham (Tikim)",
    "TIKIM CHOCO BROWNIE": "Choco Brownie (Tikim)",
}

# BKI commissary BOMs — these are manufacturing BOMs, NOT POS menu items.
# They produce finished goods (FG001, FG012, etc.) that ARE ingredients in menu BOMs.
# Do NOT map these to POS products; they are tracked at the material level.
BKI_MANUFACTURING_BOMS = {
    "LECHE FLAN", "BANANA CINNAMON", "RICE CRISPIES", "BUKO PANDAN JELLY",
    "VANILLA WHITE JELLY", "COCONUT JELLY", "COCONUT SYRUP", "SAGO",
    "TAPIOCA", "MELTED UBE / SPREAD", "PISTACHIO / CASHEW MIX",
    "BUKO PANDAN FLAVORED SAUCE", "UBE FLAVORED SAUCE",
    "MATCHA FLAVORED SAUCE", "MELON FLAVORED SAUCE",
    "CHOCOLATE FLAVORED SAUCE", "FROZEN ICE MILK",
}


def fetch_frappe_boms():
    """Fetch all active default BOMs with their items from Frappe."""
    print("Fetching active default BOMs from Frappe...")
    r = requests.get(f"{FRAPPE_URL}/api/resource/BOM", params={
        "filters": '[["is_active","=",1],["is_default","=",1]]',
        "fields": '["name","item","item_name","company","quantity"]',
        "limit_page_length": 0,
    }, headers=FRAPPE_AUTH, timeout=30)
    r.raise_for_status()
    boms = r.json()["data"]
    print(f"  Found {len(boms)} active default BOMs")

    for bom in boms:
        items_r = requests.get(f"{FRAPPE_URL}/api/resource/BOM Item", params={
            "filters": f'[["parent","=","{bom["name"]}"]]',
            "fields": '["item_code","item_name","qty","uom","rate"]',
            "limit_page_length": 0,
        }, headers=FRAPPE_AUTH, timeout=30)
        items_r.raise_for_status()
        bom["items"] = items_r.json()["data"]

    return boms


def fetch_tikim_recipes():
    """Fetch Tikim recipes from local CSV fallback."""
    csv_path = Path("data/_tools/store_order_component_recipes.csv")
    if not csv_path.exists():
        print(f"  Tikim CSV not found at {csv_path}, skipping")
        return []

    recipes = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            recipes.append(row)
    print(f"  Found {len(recipes)} Tikim recipe rows from CSV")
    return recipes


def fetch_pos_product_names():
    """Fetch distinct product names from Supabase pos_order_items."""
    print("Fetching distinct POS product names from Supabase...")
    mgmt_token = os.environ.get("SUPABASE_MGMT_TOKEN", "")
    if not mgmt_token:
        print("  WARNING: SUPABASE_MGMT_TOKEN not set, using PostgREST fallback")
        # PostgREST can't do DISTINCT easily, but we can fetch and dedupe
        all_names = set()
        offset = 0
        while True:
            r = requests.get(
                f"{SUPABASE_URL}/rest/v1/pos_order_items",
                params={"select": "product_name", "limit": 1000, "offset": offset},
                headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"},
            )
            if not r.ok or not r.json():
                break
            batch = r.json()
            all_names.update(item["product_name"] for item in batch)
            if len(batch) < 1000:
                break
            offset += 1000
        return sorted(all_names)

    mgmt_url = "https://api.supabase.com/v1/projects/csnniykjrychgajfrgua/database/query"
    r = requests.post(mgmt_url, headers={
        "Authorization": f"Bearer {mgmt_token}",
        "Content-Type": "application/json",
    }, json={"query": "SELECT DISTINCT product_name FROM pos_order_items ORDER BY product_name"})
    r.raise_for_status()
    names = [row["product_name"] for row in r.json()]
    print(f"  Found {len(names)} distinct POS product names")
    return names


def map_bom_to_pos(bom_item_name, company):
    """Map a Frappe BOM item_name to POS product_name."""
    upper = bom_item_name.upper().strip()

    # Skip BKI manufacturing BOMs — they produce FG ingredients, not menu items
    if company == "Bebang Kitchen Inc." and upper in BKI_MANUFACTURING_BOMS:
        return None

    # Check BEI menu BOMs even from BKI (e.g., BOM-FG002-A is BANANA CINNAMON for BEI menu)
    # But BKI FG002 is BANANA CINNAMON for manufacturing — different purpose
    if company == "Bebang Kitchen Inc.":
        return None

    return VERIFIED_MAPPINGS.get(upper)


def build_product_bom_rows(boms, tikim_recipes):
    """Build product_bom rows from Frappe BOMs + Tikim recipes."""
    rows = []
    seen = {}  # (product_name, material_code) -> grams for dedup

    for bom in boms:
        product_name = map_bom_to_pos(bom["item_name"], bom["company"])
        if not product_name:
            continue

        bom_qty = float(bom.get("quantity", 1))
        for item in bom["items"]:
            material_code = item["item_code"]
            material_name = item["item_name"]
            # grams_per_serving = qty in BOM / bom_quantity (normalize to 1 serving)
            grams = float(item["qty"]) / bom_qty

            key = (product_name, material_code)
            if key in seen:
                # COOKIE CRUMBLE_RM002 duplicate: use higher value
                if grams > seen[key]:
                    seen[key] = grams
                    # Update existing row
                    for r in rows:
                        if r["product_name"] == product_name and r["material_code"] == material_code:
                            r["grams_per_serving"] = grams
                            break
                    print(f"  WARNING: Duplicate {key}, using higher value {grams}g")
                continue

            seen[key] = grams
            rows.append({
                "product_name": product_name,
                "material_code": material_code,
                "material_name": material_name,
                "grams_per_serving": grams,
                "bom_source": "frappe_bom",
                "bom_source_name": bom["name"],
                "uom": "g",
                "conversion_factor": 1.0,
                "is_active": True,
            })

    # Add Tikim recipes from CSV
    # CSV format: recipe_key, item_code, item_name, qty_per_unit, note
    # recipe_key is like TIKIM-PRESIDENTIAL, item_code is material code
    # qty_per_unit is a ratio (e.g., 0.007071 for 7g per 990g yield)
    # For consumption tracking, we convert to grams: qty_per_unit * reference_weight
    # But since these are already normalized per-serving, we store as-is (unit = ratio)
    tikim_mapping = {
        "TIKIM-PRESIDENTIAL": "Presidential (Tikim)",
        "TIKIM-MANGO-GRAHAM": "Mango Graham (Tikim)",
        "TIKIM-CHOCO-BROWNIE": "Choco Brownie (Tikim)",
    }
    for recipe in tikim_recipes:
        recipe_key = recipe.get("recipe_key", "")
        product_name = tikim_mapping.get(recipe_key)
        if not product_name:
            continue

        material_code = recipe.get("item_code", "")
        material_name = recipe.get("item_name", "")
        # qty_per_unit is already grams-per-serving for RM/FG items, or 1.0 for packaging
        grams = float(recipe.get("qty_per_unit", 0))

        key = (product_name, material_code)
        if key in seen:
            continue
        seen[key] = grams

        rows.append({
            "product_name": product_name,
            "material_code": material_code,
            "material_name": material_name,
            "grams_per_serving": grams,
            "bom_source": "tikim_csv",
            "bom_source_name": None,
            "uom": "g",
            "conversion_factor": 1.0,
            "is_active": True,
        })

    return rows


def upsert_to_supabase(rows, dry_run=False):
    """Upsert product_bom rows to Supabase."""
    if dry_run:
        print(f"\n[DRY RUN] Would upsert {len(rows)} rows to product_bom")
        return

    print(f"\nUpserting {len(rows)} rows to product_bom...")
    # PostgREST upsert with on_conflict on unique(product_name, material_code)
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/product_bom",
        headers=sb_headers("resolution=merge-duplicates,return=minimal"),
        json=rows,
    )
    if r.ok:
        print(f"  SUCCESS: {len(rows)} rows upserted")
    else:
        print(f"  FAILED: {r.status_code} {r.text}")
        sys.exit(1)


def verify_mapping(rows, pos_names):
    """Verify all product_bom product_names exist in POS data."""
    bom_products = set(r["product_name"] for r in rows)
    pos_set = set(pos_names)

    unmatched = bom_products - pos_set
    if unmatched:
        print(f"\n  WARNING: {len(unmatched)} BOM products NOT found in POS data:")
        for name in sorted(unmatched):
            print(f"    - {name}")
    else:
        print(f"\n  All {len(bom_products)} BOM products found in POS data")

    return unmatched


def main():
    parser = argparse.ArgumentParser(description="Seed product_bom from Frappe BOMs")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to Supabase")
    args = parser.parse_args()

    # Fetch data
    boms = fetch_frappe_boms()
    tikim_recipes = fetch_tikim_recipes()
    pos_names = fetch_pos_product_names()

    # Build rows
    rows = build_product_bom_rows(boms, tikim_recipes)
    print(f"\nTotal product_bom rows: {len(rows)}")
    print(f"  Unique products: {len(set(r['product_name'] for r in rows))}")
    print(f"  Unique materials: {len(set(r['material_code'] for r in rows))}")

    # Verify mapping
    unmatched = verify_mapping(rows, pos_names)

    # Save verified mappings
    mapping_path = Path("tmp/s189_verified_product_mappings.json")
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    mapping_data = {
        "verified_mappings": VERIFIED_MAPPINGS,
        "total_bom_rows": len(rows),
        "unique_products": len(set(r["product_name"] for r in rows)),
        "unique_materials": len(set(r["material_code"] for r in rows)),
        "unmatched_products": sorted(unmatched) if unmatched else [],
        "pos_products_with_bom": sorted(set(r["product_name"] for r in rows)),
    }
    mapping_path.write_text(json.dumps(mapping_data, indent=2, ensure_ascii=False))
    print(f"\nVerified mappings saved to {mapping_path}")

    # Upsert
    upsert_to_supabase(rows, dry_run=args.dry_run)

    # Summary
    rm018_count = sum(1 for r in rows if r["material_code"] == "RM018")
    print(f"\nRM018 (Ube Halaya) appears in {rm018_count} products")


if __name__ == "__main__":
    main()
