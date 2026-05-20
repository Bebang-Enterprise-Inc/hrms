"""S255 Phase 4 — Dedup cleanup using invNoVariants_-equivalent normalization.

Mirrors the JS invNoVariants_ from v3.9 line 954:
  Input: invoice no string
  Variants: uppercase-trimmed, digits-only-noLeadingZeros, no-prefix (SI/OR/INV/#)

Dedup tuple: (payeeKey_upper, invVariant, amount_rounded_2dp)
Delete rule: keep legacy/FPM/Suppliers-SOA-sourced; delete Denise PP-sourced duplicates.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parents[2]
CREDS_PATH = "F:/Dropbox/Projects/BEI-ERP/credentials/task-manager-service.json"
AP_MASTER_ID = "1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c"


def inv_no_variants(v):
    """Python mirror of v3.9's invNoVariants_."""
    if v is None: return [""]
    s = str(v).strip().upper()
    if not s or s in ("NAN", "NA", "NONE"): return [""]
    out = {s: 1}
    digits = re.sub(r"\D", "", s)
    if digits:
        try:
            out[str(int(digits))] = 1
        except ValueError:
            pass
    no_prefix = re.sub(r"^(SI|OR|INV|#)[-\s]*", "", s)
    if no_prefix != s:
        out[no_prefix] = 1
    return list(out.keys())


def to_num(v):
    try: return float(v) if v not in (None, "") else 0.0
    except (TypeError, ValueError): return 0.0


def get_sheets():
    creds = service_account.Credentials.from_service_account_file(
        CREDS_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    ).with_subject("sam@bebang.ph")
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def get_sheet_id(sheets, ss_id, name):
    meta = sheets.spreadsheets().get(spreadsheetId=ss_id, fields="sheets(properties(sheetId,title))").execute()
    for s in meta["sheets"]:
        if s["properties"]["title"] == name: return s["properties"]["sheetId"]
    return None


def dedup_tab(sheets, tab_name, header_row):
    """Run dedup audit on one tab. Returns (delete_row_ids, dup_groups_found)."""
    print(f"\n[{tab_name}] reading data (header at row {header_row})...")
    res = sheets.spreadsheets().values().get(
        spreadsheetId=AP_MASTER_ID,
        range=f"'{tab_name}'!A{header_row}:Z",
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute()
    rows = res.get("values", [])
    if not rows or len(rows) < 2:
        print(f"  [skip] no data")
        return [], []
    hdr = rows[0]
    data = rows[1:]
    ncols = len(hdr)
    for r in data:
        while len(r) < ncols: r.append("")

    try:
        iSource = hdr.index("SOURCE")
        iPayee = hdr.index("PAYEE")
        iInvNo = hdr.index("INVOICE NO.")
        iAmount = hdr.index("AMOUNT")
    except ValueError as e:
        print(f"  [skip] missing column: {e}")
        return [], []

    # Build index: tuple → [(sheet_row, source)]
    by_tuple = {}
    for ridx, r in enumerate(data):
        sheet_row = ridx + header_row + 1  # 1-indexed
        payee_key = str(r[iPayee] or "").strip().upper()
        amt = round(to_num(r[iAmount]) * 100) / 100
        inv_no = r[iInvNo] if iInvNo < len(r) else ""
        source = str(r[iSource] or "").strip()
        if not payee_key or not amt:
            continue  # ignore rows missing identification
        variants = inv_no_variants(inv_no)
        for v in variants:
            if not v:
                continue
            key = (payee_key, v, amt)
            by_tuple.setdefault(key, []).append({"sheet_row": sheet_row, "source": source, "inv_no": str(inv_no)})

    # Find groups with >1 entry; identify which to keep/delete
    dup_groups = []
    rows_to_delete = []
    seen_pairs = set()  # avoid double-counting via multiple variants

    for key, entries in by_tuple.items():
        if len(entries) < 2:
            continue
        # Sort: legacy/FPM/Suppliers-SOA-sourced FIRST (these we keep); Denise PP last
        def sort_key(e):
            src = e["source"]
            if src.startswith("Denise PP"):
                return (2, src)
            elif src in ("Suppliers SOA", "FPM", "FPM-SOA"):
                return (0, src)
            return (1, src)
        entries_sorted = sorted(entries, key=sort_key)
        keep = entries_sorted[0]
        for delete_candidate in entries_sorted[1:]:
            pair = (keep["sheet_row"], delete_candidate["sheet_row"])
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            # Only delete if delete_candidate is Denise PP-sourced
            if delete_candidate["source"].startswith("Denise PP"):
                rows_to_delete.append(delete_candidate["sheet_row"])
            dup_groups.append({"key_payee": key[0], "key_variant": key[1], "amount": key[2], "keep": keep, "delete_candidate": delete_candidate, "deleted": delete_candidate["source"].startswith("Denise PP")})

    # Dedupe rows_to_delete (a row might be flagged by multiple variants)
    rows_to_delete = sorted(set(rows_to_delete), reverse=True)

    print(f"  Found {len(dup_groups)} dupe-group entries (cross-variant); {len(rows_to_delete)} unique rows to delete (Denise PP-sourced)")
    return rows_to_delete, dup_groups


def main():
    sheets = get_sheets()

    log = {
        "phase": "4",
        "started_at": datetime.now().astimezone().isoformat(),
        "normalization_fn": "invNoVariants_",
        "tasks": {},
        "tabs": {},
    }

    HEADER_ROWS = {"Payment Plan": 3, "CAPEX": 19}

    for tab in ("Suppliers SOA", "Payment Plan"):
        header_row = HEADER_ROWS.get(tab, 17)
        rows_to_delete, dup_groups = dedup_tab(sheets, tab, header_row)
        # Delete via batchUpdate.deleteDimension (highest-row-first)
        sheet_id = get_sheet_id(sheets, AP_MASTER_ID, tab)
        if rows_to_delete:
            delete_requests = [{
                "deleteDimension": {
                    "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": r - 1, "endIndex": r}
                }
            } for r in rows_to_delete]
            sheets.spreadsheets().batchUpdate(spreadsheetId=AP_MASTER_ID, body={"requests": delete_requests}).execute()
            print(f"  Deleted {len(rows_to_delete)} rows from {tab}")
        log["tabs"][tab] = {
            "header_row": header_row,
            "dupes_found": len(dup_groups),
            "rows_deleted": len(rows_to_delete),
            "sample_deleted": dup_groups[:10],
        }

    # Verify post-delete: dupes_after = 0
    print("\n[verify] Re-running dedup audit post-delete...")
    for tab in ("Suppliers SOA", "Payment Plan"):
        header_row = HEADER_ROWS.get(tab, 17)
        rows_to_delete2, dup_groups2 = dedup_tab(sheets, tab, header_row)
        log["tabs"][tab]["dupes_after"] = len(dup_groups2)
        log["tabs"][tab]["rows_still_to_delete"] = len(rows_to_delete2)
        if rows_to_delete2:
            print(f"  WARN: {tab} still has {len(rows_to_delete2)} rows that would dedup (probably non-Denise sources keeping each other)")
        else:
            print(f"  OK: {tab} no Denise-PP-deletable dupes remain")

    log["finished_at"] = datetime.now().astimezone().isoformat()
    (ROOT / "output" / "s255" / "dedup_cleanup_log.json").write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")
    (ROOT / "output" / "s255" / "phase4_log.json").write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")
    print(f"\nPhase 4 logs: dedup_cleanup_log.json + phase4_log.json")


if __name__ == "__main__":
    main()
