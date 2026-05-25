# Team Training — Sheet Access Map (2026-05-14)

> **One-page reference** for every Finance / AP / Compliance / SCM person. Tells you exactly which sheet you use, which tabs you edit, which tabs you don't touch, and how your edits flow to the AP Master.
>
> All sheet links are clickable. Read the section for YOUR role.
>
> **Lock verification (2026-05-20, updated S255):** All 6 AP Master writers tested against all 16 locked tabs (including Intercompany added in S255). **96 / 96 lock checks PASS.** Result file: `output/s255/lock_test_post_v1.json`.

---

## The 8 sheets you might see (with role-based access)

| Sheet | Open in browser | Owner | Used by |
|---|---|---|---|
| **BEI AP Master** | [open ↗](https://docs.google.com/spreadsheets/d/1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c/edit) | Sam | Everyone reads; Ms. Mel + Denise + Avis + Bethina + Izza + Je-Ann write to entry tabs |
| **FPM (Finance Payment Monitoring)** | [open ↗](https://docs.google.com/spreadsheets/d/1t4wJLiAfIMJm6fe-x6h4eZn_S_Lx1AGN5ORd5Ywhcyw/edit) | Denise | Denise + Je-Ann process RFPs; many readers |
| **Procurement Compliance AppSheet** | [open ↗](https://docs.google.com/spreadsheets/d/1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q/edit) | Sam | Cayla + Luwi + Ashish + Ian (SCM) write; Avis reads |
| **Bebang Project Cost Monitoring (PCM)** | [open ↗](https://docs.google.com/spreadsheets/d/1_5BSZeNL9A_o5QO6WD4L42gGjYY6-yCDfgTp01y0fpo/edit) | Sam | Angela (top section per store); Avis writes |
| **BGF, INVESTMENTS and CAPEX** | [open ↗](https://docs.google.com/spreadsheets/d/1dfIyAeGH_5ga_mjA1o-WWN9xM6VO3v7XKKoU1Jtq1eI/edit) | Mae | Angela (Partner Reserve, Franchise Fee, BGF capital) |
| **BEI Bank Balances — LIVE** | [open ↗](https://docs.google.com/spreadsheets/d/19kSR8HQdveZVleMZORGQetHXVCxaeDy6EMlKfe2G77w/edit) | Sam | Denise + Je-Ann + Avis update daily |
| **CASHFLOW TRACKER — CEO** | [open ↗](https://docs.google.com/spreadsheets/d/1W2GERTwbODqfbHM70XpJJEtFwL-jIPbb2zzwC0Rcfeg/edit) | Sam | CEO dashboard; Avis writes; Denise + Mae + Dom read |
| **Project: 2-Week Payment Plan (Denise's)** | [open ↗](https://docs.google.com/spreadsheets/d/13cyYaPLmjL0TPaeqyYd2esjJNYj-5qJCDS8OZLdhURU/edit) | Denise | Denise's own 2-week pay-plan tracker. Will retire when she switches to AP Master `Payment Plan` tab. **Bridge (fractional CFO / DD auditor) also writes here — authorized.** |

---

## Per-role instructions

### 🟦 Ms. Mel (Angelamel Letada — AP data entry)

**Your job:** Type every NEW invoice into AP Master. Each invoice goes into ONE of three tabs.

**Use this sheet:**
- 🔗 **[BEI AP Master](https://docs.google.com/spreadsheets/d/1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c/edit)**

**Type into THESE tabs only** (you have write access):

| Tab | What goes here | Required |
|---|---|---|
| **Suppliers SOA** | Inventory supplier invoices (food, packaging, ingredients) | PAYEE, INVOICE NO., INVOICE DATE, AMOUNT |
| **Head Office** | HO operating expenses (rent, utilities, services, reimbursements) | PAYEE, INVOICE NO., INVOICE DATE, AMOUNT |
| **CAPEX** | Contractor / project / equipment invoices | PAYEE, INVOICE NO., AMOUNT, **STORE dropdown** |

**Do NOT type into these tabs** (they're auto-rebuilt by the script every hour — your entries will be wiped):

❌ `All Liabilities` ❌ `Summary` ❌ `Commissary` ❌ `Head Office (BEI)` ❌ `Needs Attention`
❌ `Needs RFP` ❌ `With Finance (No RFP)` ❌ `Check Released` ❌ `In Pipeline` ❌ `VAT Gaps`
❌ `PAID` ❌ `_sync_log` ❌ `_sync_log_v3` ❌ `_dry_run_preview` ❌ `Payment Plan`

**System enforces this:** if you try to edit any of these 15 tabs, Google shows you a "protected cell" error. **Tested and verified 2026-05-14.**

**What happens after you type:**
1. Your row sits in the entry tab as you typed it
2. Within 1 hour, the script reads FPM (Denise's status updates) and Compliance (Cayla's VAT tags) and auto-fills the matching columns
3. Within the same hour, your row appears in `All Liabilities` and `Needs RFP` (read-only summary tabs)

**Don't touch:**
- ❌ FPM — that's Denise's territory
- ❌ Compliance AppSheet — that's Cayla/Luwi/Ian's territory
- ❌ PCM — that's Angela's territory
- ❌ Bank Balances, Cashflow Tracker — read-only for you
- ❌ Denise's 2-Week Payment Plan sheet — don't even open

---

### 🟦 Denise (Finance Lead)

**Your job (now):** Tag payment status in FPM, manage the 2-week pay plan, approve check releases.
**Your job (after the Payment Plan tab cutover):** Same, but typed directly into AP Master `Payment Plan` tab instead of your standalone sheet.

**Use these sheets:**
- 🔗 **[FPM](https://docs.google.com/spreadsheets/d/1t4wJLiAfIMJm6fe-x6h4eZn_S_Lx1AGN5ORd5Ywhcyw/edit)** — you OWN this; tag Status, RFP No., Check No., Method, BDO Cleared Date
- 🔗 **[Your 2-Week Payment Plan](https://docs.google.com/spreadsheets/d/13cyYaPLmjL0TPaeqyYd2esjJNYj-5qJCDS8OZLdhURU/edit)** — your current workspace (4 tabs: Suppliers w/o FD & Middleby, Middleby, Forward Dynamics, Masterlist)
- 🔗 **[Bank Balances](https://docs.google.com/spreadsheets/d/19kSR8HQdveZVleMZORGQetHXVCxaeDy6EMlKfe2G77w/edit)** — daily bank balance updates
- 🔗 **[AP Master](https://docs.google.com/spreadsheets/d/1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c/edit)** — preview your data in `Payment Plan` tab (auto-mirrored hourly from your sheet); writer access to entry tabs for emergency edits

**About the new `Payment Plan` tab in AP Master:** It is **populated and refreshed every hour** from your sheet. You see your familiar 30-column layout (Address, TIN, VAT/Nonvat, Terms, Description, separate aging columns, etc.). **Don't type there yet** — strict-locked while in mirror mode. When you're ready to switch, tell Sam and we'll relax the lock + stop the auto-mirror so your edits are kept.

**Do NOT type into these tabs on AP Master:**
❌ Same 15 locked tabs as Ms. Mel (verified locked against your account)

**Don't touch:**
- ❌ Compliance AppSheet — Cayla/Luwi/Ian own it
- ❌ PCM — Angela
- ❌ BGF — Angela
- ❌ Cashflow Tracker — Sam's dashboard (you have READ ONLY access here, which is intentional)

---

### 🟦 Je-Ann (RFP processing in FPM)

**Your job:** Process Request-for-Payment forms in FPM. Update RFP numbers, check numbers, payment methods, processed dates.

**Use this sheet:**
- 🔗 **[FPM](https://docs.google.com/spreadsheets/d/1t4wJLiAfIMJm6fe-x6h4eZn_S_Lx1AGN5ORd5Ywhcyw/edit)** — write access; primary tab `RFP Summary`

**Reference reads (don't write):**
- 🔗 [AP Master](https://docs.google.com/spreadsheets/d/1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c/edit) — see invoice context (you have writer access but normally don't type here — Ms. Mel does)
- 🔗 [Bank Balances](https://docs.google.com/spreadsheets/d/19kSR8HQdveZVleMZORGQetHXVCxaeDy6EMlKfe2G77w/edit) — daily balance updates if you cover for Denise

**Do NOT touch:**
- ❌ The 15 locked AP Master tabs (Google enforces this — verified against your account)
- ❌ Compliance AppSheet — not your area
- ❌ PCM, BGF — Angela's

---

### 🟦 Cayla & Luwi (Compliance — VAT/EWT tagging)

**Your job:** Tag VAT, EWT, vatable status in the Compliance AppSheet. The script reads YOUR tags hourly and auto-fills the VAT/VAT-amount/EWT columns on AP Master entry tabs.

**Use this sheet:**
- 🔗 **[Procurement Compliance AppSheet](https://docs.google.com/spreadsheets/d/1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q/edit)** — write access via the AppSheet app
  - Tabs you tag: `PO Items`, `Advance Invoices`, `Suppliers`

**Do NOT touch:**
- ❌ AP Master — your tags flow there AUTOMATICALLY via the hourly sync. Don't type in any AP Master tab.
- ❌ FPM — Denise's
- ❌ PCM, BGF, Bank Balances, Cashflow Tracker

---

### 🟦 Ian (SCM head)

**Your job:** Log Goods Receipts in Compliance AppSheet when deliveries arrive at 3PL warehouses.

**Use this sheet:**
- 🔗 **[Procurement Compliance AppSheet](https://docs.google.com/spreadsheets/d/1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q/edit)** — primary tab `Goods Receipts`

**Do NOT touch:**
- ❌ AP Master — your GR confirmations flow there via the PO → GR → SI pipeline. Don't type directly.
- ❌ FPM — Denise's
- ❌ Anything else

---

### 🟦 Angela (Project Cost Monitoring)

**Your job:** Maintain per-store CAPEX budgets in PCM. The bottom section auto-fills from AP Master CAPEX tab — never manually edit it.

**Use these sheets:**
- 🔗 **[PCM](https://docs.google.com/spreadsheets/d/1_5BSZeNL9A_o5QO6WD4L42gGjYY6-yCDfgTp01y0fpo/edit)** — type budgets in the TOP section of each per-store tab. The BOTTOM section is live-fed from AP Master and is read-only-by-convention (script overwrites it).
- 🔗 **[BGF, INVESTMENTS and CAPEX](https://docs.google.com/spreadsheets/d/1dfIyAeGH_5ga_mjA1o-WWN9xM6VO3v7XKKoU1Jtq1eI/edit)** — Partner Reserve, Franchise Fee, BGF capital (you're an editor)

**Do NOT touch:**
- ❌ AP Master entry tabs — that's Ms. Mel's territory (you're not even on the writer list, so you'd see "view only")
- ❌ FPM, Compliance AppSheet — not your area
- ❌ The BOTTOM section of PCM per-store tabs (`_CAPEX_FROM_AP_MASTER` live-feed) — auto-overwritten

---

### 🟦 Avis Lyndelle Principe (Compliance / cross-functional reader)

**Your job:** Audit + cross-functional read; recently upgraded to writer on AP Master so you can correct Ms. Mel's entries when needed.

**Use these sheets:**
- 🔗 **[AP Master](https://docs.google.com/spreadsheets/d/1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c/edit)** — writer; only edit entry tabs (Suppliers SOA / Head Office / CAPEX)
- 🔗 **[FPM](https://docs.google.com/spreadsheets/d/1t4wJLiAfIMJm6fe-x6h4eZn_S_Lx1AGN5ORd5Ywhcyw/edit)** — writer for back-up
- 🔗 **[PCM](https://docs.google.com/spreadsheets/d/1_5BSZeNL9A_o5QO6WD4L42gGjYY6-yCDfgTp01y0fpo/edit)** — writer (back-up Angela)
- 🔗 **[Bank Balances](https://docs.google.com/spreadsheets/d/19kSR8HQdveZVleMZORGQetHXVCxaeDy6EMlKfe2G77w/edit)** — writer
- 🔗 **[Cashflow Tracker](https://docs.google.com/spreadsheets/d/1W2GERTwbODqfbHM70XpJJEtFwL-jIPbb2zzwC0Rcfeg/edit)** — writer
- 🔗 [Compliance AppSheet](https://docs.google.com/spreadsheets/d/1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q/edit) — READER (don't edit; ask Cayla/Luwi if a tag is wrong)

**Do NOT touch:**
- ❌ Any of the 15 locked AP Master tabs (system enforces this — verified)
- ❌ Anyone else's standalone sheet

---

### 🟦 Bethina, Izza (writers on AP Master)

Same rules as Ms. Mel — use only the 3 entry tabs. All 16 locked tabs are blocked at the system level. Tested and verified.

---

### 🟦 Joevic Almajar (Supplier Payments)

**Your job:** Handle supplier payment processing (confirmed by Denise, S255 closeout 2026-05-21).

**Use this sheet:**
- 🔗 **[Denise's 2-Week Payment Plan](https://docs.google.com/spreadsheets/d/13cyYaPLmjL0TPaeqyYd2esjJNYj-5qJCDS8OZLdhURU/edit)** — editor access (kept per Denise A3)

**Do NOT touch:**
- ❌ AP Master locked tabs (system enforces this)
- ❌ FPM — Denise/Je-Ann's territory unless directed

---

### 🟦 Sam (CEO)

You own everything. You can edit any tab. Use the read-only summary tabs (`All Liabilities`, `PAID`, etc.) for at-a-glance dashboards. **NEVER manually edit auto-rebuilt tabs unless intentionally fixing a script-output issue — your edits will be wiped on the next hourly run.**

---

## How your edits flow to AP Master (the picture)

```
┌──────────────────────┐         ┌──────────────────────────┐
│  Ms. Mel types here  │ ───→    │ AP Master entry tabs:    │
│  3 entry tabs        │         │ - Suppliers SOA          │
│  (writes preserved)  │         │ - Head Office            │
│                      │         │ - CAPEX                  │
└──────────────────────┘         └─────────────┬────────────┘
                                               │
┌──────────────────────┐                       ↓ (hourly auto-sync xx:12 PHT)
│  Denise tags status  │ ───→ FPM ───→ ┌──────────────────────┐
│  in FPM (RFP Summary)│               │  AP Master summary   │
└──────────────────────┘               │  tabs (READ-ONLY):   │
                                       │  - All Liabilities   │
┌──────────────────────┐               │  - Needs RFP         │
│  Cayla/Luwi tag      │ ───→ Compl ──→│  - Check Released    │
│  VAT/EWT in          │               │  - In Pipeline       │
│  Compliance AppSheet │               │  - VAT Gaps          │
└──────────────────────┘               │  - PAID              │
                                       │  - Payment Plan      │
┌──────────────────────┐               │    (Denise's mirror) │
│  Denise types in her │ ───→ ─────────│                      │
│  2-Week Payment Plan │               │                      │
│  sheet (4 tabs)      │               └──────────────────────┘
└──────────────────────┘
```

---

## What's NEW since 2026-05-13/14

### Phase 0-3 (PR #751, merged 2026-05-14)
- The hourly Cloud Scheduler now also reads from Denise's 4-tab payment plan sheet and seeds new rows into AP Master `Suppliers SOA` (tagged `SOURCE = 'Denise PP'` or `'Denise PP - Disputed (Middleby)'` etc.)
- **278 of Denise's rows already in AP Master** since 2026-05-13

### Phase 5-6 (PR #752, awaiting merge)
- New `Payment Plan` tab in AP Master (green-tabbed, 30 columns, sheetId `2073065932`)
- 422 rows currently mirrored from Denise's sheet
- Refreshed every hour at xx:12 PHT
- Strict-locked to sam@bebang.ph only **during the mirror phase** — Denise has the option to switch over whenever she's ready

### What this means for you
- **Ms. Mel:** No change. Keep typing in Suppliers SOA / Head Office / CAPEX.
- **Denise:** Choice. Keep using your standalone sheet (still mirrored automatically), OR tell Sam when you want to switch to working directly in AP Master `Payment Plan` tab. Either works.
- **Everyone else:** No change.

### S255 (PR #760, merged 2026-05-20) — AP v3.9 deployed
- New `Intercompany` tab added — Bebang-entity fund transfers auto-route here instead of Head Office
- 331 rows migrated to Intercompany; 19 duplicate rows cleaned
- All 16 tabs now strict-locked (was 15; Intercompany added). **96/96 lock checks PASS.**
- Denise PP ACL trimmed: Bea Garcia (intern, left), Liezel Acero, Maika Talisayon removed
- Bridge (fractional CFO / DD auditor) granted reader on AP Master + FPM + Compliance + Bank Balances + Cashflow + PCM
- Joevic Almajar confirmed as Supplier Payments handler (Denise A1)

### S256 (in-flight) — AP v3.10
- Intercompany broadened to 14 non-Bebang affiliated entities (per Denise's signed Section B addendum)
- 3PL bypass suppliers (3MD, Pinnacle, RCS, Fourkoolitz, Suzuyo) auto-tagged 'Denise PP - Manual' at seed time
- Procurement App now feeds Suppliers SOA (per Denise D2 source-of-truth directive)
- HO opening balance one-shot seed from `05 - AP Opening Balance Head Office`
- FPM-SOA-aware dedup prevents the script from re-adding already-tracked invoices
- Bridge PII audit: no employee personal info or salary data found on any of the 5 upstream sheets. Bridge can see all tabs safely.

---

## Lock verification — proof every locked tab is enforced

Tested 2026-05-14 with the service account impersonating each AP Master writer. Each writer was asked to write to all 15 locked tabs. **Every attempt was blocked** by Google with the message "You are trying to edit a protected cell or object."

| Writer | Entry tabs writable | Locked tabs blocked | Lock failures |
|---|---:|---:|---:|
| angelamel@bebang.ph (Ms. Mel) | 3 / 3 ✓ | 15 / 15 ✓ | 0 |
| avislyndelle@bebang.ph | 3 / 3 ✓ | 15 / 15 ✓ | 0 |
| bethina@bebang.ph | 3 / 3 ✓ | 15 / 15 ✓ | 0 |
| denise@bebang.ph | 3 / 3 ✓ | 15 / 15 ✓ | 0 |
| izza@bebang.ph | 3 / 3 ✓ | 15 / 15 ✓ | 0 |
| je-ann@bebang.ph | 3 / 3 ✓ | 15 / 15 ✓ | 0 |

**90 / 90 lock checks pass.** Test artifact: `tmp/finance_ap_audit/audit_2026-05-13/impersonate_lock_test_results.json`.

If a team member ever tries to edit a locked tab they'll see a popup like this:

> 🛑 **You are trying to edit a protected cell or object.**
> Please contact the spreadsheet owner to remove protection if you need to edit.

That's the system working as designed. They should **not** ask Sam to remove protection — they should ask "which tab am I supposed to type in?" and refer back to this training.

---

## Escalation map

| You see this | Ask |
|---|---|
| "protected cell" popup | Refer to this guide → use the correct entry tab |
| Invoice missing from AP Master after typing | Wait 1 hour for hourly sync; if still missing after 2 hours, ping Sam |
| VAT/EWT wrong on AP Master row | Cayla / Luwi (they tag it in Compliance; the script propagates) |
| RFP status wrong | Denise / Je-Ann (they tag it in FPM) |
| Bank balance mismatch | Denise / Je-Ann |
| CAPEX row routed to wrong store | Angela (she controls per-store CAPEX in PCM) |
| Want to add a NEW supplier | Cayla / Luwi (they onboard in Compliance AppSheet `Suppliers` tab) |
| Approval needed | **Sam directly** (CFO seat vacant; Sam approves alone) |

---

**End of training. Bookmark this file:** `.claude/skills/finance-ap/references/team-training-2026-05-14.md` or ask Sam to share the rendered Google Doc version (forthcoming).


## SOURCE class additions (S255 — 2026-05-20)

When filtering or reading AP Master rows by SOURCE column, recognize:

- **`Denise PP - Manual`** — invoices that bypass the procurement AppSheet (e.g. 3M Dragon). Detect by INVOICE NO. starting with `Invoice No.` text. These rows skipped the standard PR/PO/GR/RFP flow; Bridge will want them tagged separately during DD audit.


## Filter Views on AP Master Payment Plan tab (S255 — 2026-05-20)

Two native Sheets filter views were added on the AP Master Payment Plan tab, mirroring Angela's old tabs from Project: 2-Week Payment Plan:

| Filter view | Filters where | Sample today |
|---|---|---|
| **Scheduled for Online Transfer - Due** | col I (STATUS) = `FOR ONLINE PAYMENT` | 7 rows |
| **Scheduled for Release Check - Due** | col I (STATUS) IN (`CHECK READY`, `CHECK RELEASED`) | 73 rows |

**How to use:** AP Master → Payment Plan tab → filter funnel icon → "Filter views" → pick view.

These filter LIVE off col I which is maintained by the script's `mapDeniseToApStatus_` mapping (Denise's raw STATUS → AP-vocab). No data duplication, no manual refresh.

When Denise transitions off her standalone sheet, Sam toggles `payment_plan_mirror_disabled=true` and the mirror stops; status sync starts writing PP col I directly.
