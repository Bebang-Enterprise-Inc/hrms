# Sprint S140 — Warehouse Setup + Full Inventory Re-sync

```yaml
sprint: S140
branch: s140-disable-inventory-sync (hooks.py change only; rest is data-only)
status: IN_PROGRESS (AUDIT: 8 blockers identified → 5 MUST-FIX applied, 3 SHOULD-FIX applied)
plan_file: docs/plans/2026-03-28-sprint-140-warehouse-setup-inventory-resync.md
depends_on: S139
registry_row: "| S140 | Sprint 140 | s140-disable-inventory-sync | #388 | IN_PROGRESS — Warehouse setup + full inventory re-sync via /frappe-bulk-edits. |"
completed_date:
execution_summary:
backend_pr: "#388 (sync disable — merged 2026-03-28)"
```

---

## Why This Exists

S139 inventory sync testing revealed three critical problems:
1. **The shadow sync code reads column A (empty) instead of column B (item codes)** — every previous sync produced zero store data.
2. **BKI warehouses don't exist in Frappe** — S138 changed code constants but never created the actual BKI company or warehouses.
3. **4 stores wrongly tagged as BKI** in the sync registry — NAIA, SM Sta. Rosa, SM Taytay, Greenhills are all BEI.

The database is currently **clean** (all inventory wiped via `/frappe-bulk-edits` Recipe 1 on 2026-03-28).

---

## Decisions (All Confirmed by Sam 2026-03-28)

| Decision | Answer |
|----------|--------|
| BKI warehouses | 6: Shaw BLVD, Commissary, 3MD, Pinnacle, Jentec, RCS |
| Commissary stock flow | Internal stock transfer ONLY (no direct PO) |
| Other BKI warehouses | Can receive PO from suppliers AND internal transfers |
| NAIA, SM Sta. Rosa, SM Taytay, Greenhills, Estancia | All BEI |
| Commissary inventory source | **SKIP for this sprint** — no Google Sheet available |
| Sync disable approach | Comment out cron in hooks.py (PR #388 merged + deployed) |
| Total locations for inventory | **51** (46 stores + 5 BKI warehouses, Commissary deferred) |

---

## Agent Boot Sequence

1. Read this plan fully.
2. Read `/frappe-bulk-edits` skill at `.claude/skills/frappe-bulk-edits/SKILL.md` — all Frappe data operations use this skill's SSM execution pattern.
3. Verify inventory cron is disabled: check `hrms/hooks.py` for commented-out `enqueue_scheduled_store_inventory_shadow_sync`.
4. Verify database is clean: `GET /api/method/frappe.client.get_count?doctype=Stock Reconciliation` should return 0.
5. Proceed to the first non-completed phase.

---

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

---

## Google Sheet Source Registry (SSOT for this plan)

### 46 BEI Store Sheets

Each store has its own Google Sheet. Inventory is on the `3. INVENTORY` tab.

| # | Code | Store | Warehouse Docname in Frappe | Sheet ID |
|---|------|-------|-----------------------------|----------|
| 1 | AFT | Fairview Terraces | Ayala Malls Fairview Terraces - BEI | `1yqww-pFFtGoSNGSCbROoXc1DkyADip_cHyXMZ4qlQi0` |
| 2 | AMM | Market Market | Ayala Market Market - BEI | `1V0_zLyKHzKw3-r0DwxED1treOucuBXmnA29UXJPZzRw` |
| 3 | ARGW | Gateway Mall | Araneta Gateway - BEI | `1aYhdmGhoHuq06OyjX4HpEafnrTOraotHFeC8sjnp9aU` |
| 4 | AYEVO | Ayala Evo | Ayala Evo - BEI | `1MaDg1lto7GijXv043e_Og7gxaJw0pMBmATbMBqjw9hw` |
| 5 | AYSOL | Ayala Solenad | Ayala Solenad - BEI | `1xtJMMD8RJG-Ax7qSzfK-XNLOCMbKqdHBLQ5xEG7BNcw` |
| 6 | AYVER | Ayala Vermosa | Ayala Vermosa - BEI | `1dtRN6O6F3vrvzlBkjbgeIw8maZzecaHBmAG6JMNWofE` |
| 7 | BFH | BF Homes | BF Homes - BEI | `1kr6xuUwZQNh7F85G6GPP-ZvqLnoY9P9PjxrA1GcxKrU` |
| 8 | CTTM | CTTM | CTTM Tomas Morato - BEI | `1bqNwE71RWrXuS_ehh1Y_oWAxZnqLl2V6olBahT3Yk3k` |
| 9 | DVCAL | Dverde Calamba | D'verde Laguna - BEI | `1XeauhRccyw9Y4Y1zo3etdT448tA0haajbsO0Mbq7J2E` |
| 10 | EGC | Ever Gotesco | Ever Commonwealth - BEI | `1foNS2gXZg3fbp-49uOaL559lxQzxqaDSsBdsdp76XuI` |
| 11 | FMA | Festival Mall | Festival Mall Alabang - BEI | `17NKaUfmfXwwCwi4YrDedmIah0E8pOT-PpvKkI569kl0` |
| 12 | LCT | Chinatown | Lucky Chinatown - BEI | `1HdM8f5rNLFVMgRiMRkf-2TWikp0VbwAP7m4JVvwS-rg` |
| 13 | MPD | Paseo De Roxas | Megaworld Paseo Center - BEI | `1HDGA3zbid63IG3eR1xzFcSczitwdjlg-1hQ5NhmFP8M` |
| 14 | NAIA | NAIA | NAIA T3 - BEI | `1ZHxSirmAwjui9qQ_JBljCVomc2aqczapZjDEf9G5MnI` |
| 15 | PTX | PITX | Megawide PITX - BEI | `1pJ0y-QpKtY5SDL4XlVneXjciBrV04UlCy9hY2wH7LGQ` |
| 16 | ROA | Rob Antipolo | Robinsons Antipolo - BEI | `1E_yZkSI7Zlz5SLm10eMp7rE8f7hl6S3Z3XB5jaAQL7E` |
| 17 | ROBGS | Rob Galleria South | Robisons Galleria South - BEI | `1VSqRaYyG-qygQibW3nAtIyxDZogmhM2G4VVYI_A7R90` |
| 18 | ROBGT | Rob Gen Trias | Robinson General Trias - BEI | `1orcPoxdj_5C2Bg_ykqNatGbb-zB4sqA8y8lpea40sis` |
| 19 | ROBIM | Rob Imus | Robinson Imus - BEI | `1bi7d7uLGxNZeTwg-2zAbGIgzaPDF8YRPMUHFpyPbHkM` |
| 20 | SJDM | SM SJDM | SJDM - BEI | `1FfJQUHF-AngAh3LsNLZutnOQe9e0c1nlG1IcF0NCHZA` |
| 21 | SLGM | Sta. Lucia | Sta. Lucia East Grand Mall - BEI | `1ajT0MJVFmrDXs7qvIfXjAlepnX1CNug63-e--CbBJ7s` |
| 22 | SMBIC | SM Bicutan | SM Bicutan - BEI | `19RxeYcBN3FiSf_WseUgJLJ6R96nbQmb7AJbl1Ahkw8Q` |
| 23 | SMCAL | SM Caloocan | SM Caloocan - BEI | `1hCBjbOJt9KaPIyrnyKzY9RYNd6_h0orkdhlAUnZV9Rw` |
| 24 | SMCLK | SM Clark | SM Clark - BEI | `1BEAsajbV05894sN3JralOJd8-pBiXVthW0qH12h2Kkg` |
| 25 | SMEO | SM East Ortigas | SM East Ortigas - BEI | `1jtpbSV_EeI_JAuawYey5uUiGQsL4RCCJsHW5xjjHG30` |
| 26 | SMGC | SM Grand Central | SM Grand Central - BEI | `1XDolAvTJ9hJDxdHBeitlTZa_pX9ybVDGdvWUuVKRRm0` |
| 27 | SMK | SM Marikina | SM Marikina - BEI | `1LKk8g8O_G-RLZUMqcVb9jnaDRr5AFYhXxF1d6NJbESM` |
| 28 | SMM | SM Manila | SM  Manila - BEI | `1VZ34rxs7iAqTvx2d7Zb5Ve276cGE5OeSepBWAp501ZQ` |
| 29 | SMMAR | SM Marilao | SM Marilao - BEI | `1pXF5UEHanspQJdGabai1MiRqFJj_5J33Wyxag1UO7HY` |
| 30 | SMMM | SM Megamall | SM Megamall - BEI | `1CR_Zmqvr4zNi5ZUgS8Eb-gNeLQgdYjR6_CHrxIhBaqI` |
| 31 | SMMOA | SM MOA | SM Mall Of Asia - BEI | `1PnSkfPF4XL1oIHneIoXqIPG8faD4sRgIYg3XxVRdJ7A` |
| 32 | SMNE | SM North | SM North EDSA - BEI | `1eGuZF9Xif4tEdsqlgfCX8qhV2fX8PJGERz_kANWbK4Y` |
| 33 | SMPUL | SM Pulilan | SM Pulilan - BEI | `1fblLNB2rMBVRMYmo764dICz-8Mp3QANzqkYGj8hlV9Y` |
| 34 | SMS | SM Southmall | SM Southmall - BEI | `1ZQY6oPc90WpDOv_-DkYfmOn-x9EztVNk1JiX9DCvcLA` |
| 35 | SMSDN | SM Sangandaan | SM Sangandaan - BEI | `1v2chqws-Fn-Gv4Lvww3Vv5HgZ4BrHt1Dg3U9o6_mFxQ` |
| 36 | SMSTR | SM Sta. Rosa | SM Sta. Rosa - BEI | `1PPvCF2r-6QtSw0us1TEuUgbzPr1ja4KAZvDg6ihbTBk` |
| 37 | SMTAY | SM Taytay | SM Taytay - BEI | `1sNSJ8uJrjDAZAZSY8ihFmUGGuia_SW3MYpTFsGTktns` |
| 38 | SMTZ | SM Tanza | SM Tanza - BEI | `1wxMtSqYgSGC_ouGjvuBjwwapB6aanwsAPTyzcHfgq84` |
| 39 | SMV | SM Valenzuela | SM Valenzuela - BEI | `1O6dqidsykQrMIxepruD1n8GG4H8pn0zss1K-_pieCWw` |
| 40 | TGR | The Grid | The Grid - Rockwell - BEI | `1ZTbTXCw4sho6W49NoZCYj27yjmW0o0030YJuq470e6U` |
| 41 | TTA | Terminal Alabang | The Terminal - BEI | `16Jh2r_aVeGYeZGLchkrHFkJwsUaLUAztWBDpPmZzVMc` |
| 42 | UMBGC | Uptown Mall | Up Town Mall BGC - BEI | `1eITKedRkLhKijPPA9x2ERcaH-e8xsOnAyTd3qYdBMUk` |
| 43 | UPTC | UP Town Center | Ayala UPTC - BEI | `128TInr6x1IK4DYs0VVYCFnslqEXlIvZR-ZhaFyR8_UA` |
| 44 | VGC | Venice Grand | Megaworld Venice Grand Canal - BEI | `1jSvqnzaoBCLjp-c7WSyNf09y9x8ltJ7BQs3SHTg8lk4` |
| 45 | VMTAG | Vistamall Taguig | Vista Mall Taguig - BEI | `1h18LRjPJ-ApAHqFkYTefI1SSqFUK0YxG_UUEqFqYmgM` |
| 46 | GHO | Greenhills Ortigas | Greenhills Ortigas - BEI | `1M5Muf_SshieMrbGevH6a2NWsS9npiH_X7aCgzkRutIA` |

**Store sheet extraction spec:**
- Tab: `3. INVENTORY`
- Column A: EMPTY (contains buttons/images — DO NOT READ)
- Column B: Item codes (RM001, CM001, FG001, PM001, etc.)
- Header row: Row 6 or 7 (contains "CODE", "ITEMS", "UOM", etc.)
- Data rows: Row 8 or 9 onward
- Row 8: Section label "Raw Materials" (skip)
- ENCODE column: **Varies per sheet** — discover by searching header row for "ENCODE" or "Total"
- The ENCODE column contains the current stock-on-hand quantity
- Skip rows where item_code does not exist in Frappe Item master

### Ian's SUMMARY 2026 Sheet (5 BKI Warehouses)

**Sheet ID:** `19Hm25vaj9gD8p6z_M6-4CPWvcXaPzAeOFKlUZ298V4s`
**Tab:** `SUMMARY 2026`
**Link:** https://docs.google.com/spreadsheets/d/19Hm25vaj9gD8p6z_M6-4CPWvcXaPzAeOFKlUZ298V4s

| Column | Header | Frappe Warehouse Docname | Company |
|--------|--------|--------------------------|---------|
| A | CATEGORY | (metadata) | — |
| B | ITEM DESCRIPTION | (metadata) | — |
| C | MATERIAL CODE | Item code for Frappe lookup | — |
| D | UOM | (metadata) | — |
| **E** | **3MD** | 3MD Logistics - Camangyanan - BKI | BKI |
| **F** | **JENTEC** | Jentec Storage Inc. - BKI | BKI |
| **G** | **RCS** | Royal Cold Storage - Taytay (RCS) - BKI | BKI |
| **H** | **PINNACLE** | Pinnacle Cold Storage Solutions - BKI | BKI |
| **I** | **SHAW** | Shaw BLVD - BKI | BKI |

- Row 1: Date header ("SOH AS OF", date)
- Row 2: Column headers (CATEGORY, ITEM DESCRIPTION, MATERIAL CODE, UOM, 3MD, JENTEC, RCS, PINNACLE, SHAW, ...)
- Row 3: Sub-headers ("REMAINING SOH" under each warehouse)
- Row 4: Section label (e.g., "DRY")
- Row 5+: Data rows with item code in column C, quantities in columns E-I
- Values may contain commas (e.g., "2,439") — strip commas before parsing as float
- Dash "-" means zero stock

### Commissary

**DEFERRED** — no inventory source identified. Will be handled in a future sprint after Sam provides the source sheet.

### Google API Credentials

- Service account: `credentials/task-manager-service.json`
- Impersonate: `sam@bebang.ph` (required for domain-wide delegation)
- Scopes: `https://www.googleapis.com/auth/spreadsheets.readonly`

```python
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

creds = Credentials.from_service_account_file(
    'credentials/task-manager-service.json',
    scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'],
    subject='sam@bebang.ph'
)
service = build('sheets', 'v4', credentials=creds)
```

### Frappe API Credentials (for verification)

- Test account: `test.warehouse@bebang.ph` / `BeiTest2026!`
- API base: `https://hq.bebang.ph`
- SSM instance: `i-026b7477d27bd46d6` (ap-southeast-1)

---

## BKI Warehouses to Create in Frappe

These warehouses do NOT exist in Frappe yet and must be created in Phase B.

| # | Warehouse Name | Company | Type | Stock Flow |
|---|---------------|---------|------|------------|
| 1 | Shaw BLVD - BKI | Bebang Kitchen Inc. | Main Warehouse | PO from suppliers + internal transfers |
| 2 | Commissary - BKI | Bebang Kitchen Inc. | Production | Internal stock transfer ONLY (no direct PO) |
| 3 | 3MD Logistics - Camangyanan - BKI | Bebang Kitchen Inc. | 3PL Cold Storage | PO + internal transfers |
| 4 | Pinnacle Cold Storage Solutions - BKI | Bebang Kitchen Inc. | 3PL Cold/Dry | PO + internal transfers |
| 5 | Jentec Storage Inc. - BKI | Bebang Kitchen Inc. | 3PL Storage | PO + internal transfers |
| 6 | Royal Cold Storage - Taytay (RCS) - BKI | Bebang Kitchen Inc. | 3PL Cold Storage | PO + internal transfers |

Also required for BKI:
- Temporary Opening account (for Stock Reconciliation expense_account)
- Default cost center

---

## Phase A: Disable Inventory Syncs (2 units) — DONE

**Status: COMPLETED** — PR #388 merged and deployed 2026-03-28.

What was disabled:
- `enqueue_scheduled_store_inventory_shadow_sync` (7 AM daily cron)
- `watch_store_inventory_shadow_sync_health` (every 10 min watchdog)

What remains active:
- Biometric digest, demand snapshot, weather, POS, procurement, discount audit, missing punch — all untouched.

---

## Phase B: Create BKI Company + Warehouses in Frappe (3 units)

| Task | Action | Skill |
|------|--------|-------|
| B1 | Create BKI company "Bebang Kitchen Inc." in Frappe (if not exists). Verify with `frappe.db.exists("Company", "Bebang Kitchen Inc.")` | `/frappe-bulk-edits` |
| B2 | Create 6 BKI warehouses (see table above). Set `company = "Bebang Kitchen Inc."`, `is_group = 0` | `/frappe-bulk-edits` |
| B3 | Create Temporary Opening account for BKI: `account_name = "Temporary Opening"`, `root_type = "Equity"`, `account_type = "Temporary"`, `company = "Bebang Kitchen Inc."` | `/frappe-bulk-edits` |

**HARD BLOCKER (B2):** Before creating the 4 external 3PL warehouses (3MD, Jentec, RCS, Pinnacle), verify whether `- BEI` versions already exist in Frappe (e.g., `3MD Logistics - Camangyanan - BEI`). The `commissary.py` code references BEI-suffixed versions. If they exist, clarify with Sam whether BKI should have separate warehouse records or share the BEI ones. Do NOT create duplicates without confirmation.

**Verify after B1-B3:**
```python
for wh in ["Shaw BLVD - BKI", "Commissary - BKI", "3MD Logistics - Camangyanan - BKI",
           "Pinnacle Cold Storage Solutions - BKI", "Jentec Storage Inc. - BKI",
           "Royal Cold Storage - Taytay (RCS) - BKI"]:
    assert frappe.db.exists("Warehouse", wh), f"Missing: {wh}"
```

---

## Phase C: Fix Sync Registry + Frappe Warehouses (2 units)

| Task | Action |
|------|--------|
| C1 | Update `hrms/fixtures/store_inventory_shadow_sync/store_inventory_shadow_sync_registry.csv` — change warehouse_docname for NAIA (`NAIA T3 - BKI` → `NAIA T3 - BEI`), SM Sta. Rosa (`SM Sta. Rosa - BKI` → `SM Sta. Rosa - BEI`), SM Taytay (`SM Taytay - BKI` → `SM Taytay - BEI`), Greenhills (`Greenhills Ortigas - BKI` → `Greenhills Ortigas - BEI`) |
| C2 | Verify these 4 warehouses exist in Frappe as BEI. If they exist as BKI, rename via `/frappe-bulk-edits`. If they don't exist, create them as BEI. Also verify Estancia warehouse exists. |

---

## Phase D: Download + Extract Inventory Data (8 units)

### D-Step 1: Download All Sheets Locally (2 units)

| Task | Action | Skill |
|------|--------|-------|
| D1 | **Download all 46 store sheets** — use Google Sheets API to export each sheet's `3. INVENTORY` tab as CSV to `tmp/s140_sheets/stores/{store_code}.csv`. One file per store. | Python + Google Sheets API |
| D2 | **Download Ian's SUMMARY 2026 sheet** — export `SUMMARY 2026` tab as CSV to `tmp/s140_sheets/bki/ian_summary_2026.csv` | Python + Google Sheets API |

**Output folder structure:**
```
tmp/s140_sheets/
├── stores/           # 46 CSV files (one per store)
│   ├── AFT.csv
│   ├── AMM.csv
│   └── ...
├── bki/              # 1 CSV file (Ian's summary)
│   └── ian_summary_2026.csv
└── exceptions/       # Any failed downloads logged here
    └── download_exceptions.json
```

**Why CSV?** Google Sheets API `spreadsheets.values.get` returns raw cell values natively. CSV avoids XLSX conversion overhead and formula evaluation issues. Each file is a direct dump of cell values — what you see is what you get.

**Retry policy:** If a sheet download fails, retry 3x with 5s backoff. If still failing, log to `download_exceptions.json` and continue.

### D-Step 2: Extract Locally with Parallel Agents (4 units)

| Task | Action | Skill |
|------|--------|-------|
| D3 | **Spawn parallel extraction agents** — split the 46 store CSVs into 4 batches (~12 stores each). Each agent runs `/extract-data` on its batch, discovers the ENCODE column per sheet by scanning the header row, reads column B for item codes, and writes per-store JSON to `tmp/s140_extracted/stores/{store_code}.json` | `/extract-data` via 4 parallel agents |
| D4 | **Extract Ian's BKI sheet** — a 5th parallel agent extracts from `ian_summary_2026.csv`: column C for item codes, columns E-I for warehouse quantities (3MD, JENTEC, RCS, PINNACLE, SHAW). Writes per-warehouse JSON to `tmp/s140_extracted/bki/{warehouse}.json` | `/extract-data` via parallel agent |

**Per-store JSON format** (`tmp/s140_extracted/stores/{store_code}.json`):
```json
{
  "store_code": "AFT",
  "source_file": "tmp/s140_sheets/stores/AFT.csv",
  "header_row": 6,
  "encode_column": "G",
  "items_extracted": 42,
  "items": [
    {"item_code": "RM001", "qty": 15.0},
    {"item_code": "CM001", "qty": 8.5}
  ],
  "exceptions": []
}
```

**Agent batch assignment:**
- Agent 1: Stores 1-12 (AFT through EGC)
- Agent 2: Stores 13-24 (FMA through SMCAL)
- Agent 3: Stores 25-36 (SMCLK through SMTAY)
- Agent 4: Stores 37-46 (SMTZ through GHO)
- Agent 5: Ian's BKI summary sheet (5 warehouses)

### D-Step 2.5: Handoff Gate + Schema Validation (1 unit)

| Task | Action | Skill |
|------|--------|-------|
| D4.5 | **Handoff gate:** Verify ALL expected output files exist: 46 files in `tmp/s140_extracted/stores/` + 5 files in `tmp/s140_extracted/bki/`. Then validate every JSON file against strict schema (must have `store_code`/`warehouse`, `items` array with `item_code` + `qty` as float). Fail fast if any file is missing or malformed. | Python validation |

### D-Step 3: Cross-Reference + Consolidate (2 units)

| Task | Action | Skill |
|------|--------|-------|
| D5 | **Cross-reference ALL extracted item codes** against Frappe Item master via bench execute in SSM: `frappe.get_all("Item", pluck="name", limit_page_length=0)`. Log any items not found to `tmp/s140_extracted/item_exceptions.json` | Cross-reference via SSM |
| D6 | **Consolidate** all per-store and per-warehouse JSONs into `tmp/s140_inventory_payload.json` — structure: `{store_code: {warehouse: "...", company: "...", items: [{item_code, qty}]}}`. Only include items that exist in Frappe Item master. | Output file |

**HARD BLOCKER (D3):** Do NOT assume all store sheets have the same column layout. The ENCODE column position varies per sheet. Read the header row of EACH sheet to find it. If ENCODE column cannot be found, log the store as an exception and continue.

**HARD BLOCKER (D1):** Column A is ALWAYS empty in store sheets (it contains buttons/images). Item codes are in column B. If you read column A, you will get zero items. This was the root cause of the entire S139 sync failure.

---

## Phase E: Full Fact-Check Before Upload (3 units)

| Task | Action | Skill |
|------|--------|-------|
| E1 | **Row-count verification** — `/fact-check-bei-erp`: for each of 51 locations, verify extracted item count in payload JSON matches the actual data row count in the downloaded CSV source file. Zero-tolerance: every location must match exactly. | Programmatic Layer 1 |
| E2 | **Cell-level verification** — `/fact-check-bei-erp`: for ALL 51 locations, re-read the downloaded CSV and compare EVERY item_code + qty pair against the extracted JSON. Report any mismatches (wrong qty, missing item, extra item). This is a full diff, NOT a spot-check. | Programmatic Layer 2 |
| E3 | **Source fidelity check** — re-read 10 random stores directly from Google Sheets API (live, not from downloaded CSV) and compare against the downloaded CSV values. This catches download corruption or stale cache. If any value differs, re-download that store's sheet and re-extract. | Google Sheets API comparison |

**Gate:** ALL 51 locations must pass E1 + E2 with zero mismatches. E3 must pass for all 10 sampled stores. Any failure = STOP, investigate, fix, and re-run the failing check before uploading.

**Why three layers?**
- E1 catches gross extraction errors (missed rows, wrong tab)
- E2 catches cell-level errors (bad float parsing, column misread, hallucinated quantities)
- E3 catches download-time errors (API returned stale data, network truncation)

---

## Phase F: Upload to Frappe (4 units)

| Task | Action | Skill |
|------|--------|-------|
| F0 | **Pre-flight:** For each warehouse_docname in payload, verify `frappe.db.exists("Warehouse", wh)`. Abort if ANY warehouse is missing — Phase C must be committed first. | SSM execution |
| F1 | Upload 5 BKI warehouse inventory via `/frappe-bulk-edits` — create one Stock Reconciliation per warehouse. **Set `allow_zero_valuation_rate = 1` on every SR item row** (BKI warehouses have no purchase history). | SSM execution |
| F2 | Upload 46 BEI store inventory via `/frappe-bulk-edits` — in batches of 10 stores per SSM command (5 batches) to avoid timeout | SSM execution |
| F3 | Each SR uses: `company` from warehouse lookup, `expense_account` = **company-scoped Temporary Opening** (resolve per company: `frappe.db.get_value("Account", {"company": sr.company, "account_type": "Temporary", "is_group": 0}, "name")`), `posting_date` = today, `frappe.db.commit()` after each SR submit | Per-warehouse commit |
| F4 | Verify zero errors in SSM stdout for all batches | Check output |

**HARD BLOCKER (F0):** Phase C (registry fix + warehouse rename) MUST be committed and verified BEFORE Phase F begins. The upload script reads warehouse_docname from the payload — if the registry still has BKI labels for NAIA, SM Sta. Rosa, SM Taytay, Greenhills, those stores will fail with `DoesNotExistError`.

**HARD BLOCKER (F1):** BKI warehouses are brand new with zero purchase history. Frappe v15 rejects SR items with zero valuation rate unless `allow_zero_valuation_rate = 1` is set per item row. Omitting this flag will cause SR submission failures for ALL BKI items.

**HARD BLOCKER (F3):** Do NOT hardcode `"Temporary Opening"` as a string. BEI stores need BEI's Temporary Opening account; BKI warehouses need BKI's Temporary Opening account (created in B3). Frappe enforces company scoping on GL accounts — a mismatch throws `ValidationError`.

**Batch approach:** 5 batches of ~10 stores each. Each batch is one SSM command with `--timeout-seconds 1800`. Each SR is committed independently (per-warehouse commit from S138 PR #386). **Idempotency guard:** Before creating each SR, check `frappe.db.get_value("Stock Reconciliation", {"warehouse": wh, "posting_date": today, "docstatus": 1}, "name")` — if a submitted SR exists, skip and log warning.

**For batch-tracked items:** Create synthetic batch IDs: `SYNC-{store_code}-{item_code}`. Check `has_batch_no` from Item master before adding batch fields. Pre-create Batch records before submitting SRs (Frappe does not auto-create batches on SR submit).

---

## Phase G: Full Item-by-Item Validation Against Google Sheets (5 units)

This is a **complete end-to-end validation** that traces every single item from the **live Google Sheet** (authoritative source) through the extraction pipeline to the **Frappe Bin** (final destination). No sampling — every item, every store, every warehouse.

### Validation Chain Per Store

```
Google Sheet (live API, UNFORMATTED_VALUE)
    ↓ column mapping (item_code col, qty col per schema)
Downloaded CSV (tmp/s140_sheets/stores/{code}.csv)
    ↓ extraction (per-sheet schema from ALL_SCHEMAS.json)
Extracted JSON (tmp/s140_extracted/stores/{code}.json)
    ↓ cross-reference (Frappe Item master filter)
Payload JSON (tmp/s140_inventory_payload.json)
    ↓ upload (Stock Reconciliation via SSM)
Frappe Bin (actual_qty in warehouse)
```

Each validation step must prove the data was not corrupted, hallucinated, or lost at any link in the chain.

| Task | Action | Skill |
|------|--------|-------|
| G1 | **Re-read ALL 46 store Google Sheets** via live API (`UNFORMATTED_VALUE`) — for each store, read the `3. INVENTORY` tab, locate the item_code column and qty column using the per-sheet schema from `ALL_SCHEMAS.json`. Build a `{item_code: qty}` lookup directly from the live sheet. | `/fact-check-bei-erp` + Google Sheets API |
| G2 | **Re-read Ian's SUMMARY 2026 sheet** via live API — for each of 5 BKI warehouses, read column C (item codes) and the warehouse's qty column (E-I). Build a `{item_code: qty}` lookup per warehouse. | `/fact-check-bei-erp` + Google Sheets API |
| G3 | **Query Frappe Bins** for ALL 51 locations via SSM — `SELECT item_code, actual_qty FROM tabBin WHERE warehouse = %s AND actual_qty > 0`. Build a `{item_code: qty}` lookup per warehouse. | `/fact-check-bei-erp` + SSM |
| G4 | **Item-by-item comparison** — for EACH of 51 locations, compare every item in the Google Sheet lookup (G1/G2) against the Frappe Bin lookup (G3). Report: (a) items in sheet but missing from Frappe, (b) items in Frappe but missing from sheet, (c) qty mismatches > 0.01, (d) items correctly skipped (not in Frappe Item master or disabled). Every single item must be accounted for — either matched, correctly skipped, or flagged as a mismatch. | `/fact-check-bei-erp` |
| G5 | **Write proof report** to `tmp/s140_verification_report.md` — for EACH of 51 locations, list: store_code, warehouse_docname, Google Sheet ID, qty_source (ENCODE or FALLBACK END col), items_in_sheet, items_in_frappe, items_matched, items_skipped (with reason), mismatches (with both values). The report must have a per-store PASS/FAIL verdict and a global PASS/FAIL. Write item-level proof to `tmp/s140_verification_detail.json`. | Report |

**Gate:** ALL 51 locations must pass with zero qty mismatches. Items not in Frappe Item master or disabled items are acceptable skips (documented in report). Any qty mismatch = STOP, investigate, and fix before proceeding to Phase H.

**HARD BLOCKER (G1):** The Google Sheet is the ONLY authoritative source. Do NOT validate against the downloaded CSV (that's Phase E territory). G1 must re-read from the live API to catch any download corruption that Phase E3's 10-store sample might have missed. Use `UNFORMATTED_VALUE` to get actual numbers, not formatted strings.

**HARD BLOCKER (G4):** Every item must be accounted for in one of these categories:
1. **MATCHED** — item_code exists in both sheet and Frappe, qty matches within 0.01
2. **CORRECTLY_SKIPPED_NOT_IN_FRAPPE** — item_code is in sheet but not in Frappe Item master (logged in `item_exceptions.json`)
3. **CORRECTLY_SKIPPED_DISABLED** — item_code is in Frappe but disabled
4. **MISMATCH** — item_code exists in both but qty differs (THIS IS A FAILURE)
5. **MISSING_FROM_FRAPPE** — item_code should be in Frappe but isn't (THIS IS A FAILURE)
6. **EXTRA_IN_FRAPPE** — item_code in Frappe Bin but not in sheet (THIS IS A FAILURE)

Categories 4, 5, 6 are failures. Categories 1, 2, 3 are acceptable. The report must show the count for each category per store.

---

## Rollback Procedures

| Scenario | Action |
|----------|--------|
| Phase F partial failure (some batches committed, some failed) | Run Recipe 1 via `/frappe-bulk-edits` to wipe ALL Stock Reconciliations, SLEs, and GLs. Then retry Phase F from scratch. Do NOT retry individual failed batches — this creates duplicate SRs. |
| Phase G reveals mismatches | Investigate the specific stores. If data is wrong, run Recipe 1 to wipe, fix extraction, re-run Phase E → F → G. |
| Phase B/C failure (orphaned BKI warehouses) | Delete orphaned warehouses via SSM: `frappe.delete_doc("Warehouse", wh_name)` for each orphaned warehouse. |
| Phase D download corruption | Re-download affected stores (D1). Re-extract (D3). Re-run Phase E. |

**Recipe 1 reference:** Tested on 2026-03-28 — deleted 132 SRs, 2,564 SLEs, 208 GLs cleanly. This is the proven rollback mechanism.

---

## Phase H: Re-enable Syncs + Closeout (2 units)

| Task | Action |
|------|--------|
| H1 | Uncomment `enqueue_scheduled_store_inventory_shadow_sync` and `watch_store_inventory_shadow_sync_health` in `hooks.py`, commit, push, create PR, wait for Sam to merge+deploy |
| H2 | Update plan YAML status to COMPLETED, update `docs/plans/SPRINT_REGISTRY.md`, commit + push with `git add -f` |

**HARD BLOCKER (H1):** Do NOT re-enable syncs until Phase G fact-check passes with 100% match for all 51 locations.

---

## Total: 28 units across 8 phases (3 agents)

| Phase | Units | Agent | Status | Description |
|-------|-------|-------|--------|-------------|
| A | 2 | — | **DONE** | Disable syncs (PR #388) |
| B | 3 | main | Pending | Create BKI company + 6 warehouses (verify 3PL duplicates first) |
| C | 2 | main | Pending | Fix registry + warehouse names |
| D (main) | 5 | main | Pending | Download 47 sheets (D1-D2), validate (D4.5), cross-ref (D5), consolidate (D6) |
| D (parallel) | 4 | 5 extraction agents | Pending | Extract 46 stores + 5 BKI warehouses |
| E | 3 | qa-delta | Pending | Full fact-check (row-count + cell-level + source fidelity) |
| F | 5 | main | Pending | Pre-flight (F0) + Upload to Frappe via SSM (F1-F4) |
| G | 3 | qa-delta | Pending | Post-upload fact-check |
| H | 2 | main | Pending | Re-enable syncs + closeout |

---

## Requirements Regression Checklist

- [ ] Are inventory syncs disabled in hooks.py? (Phase A — DONE, PR #388)
- [ ] Is column B (not A) being read for item codes from store Google Sheets?
- [ ] Is the ENCODE column discovered per-sheet by scanning the header row?
- [ ] Is Ian's SUMMARY 2026 read from column C (item codes) and E-I (warehouse SOH)?
- [ ] Are NAIA, SM Sta. Rosa, SM Taytay, Greenhills tagged as BEI (not BKI)?
- [ ] Does every uploaded item_code exist in Frappe Item master?
- [ ] Is Commissary inventory SKIPPED (no source available)?
- [ ] Is fact-check FULL (cell-level, not spot-check) BEFORE upload (Phase E) and AFTER upload (Phase G)?
- [ ] Does Phase E include source fidelity check (re-read from live Google Sheets API vs downloaded CSV)?
- [ ] Are extraction agents run in parallel (5 agents: 4 store batches + 1 BKI)?
- [ ] Are syncs re-enabled ONLY after Phase G fact-check passes 100%?
- [ ] Does every Stock Reconciliation use company-scoped Temporary Opening (resolved per company, NOT hardcoded)?
- [ ] Does Phase F set `allow_zero_valuation_rate = 1` for BKI warehouse items?
- [ ] Is Phase C committed and verified BEFORE Phase F begins (warehouse existence pre-flight)?
- [ ] Does the upload script check for existing submitted SRs before creating (idempotency guard)?
- [ ] Are 3PL warehouse docnames verified against existing BEI-suffixed warehouses before BKI creation?
- [ ] Is qa-delta agent (not main agent) running E1-E3 and G1-G3?
- [ ] Is `frappe.db.commit()` called after each SR submit (per-warehouse commit)?

---

## Autonomous Execution Contract

- completion_condition:
  - All 51 locations (46 stores + 5 BKI warehouses) have inventory in Frappe
  - Post-upload fact-check passes 100% for all 51 locations
  - Syncs re-enabled (PR merged + deployed)
  - Plan YAML status updated to COMPLETED and pushed to production
  - SPRINT_REGISTRY.md row updated to COMPLETED and pushed to production
- stop_only_for:
  - Phase E: ANY fact-check failure (zero tolerance) — do NOT proceed to Phase F with mismatches
  - Phase G: ANY fact-check failure (zero tolerance) — do NOT proceed to Phase H with mismatches
  - Phase F: ANY SSM batch failure after at least one batch committed — run Rollback before retry
  - Phase H: PR creation requires user merge
  - SSM credential issues
- continue_without_pause_through:
  - B, C, D, F (data operations)
- blocker_policy:
  - missing Item in Frappe -> skip item, log to exceptions file
  - Google Sheet API error -> retry 3x, then flag store as exception
  - SSM timeout -> split into smaller batches
  - BKI company already exists -> skip creation, continue
- agent_split:
  - main_agent (10 units): D1, D2, D5, D6, F0, F1, F2, F3, F4, H1, H2 — max_turns=30
  - qa_delta_agent (6 units): E1, E2, E3, G1, G2, G3 — max_turns=25 (separate agent verifies main agent's work)
  - extraction_agent_1-4 (1 unit each): D3 store batches — max_turns=25
  - extraction_agent_5 (1 unit): D4 BKI sheet — max_turns=25
  - checkpoint: after D6 (main), after E3 (qa_delta), after F4 (main)
  - handoff_gate_D5: Do NOT proceed to D5 until ALL 51 expected JSON files exist in tmp/s140_extracted/ (46 store + 5 BKI)
- signoff_authority: single-owner (Sam)
- canonical_closeout_artifacts:
  - `tmp/s140_sheets/` (downloaded source CSVs — 46 store + 1 BKI)
  - `tmp/s140_extracted/` (per-store/warehouse extraction JSONs from parallel agents)
  - `tmp/s140_inventory_payload.json` (consolidated extraction output)
  - `tmp/s140_pre_upload_factcheck.md` (Phase E full fact-check report)
  - `tmp/s140_verification_report.md` (Phase G post-upload fact-check)
  - `docs/plans/2026-03-28-sprint-140-warehouse-setup-inventory-resync.md` (this plan)
  - `docs/plans/SPRINT_REGISTRY.md`

---

## Design Rationale (For Cold-Start Agents)

**Why manual pipeline instead of automated sync?**
The automated shadow sync (`store_inventory_shadow_sync.py`) reads the Google Sheets via the Sheets API, but the sync code's column mapping is wrong — it reads column A (empty, contains buttons/images) instead of column B (where item codes actually are). This was discovered during S139 testing on 2026-03-28 when the fact-check showed 0 items for sheets that clearly had inventory data. Fixing the sync code would require a code change + deploy + re-test cycle. The manual pipeline bypasses this bug entirely.

**Why disable syncs?**
The inventory sync cron fires at 7 AM PHT daily. If it runs during our upload, it will create duplicate Stock Reconciliations (one from the manual upload, one from the cron). The sheets-receiver's inventory webhook could also trigger on Ian's sheet changes. Both must be paused during the re-sync window.

**Why `/frappe-bulk-edits` via SSM instead of the sync API?**
The sync API (`erp_sync.sync_inventory`) inherits the column A bug from the shadow sync builder. Direct Frappe insertion via SSM gives us full control. This approach was tested on 2026-03-28 with 5 stores (231 items, zero failures) before being used for the full wipe (Recipe 1: 132 SRs, 2,564 SLEs, 208 GLs deleted cleanly).

**Why download locally instead of processing via API?**
The Google Sheets API can return stale cached data, and processing 47 sheets over repeated API calls is slow and rate-limit-prone. Downloading once to local CSVs creates an immutable snapshot that can be: (1) processed in parallel by multiple agents without API contention, (2) re-read for fact-checking without hitting the API again, (3) kept as an auditable artifact. The source fidelity check (Phase E3) samples 10 stores from the live API to verify the download wasn't corrupted.

**Why parallel extraction agents?**
46 store sheets + 1 BKI sheet = 47 files to parse. Sequential processing takes ~15-20 minutes. Splitting into 5 parallel agents (~12 stores each + 1 BKI agent) cuts extraction time to ~4 minutes. Each agent works on local files only — no shared state, no API contention, no race conditions.

**Why fact-check twice?**
Pre-upload fact-check (Phase E) catches extraction errors — wrong column read, bad float parsing, missing item codes. Post-upload fact-check (Phase G) catches Frappe insertion errors — missing Items rejected by Frappe, batch creation failures, valuation rate issues. The error modes are different, so both checks are needed.

**Why skip Commissary?**
Sam confirmed Commissary is a separate warehouse from Shaw BLVD that receives stock only via internal transfer (no PO). There is no Google Sheet with Commissary inventory data. Ian's SUMMARY 2026 sheet does not have a Commissary column. Commissary inventory will be handled in a future sprint once the source is identified.
