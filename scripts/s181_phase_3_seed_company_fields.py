"""S181 Phase 3, Task 3.1: seed existing Companies with new field data.

Backfills the 47 S181 Custom Fields for the 45+ existing Frappe Companies
from three local source CSVs:

1. S037 store-buyer-entity register -> entity_category, store_ownership_type,
   operational_status
2. Mosaic POS API keys              -> mosaic_location_id, pos_system,
                                       gps_latitude, gps_longitude (fallback)
3. Bebang Halo-Halo store locations -> gps_latitude, gps_longitude, city,
                                       full_address (preferred over Mosaic
                                       fallback because this is what the
                                       public website uses)

Execution model:
- This script is designed to run inside bench console:
    bench --site hq.bebang.ph execute scripts.s181_phase_3_seed_company_fields.main
- It imports `frappe` and calls `frappe.db.set_value`. Offline "dry-run"
  mode is available via `python scripts/s181_phase_3_seed_company_fields.py
  --dry-run` which prints the planned mutations without touching the DB.

The dry-run path is how this script is verified during development before
the operator runs it live on hq.bebang.ph during the S181 deploy.

Non-store companies (Head Office, Commissary, Holding Company, Franchisor)
have no S037 row, so they get entity_category from a small hardcoded map
and no store_ownership_type. Unmapped Companies are reported at the end.

Idempotent: re-running does not mutate fields that already have the target
value. Safe to run multiple times on the same environment.

Output: output/s181/phase3_seed_results.json with:
- updated count
- skipped (no-change) count
- unmatched Companies list (docname, reason)
- per-field mutation counts
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path resolution: works both when run via `bench execute` (frappe available)
# and standalone `--dry-run` mode (pure Python, no frappe).
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

# HOTFIX 2026-04-11: reference CSVs ship inside the hrms Python package
# at `hrms/data_seed/` (the original v1 paths under `data/_CLEANROOM/...`
# and `docs/stores/...` are gitignored and never reach the Frappe Docker
# image). The package-internal location ships with the source code.
DATA_SEED = REPO_ROOT / "hrms" / "data_seed"

S037_CSV = DATA_SEED / "store_buyer_entity_register_2026-03-12.csv"
MOSAIC_CSV = DATA_SEED / "MOSAIC_POS_API_KEYS.csv"
LOCATIONS_CSV = DATA_SEED / "Bebang_Halo-Halo_Stores_Locations_2025-12-29.csv"

RESULTS_PATH = REPO_ROOT / "output" / "s181" / "phase3_seed_results.json"


# ---------------------------------------------------------------------------
# Non-store entity category map. These companies do not appear in the S037
# register (which is store-only) and need explicit classification.
# ---------------------------------------------------------------------------

NON_STORE_ENTITY_CATEGORIES: dict[str, str] = {
	"Bebang Enterprise Inc.": "Head Office",
	"Bebang Kitchen Inc.": "Commissary",
	"BEBANG FRANCHISE CORP.": "Franchisor",
	"Irresistible Infusions Inc.": "Holding Company",
	"DMD HOLDINGS INC.": "Holding Company",
	# BFC created during S175 COA restructure -- also a franchisor shell
	"BFC": "Franchisor",
	"Bebang Franchise Corporation": "Franchisor",
}


# S037 store_type -> S181 store_ownership_type mapping.
# The S037 register uses the SAME vocabulary as the S181 Custom Field options,
# so this is a direct passthrough except for defaulting empty/missing to
# "Company Owned".
def map_store_ownership_type(s037_store_type: str | None) -> str:
	t = (s037_store_type or "").strip()
	if t in {"JV", "Managed Franchise", "Full Franchise", "Company Owned"}:
		return t
	return "Company Owned"


# ---------------------------------------------------------------------------
# Normalization helpers for fuzzy matching across the three CSVs.
# ---------------------------------------------------------------------------

_STRIP_SUFFIXES = re.compile(
	r"\b(inc\.?|corp\.?|corporation|opc|company|co\.?)\b",
	re.IGNORECASE,
)
_PUNCT = re.compile(r"[.,'\"!\(\)\[\]]")
_WHITESPACE = re.compile(r"\s+")


def normalize_name(s: str) -> str:
	"""Lowercase, strip suffixes (Inc., Corp., OPC, etc.), remove punctuation,
	collapse whitespace. Used to bridge store_name variants across CSVs.
	"""
	if not s:
		return ""
	s = s.lower()
	s = _STRIP_SUFFIXES.sub("", s)
	s = _PUNCT.sub(" ", s)
	s = _WHITESPACE.sub(" ", s)
	return s.strip()


# ---------------------------------------------------------------------------
# CSV loaders
# ---------------------------------------------------------------------------


def load_s037() -> list[dict]:
	with open(S037_CSV, encoding="utf-8-sig") as f:
		return list(csv.DictReader(f))


def load_mosaic() -> list[dict]:
	with open(MOSAIC_CSV, encoding="utf-8-sig") as f:
		return list(csv.DictReader(f))


def load_locations() -> list[dict]:
	with open(LOCATIONS_CSV, encoding="utf-8-sig") as f:
		return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Core seeding
# ---------------------------------------------------------------------------


def build_update_payload(
	company_name: str,
	s037_row: dict | None,
	mosaic_row: dict | None,
	location_row: dict | None,
) -> dict:
	"""Build the field -> value dict for one Company.

	Resolution order for overlapping fields:
	- GPS lat/long: locations CSV (preferred) -> mosaic CSV (fallback)
	- City: locations CSV (preferred) -> mosaic CSV (fallback)
	- full_address: locations CSV (preferred) -> mosaic CSV (fallback)
	- entity_category + store_ownership_type: S037 row (stores) or
	  NON_STORE_ENTITY_CATEGORIES map
	- operational_status: S037 active_fulfillment_status -> "Active" if
	  active, else "Temporarily Closed"; non-store entities -> "Active"
	"""
	payload: dict = {}

	# --- entity_category + store_ownership_type ---
	if s037_row:
		payload["entity_category"] = "Store"
		payload["store_ownership_type"] = map_store_ownership_type(
			s037_row.get("store_type")
		)
	elif company_name in NON_STORE_ENTITY_CATEGORIES:
		payload["entity_category"] = NON_STORE_ENTITY_CATEGORIES[company_name]
		# No store_ownership_type for non-stores (leave empty)

	# --- mosaic_location_id + pos_system ---
	if mosaic_row:
		loc_id = (mosaic_row.get("Mosaic Location ID") or "").strip()
		if loc_id:
			payload["mosaic_location_id"] = loc_id
			payload["pos_system"] = "Mosaic"

	# --- GPS lat/long (prefer locations CSV) ---
	lat = lng = None
	if location_row:
		try:
			lat = float(location_row["latitude"]) if location_row.get("latitude") else None
			lng = float(location_row["longitude"]) if location_row.get("longitude") else None
		except (ValueError, TypeError):
			lat = lng = None
	if (lat is None or lng is None) and mosaic_row:
		try:
			if mosaic_row.get("Latitude"):
				lat = float(mosaic_row["Latitude"])
			if mosaic_row.get("Longitude"):
				lng = float(mosaic_row["Longitude"])
		except (ValueError, TypeError):
			pass
	if lat is not None:
		payload["gps_latitude"] = lat
	if lng is not None:
		payload["gps_longitude"] = lng

	# --- City (prefer locations CSV) ---
	city = None
	if location_row and location_row.get("city"):
		city = location_row["city"].strip()
	elif mosaic_row and mosaic_row.get("City"):
		city = mosaic_row["City"].strip()
	if city:
		payload["city"] = city

	# --- full_address (prefer locations CSV) ---
	addr = None
	if location_row and location_row.get("address"):
		addr = location_row["address"].strip()
	elif mosaic_row and mosaic_row.get("Address"):
		addr = mosaic_row["Address"].strip()
	if addr:
		payload["full_address"] = addr

	# --- operational_status ---
	if s037_row:
		active = (s037_row.get("active_fulfillment_status") or "").strip().lower()
		payload["operational_status"] = "Active" if active == "active" else "Temporarily Closed"
	elif company_name in NON_STORE_ENTITY_CATEGORIES:
		payload["operational_status"] = "Active"

	return payload


def build_match_indices(
	s037_rows: list[dict],
	mosaic_rows: list[dict],
	location_rows: list[dict],
) -> tuple[dict, dict, dict, dict]:
	"""Build lookup indices keyed by normalized store name.

	Returns:
	- s037_by_warehouse_docname (exact match, no normalization — this is the
	  authoritative Frappe docname link)
	- s037_by_normalized_store_name (fuzzy fallback for stores whose
	  warehouse_docname doesn't match a Company)
	- mosaic_by_normalized_store_name
	- locations_by_normalized_store_name
	"""
	s037_by_docname = {}
	s037_by_norm = {}
	for row in s037_rows:
		docname = (row.get("warehouse_docname") or "").strip()
		if docname:
			s037_by_docname[docname] = row
		store_name = (row.get("store_name") or "").strip()
		if store_name:
			s037_by_norm[normalize_name(store_name)] = row

	mosaic_by_norm = {}
	for row in mosaic_rows:
		name = (row.get("Store Name") or "").strip()
		if name:
			mosaic_by_norm[normalize_name(name)] = row

	locations_by_norm = {}
	for row in location_rows:
		name = (row.get("store_name") or "").strip()
		if name:
			locations_by_norm[normalize_name(name)] = row

	return s037_by_docname, s037_by_norm, mosaic_by_norm, locations_by_norm


def plan_updates(company_names: list[str]) -> tuple[list[dict], list[dict]]:
	"""For each Company, compute the S181 field payload.

	Returns (planned_updates, unmatched) where:
	- planned_updates: list of {docname, payload}
	- unmatched: list of {docname, reason}
	"""
	s037_rows = load_s037()
	mosaic_rows = load_mosaic()
	location_rows = load_locations()

	s037_by_docname, s037_by_norm, mosaic_by_norm, locations_by_norm = (
		build_match_indices(s037_rows, mosaic_rows, location_rows)
	)

	planned = []
	unmatched = []

	for docname in company_names:
		s037 = s037_by_docname.get(docname)
		if not s037:
			# Try fuzzy match via normalized docname -> store_name
			norm = normalize_name(docname.split(" - ")[0] if " - " in docname else docname)
			s037 = s037_by_norm.get(norm)

		# Mosaic match: prefer the S037 store_name as the bridge key; fall
		# back to fuzzy-matching the Company docname itself.
		mosaic = None
		if s037:
			mosaic = mosaic_by_norm.get(normalize_name(s037.get("store_name") or ""))
		if not mosaic:
			norm = normalize_name(docname.split(" - ")[0] if " - " in docname else docname)
			mosaic = mosaic_by_norm.get(norm)

		# Locations match: same strategy
		location = None
		if s037:
			location = locations_by_norm.get(normalize_name(s037.get("store_name") or ""))
		if not location:
			norm = normalize_name(docname.split(" - ")[0] if " - " in docname else docname)
			location = locations_by_norm.get(norm)

		payload = build_update_payload(docname, s037, mosaic, location)

		if not payload:
			unmatched.append(
				{
					"docname": docname,
					"reason": "no S037 row, no NON_STORE_ENTITY_CATEGORIES entry, no fuzzy match",
				}
			)
			continue

		planned.append({"docname": docname, "payload": payload})

	return planned, unmatched


# ---------------------------------------------------------------------------
# Frappe-aware application. Only imported when NOT running --dry-run.
# ---------------------------------------------------------------------------


def apply_updates(planned: list[dict]) -> tuple[int, int, dict[str, int]]:
	import frappe  # type: ignore[import-not-found]

	updated = 0
	skipped = 0
	per_field = {}
	company_meta = frappe.get_meta("Company")
	for item in planned:
		docname = item["docname"]
		payload = item["payload"]
		# Only set fields that actually exist on Company (defensive against
		# partial migrate state).
		mutations = {}
		for field, value in payload.items():
			if not company_meta.has_field(field):
				continue
			current = frappe.db.get_value("Company", docname, field)
			if current == value:
				continue
			mutations[field] = value
			per_field[field] = per_field.get(field, 0) + 1
		if mutations:
			for field, value in mutations.items():
				frappe.db.set_value(
					"Company", docname, field, value, update_modified=False
				)
			updated += 1
		else:
			skipped += 1
	frappe.db.commit()
	return updated, skipped, per_field


def list_companies_via_frappe() -> list[str]:
	import frappe  # type: ignore[import-not-found]

	return frappe.get_all("Company", pluck="name")


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def write_results(
	planned: list[dict],
	unmatched: list[dict],
	updated: int,
	skipped: int,
	per_field: dict[str, int],
	dry_run: bool,
) -> None:
	RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
	summary = {
		"dry_run": dry_run,
		"total_companies_considered": len(planned) + len(unmatched),
		"planned_updates": len(planned),
		"updated": updated,
		"skipped_already_current": skipped,
		"unmatched": unmatched,
		"per_field_mutation_counts": per_field,
		"sample_planned_first_5": planned[:5],
	}
	RESULTS_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main_dry_run(sample_companies: list[str] | None = None) -> int:
	"""Offline dry-run. If sample_companies is None, reads a hardcoded list
	of well-known Frappe Company docnames for demonstration.
	"""
	# Hardcoded sample so the script can be dry-run without frappe access.
	# The real run (via bench execute) calls list_companies_via_frappe().
	if sample_companies is None:
		sample_companies = [
			"Bebang Enterprise Inc.",
			"Bebang Kitchen Inc.",
			"Ayala Evo - Bebang Enterprise Inc.",
			"Ayala Malls Fairview Terraces - Bebang Enterprise Inc.",
			"SM Megamall - Bebang Enterprise Inc.",
		]

	planned, unmatched = plan_updates(sample_companies)
	write_results(planned, unmatched, 0, 0, {}, dry_run=True)

	print(f"DRY RUN -- {len(sample_companies)} companies considered")
	print(f"  planned updates : {len(planned)}")
	print(f"  unmatched       : {len(unmatched)}")
	for p in planned:
		print(f"\n  {p['docname']}")
		for k, v in p["payload"].items():
			print(f"    {k:24s} = {v}")
	if unmatched:
		print(f"\n  Unmatched:")
		for u in unmatched:
			print(f"    {u['docname']}: {u['reason']}")
	print(f"\nResults written to {RESULTS_PATH}")
	return 0


def main() -> int:
	"""Live run. Must be invoked inside bench console context so `frappe`
	is importable.
	"""
	try:
		import frappe  # type: ignore[import-not-found]
	except ImportError:
		print("ERROR: frappe not available. Run via `bench --site <site> execute "
		      "scripts.s181_phase_3_seed_company_fields.main` or use --dry-run.")
		return 1

	company_names = list_companies_via_frappe()
	print(f"Found {len(company_names)} companies in Frappe")

	planned, unmatched = plan_updates(company_names)
	print(f"Planned updates: {len(planned)}")
	print(f"Unmatched      : {len(unmatched)}")

	updated, skipped, per_field = apply_updates(planned)
	print(f"Applied        : {updated} updated, {skipped} skipped (already current)")
	print(f"Per-field counts: {per_field}")

	write_results(planned, unmatched, updated, skipped, per_field, dry_run=False)
	print(f"Results written to {RESULTS_PATH}")

	# Phase 3 acceptance assertions
	ok = True
	if per_field.get("entity_category", 0) < 35:
		print(f"WARN: entity_category populated on only {per_field.get('entity_category', 0)} companies (expected >=35)")
		ok = False
	if per_field.get("mosaic_location_id", 0) < 40:
		print(f"WARN: mosaic_location_id populated on only {per_field.get('mosaic_location_id', 0)} companies (expected >=40)")
	if per_field.get("gps_latitude", 0) < 30:
		print(f"WARN: gps_latitude populated on only {per_field.get('gps_latitude', 0)} companies (expected >=30)")

	return 0 if ok else 2


if __name__ == "__main__":
	if "--dry-run" in sys.argv:
		sys.exit(main_dry_run())
	sys.exit(main())
