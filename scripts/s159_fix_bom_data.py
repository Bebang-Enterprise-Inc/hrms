#!/usr/bin/env python3
"""
S159: Fix BOM Data -- Company Assignments, Missing Products, Pipeline Fixture.

Subcommands:
  audit              Query all BOMs, produce BOM_TARGET_MANIFEST.csv
  fix-ingredients    Deactivate FG BOMs under BEI, recreate under BKI
  fix-products       Update MN draft BOMs to BEI, validate, submit
  create-missing     Create Items RM216/RM217, new BOMs for Iskrambol/Ginataang/Pop Lamig/Tikims
  regenerate-fixtures  Regenerate bom_master_compact.csv from Frappe BOMs
  cleanup            Delete bad demand snapshots and hallucinated files
  verify             Run all phase gates

Usage:
  python scripts/s159_fix_bom_data.py audit
  python scripts/s159_fix_bom_data.py fix-ingredients --dry-run
  python scripts/s159_fix_bom_data.py verify --phase 2
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
FRAPPE_URL = os.environ.get("FRAPPE_URL", "https://hq.bebang.ph")
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

BEI = "Bebang Enterprise Inc."
BKI = "Bebang Kitchen Inc."

MANIFEST_DIR = ROOT / "tmp" / "bom_investigation"
MANIFEST_PATH = MANIFEST_DIR / "BOM_TARGET_MANIFEST.csv"
FIXTURE_DIR = ROOT / "hrms" / "fixtures" / "store_ordering"
OUTPUT_DIR = ROOT / "output" / "s159"

HEADERS: dict[str, str] = {}  # set in _init_auth()


def _get_secret(env_name: str) -> str:
    value = os.environ.get(env_name, "").strip()
    if value:
        return value
    result = subprocess.run(
        ["C:/Users/Sam/bin/doppler.exe", "secrets", "get", env_name,
         "--plain", "--project", "bei-erp", "--config", "dev"],
        capture_output=True, text=True, timeout=15,
        creationflags=CREATE_NO_WINDOW,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    raise RuntimeError(f"{env_name} not found in env or Doppler")


def _init_auth():
    api_key = _get_secret("FRAPPE_API_KEY")
    api_secret = _get_secret("FRAPPE_API_SECRET")
    HEADERS.update({
        "Authorization": f"token {api_key}:{api_secret}",
        "Content-Type": "application/json",
        "User-Agent": "BEI-Agent/1.0",
    })


def _api_get(endpoint: str, params: dict | None = None, timeout: int = 30) -> dict:
    resp = requests.get(f"{FRAPPE_URL}{endpoint}", headers=HEADERS,
                        params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _api_post(endpoint: str, data: dict, timeout: int = 30) -> dict:
    resp = requests.post(f"{FRAPPE_URL}{endpoint}", headers=HEADERS,
                         json=data, timeout=timeout)
    if resp.status_code not in (200, 201):
        print(f"  POST {endpoint} -> {resp.status_code}: {resp.text[:300]}")
    resp.raise_for_status()
    return resp.json()


def _api_put(endpoint: str, data: dict, timeout: int = 30) -> dict:
    resp = requests.put(f"{FRAPPE_URL}{endpoint}", headers=HEADERS,
                        json=data, timeout=timeout)
    if resp.status_code not in (200, 201):
        print(f"  PUT {endpoint} -> {resp.status_code}: {resp.text[:300]}")
    resp.raise_for_status()
    return resp.json()


def _api_delete(endpoint: str, timeout: int = 30) -> dict:
    resp = requests.delete(f"{FRAPPE_URL}{endpoint}", headers=HEADERS, timeout=timeout)
    if resp.status_code not in (200, 202):
        print(f"  DELETE {endpoint} -> {resp.status_code}: {resp.text[:300]}")
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

def fetch_all_boms() -> list[dict]:
    """Fetch all BOMs with pagination."""
    all_boms = []
    offset = 0
    page_size = 100
    while True:
        data = _api_get("/api/resource/BOM", params={
            "fields": json.dumps(["name", "item", "item_name", "company", "docstatus",
                                   "is_active", "is_default", "quantity", "uom"]),
            "limit_page_length": page_size,
            "limit_start": offset,
            "order_by": "name asc",
        })
        rows = data.get("data", [])
        all_boms.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return all_boms


def fetch_bom_items(bom_name: str) -> list[dict]:
    """Fetch child items for a specific BOM."""
    data = _api_get(f"/api/resource/BOM/{bom_name}", params={
        "fields": json.dumps(["*"]),
    })
    bom_doc = data.get("data", {})
    return bom_doc.get("items", [])


def check_linked_docs(bom_name: str) -> dict:
    """Check if a BOM has linked Stock Entries or Work Orders."""
    linked = {"stock_entries": 0, "work_orders": 0}
    try:
        se = _api_get("/api/resource/Stock Entry", params={
            "filters": json.dumps([["bom_no", "=", bom_name]]),
            "limit_page_length": 1,
            "fields": json.dumps(["count(name) as total"]),
        })
        linked["stock_entries"] = se.get("data", [{}])[0].get("total", 0)
    except Exception:
        pass
    try:
        wo = _api_get("/api/resource/Work Order", params={
            "filters": json.dumps([["bom_no", "=", bom_name]]),
            "limit_page_length": 1,
            "fields": json.dumps(["count(name) as total"]),
        })
        linked["work_orders"] = wo.get("data", [{}])[0].get("total", 0)
    except Exception:
        pass
    return linked


# ---------------------------------------------------------------------------
# Phase 1: Audit
# ---------------------------------------------------------------------------

def cmd_audit(args):
    """Query all BOMs and produce BOM_TARGET_MANIFEST.csv."""
    _init_auth()
    print("Phase 1: Auditing all BOMs in Frappe...")

    boms = fetch_all_boms()
    print(f"  Found {len(boms)} total BOMs")

    # Classify each BOM
    manifest_rows = []
    for b in boms:
        item = b.get("item", "")
        company = b.get("company", "")
        docstatus = b.get("docstatus", 0)
        is_active = b.get("is_active", 0)

        # Determine target company
        if item.startswith("FG"):
            target_company = BKI
        elif item.startswith("MN"):
            target_company = BEI
        else:
            target_company = company  # leave as-is

        # Determine action
        action = "NONE"
        if company != target_company:
            if docstatus == 1:  # submitted
                action = "DEACTIVATE_RECREATE"
            else:
                action = "UPDATE_COMPANY"
        elif docstatus == 0 and is_active:
            action = "SUBMIT"

        # Fetch component count
        try:
            items = fetch_bom_items(b["name"])
            comp_count = len(items)
        except Exception:
            comp_count = -1

        manifest_rows.append({
            "bom_name": b["name"],
            "item_code": item,
            "item_name": b.get("item_name", ""),
            "current_company": company,
            "target_company": target_company,
            "docstatus": docstatus,
            "is_active": is_active,
            "is_default": b.get("is_default", 0),
            "action_needed": action,
            "component_count": comp_count,
        })
        time.sleep(0.1)  # rate limit

    # Write manifest
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "bom_name", "item_code", "item_name", "current_company",
            "target_company", "docstatus", "is_active", "is_default",
            "action_needed", "component_count",
        ])
        writer.writeheader()
        writer.writerows(manifest_rows)

    # Summary
    actions = defaultdict(int)
    for r in manifest_rows:
        actions[r["action_needed"]] += 1

    print(f"\n  Manifest written to: {MANIFEST_PATH}")
    print(f"  Total BOMs: {len(manifest_rows)}")
    print("  Actions needed:")
    for action, count in sorted(actions.items()):
        print(f"    {action}: {count}")

    # Print detail table
    print(f"\n{'BOM':<25} {'Item':<12} {'Company':<25} {'Target':<25} {'Status':>6} {'Action':<20} {'Comps':>5}")
    print("-" * 125)
    for r in manifest_rows:
        status = {0: "Draft", 1: "Submit", 2: "Cancel"}.get(r["docstatus"], "?")
        print(f"{r['bom_name']:<25} {r['item_code']:<12} {r['current_company']:<25} "
              f"{r['target_company']:<25} {status:>6} {r['action_needed']:<20} {r['component_count']:>5}")

    return manifest_rows


# ---------------------------------------------------------------------------
# Phase 2a: Fix FG ingredient BOMs -> BKI
# ---------------------------------------------------------------------------

def cmd_fix_ingredients(args):
    """Deactivate FG BOMs under BEI, recreate under BKI."""
    _init_auth()
    dry_run = args.dry_run
    print(f"Phase 2a: Fix FG ingredient BOMs -> BKI {'[DRY RUN]' if dry_run else ''}")

    # Load manifest
    if not MANIFEST_PATH.exists():
        print("ERROR: Run 'audit' first to generate manifest.")
        sys.exit(1)

    targets = []
    with open(MANIFEST_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["action_needed"] == "DEACTIVATE_RECREATE" and row["item_code"].startswith("FG"):
                targets.append(row)

    print(f"  Found {len(targets)} FG BOMs to fix")

    if not targets:
        print("  Nothing to do.")
        return

    # Pre-check linked docs
    print("\n  Pre-check: Verifying no linked Stock Entries or Work Orders...")
    blocked = []
    for t in targets:
        linked = check_linked_docs(t["bom_name"])
        if linked["stock_entries"] > 0 or linked["work_orders"] > 0:
            blocked.append((t["bom_name"], linked))
            print(f"    BLOCKED: {t['bom_name']} -- SE:{linked['stock_entries']}, WO:{linked['work_orders']}")
        time.sleep(0.1)

    if blocked:
        print(f"\n  NOTE: {len(blocked)} BOMs have linked transactions.")
        print("  Old BOMs will be deactivated. New BOMs created under BKI (safe -- not canceling).")

    # Process each BOM
    success = 0
    errors = []
    for t in targets:
        bom_name = t["bom_name"]
        item_code = t["item_code"]

        print(f"\n  Processing {bom_name} ({item_code})...")

        if dry_run:
            print(f"    [DRY RUN] Would deactivate {bom_name} and recreate under BKI")
            success += 1
            continue

        # Step 1: Fetch full BOM doc
        try:
            bom_data = _api_get(f"/api/resource/BOM/{bom_name}")["data"]
        except Exception as e:
            errors.append((bom_name, f"fetch failed: {e}"))
            continue

        # Step 2: Deactivate old BOM
        try:
            _api_put(f"/api/resource/BOM/{bom_name}", {
                "is_active": 0,
                "is_default": 0,
            })
            print(f"    Deactivated {bom_name}")
        except Exception as e:
            errors.append((bom_name, f"deactivate failed: {e}"))
            continue

        # Step 3: Create new BOM under BKI
        new_items = []
        for item in bom_data.get("items", []):
            new_items.append({
                "item_code": item["item_code"],
                "qty": item["qty"],
                "uom": item.get("uom", ""),
            })

        new_bom_doc = {
            "doctype": "BOM",
            "item": item_code,
            "company": BKI,
            "quantity": bom_data.get("quantity", 1),
            "uom": bom_data.get("uom", "Kg"),
            "is_active": 1,
            "is_default": 1,
            "with_operations": 0,
            "bei_source_file": "s159_fix_bom_data.py",
            "bei_source_sheet": "Phase 2a: FG company fix",
            "bei_source_row": item_code,
            "items": new_items,
        }

        try:
            resp = _api_post("/api/resource/BOM", new_bom_doc)
            new_name = resp.get("data", {}).get("name", "?")
            print(f"    Created {new_name} under BKI")
        except Exception as e:
            errors.append((bom_name, f"create failed: {e}"))
            continue

        # Step 4: Submit new BOM
        try:
            _api_put(f"/api/resource/BOM/{new_name}", {"docstatus": 1})
            print(f"    Submitted {new_name}")
            success += 1
        except Exception as e:
            errors.append((bom_name, f"submit failed: {e}"))

        time.sleep(0.2)

    print(f"\n  Results: {success}/{len(targets)} BOMs fixed")
    if errors:
        print("  Errors:")
        for name, err in errors:
            print(f"    {name}: {err}")


# ---------------------------------------------------------------------------
# Phase 2b: Fix MN product BOMs -> BEI
# ---------------------------------------------------------------------------

def cmd_fix_products(args):
    """Update MN draft BOMs to BEI, submit."""
    _init_auth()
    dry_run = args.dry_run
    print(f"Phase 2b: Fix MN product BOMs -> BEI {'[DRY RUN]' if dry_run else ''}")

    if not MANIFEST_PATH.exists():
        print("ERROR: Run 'audit' first.")
        sys.exit(1)

    targets = []
    with open(MANIFEST_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["item_code"].startswith("MN") and row["action_needed"] in ("UPDATE_COMPANY", "SUBMIT"):
                targets.append(row)

    print(f"  Found {len(targets)} MN BOMs to fix")

    success = 0
    errors = []
    for t in targets:
        bom_name = t["bom_name"]
        item_code = t["item_code"]
        docstatus = int(t["docstatus"])

        print(f"\n  Processing {bom_name} ({item_code})...")

        if dry_run:
            action = "update company + submit" if t["action_needed"] == "UPDATE_COMPANY" else "submit"
            print(f"    [DRY RUN] Would {action}")
            success += 1
            continue

        # Update company if needed (only on drafts)
        if t["action_needed"] == "UPDATE_COMPANY" and docstatus == 0:
            try:
                _api_put(f"/api/resource/BOM/{bom_name}", {
                    "company": BEI,
                    "is_active": 1,
                    "is_default": 1,
                })
                print(f"    Updated company to BEI")
            except Exception as e:
                errors.append((bom_name, f"update company failed: {e}"))
                continue

        # Submit if draft
        if docstatus == 0:
            try:
                _api_put(f"/api/resource/BOM/{bom_name}", {"docstatus": 1})
                print(f"    Submitted {bom_name}")
                success += 1
            except Exception as e:
                errors.append((bom_name, f"submit failed: {e}"))
        else:
            print(f"    Already submitted (docstatus={docstatus})")
            success += 1

        time.sleep(0.2)

    print(f"\n  Results: {success}/{len(targets)} MN BOMs fixed")
    if errors:
        print("  Errors:")
        for name, err in errors:
            print(f"    {name}: {err}")


# ---------------------------------------------------------------------------
# Phase 3: Create missing BOMs
# ---------------------------------------------------------------------------

# Ingredient mappings from sprint plan (Arnold's verified data)
ISKRAMBOL_INGREDIENTS = [
    {"item_code": "FG020", "qty": 0.306, "uom": "Kg"},      # Frozen Milk 306g
    {"item_code": "FG001", "qty": 0.050, "uom": "Kg"},      # Leche Flan 50g
    {"item_code": "FG005", "qty": 0.030, "uom": "Kg"},      # Vanilla Jelly 30g
    {"item_code": "FG018", "qty": 0.025, "uom": "Kg"},      # Melon Sauce 25g
    {"item_code": "RM007", "qty": 0.023, "uom": "Kg"},      # Nata 23g
    {"item_code": "FG019", "qty": 0.015, "uom": "Kg"},      # Chocolate Syrup 15g
    {"item_code": "RM216", "qty": 0.012, "uom": "Gram"},    # Brown Sugar Balls 12g
    {"item_code": "M006", "qty": 0.012, "uom": "Kg"},       # Mini Mallows 12g
    {"item_code": "RM020", "qty": 0.007, "uom": "Kg"},      # Brownies 7g
    {"item_code": "FG003", "qty": 0.002, "uom": "Kg"},      # Rice Crispies 2g
    {"item_code": "PM001", "qty": 1.0, "uom": "Nos"},       # Cup 16 OZ
    {"item_code": "PM002", "qty": 1.0, "uom": "Nos"},       # Dome Lid
    {"item_code": "PM003", "qty": 1.0, "uom": "Nos"},       # Green Spoon
]

GINATAANG_INGREDIENTS = [
    {"item_code": "RM217", "qty": 0.100, "uom": "Gram"},    # Ginataan Sauce 100g
    {"item_code": "RM213", "qty": 0.030, "uom": "Kg"},      # Bilo Bilo 30g
    {"item_code": "FG004", "qty": 0.030, "uom": "Kg"},      # Pandan Jelly 30g
    {"item_code": "RM007", "qty": 0.023, "uom": "Kg"},      # Nata 23g
    {"item_code": "FG009", "qty": 0.020, "uom": "Kg"},      # Sago 20g
    {"item_code": "RM006-C", "qty": 0.017, "uom": "Kg"},    # Corn Kernels 17g
    {"item_code": "FG013", "qty": 0.013, "uom": "Kg"},      # Langka 13g
    {"item_code": "FG016", "qty": 0.010, "uom": "Kg"},      # Ube Sauce 10g
    {"item_code": "PM001", "qty": 1.0, "uom": "Nos"},       # Cup 16 OZ
    {"item_code": "PM002", "qty": 1.0, "uom": "Nos"},       # Dome Lid
    {"item_code": "PM003", "qty": 1.0, "uom": "Nos"},       # Green Spoon
]

# From POP_LAMIG_BOM_CANONICAL_MAPPING.csv (yield-converted)
POP_LAMIG_INGREDIENTS = [
    {"item_code": "PM100", "qty": 0.006024, "uom": "Nos"},  # CO2 Canister (1/166 cups)
    {"item_code": "FG009", "qty": 0.040, "uom": "Kg"},      # Sago 40g
    {"item_code": "RM203", "qty": 0.026, "uom": "Bottle"},  # Syrup 26g
    {"item_code": "FG005", "qty": 0.060, "uom": "Kg"},      # Vanilla Jelly 60g
    {"item_code": "PM001", "qty": 1.0, "uom": "Nos"},       # Cup 16 OZ
    {"item_code": "PM070", "qty": 0.000333, "uom": "Roll"}, # Sealing Film (1/3000 cups)
    {"item_code": "PM102", "qty": 1.0, "uom": "Nos"},       # Paper Straw
]


def _create_item_if_missing(item_code: str, item_name: str, item_group: str,
                             stock_uom: str, dry_run: bool) -> bool:
    """Create an Item in Frappe if it doesn't exist. Returns True if exists/created."""
    try:
        _api_get(f"/api/resource/Item/{item_code}")
        print(f"    Item {item_code} already exists")
        return True
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            pass  # doesn't exist, create it
        else:
            raise

    if dry_run:
        print(f"    [DRY RUN] Would create Item {item_code} ({item_name})")
        return True

    try:
        _api_post("/api/resource/Item", {
            "doctype": "Item",
            "item_code": item_code,
            "item_name": item_name,
            "item_group": item_group,
            "stock_uom": stock_uom,
            "is_stock_item": 1,
            "include_item_in_manufacturing": 1,
        })
        print(f"    Created Item {item_code} ({item_name})")
        return True
    except Exception as e:
        print(f"    ERROR creating Item {item_code}: {e}")
        return False


def _create_bom(item_code: str, ingredients: list[dict], company: str,
                quantity: float, uom: str, dry_run: bool) -> str | None:
    """Create and submit a BOM. Returns new BOM name or None."""

    # Check for existing active BOM
    try:
        existing = _api_get("/api/resource/BOM", params={
            "filters": json.dumps([
                ["item", "=", item_code],
                ["is_active", "=", 1],
                ["is_default", "=", 1],
                ["docstatus", "=", 1],
            ]),
            "fields": json.dumps(["name"]),
            "limit_page_length": 1,
        })
        if existing.get("data"):
            existing_name = existing["data"][0]["name"]
            print(f"    Active BOM already exists: {existing_name}")
            return existing_name
    except Exception:
        pass

    if dry_run:
        print(f"    [DRY RUN] Would create BOM for {item_code} with {len(ingredients)} ingredients under {company}")
        return "DRY_RUN"

    bom_doc = {
        "doctype": "BOM",
        "item": item_code,
        "company": company,
        "quantity": quantity,
        "uom": uom,
        "is_active": 1,
        "is_default": 1,
        "with_operations": 0,
        "bei_source_file": "s159_fix_bom_data.py",
        "bei_source_sheet": "Phase 3: Create missing BOMs",
        "bei_source_row": item_code,
        "items": ingredients,
    }

    try:
        resp = _api_post("/api/resource/BOM", bom_doc)
        new_name = resp.get("data", {}).get("name", "?")
        print(f"    Created BOM {new_name}")
    except Exception as e:
        print(f"    ERROR creating BOM for {item_code}: {e}")
        return None

    # Submit
    try:
        _api_put(f"/api/resource/BOM/{new_name}", {"docstatus": 1})
        print(f"    Submitted {new_name}")
        return new_name
    except Exception as e:
        print(f"    ERROR submitting {new_name}: {e}")
        return new_name  # created but not submitted


def _find_next_mn_code() -> str:
    """Find the next available MN item code."""
    try:
        data = _api_get("/api/resource/Item", params={
            "filters": json.dumps([["name", "like", "MN%"]]),
            "fields": json.dumps(["name"]),
            "limit_page_length": 100,
            "order_by": "name desc",
        })
        existing = [r["name"] for r in data.get("data", [])]
    except Exception:
        existing = []

    # Find max numeric suffix
    max_num = 0
    for code in existing:
        # Handle MN001, MN016, MN-ISKRAMBOL etc
        suffix = code.replace("MN", "").replace("-", "")
        try:
            num = int(suffix)
            max_num = max(max_num, num)
        except ValueError:
            pass
    return f"MN{max_num + 1:03d}"


def cmd_create_missing(args):
    """Create missing Items and BOMs."""
    _init_auth()
    dry_run = args.dry_run
    print(f"Phase 3: Create missing BOMs {'[DRY RUN]' if dry_run else ''}")

    # Step 1: Create new Items
    print("\n  Step 1: Create missing Items...")
    _create_item_if_missing("RM216", "BROWN SUGAR TAPIOCA BALLS", "Raw Material", "Gram", dry_run)
    _create_item_if_missing("RM217", "GINATAAN SAUCE", "Raw Material", "Gram", dry_run)

    # Find item codes for Iskrambol and Ginataang
    # Check if they already exist as MN items
    iskrambol_code = None
    ginataang_code = None

    try:
        data = _api_get("/api/resource/Item", params={
            "filters": json.dumps([["item_name", "like", "%ISKRAMBOL%"]]),
            "fields": json.dumps(["name", "item_name"]),
            "limit_page_length": 5,
        })
        if data.get("data"):
            iskrambol_code = data["data"][0]["name"]
            print(f"  Found existing Iskrambol item: {iskrambol_code}")
    except Exception:
        pass

    try:
        data = _api_get("/api/resource/Item", params={
            "filters": json.dumps([["item_name", "like", "%GINATAANG%"]]),
            "fields": json.dumps(["name", "item_name"]),
            "limit_page_length": 5,
        })
        if data.get("data"):
            ginataang_code = data["data"][0]["name"]
            print(f"  Found existing Ginataang item: {ginataang_code}")
    except Exception:
        pass

    if not iskrambol_code:
        iskrambol_code = "MN-ISKRAMBOL"
        _create_item_if_missing(iskrambol_code, "ISKRAMBOL", "Menu Item", "Cup", dry_run)

    if not ginataang_code:
        ginataang_code = "MN-GINATAANG"
        _create_item_if_missing(ginataang_code, "GINATAANG HALO-HALO", "Menu Item", "Cup", dry_run)

    # Step 2: Create Iskrambol BOM
    print(f"\n  Step 2: Create Iskrambol BOM ({iskrambol_code})...")
    _create_bom(iskrambol_code, ISKRAMBOL_INGREDIENTS, BEI, 1, "Cup", dry_run)

    # Step 3: Create Ginataang Halo-Halo BOM
    print(f"\n  Step 3: Create Ginataang Halo-Halo BOM ({ginataang_code})...")
    _create_bom(ginataang_code, GINATAANG_INGREDIENTS, BEI, 1, "Cup", dry_run)

    # Step 4: Recreate Pop Lamig BOM (MN016)
    print("\n  Step 4: Recreate Pop Lamig BOM (MN016)...")
    _create_bom("MN016", POP_LAMIG_INGREDIENTS, BEI, 1, "Cup", dry_run)

    # Step 5: Create Tikim BOMs
    print("\n  Step 5: Create Tikim BOMs...")
    tikim_recipes = _load_tikim_recipes()
    for recipe_key, ingredients in tikim_recipes.items():
        # Determine item code
        product_name = recipe_key.replace("TIKIM-", "TIKIM ")
        tikim_code = f"MN-{recipe_key}"

        # Check if item exists
        try:
            _api_get(f"/api/resource/Item/{tikim_code}")
            print(f"    Item {tikim_code} exists")
        except requests.exceptions.HTTPError:
            _create_item_if_missing(tikim_code, product_name, "Menu Item", "Cup", dry_run)

        _create_bom(tikim_code, ingredients, BEI, 1, "Cup", dry_run)


def _load_tikim_recipes() -> dict[str, list[dict]]:
    """Load tikim recipes from store_order_component_recipes.csv."""
    recipes: dict[str, list[dict]] = defaultdict(list)
    csv_path = FIXTURE_DIR / "store_order_component_recipes.csv"
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = row.get("recipe_key", "").strip()
            if not key.startswith("TIKIM-"):
                continue
            recipes[key].append({
                "item_code": row["item_code"].strip(),
                "qty": float(row["qty_per_unit"]),
                "uom": "Nos" if float(row["qty_per_unit"]) >= 1.0 else "Kg",
            })
    return dict(recipes)


# ---------------------------------------------------------------------------
# Phase 4: Regenerate CSV fixtures
# ---------------------------------------------------------------------------

def cmd_regenerate_fixtures(args):
    """Regenerate bom_master_compact.csv and friends from Frappe BOM data."""
    _init_auth()
    dry_run = args.dry_run
    print(f"Phase 4: Regenerate CSV fixtures {'[DRY RUN]' if dry_run else ''}")

    # Fetch all active submitted BOMs
    boms = fetch_all_boms()
    active_boms = [b for b in boms if b.get("is_active") and b.get("docstatus") == 1]
    print(f"  Found {len(active_boms)} active submitted BOMs")

    # Build bom_master_compact rows
    compact_rows = []
    crosswalk_entries = {}  # fg_name -> fg_name_norm

    for b in active_boms:
        item_code = b.get("item", "")
        item_name = b.get("item_name", "").strip()

        # Only include product BOMs (MN-series) for the demand pipeline
        # FG-series are ingredient BOMs (commissary recipes) -- not needed in compact fixture
        if not item_code.startswith("MN"):
            continue

        # Fetch child items
        try:
            items = fetch_bom_items(b["name"])
        except Exception as e:
            print(f"    WARNING: Could not fetch items for {b['name']}: {e}")
            continue

        # Normalize product name for fixture
        fg_name = item_name.upper()
        fg_name_norm = fg_name.replace("-", " ").replace("  ", " ").strip()

        crosswalk_entries[fg_name] = fg_name_norm

        for item in items:
            compact_rows.append({
                "fg_name": fg_name,
                "fg_name_norm": fg_name_norm,
                "component_item_code": item.get("item_code", ""),
                "component_item_name_bom": item.get("item_name", ""),
                "qty_per_fg": item.get("qty", 0),
            })

        time.sleep(0.1)

    print(f"  Built {len(compact_rows)} rows for {len(crosswalk_entries)} products")

    if dry_run:
        print(f"  [DRY RUN] Would write {len(compact_rows)} rows to bom_master_compact.csv")
        return

    # Write bom_master_compact.csv
    compact_path = FIXTURE_DIR / "bom_master_compact.csv"
    with open(compact_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "fg_name", "fg_name_norm", "component_item_code",
            "component_item_name_bom", "qty_per_fg",
        ])
        writer.writeheader()
        writer.writerows(compact_rows)
    print(f"  Wrote {len(compact_rows)} rows to {compact_path}")

    # Update crosswalk -- read existing, add missing
    crosswalk_path = FIXTURE_DIR / "bom_fg_to_pos_crosswalk_compact.csv"
    existing_crosswalk = {}
    if crosswalk_path.exists():
        with open(crosswalk_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                existing_crosswalk[row["fg_name"]] = row

    # Add new product POS name mappings
    pos_name_map = {
        "ISKRAMBOL": "Iskrambol",
        "GINATAANG HALO-HALO": "Ginataang Halo Halo",
        "GINATAANG HALO HALO": "Ginataang Halo Halo",
        "POP LAMIG": "Pop Lamig",
        "TIKIM PRESIDENTIAL": "Tikim Presidential",
        "TIKIM MANGO GRAHAM": "Tikim Mango Graham",
        "TIKIM CHOCO BROWNIE": "Tikim Choco Brownie",
    }

    for fg_name, fg_norm in crosswalk_entries.items():
        if fg_name not in existing_crosswalk:
            pos_name = pos_name_map.get(fg_name, fg_name.title())
            existing_crosswalk[fg_name] = {
                "fg_name": fg_name,
                "fg_name_norm": fg_norm,
                "pos_item_name_top1": pos_name,
            }

    with open(crosswalk_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["fg_name", "fg_name_norm", "pos_item_name_top1"])
        writer.writeheader()
        for key in sorted(existing_crosswalk.keys()):
            writer.writerow(existing_crosswalk[key])
    print(f"  Updated crosswalk: {len(existing_crosswalk)} entries -> {crosswalk_path}")

    # Update component recipes -- add FULL-ISKRAMBOL and FULL-GINATAANG
    recipes_path = FIXTURE_DIR / "store_order_component_recipes.csv"
    existing_recipes = []
    existing_keys = set()
    if recipes_path.exists():
        with open(recipes_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                existing_recipes.append(row)
                existing_keys.add(row["recipe_key"])

    # Add Iskrambol recipe
    if "FULL-ISKRAMBOL" not in existing_keys:
        for ing in ISKRAMBOL_INGREDIENTS:
            existing_recipes.append({
                "recipe_key": "FULL-ISKRAMBOL",
                "item_code": ing["item_code"],
                "item_name": "",  # will be filled from Frappe on next load
                "qty_per_unit": ing["qty"],
                "note": "S159: Iskrambol BOM from Arnold's Store BOM 2026.",
            })

    if "FULL-GINATAANG" not in existing_keys:
        for ing in GINATAANG_INGREDIENTS:
            existing_recipes.append({
                "recipe_key": "FULL-GINATAANG",
                "item_code": ing["item_code"],
                "item_name": "",
                "qty_per_unit": ing["qty"],
                "note": "S159: Ginataang Halo-Halo BOM from Arnold's Store BOM 2026.",
            })

    with open(recipes_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["recipe_key", "item_code", "item_name", "qty_per_unit", "note"])
        writer.writeheader()
        writer.writerows(existing_recipes)
    print(f"  Updated component recipes: {len(existing_recipes)} entries -> {recipes_path}")


# ---------------------------------------------------------------------------
# Phase 5: Cleanup
# ---------------------------------------------------------------------------

def cmd_cleanup(args):
    """Delete bad demand snapshots and hallucinated files."""
    _init_auth()
    dry_run = args.dry_run
    print(f"Phase 5: Cleanup {'[DRY RUN]' if dry_run else ''}")

    # Delete bad demand snapshots
    print("\n  Checking for bad demand snapshots...")
    try:
        data = _api_get("/api/resource/BEI Inventory Risk Snapshot", params={
            "fields": json.dumps(["name", "creation"]),
            "limit_page_length": 100,
            "order_by": "creation asc",
        })
        snapshots = data.get("data", [])
        print(f"  Found {len(snapshots)} demand snapshots")

        if len(snapshots) > 0:
            if dry_run:
                print(f"  [DRY RUN] Would delete {len(snapshots)} bad snapshots")
            else:
                deleted = 0
                for s in snapshots:
                    try:
                        _api_delete(f"/api/resource/BEI Inventory Risk Snapshot/{s['name']}")
                        deleted += 1
                    except Exception as e:
                        print(f"    Error deleting {s['name']}: {e}")
                    time.sleep(0.1)
                print(f"  Deleted {deleted}/{len(snapshots)} snapshots")
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            print("  DocType 'BEI Inventory Risk Snapshot' not found -- skipping")
        else:
            print(f"  Error querying snapshots: {e}")

    # Delete hallucinated files
    hallucinated_files = [
        ROOT / "data" / "_CLEANROOM" / "bom" / "store_consumption_bom.csv",
        ROOT / "data" / "_CLEANROOM" / "central_warehouse_2026_03" / "delivery_schedule.csv",
    ]

    print("\n  Deleting hallucinated files...")
    for fp in hallucinated_files:
        if fp.exists():
            if dry_run:
                print(f"  [DRY RUN] Would delete {fp}")
            else:
                fp.unlink()
                print(f"  Deleted {fp}")
        else:
            print(f"  Already gone: {fp}")


# ---------------------------------------------------------------------------
# Phase 6: Verification
# ---------------------------------------------------------------------------

def cmd_verify(args):
    """Run verification gates."""
    _init_auth()
    phase = args.phase
    print(f"Phase 6: Verification {'(phase ' + str(phase) + ')' if phase else '(all)'}")

    results = {"timestamp": datetime.now().isoformat(), "checks": [], "passed": 0, "failed": 0}

    def check(name: str, condition: bool, detail: str = ""):
        status = "PASS" if condition else "FAIL"
        results["checks"].append({"name": name, "status": status, "detail": detail})
        if condition:
            results["passed"] += 1
        else:
            results["failed"] += 1
        icon = "OK" if condition else "FAIL"
        print(f"  [{icon}] {name}" + (f" -- {detail}" if detail else ""))

    # Phase 2 checks
    if not phase or phase == 2:
        print("\n  --- Phase 2 Gate ---")

        # FG BOMs under BKI
        try:
            data = _api_get("/api/resource/BOM", params={
                "filters": json.dumps([
                    ["item", "like", "FG%"],
                    ["company", "=", BKI],
                    ["docstatus", "=", 1],
                    ["is_active", "=", 1],
                ]),
                "limit_page_length": 0,
            })
            fg_bki_count = len(data.get("data", []))
            check("FG BOMs under BKI (>=18)", fg_bki_count >= 18, f"count={fg_bki_count}")
        except Exception as e:
            check("FG BOMs under BKI (>=18)", False, str(e))

        # MN BOMs under BEI
        try:
            data = _api_get("/api/resource/BOM", params={
                "filters": json.dumps([
                    ["item", "like", "MN%"],
                    ["company", "=", BEI],
                    ["docstatus", "=", 1],
                    ["is_active", "=", 1],
                ]),
                "limit_page_length": 0,
            })
            mn_bei_count = len(data.get("data", []))
            check("MN BOMs under BEI (>=12)", mn_bei_count >= 12, f"count={mn_bei_count}")
        except Exception as e:
            check("MN BOMs under BEI (>=12)", False, str(e))

        # No FG under BEI (active)
        try:
            data = _api_get("/api/resource/BOM", params={
                "filters": json.dumps([
                    ["item", "like", "FG%"],
                    ["company", "=", BEI],
                    ["is_active", "=", 1],
                ]),
                "limit_page_length": 0,
            })
            fg_bei_count = len(data.get("data", []))
            check("No active FG BOMs under BEI (=0)", fg_bei_count == 0, f"count={fg_bei_count}")
        except Exception as e:
            check("No active FG BOMs under BEI (=0)", False, str(e))

    # Phase 3 checks
    if not phase or phase == 3:
        print("\n  --- Phase 3 Gate ---")

        # RM216 exists
        try:
            _api_get("/api/resource/Item/RM216")
            check("Item RM216 exists", True)
        except Exception:
            check("Item RM216 exists", False)

        # RM217 exists
        try:
            _api_get("/api/resource/Item/RM217")
            check("Item RM217 exists", True)
        except Exception:
            check("Item RM217 exists", False)

        # Iskrambol BOM
        try:
            data = _api_get("/api/method/hrms.api.commissary_bom.get_bom_detail",
                            params={"item_code": "MN-ISKRAMBOL"})
            bom_data = data.get("message", {}).get("data", {})
            comp_count = bom_data.get("materials_count", 0)
            check("Iskrambol BOM (>=13 components)", comp_count >= 13, f"count={comp_count}")
        except Exception as e:
            check("Iskrambol BOM (>=13 components)", False, str(e))

        # Pop Lamig BOM
        try:
            data = _api_get("/api/method/hrms.api.commissary_bom.get_bom_detail",
                            params={"item_code": "MN016"})
            bom_data = data.get("message", {}).get("data", {})
            comp_count = bom_data.get("materials_count", 0)
            check("Pop Lamig BOM (>=7 components)", comp_count >= 7, f"count={comp_count}")
        except Exception as e:
            check("Pop Lamig BOM (>=7 components)", False, str(e))

    # Phase 4 checks
    if not phase or phase == 4:
        print("\n  --- Phase 4 Gate ---")
        compact_path = FIXTURE_DIR / "bom_master_compact.csv"
        if compact_path.exists():
            content = compact_path.read_text(encoding="utf-8")
            check("bom_master_compact.csv exists", True)
            check("Contains ISKRAMBOL", "ISKRAMBOL" in content)
            check("Contains GINATAANG", "GINATAANG" in content)
        else:
            check("bom_master_compact.csv exists", False)

        crosswalk_path = FIXTURE_DIR / "bom_fg_to_pos_crosswalk_compact.csv"
        if crosswalk_path.exists():
            content = crosswalk_path.read_text(encoding="utf-8")
            check("Crosswalk contains Iskrambol", "Iskrambol" in content)
        else:
            check("Crosswalk exists", False)

    # Phase 5 checks
    if not phase or phase == 5:
        print("\n  --- Phase 5 Gate ---")

        hallucinated1 = ROOT / "data" / "_CLEANROOM" / "bom" / "store_consumption_bom.csv"
        check("Hallucinated BOM CSV deleted", not hallucinated1.exists())

        hallucinated2 = ROOT / "data" / "_CLEANROOM" / "central_warehouse_2026_03" / "delivery_schedule.csv"
        check("Hallucinated delivery schedule deleted", not hallucinated2.exists())

    # Write results
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_DIR / "RUN_STATUS.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Summary
    total = results["passed"] + results["failed"]
    print(f"\n  TOTAL: {results['passed']}/{total} checks passed")
    if results["failed"] > 0:
        print(f"  WARNING: {results['failed']} checks FAILED")

    # Write summary markdown
    with open(OUTPUT_DIR / "RUN_SUMMARY.md", "w", encoding="utf-8") as f:
        f.write(f"# S159 Run Summary\n\n")
        f.write(f"**Date:** {results['timestamp']}\n\n")
        f.write(f"**Result:** {results['passed']}/{total} checks passed\n\n")
        f.write("| Check | Status | Detail |\n|-------|--------|--------|\n")
        for c in results["checks"]:
            f.write(f"| {c['name']} | {c['status']} | {c.get('detail', '')} |\n")

    print(f"  Results written to {OUTPUT_DIR / 'RUN_STATUS.json'}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="S159: Fix BOM Data")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("audit", help="Phase 1: Audit all BOMs and produce manifest")

    p_fi = sub.add_parser("fix-ingredients", help="Phase 2a: Fix FG BOMs -> BKI")
    p_fi.add_argument("--dry-run", action="store_true")

    p_fp = sub.add_parser("fix-products", help="Phase 2b: Fix MN BOMs -> BEI")
    p_fp.add_argument("--dry-run", action="store_true")

    p_cm = sub.add_parser("create-missing", help="Phase 3: Create missing BOMs")
    p_cm.add_argument("--dry-run", action="store_true")

    p_rf = sub.add_parser("regenerate-fixtures", help="Phase 4: Regenerate CSV fixtures")
    p_rf.add_argument("--dry-run", action="store_true")

    p_cl = sub.add_parser("cleanup", help="Phase 5: Cleanup bad data")
    p_cl.add_argument("--dry-run", action="store_true")

    p_v = sub.add_parser("verify", help="Phase 6: Run verification gates")
    p_v.add_argument("--phase", type=int, help="Verify specific phase only")

    args = parser.parse_args()

    commands = {
        "audit": cmd_audit,
        "fix-ingredients": cmd_fix_ingredients,
        "fix-products": cmd_fix_products,
        "create-missing": cmd_create_missing,
        "regenerate-fixtures": cmd_regenerate_fixtures,
        "cleanup": cmd_cleanup,
        "verify": cmd_verify,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
