"""S208 — Build picks file + entity map from BD drive missing compliance list.

Reads `.scratch/bd_drive_missing_compliance.csv` (220 rows).
Filters out drafts, templates, images (PDFs only for S208 scope).
Maps each remaining row to {file_id, entity_code, permit_code, proposed_filename}
based on folder path in Business Development drive.

Writes:
- .scratch/s208_picks.json              (list[dict]: file_id + entity_code + permit_code + ...)
- .scratch/s208_entity_map.csv          (per-file mapping table)
- .scratch/s208_entity_map_summary.csv  (counts per entity_code)
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
SCRATCH = ROOT / ".scratch"
IN_CSV = SCRATCH / "bd_drive_missing_compliance.csv"
OUT_PICKS = SCRATCH / "s208_picks.json"
OUT_MAP = SCRATCH / "s208_entity_map.csv"
OUT_SUM = SCRATCH / "s208_entity_map_summary.csv"

# ---------- filter rules ----------------------------------------------------
EXCLUDE_PATH_RE = re.compile(r"(?i)(\(not signed\)|template|\(revised\)|input bebang|for editing|draft|proposal)")
PDF_ONLY = True  # S208 scope decision #2: PDFs only in this sprint

# ---------- entity mapping --------------------------------------------------
# Map folder path segments → entity_code. Order matters: more specific first.
FRANCHISE_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"/LEGACY77 FOOD CORP/", re.I), "FRANCHISE_LEGACY77"),
    (re.compile(r"/TUNGSTEN HOLDINGS OPC/", re.I), "FRANCHISE_TUNGSTEN"),
    (re.compile(r"/TAJ FOOD CORP/", re.I), "FRANCHISE_TAJ"),
    (re.compile(r"/RED TALDAWA/", re.I), "FRANCHISE_RED_TALDAWA"),
    (re.compile(r"/PERPETUAL FOOD CORP/", re.I), "FRANCHISE_PERPETUAL"),
    (re.compile(r"/HFFM Solenad Food Services Inc/", re.I), "FRANCHISE_HFFM"),
    (re.compile(r"/B CUBED VENTURES CORP/", re.I), "FRANCHISE_B_CUBED"),
    (re.compile(r"/TRICERN FOOD CORP/", re.I), "FRANCHISE_TRICERN"),
    (re.compile(r"/DLS Dessert Craft", re.I), "FRANCHISE_DLS"),
    (re.compile(r"/FREEZE DELIGHT INC/", re.I), "FRANCHISE_FREEZE_DELIGHT"),
    (re.compile(r"/DAY ONES/", re.I), "FRANCHISE_DAY_ONES"),
    (re.compile(r"/CHARLES PAW/", re.I), "FRANCHISE_TASTECARTEL"),
    (re.compile(r"/IAN UMALI/", re.I), "FRANCHISE_IAN_UMALI"),
    (re.compile(r"/BEIFranchise Food OPC/", re.I), "CORP_FRANCHISE_OPC"),
    (re.compile(r"/BEBANG COMINTANES FOOD CORP/", re.I), "FRANCHISE_COMINTANES"),
    (re.compile(r"/DMD HOLDINGS INC/", re.I), "CORP_UPTOWN_BGC"),
    (re.compile(r"/HALO HALO TERMINAL FOOD CORP/", re.I), "FRANCHISE_HALOHALO_TERMINAL"),
    (re.compile(r"/HALO HALO ALABANG TOWN CENTER FOOD CORP/", re.I), "FRANCHISE_ATC"),
    (re.compile(r"/GLORIETTA/", re.I), "FRANCHISE_GLORIETTA"),
    (re.compile(r"/FRANCHISE BRANCHES/FRANCHISE BRANCHES/([^/]+)/", re.I), "__FRANCHISE_DYNAMIC__"),
]

JV_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"/IMELDA SORIANO/", re.I), "JV_IMELDA"),
    (re.compile(r"/EDWARD SY & RALPH TY/", re.I), "JV_EDWARD_SY_RALPH_TY"),
    (re.compile(r"/EMPIRE77 INC \(BEBANG\)/", re.I), "JV_EMPIRE77"),
    (re.compile(r"/PERPETUALLY CANDID GROUP/", re.I), "JV_PERPETUALLY_CANDID"),
    (re.compile(r"/VISHAL SURESH DASWANI/", re.I), "JV_VISHAL_DASWANI"),
    (re.compile(r"/DMD HOLDINGS INC/", re.I), "CORP_UPTOWN_BGC"),
    (re.compile(r"/JV BRANCHES/JV BRANCHES/([^/]+)/", re.I), "__JV_DYNAMIC__"),
]

# ---------- permit-code heuristics ------------------------------------------
# These are educated guesses from filename + folder hints; OCR/Opus will
# further classify inside the pipeline, but we need a starting subfolder.
PERMIT_HEURISTICS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(?i)(by[-\s_]?laws?|by[-\s_]?law)"), "SEC_BYLAWS"),
    (re.compile(r"(?i)(articles? of inc|art of inc|AOI|incorporation)"), "SEC_AOI"),
    (re.compile(r"(?i)(certificate of inc|cert of inc|\bCOI\b)"), "SEC_COI"),
    (re.compile(r"(?i)(GIS\b|general information sheet)"), "SEC_GIS"),
    (re.compile(r"(?i)(certificate of authentication|cert auth)"), "SEC_CERT"),
    (re.compile(r"(?i)\b(2303|BIR 2303|Form 2303|COR\b|certificate of registration)"), "BIR_2303"),
    (re.compile(r"(?i)(BIR PTU|POS Reg|permit to use)"), "BIR_PTU_POS"),
    (re.compile(r"(?i)(mayor.?s permit|business permit|\bBP\b)"), "MAYORS_PERMIT"),
    (re.compile(r"(?i)(barangay clearance|brgy)"), "BARANGAY_CLEARANCE"),
    (re.compile(r"(?i)(building permit)"), "BUILDING_PERMIT"),
    (re.compile(r"(?i)(fire safety|\bFSIC\b)"), "FSIC"),
    (re.compile(r"(?i)(sanitary)"), "SANITARY"),
    (re.compile(r"(?i)(occupancy)"), "CERT_OCCUPANCY"),
    (re.compile(r"(?i)(franchise management|management agreement)"), "FRANCHISE_AGREEMENT"),
    (re.compile(r"(?i)(franchise agreement|\bFA\b)"), "FRANCHISE_AGREEMENT"),
    (re.compile(r"(?i)(jv[_\-\s]agreement|joint venture|jv contract)"), "JV_AGREEMENT"),
    (re.compile(r"(?i)(lease offer|lease contract|\blease\b)"), "LEASE"),
    (re.compile(r"(?i)(insurance)"), "INSURANCE"),
    (re.compile(r"(?i)(receipt)"), "RECEIPT"),
    (re.compile(r"(?i)(sales invoice|\bSI\b)"), "SALES_INVOICE"),
    (re.compile(r"(?i)(sworn)"), "SWORN_STATEMENT"),
    (re.compile(r"(?i)(passport|valid id|voters id|id$|\bID\b)"), "ID"),
    (re.compile(r"(?i)(letter)"), "LETTER"),
]

DYNAMIC_PARTNER_CODES = {
    "LEGACY77 FOOD CORP": "FRANCHISE_LEGACY77",
    "TUNGSTEN HOLDINGS OPC": "FRANCHISE_TUNGSTEN",
    "TAJ FOOD CORP": "FRANCHISE_TAJ",
    "RED TALDAWA": "FRANCHISE_RED_TALDAWA",
    "PERPETUAL FOOD CORP": "FRANCHISE_PERPETUAL",
    "HFFM Solenad Food Services Inc": "FRANCHISE_HFFM",
    "B CUBED VENTURES CORP": "FRANCHISE_B_CUBED",
    "TRICERN FOOD CORP": "FRANCHISE_TRICERN",
    "DLS Dessert Craft ": "FRANCHISE_DLS",
    "FREEZE DELIGHT INC": "FRANCHISE_FREEZE_DELIGHT",
    "DAY ONES": "FRANCHISE_DAY_ONES",
    "CHARLES PAW": "FRANCHISE_TASTECARTEL",
    "IAN UMALI": "FRANCHISE_IAN_UMALI",
    "BEIFranchise Food OPC": "CORP_FRANCHISE_OPC",
    "BEBANG COMINTANES FOOD CORP": "FRANCHISE_COMINTANES",
    "DMD HOLDINGS INC": "CORP_UPTOWN_BGC",
    "HALO HALO TERMINAL FOOD CORP": "FRANCHISE_HALOHALO_TERMINAL",
    "HALO HALO ALABANG TOWN CENTER FOOD CORP": "FRANCHISE_ATC",
    "GLORIETTA": "FRANCHISE_GLORIETTA",
    "IMELDA SORIANO": "JV_IMELDA",
    "EDWARD SY & RALPH TY": "JV_EDWARD_SY_RALPH_TY",
    "EMPIRE77 INC (BEBANG)": "JV_EMPIRE77",
    "PERPETUALLY CANDID GROUP": "JV_PERPETUALLY_CANDID",
    "VISHAL SURESH DASWANI": "JV_VISHAL_DASWANI",
}


def _sanitize_name(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    s = s.strip("_.")
    return s[:120]


def classify_entity(path: str) -> str | None:
    p = "/" + path  # ensure leading /
    if "/FRANCHISE BRANCHES/" in p:
        # try specific mapping first
        for rx, code in FRANCHISE_MAP:
            if code.startswith("__"):
                continue
            if rx.search(p):
                return code
        # dynamic fallback
        m = re.search(r"/FRANCHISE BRANCHES/FRANCHISE BRANCHES/([^/]+)/", p, re.I)
        if m:
            return DYNAMIC_PARTNER_CODES.get(m.group(1).strip(), "FRANCHISE_" + _sanitize_name(m.group(1)).upper())
        # partner-section only
        return "FRANCHISE_UNKNOWN"
    if "/JV BRANCHES/" in p:
        for rx, code in JV_MAP:
            if code.startswith("__"):
                continue
            if rx.search(p):
                return code
        m = re.search(r"/JV BRANCHES/JV BRANCHES/([^/]+)/", p, re.I)
        if m:
            return DYNAMIC_PARTNER_CODES.get(m.group(1).strip(), "JV_" + _sanitize_name(m.group(1)).upper())
        return "JV_UNKNOWN"
    # top-level BD drive doc (e.g. "Business Development/Ayala Marikina JV Agreement.docx")
    return "JV_TOPLEVEL"


def classify_permit(name: str, path: str) -> str:
    hay = f"{path}  {name}"
    for rx, code in PERMIT_HEURISTICS:
        if rx.search(hay):
            return code
    return "UNKNOWN"


def proposed_filename(name: str, entity: str, permit: str) -> str:
    base = _sanitize_name(Path(name).stem)
    return f"{permit}_{entity}_{base}.md"


def main() -> None:
    if not IN_CSV.exists():
        print(f"ERROR: missing {IN_CSV}")
        sys.exit(1)

    picks: list[dict] = []
    skipped = 0
    skip_reasons: Counter = Counter()

    with IN_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        r = csv.DictReader(fh)
        for row in r:
            mime = (row.get("mimeType") or "").strip()
            path = (row.get("path") or "").strip()
            name = (row.get("name") or "").strip()
            fid = (row.get("id") or "").strip()
            md5 = (row.get("md5") or "").strip()
            size = (row.get("size") or "").strip()
            modified = (row.get("modifiedTime") or "").strip()

            # Filter: PDFs only in this sprint
            if PDF_ONLY and mime != "application/pdf":
                skipped += 1
                skip_reasons["not_pdf_" + (mime.split("/")[-1] or "unknown")] += 1
                continue

            # Filter: drafts / templates / images
            if EXCLUDE_PATH_RE.search(path) or EXCLUDE_PATH_RE.search(name):
                skipped += 1
                skip_reasons["draft_or_template"] += 1
                continue

            entity = classify_entity(path) or "UNMAPPED"
            permit = classify_permit(name, path)
            new_filename = proposed_filename(name, entity, permit)

            picks.append({
                "file_id": fid,
                "name": name,
                "path": path,
                "md5": md5,
                "size": int(size) if size.isdigit() else None,
                "modifiedTime": modified,
                "entity_code": entity,
                "permit_code": permit,
                "proposed_filename": new_filename,
            })

    # Write JSON
    OUT_PICKS.write_text(json.dumps(picks, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT_PICKS}  ({len(picks)} picks)")

    # Write CSV map
    with OUT_MAP.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "file_id", "name", "path", "md5", "size", "modifiedTime",
            "entity_code", "permit_code", "proposed_filename",
        ])
        w.writeheader()
        for p in picks:
            w.writerow(p)
    print(f"wrote {OUT_MAP}")

    # Summary
    entity_counts = Counter(p["entity_code"] for p in picks)
    permit_counts = Counter(p["permit_code"] for p in picks)
    with OUT_SUM.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["dimension", "value", "count"])
        for code, n in sorted(entity_counts.items(), key=lambda x: -x[1]):
            w.writerow(["entity_code", code, n])
        for code, n in sorted(permit_counts.items(), key=lambda x: -x[1]):
            w.writerow(["permit_code", code, n])
    print(f"wrote {OUT_SUM}")

    # Print summary to stdout
    print(f"\n=== S208 picks summary ===")
    print(f"included: {len(picks)}")
    print(f"skipped: {skipped}")
    for reason, n in skip_reasons.most_common():
        print(f"  skip[{reason}]: {n}")

    print(f"\nby entity_code:")
    for code, n in sorted(entity_counts.items(), key=lambda x: -x[1])[:30]:
        print(f"  {n:4}  {code}")

    print(f"\nby permit_code:")
    for code, n in sorted(permit_counts.items(), key=lambda x: -x[1]):
        print(f"  {n:4}  {code}")


if __name__ == "__main__":
    main()
