"""Regenerate warehouse_record_name / warehouse_docname in two fixtures.

Phase 1: Apply an EXPLICIT rename map (for warehouses actually renamed by
         S196 Item #3 / Phase 2 Step B).
Phase 2: For stale `- Bebang Enterprise Inc.` / `- BEI` / `- BKI` suffixes that
         DON'T match production docnames, use the live warehouse_snapshot.csv
         to find the correct current docname for that short store name,
         excluding stale companies (e.g. JV).

Input:
  - hrms/fixtures/sales_dashboard_store_mapping.csv
  - hrms/fixtures/store_inventory_shadow_sync/store_inventory_shadow_sync_registry.csv
  - output/s196/state/warehouse_snapshot.csv  (SSOT from live DB)
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_A = ROOT / "hrms" / "fixtures" / "sales_dashboard_store_mapping.csv"
FIXTURE_B = ROOT / "hrms" / "fixtures" / "store_inventory_shadow_sync" / "store_inventory_shadow_sync_registry.csv"
SNAPSHOT = ROOT / "output" / "s196" / "state" / "warehouse_snapshot.csv"

# --- Phase 1 explicit rename map (from SSM action log) -----------------
RENAMES = {
    # Phase 2 Step B (pre-Item #3, already in production):
    "BB ESTANCIA FOOD CORP. - Ortigas Estancia - BBEFC": "Ortigas Estancia - BB ESTANCIA FOOD CORP.",
    "BEBANG PASEO INC. - Paseo Center - BPI": "Paseo Center - BEBANG PASEO INC.",
    "Vista Mall Taguig - BEI": "Vista Mall Taguig - Tricern Food Corp.",
    "SM Taytay - BEI": "SM Taytay - Day Ones Food and Drink Establishments Corp.",
    "SM Taytay - BKI": "SM Taytay - Day Ones Food and Drink Establishments Corp.",
    "SM Clark - BEI": "SM Clark - Red Taldawa Foods OPC",
    # Item #3 sweep (35 renames):
    "Araneta Gateway - BEI": "Araneta Gateway - Tungsten Capital",
    "Ayala Evo - BEI": "Ayala Evo - BEBANG MEGA INC.",
    "Ayala Malls Fairview Terraces - BEI": "Ayala Malls Fairview Terraces - BEBANG FT INC.",
    "Ayala Market Market - BEI": "Ayala Market Market - BEBANG MARKET MARKET INC.",
    "Ayala Solenad - BEI": "Ayala Solenad - HFFM SOLENAD FOOD SERVICES INC.",
    "Ayala UPTC - BEI": "Ayala UPTC - BEBANG UP TOWN CENTER INC.",
    "Ayala Vermosa - BEI": "Ayala Vermosa - BEBANG MEGA INC.",
    "BF Homes - BEI": "BF Homes - BEBANG BF HOMES INC.",
    "CTTM Tomas Morato - BEI": "CTTM Tomas Morato - B CUBED VENTURES CORP.",
    "D'verde Laguna - BEI": "D'verde Laguna - TAJ Food Corp.",
    "Ever Commonwealth - BEI": "Ever Commonwealth - DLS Dessert Craft Inc.",
    "Festival Mall Alabang - BEI": "Festival Mall Alabang - BEBANG FESTIVAL INC.",
    "Greenhills Ortigas - BEI": "Greenhills Ortigas - BEIFRANCHISE FOOD OPC",
    "Lucky Chinatown - BEI": "Lucky Chinatown - BEBANG LCT INC.",
    "Megawide PITX - BEI": "Megawide PITX - BEBANG PITX INC.",
    "Megaworld Venice Grand Canal - BEI": "Megaworld Venice Grand Canal - BEBANG VENICE GRAND CANAL INC.",
    "NAIA T3 - BEI": "NAIA T3 - HALO-HALO TERMINAL FOOD CORP.",
    "Robisons Galleria South - BEI": "Robisons Galleria South - Tungsten Capital",
    "SJDM - BEI": "SJDM - JL TRADE OPC",
    "SM Bicutan - BEI": "SM Bicutan - BEBANG SM BICUTAN INC.",
    "SM Caloocan - BEI": "SM Caloocan - TAJ Food Corp.",
    "SM East Ortigas - BEI": "SM East Ortigas - BEBANG SMEO INC.",
    "SM Grand Central - BEI": "SM Grand Central - BEBANG GRAND CENTRAL INC.",
    "SM Mall Of Asia - BEI": "SM Mall Of Asia - BEBANG SMOA INC.",
    "SM Marikina - BEI": "SM Marikina - BEBANG SM MARIKINA INC.",
    "SM Marilao - BEI": "SM Marilao - BEBANG MARILAO INC.",
    "SM North EDSA - BEI": "SM North EDSA - BEBANG NORTH EDSA INC.",
    "SM Pulilan - BEI": "SM Pulilan - BEBANG SMM INC.",
    "SM Sangandaan - BEI": "SM Sangandaan - Tungsten Capital",
    "SM Sta. Rosa - BEI": "SM Sta. Rosa - SWEET HARMONY FOOD CORP.",
    "SM Sta. Rosa - BKI": "SM Sta. Rosa - SWEET HARMONY FOOD CORP.",
    "SM Tanza - BEI": "SM Tanza - BEBANG MEGA INC.",
    "SM Valenzuela - BEI": "SM Valenzuela - BEBANG SMV INC.",
    "The Grid - Rockwell - BEI": "The Grid - Rockwell - TASTECARTEL CORP.",
    "The Terminal - BEI": "The Terminal - BEBANG STARMALL ALABANG INC.",
    "Up Town Mall BGC - BEI": "Up Town Mall BGC - DMD HOLDINGS INC.",
    # Semantic name mismatches (fixture short_name != live short_name):
    "Megaworld Paseo Center - Bebang Enterprise Inc.": "Paseo Center - BEBANG PASEO INC.",
    "Robinson General Trias - Bebang Enterprise Inc.": "Bebang Mega Inc. - Robinsons Gen Trias - BMI-RGT",
    "Robinson Imus - Bebang Enterprise Inc.": "Bebang Mega Inc. - Robinsons Imus - BMI-RI",
    "Sta. Lucia East Grand Mall - Bebang Enterprise Inc.": "Bebang SM Marikina Inc. - Sta Lucia - BSMM-SL",
}

# Companies to exclude when resolving via snapshot (stale/ghost/holding):
EXCLUDED_COMPANIES = {"JV"}

# Structural warehouse prefixes (not store-facing):
INTERNAL_PREFIXES = (
    "Stores", "Finished Goods", "Goods In Transit",
    "Work In Progress", "All Warehouses", "Raw Materials",
    "In Transit",
)

# Stale fixture suffixes that trigger Phase 2 snapshot lookup:
STALE_SUFFIXES = (
    " - Bebang Enterprise Inc.",
    " - BEI",
    " - BKI",
)


def load_snapshot_index():
    """Build three maps for lookup:
    - by_short: short_store_name_prefix -> list[(docname, company)]
    - by_company: company_name -> list[(docname, warehouse_name)]
    - all_live: list of (docname, warehouse_name_field, company) for substring scan
    """
    by_short = {}
    by_company = {}
    all_live = []
    with open(SNAPSHOT, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            docname = row.get("warehouse_record_name", "").strip()
            company = row.get("company", "").strip()
            wh_name_field = row.get("warehouse_name", "").strip()
            if not docname or company in EXCLUDED_COMPANIES:
                continue
            # Skip internal structural
            if any(docname == p for p in INTERNAL_PREFIXES):
                continue
            if any(docname.startswith(p + " - ") for p in INTERNAL_PREFIXES):
                continue
            # Extract short store name (everything before first " - ")
            short = docname.split(" - ", 1)[0] if " - " in docname else docname
            by_short.setdefault(short, []).append((docname, company))
            by_company.setdefault(company, []).append((docname, wh_name_field))
            all_live.append((docname, wh_name_field, company))
    return by_short, by_company, all_live


def resolve_via_substring(short_name, all_live):
    """Fallback: find live docname whose warehouse_name field contains short_name.

    Used for S188-pattern corp-first warehouses like
    'Bebang Enterprise Inc. - SM Megamall - BEI-SMG' whose warehouse_name field
    is 'Bebang Enterprise Inc. - SM Megamall' and whose docname doesn't
    start with the short key 'SM Megamall'.
    """
    # Normalize for matching (strip trailing/leading whitespace, collapse spaces)
    short_norm = " ".join(short_name.split()).lower()
    candidates = []
    for docname, wh_name, company in all_live:
        wh_norm = " ".join((wh_name or "").split()).lower()
        dn_norm = " ".join(docname.split()).lower()
        # Require short name to appear as delimited substring in warehouse_name
        # or docname (to avoid "SM" matching "SM Mall Of Asia")
        if short_norm in wh_norm or short_norm in dn_norm:
            # Prefer wh_name match where short is at the end or after " - "
            if wh_norm.endswith(short_norm) or (" - " + short_norm) in wh_norm:
                candidates.append((docname, company, 2))  # high priority
            elif dn_norm.startswith(short_norm + " - "):
                candidates.append((docname, company, 2))
            else:
                candidates.append((docname, company, 1))  # low priority
    if not candidates:
        return None
    # Sort by priority descending, then prefer non-BEI suffix
    candidates.sort(key=lambda t: (-t[2], t[0].endswith(" - BEI")))
    return candidates[0][0]


def extract_short(docname):
    """Strip known stale suffix; if none match, split on ' - '."""
    for suf in STALE_SUFFIXES:
        if docname.endswith(suf):
            return docname[: -len(suf)]
    if " - " in docname:
        return docname.split(" - ", 1)[0]
    return docname


def resolve_via_snapshot(short, by_short):
    """Return the preferred live docname for a short store name, or None."""
    candidates = by_short.get(short)
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0][0]
    for docname, _ in candidates:
        if not docname.endswith(" - BEI") and not docname.endswith(" - BKI"):
            return docname
    return candidates[0][0]


def resolve_via_company(fixture_company, by_company):
    """Fallback: use fixture's Company field to find live docname.

    Prefer a leaf warehouse (non-structural) owned by that Company.
    SKIP when Company is the broad "Bebang Enterprise Inc." parent (too many matches).
    """
    if fixture_company == "Bebang Enterprise Inc.":
        return None  # Too broad - multiple matches are ambiguous
    candidates = by_company.get(fixture_company)
    if not candidates:
        return None
    leaf_whs = [
        (d, w) for d, w in candidates
        if not any(d == p for p in INTERNAL_PREFIXES)
        and not any(d.startswith(p + " - ") for p in INTERNAL_PREFIXES)
        and not any(p in (w or "") for p in INTERNAL_PREFIXES)
    ]
    if not leaf_whs:
        return None
    if len(leaf_whs) == 1:
        return leaf_whs[0][0]
    # Prefer one without '- BEI' suffix
    for d, _ in leaf_whs:
        if not d.endswith(" - BEI"):
            return d
    return leaf_whs[0][0]


def regen_fixture(path, col_name, by_short, by_company, all_live, refresh_company=False):
    rows = []
    explicit = 0
    snapshot = 0
    via_company = 0
    via_substr = 0
    unchanged = 0
    co_updated = 0
    missed = []
    # Build docname -> company map from all_live for company refresh
    docname_to_company = {d: c for d, _, c in all_live}
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        for row in reader:
            old = (row.get(col_name) or "").strip()
            new = None
            src = None
            # Phase 1: explicit map
            if old in RENAMES:
                new = RENAMES[old]
                src = "explicit"
                explicit += 1
            # Phase 2: snapshot lookup for stale suffix
            elif any(old.endswith(suf) for suf in STALE_SUFFIXES):
                short = extract_short(old)
                new = resolve_via_snapshot(short, by_short)
                if new:
                    src = "short"
                    snapshot += 1
                if new is None:
                    fixture_co = (row.get("company") or "").strip()
                    if fixture_co:
                        new = resolve_via_company(fixture_co, by_company)
                        if new:
                            src = "company"
                            via_company += 1
                if new is None:
                    fixture_short = (row.get("warehouse_name") or "").strip()
                    if fixture_short:
                        new = resolve_via_substring(fixture_short, all_live)
                        if new:
                            src = "substr"
                            via_substr += 1
                if new is None:
                    missed.append((old, extract_short(old)))
            if new and new != old:
                row[col_name] = new
                print(f"  ({src}) {old!r} -> {new!r}")
            else:
                unchanged += 1
            # Refresh company column if applicable
            if refresh_company and "company" in fields:
                effective_dn = (row.get(col_name) or "").strip()
                live_co = docname_to_company.get(effective_dn)
                old_co = (row.get("company") or "").strip()
                if live_co and live_co != old_co:
                    row["company"] = live_co
                    co_updated += 1
                    print(f"  company: {old_co!r} -> {live_co!r} (for {effective_dn!r})")
            rows.append(row)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(
        f"  {path.name}: explicit={explicit} via_short={snapshot} via_company={via_company} via_substr={via_substr} unchanged={unchanged} co_updated={co_updated}"
    )
    if missed:
        print("  MISSED (no live match):")
        for old, short in missed:
            print(f"    {old!r} (short={short!r})")


if __name__ == "__main__":
    by_short, by_company, all_live = load_snapshot_index()
    print(f"Loaded {len(by_short)} short-name keys / {len(by_company)} companies / {len(all_live)} live warehouses\n")
    print("=== FIXTURE A: sales_dashboard_store_mapping.csv (warehouse_record_name) ===")
    regen_fixture(FIXTURE_A, "warehouse_record_name", by_short, by_company, all_live, refresh_company=False)
    print("\n=== FIXTURE B: store_inventory_shadow_sync_registry.csv (warehouse_docname) ===")
    regen_fixture(FIXTURE_B, "warehouse_docname", by_short, by_company, all_live, refresh_company=False)
    print("\nDone.")
