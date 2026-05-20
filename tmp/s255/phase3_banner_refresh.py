"""S255 Phase 3 — Banner refresh (recomputeBanners_).

Implements recomputeBanners_ in v3.9 source AND runs the same logic Python-side
NOW so AP Master banners reflect current data (without waiting for v3.9 deploy).
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parents[2]
CREDS_PATH = "F:/Dropbox/Projects/BEI-ERP/credentials/task-manager-service.json"
AP_MASTER_ID = "1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c"
V39_PATH = ROOT / "scripts" / "google_apps" / "s255_ap_view_hourly_sync_v39.gs"


def get_sheets(impersonate="sam@bebang.ph"):
    creds = service_account.Credentials.from_service_account_file(
        CREDS_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    ).with_subject(impersonate)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def to_num(v):
    try:
        return float(v) if v not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


RECOMPUTE_BANNERS_JS = """
// ───────────────────────────────────────────────────────────────────────────
// v3.9 (S255 Phase 3) — recomputeBanners_ — RF-7 fix
// Recomputes banner rows from current tab data on every hourly cycle.
// Replaces the stale legacy-only banner that buildGrid() wrote via mode=v2.
// ───────────────────────────────────────────────────────────────────────────
function recomputeBanners_(ss) {
  var stats = { banners_updated: 0, tabs_processed: [], details: {} };
  var TABS = ['Suppliers SOA', 'Head Office', 'CAPEX', 'Payment Plan', 'Intercompany'];

  TABS.forEach(function(tabName) {
    var sh = ss.getSheetByName(tabName);
    if (!sh) return;
    // Payment Plan has header at row 3; entry tabs at row 17
    var headerRow = (tabName === 'Payment Plan') ? 3 : 17;
    var dataStartRow = headerRow + 1;
    var lastRow = sh.getLastRow();
    if (lastRow < dataStartRow) {
      stats.details[tabName] = { skipped: 'no data rows' };
      return;
    }
    var ncols = sh.getLastColumn();
    var hdr = sh.getRange(headerRow, 1, 1, ncols).getValues()[0];
    var iOut = hdr.indexOf('OUTSTANDING');
    var iPayee = hdr.indexOf('PAYEE');
    var iStatus = hdr.indexOf('STATUS');
    var iAgingBucket = hdr.indexOf('AGING BUCKET');
    var iVatable = hdr.indexOf('VATABLE');
    var iVat = hdr.indexOf('VAT');
    var iEwt = hdr.indexOf('EWT');
    var iAmount = hdr.indexOf('AMOUNT');
    if (iOut < 0 || iPayee < 0) {
      stats.details[tabName] = { skipped: 'missing OUTSTANDING or PAYEE column' };
      return;
    }
    var data = sh.getRange(dataStartRow, 1, lastRow - dataStartRow + 1, ncols).getValues();

    var total = 0, items = 0;
    var payees = {}; var aging = {}; var vatable = 0, vat = 0, ewt = 0; var vatGaps = 0;
    var bk = { 'NO RFP YET': {t:0,c:0}, 'WITH FINANCE': {t:0,c:0}, 'IN PIPELINE': {t:0,c:0},
               'CHECK READY': {t:0,c:0}, 'FOR ONLINE PAYMENT': {t:0,c:0},
               'CHECK RELEASED': {t:0,c:0}, 'PAID': {t:0,c:0} };

    data.forEach(function(r) {
      var out = toNum(r[iOut]);
      var payee = String(r[iPayee] || '').trim();
      var status = String(iStatus >= 0 ? r[iStatus] : '').trim().toUpperCase();
      var bucket = String(iAgingBucket >= 0 ? r[iAgingBucket] : '').trim();

      if (out > 0) {
        total += out;
        items++;
        if (payee) payees[payee] = 1;
        if (bucket) aging[bucket] = (aging[bucket] || 0) + out;
        if (iVatable >= 0) vatable += toNum(r[iVatable]);
        if (iVat >= 0) vat += toNum(r[iVat]);
        if (iEwt >= 0) ewt += toNum(r[iEwt]);
        if (iAmount >= 0 && toNum(r[iAmount]) > 50000 && toNum(r[iVat]) === 0) vatGaps++;
      }
      if (bk[status]) { bk[status].t += out; bk[status].c++; }
    });

    var uniquePayees = Object.keys(payees).length;
    var pipelineT = bk['IN PIPELINE'].t + bk['CHECK READY'].t + bk['FOR ONLINE PAYMENT'].t;
    var pipelineC = bk['IN PIPELINE'].c + bk['CHECK READY'].c + bk['FOR ONLINE PAYMENT'].c;

    // Row 4: TOTAL OUTSTANDING — A4..E4
    sh.getRange(4, 1, 1, 5).setValues([['TOTAL OUTSTANDING', total, uniquePayees + ' payees', '', items + ' items']]);

    // Row 7 + 10 + 11 + 13 — only for entry-style tabs (Payment Plan has different banner)
    if (tabName !== 'Payment Plan') {
      sh.getRange(7, 1, 1, 15).setValues([[
        'NO RFP YET', bk['NO RFP YET'].t, bk['NO RFP YET'].c + ' items',
        'WITH FINANCE (no RFP)', bk['WITH FINANCE'].t, bk['WITH FINANCE'].c + ' items',
        'IN PIPELINE', pipelineT, pipelineC + ' items',
        'CHECK RELEASED', bk['CHECK RELEASED'].t, bk['CHECK RELEASED'].c + ' items',
        'PAID', '', bk['PAID'].c + ' items',
      ]]);
      sh.getRange(10, 1, 1, 14).setValues([[
        'Not Yet Due', aging['Not Yet Due']||0, '',
        '0-30', aging['0-30 days']||0, '',
        '31-60', aging['31-60 days']||0, '',
        '61-90', aging['61-90 days']||0, '',
        '91-120', aging['91-120 days']||0,
      ]]);
      sh.getRange(11, 1, 1, 2).setValues([['Over 120 days', aging['Over 120 days']||0]]);
      sh.getRange(13, 1, 1, 11).setValues([[
        'Vatable Sales', vatable, '',
        'VAT (12%)', vat, '',
        'EWT', ewt, '',
        'VAT gaps (amt>50K, VAT=0)', vatGaps,
      ]]);
    }

    stats.banners_updated++;
    stats.tabs_processed.push(tabName);
    stats.details[tabName] = {
      total_outstanding: total,
      unique_payees: uniquePayees,
      items: items,
      vatable: vatable, vat: vat, ewt: ewt, vat_gaps: vatGaps,
    };
  });
  return stats;
}
"""


def patch_v39():
    """Insert recomputeBanners_ function into v3.9 source + wire into doRefreshAllTabs_v3_."""
    src = V39_PATH.read_text(encoding="utf-8")
    if "function recomputeBanners_" in src:
        print("[3.1] recomputeBanners_ already in v3.9 source; skipping insertion")
        return src
    lines = src.split("\n")

    # Insert function before "// buildGrid + formatTab kept from v2" (around line 986)
    insert_anchor = None
    for idx, ln in enumerate(lines):
        if "// buildGrid + formatTab kept from v2" in ln:
            insert_anchor = idx
            break
    if insert_anchor is None:
        # Fall back to inserting before function buildGrid(
        for idx, ln in enumerate(lines):
            if ln.strip().startswith("function buildGrid("):
                insert_anchor = idx
                break
    assert insert_anchor is not None, "Could not find anchor for recomputeBanners_ insertion"

    new_lines = lines[:insert_anchor] + RECOMPUTE_BANNERS_JS.split("\n") + lines[insert_anchor:]

    # Wire recomputeBanners_(ss) into doRefreshAllTabs_v3_ before stats.duration_ms
    final = []
    wired = False
    for ln in new_lines:
        if not wired and "stats.duration_ms = Date.now() - t0;" in ln:
            final.append("  // v3.9 (S255 Phase 3.2): refresh banners from current data before logging cycle complete")
            final.append("  if (!dryRun) { stats.banners = recomputeBanners_(ss); }")
            wired = True
        final.append(ln)
    assert wired, "Failed to wire recomputeBanners_ call into doRefreshAllTabs_v3_"

    new_src = "\n".join(final)
    V39_PATH.write_text(new_src, encoding="utf-8")
    print(f"[3.1+3.2] v3.9 patched: recomputeBanners_ added + wired ({len(new_src.encode('utf-8'))} bytes)")
    return new_src


def main():
    log = {"phase": "3", "started_at": datetime.now().astimezone().isoformat(), "tasks": {}}

    # Phase 3.1+3.2 — patch v3.9 source
    src = patch_v39()
    log["tasks"]["3.1+3.2"] = {"status": "DONE", "v39_has_recomputeBanners_": "function recomputeBanners_" in src, "wired": "stats.banners = recomputeBanners_(ss)" in src}

    # Phase 3.3 — run Python-side recompute NOW so banner reflects current data (no wait for deploy)
    sheets = get_sheets()
    TABS = ["Suppliers SOA", "Head Office", "CAPEX", "Payment Plan", "Intercompany"]
    banner_log = {"updated": 0, "tabs": {}}

    HEADER_ROWS = {"Payment Plan": 3, "CAPEX": 19}  # SOA/HO/Intercompany default = 17
    for tab in TABS:
        header_row = HEADER_ROWS.get(tab, 17)
        data_start = header_row + 1
        # Get all data
        res = sheets.spreadsheets().values().get(
            spreadsheetId=AP_MASTER_ID,
            range=f"'{tab}'!A{header_row}:Z",
            valueRenderOption="UNFORMATTED_VALUE",
        ).execute()
        rows = res.get("values", [])
        if not rows or len(rows) < 2:
            print(f"[{tab}] skip (no data)")
            banner_log["tabs"][tab] = {"skipped": "no data"}
            continue
        hdr = rows[0]
        data = rows[1:]
        # Pad data rows
        ncols = len(hdr)
        for r in data:
            while len(r) < ncols:
                r.append("")

        def idx(name):
            try: return hdr.index(name)
            except ValueError: return -1

        iOut = idx("OUTSTANDING")
        iPayee = idx("PAYEE")
        iStatus = idx("STATUS")
        iAgingBucket = idx("AGING BUCKET")
        iVatable = idx("VATABLE")
        iVat = idx("VAT")
        iEwt = idx("EWT")
        iAmount = idx("AMOUNT")

        if iOut < 0 or iPayee < 0:
            print(f"[{tab}] skip (missing OUTSTANDING or PAYEE)")
            banner_log["tabs"][tab] = {"skipped": "missing OUTSTANDING or PAYEE"}
            continue

        total = 0.0
        items = 0
        payees = set()
        aging = {}
        vatable = vat = ewt = 0.0
        vat_gaps = 0
        bk = {k: {"t": 0.0, "c": 0} for k in ["NO RFP YET","WITH FINANCE","IN PIPELINE","CHECK READY","FOR ONLINE PAYMENT","CHECK RELEASED","PAID"]}

        for r in data:
            out = to_num(r[iOut])
            payee = str(r[iPayee] or "").strip()
            status = str(r[iStatus] or "").strip().upper() if iStatus >= 0 else ""
            bucket = str(r[iAgingBucket] or "").strip() if iAgingBucket >= 0 else ""
            if out > 0:
                total += out
                items += 1
                if payee: payees.add(payee)
                if bucket: aging[bucket] = aging.get(bucket, 0) + out
                if iVatable >= 0: vatable += to_num(r[iVatable])
                if iVat >= 0: vat += to_num(r[iVat])
                if iEwt >= 0: ewt += to_num(r[iEwt])
                if iAmount >= 0 and to_num(r[iAmount]) > 50000 and (iVat < 0 or to_num(r[iVat]) == 0): vat_gaps += 1
            if status in bk:
                bk[status]["t"] += out
                bk[status]["c"] += 1

        unique_payees = len(payees)
        pipeline_t = bk["IN PIPELINE"]["t"] + bk["CHECK READY"]["t"] + bk["FOR ONLINE PAYMENT"]["t"]
        pipeline_c = bk["IN PIPELINE"]["c"] + bk["CHECK READY"]["c"] + bk["FOR ONLINE PAYMENT"]["c"]

        # Write row 4
        sheets.spreadsheets().values().update(
            spreadsheetId=AP_MASTER_ID,
            range=f"'{tab}'!A4:E4",
            valueInputOption="USER_ENTERED",
            body={"values": [["TOTAL OUTSTANDING", total, f"{unique_payees} payees", "", f"{items} items"]]},
        ).execute()

        if tab != "Payment Plan":
            # Row 7
            sheets.spreadsheets().values().update(
                spreadsheetId=AP_MASTER_ID, range=f"'{tab}'!A7:O7", valueInputOption="USER_ENTERED",
                body={"values": [[
                    "NO RFP YET", bk["NO RFP YET"]["t"], f"{bk['NO RFP YET']['c']} items",
                    "WITH FINANCE (no RFP)", bk["WITH FINANCE"]["t"], f"{bk['WITH FINANCE']['c']} items",
                    "IN PIPELINE", pipeline_t, f"{pipeline_c} items",
                    "CHECK RELEASED", bk["CHECK RELEASED"]["t"], f"{bk['CHECK RELEASED']['c']} items",
                    "PAID", "", f"{bk['PAID']['c']} items",
                ]]}
            ).execute()
            # Row 10
            sheets.spreadsheets().values().update(
                spreadsheetId=AP_MASTER_ID, range=f"'{tab}'!A10:N10", valueInputOption="USER_ENTERED",
                body={"values": [[
                    "Not Yet Due", aging.get("Not Yet Due", 0), "",
                    "0-30", aging.get("0-30 days", 0), "",
                    "31-60", aging.get("31-60 days", 0), "",
                    "61-90", aging.get("61-90 days", 0), "",
                    "91-120", aging.get("91-120 days", 0),
                ]]}
            ).execute()
            # Row 11
            sheets.spreadsheets().values().update(
                spreadsheetId=AP_MASTER_ID, range=f"'{tab}'!A11:B11", valueInputOption="USER_ENTERED",
                body={"values": [["Over 120 days", aging.get("Over 120 days", 0)]]},
            ).execute()
            # Row 13
            sheets.spreadsheets().values().update(
                spreadsheetId=AP_MASTER_ID, range=f"'{tab}'!A13:K13", valueInputOption="USER_ENTERED",
                body={"values": [[
                    "Vatable Sales", vatable, "",
                    "VAT (12%)", vat, "",
                    "EWT", ewt, "",
                    "VAT gaps (amt>50K, VAT=0)", vat_gaps,
                ]]}
            ).execute()

        banner_log["updated"] += 1
        banner_log["tabs"][tab] = {
            "total_outstanding": round(total, 2),
            "unique_payees": unique_payees,
            "items": items,
            "vatable": round(vatable, 2),
            "vat": round(vat, 2),
            "ewt": round(ewt, 2),
            "vat_gaps": vat_gaps,
            "aging": {k: round(v, 2) for k, v in aging.items()},
            "status_bucket_totals": {k: {"t": round(v["t"], 2), "c": v["c"]} for k, v in bk.items()},
        }
        print(f"[{tab}] total=PHP {total:,.2f}, payees={unique_payees}, items={items}")

    log["tasks"]["3.3_python_parallel_recompute"] = banner_log
    log["finished_at"] = datetime.now().astimezone().isoformat()
    (ROOT / "output" / "s255" / "phase3_log.json").write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")
    (ROOT / "output" / "s255" / "banner_verification.json").write_text(json.dumps(banner_log, indent=2, default=str), encoding="utf-8")
    print(f"\nPhase 3 banner written for {banner_log['updated']} tabs")
    print(f"Logs: phase3_log.json, banner_verification.json")


if __name__ == "__main__":
    main()
