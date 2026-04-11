"""S181 Phase 4, Task 4.1: backfill branch_tin + bir_rdo_code on Companies.

Reads ENTITY_TIN_RDO_2026-02-27.csv (51 entities) and, for each Frappe
Company, sets:

- `branch_tin`     (new S181 field) — only when it differs from the
                    Frappe standard `tax_id` field (which S178 already
                    populated from the head-office legal entity). If
                    the branch TIN is the same as the head-office TIN,
                    branch_tin is left empty to avoid redundancy.
- `bir_rdo_code`   (new S181 field) — always, from the ENTITY_TIN_RDO
                    "RDO Code" column.

Resolution rule for which entity a Company maps to:

1. Store Companies (docname matches an S037 `warehouse_docname`):
     bridge via S037.buyer_entity_name -> ENTITY_TIN_RDO.Entity Name
     (e.g. "Ayala Evo - Bebang Enterprise Inc." -> "Bebang Mega Inc"
      -> TIN from ENTITY_TIN_RDO row matching "Bebang Mega Inc")
2. Non-store Companies:
     fuzzy match Company docname against ENTITY_TIN_RDO.Entity Name
     (e.g. "Bebang Enterprise Inc." -> "Bebang Enterprise Inc." direct)

Execution modes (same pattern as Phase 3):
- python scripts/s181_phase_4_branch_tin_backfill.py --dry-run  (offline)
- bench --site hq.bebang.ph execute \
      scripts.s181_phase_4_branch_tin_backfill.main             (live)

Idempotent. Skips values that already match.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

S037_CSV = REPO_ROOT / "data" / "_CLEANROOM" / (
	"2026-03-12-s037-store-buyer-entity-register"
) / "store_buyer_entity_register_2026-03-12.csv"

TIN_RDO_CSV = REPO_ROOT / "data" / "_CLEANROOM" / "batch_2026-02-28_cleanroom_v1" / (
	"raw_snapshot"
) / "ENTITY_TIN_RDO_2026-02-27.csv"

RESULTS_PATH = REPO_ROOT / "output" / "s181" / "phase4_tin_results.json"


# Same normalization as Phase 3 — kept separate so the two scripts can be
# audited independently.
_STRIP_SUFFIXES = re.compile(
	r"\b(inc\.?|corp\.?|corporation|opc|company|co\.?)\b",
	re.IGNORECASE,
)
_PUNCT = re.compile(r"[.,'\"!\(\)\[\]]")
_WHITESPACE = re.compile(r"\s+")


def normalize_name(s: str) -> str:
	if not s:
		return ""
	s = s.lower()
	s = _STRIP_SUFFIXES.sub("", s)
	s = _PUNCT.sub(" ", s)
	s = _WHITESPACE.sub(" ", s)
	return s.strip()


def load_s037_buyer_map() -> dict[str, str]:
	"""Return {warehouse_docname: buyer_entity_name} for all S037 rows."""
	m = {}
	with open(S037_CSV, encoding="utf-8-sig") as f:
		for row in csv.DictReader(f):
			docname = (row.get("warehouse_docname") or "").strip()
			buyer = (row.get("buyer_entity_name") or "").strip()
			if docname and buyer:
				m[docname] = buyer
	return m


def load_tin_rdo_by_entity() -> dict[str, dict]:
	"""Return {normalized entity name: {TIN, RDO Code, VAT Status, raw name}}."""
	m = {}
	with open(TIN_RDO_CSV, encoding="utf-8-sig") as f:
		for row in csv.DictReader(f):
			name = (row.get("Entity Name") or "").strip()
			if not name:
				continue
			m[normalize_name(name)] = {
				"entity_name": name,
				"tin": (row.get("TIN") or "").strip() or None,
				"rdo_code": (row.get("RDO Code") or "").strip() or None,
				"vat_status": (row.get("VAT Status") or "").strip() or None,
			}
	return m


def resolve_entity_for_company(
	company_docname: str,
	current_tax_id: str | None,
	s037_buyer_map: dict[str, str],
	tin_by_entity: dict[str, dict],
) -> dict | None:
	"""Return the ENTITY_TIN_RDO row that corresponds to this Company,
	or None if no match was found.
	"""
	# Path 1: Store — bridge via S037 to buyer_entity_name
	buyer_name = s037_buyer_map.get(company_docname)
	if buyer_name:
		entity = tin_by_entity.get(normalize_name(buyer_name))
		if entity:
			return entity

	# Path 2: Non-store — fuzzy match docname -> Entity Name
	# Try the holding legal entity parent from " - <legal>" suffix first,
	# then the full docname.
	candidates = []
	if " - " in company_docname:
		candidates.append(company_docname.rsplit(" - ", 1)[-1])
	candidates.append(company_docname)

	for c in candidates:
		entity = tin_by_entity.get(normalize_name(c))
		if entity:
			return entity

	return None


def plan_updates(
	companies: list[dict],
	s037_buyer_map: dict[str, str],
	tin_by_entity: dict[str, dict],
) -> tuple[list[dict], list[dict]]:
	"""For each company dict ({name, tax_id}), compute the TIN/RDO payload.

	Returns (planned, unmatched).
	"""
	planned = []
	unmatched = []

	for company in companies:
		docname = company["name"]
		current_tax_id = (company.get("tax_id") or "").strip() or None

		entity = resolve_entity_for_company(
			docname, current_tax_id, s037_buyer_map, tin_by_entity
		)
		if not entity:
			unmatched.append({"docname": docname, "reason": "no entity match"})
			continue

		payload = {}
		resolved_tin = entity["tin"]
		resolved_rdo = entity["rdo_code"]

		# branch_tin — only set when it differs from the Frappe standard tax_id
		# (the plan's Phase 4 assertion rejects redundant values).
		if resolved_tin and resolved_tin != current_tax_id:
			payload["branch_tin"] = resolved_tin

		# bir_rdo_code — always set when we have a value
		if resolved_rdo:
			payload["bir_rdo_code"] = resolved_rdo

		if payload:
			planned.append(
				{
					"docname": docname,
					"payload": payload,
					"matched_entity": entity["entity_name"],
					"current_tax_id": current_tax_id,
				}
			)
		else:
			unmatched.append(
				{
					"docname": docname,
					"reason": "entity matched but nothing to set (TIN == tax_id, no RDO)",
				}
			)

	return planned, unmatched


def apply_updates(planned: list[dict]) -> tuple[int, int, dict[str, int]]:
	import frappe  # type: ignore[import-not-found]

	updated = 0
	skipped = 0
	per_field: dict[str, int] = {}
	company_meta = frappe.get_meta("Company")
	for item in planned:
		docname = item["docname"]
		payload = item["payload"]
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


def main_dry_run() -> int:
	# Hardcoded sample covering both store and non-store paths.
	sample = [
		{"name": "Bebang Enterprise Inc.", "tax_id": "647-243-690-00000"},
		{"name": "Bebang Kitchen Inc.", "tax_id": "010-880-681-00001"},
		{"name": "Ayala Evo - Bebang Enterprise Inc.", "tax_id": "647-243-690-00000"},
		{"name": "Ayala Malls Fairview Terraces - Bebang Enterprise Inc.", "tax_id": "647-243-690-00000"},
		{"name": "Irresistible Infusions Inc.", "tax_id": ""},
	]
	s037_buyer_map = load_s037_buyer_map()
	tin_by_entity = load_tin_rdo_by_entity()

	planned, unmatched = plan_updates(sample, s037_buyer_map, tin_by_entity)
	write_results(planned, unmatched, 0, 0, {}, dry_run=True)

	print(f"DRY RUN -- {len(sample)} companies considered")
	print(f"  S037 buyer map : {len(s037_buyer_map)} entries")
	print(f"  TIN/RDO entities: {len(tin_by_entity)} entries")
	print(f"  planned updates : {len(planned)}")
	print(f"  unmatched       : {len(unmatched)}")
	for p in planned:
		print(f"\n  {p['docname']}")
		print(f"    matched entity  : {p['matched_entity']}")
		print(f"    current tax_id  : {p['current_tax_id']}")
		for k, v in p["payload"].items():
			print(f"    {k:16s} = {v}")
	for u in unmatched:
		print(f"\n  [UNMATCHED] {u['docname']}: {u['reason']}")
	print(f"\nResults written to {RESULTS_PATH}")
	return 0


def main() -> int:
	try:
		import frappe  # type: ignore[import-not-found]
	except ImportError:
		print("ERROR: frappe not available. Run via `bench --site <site> execute "
		      "scripts.s181_phase_4_branch_tin_backfill.main` or use --dry-run.")
		return 1

	companies = frappe.get_all("Company", fields=["name", "tax_id"])
	print(f"Found {len(companies)} companies in Frappe")

	s037_buyer_map = load_s037_buyer_map()
	tin_by_entity = load_tin_rdo_by_entity()

	planned, unmatched = plan_updates(companies, s037_buyer_map, tin_by_entity)
	print(f"Planned updates: {len(planned)}")
	print(f"Unmatched      : {len(unmatched)}")

	updated, skipped, per_field = apply_updates(planned)
	print(f"Applied        : {updated} updated, {skipped} skipped")
	print(f"Per-field counts: {per_field}")

	write_results(planned, unmatched, updated, skipped, per_field, dry_run=False)
	print(f"Results written to {RESULTS_PATH}")

	# Phase 4 acceptance assertions (from plan Task 4.3):
	# 1. Companies with branch-specific TINs have branch_tin populated
	# 2. At least 30 companies have bir_rdo_code populated
	# 3. No branch_tin value is identical to tax_id (enforced in plan_updates())
	if per_field.get("bir_rdo_code", 0) < 30:
		print(f"WARN: bir_rdo_code populated on only {per_field.get('bir_rdo_code', 0)} companies (expected >=30)")

	return 0


if __name__ == "__main__":
	if "--dry-run" in sys.argv:
		sys.exit(main_dry_run())
	sys.exit(main())
