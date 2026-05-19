# Team Guides — The 7+1 Cards

All training/reference cards that the AP team uses day-to-day. Read these if you need to know what a specific role does or how a specific operational task is meant to be performed.

## Card 1 — BEI AP Master Team Guide (`1HM60vlRn_...`)

**Audience:** Everyone in finance/AP.
**Length:** 6,040 chars.

**Core message:** One sheet (BEI AP Master) is the single accounts payable register. Ms. Mel types invoices. Denise (formerly Juanna) tags payment status in FPM. Cayla/Luwi tag VAT/EWT in Compliance. Within one hour all this flows to AP Master automatically.

**Section list:**
1. WHAT CHANGED AND WHY — before vs after, 7 sheets → 1 sheet rationale
2. WHICH SHEETS TO USE (AND NOT USE) — live sheets + the 4 retired ones
3. WHO OWNS WHAT — owner per piece of information
4. INSIDE BEI AP MASTER — 3 data-entry tabs (Suppliers SOA, Head Office, CAPEX) + 7 summary tabs
5. DAILY SPOT CHECK (FIRST WEEK) — 5-minute daily health check
6. OWNERSHIP DURING THE TRANSITION — Juanna→Denise handover
7. WHERE TO GET HELP — escalation map

**Key quote:** "If you need...Approval for any payment → Sam (CFO seat currently vacant)"

## Card 2 — Filing CAPEX Invoice for Ms. Mel (`1RJM-D-mD2ulflB6odtKXObN8vjteYGzvpTobzLcIhbk`)

**Audience:** Ms. Mel (AP Project Cost).
**Length:** 1,457 chars.

**Core message:** Operational checklist for filing a contractor/CAPEX invoice. Click into AP Master, navigate to CAPEX tab, fill in the 9 human-owned columns plus Store dropdown selection (required). The other 10 columns auto-fill from FPM/Compliance.

**What it links to:**
- AP Master (`1bQ6mO1FXD...`)
- Compliance AppSheet (`1QWdoZlT7...`) — for VAT lookup
- FPM (`1t4wJLi...`)
- PCM (`1_5BSZeNL...`) — Ms. Mel checks the per-store CAPEX budget here before filing

## Card 3 — Your PCM Workbook for Angela (`1nfFqae_d-LwKUA47xIMf-Bt5OZFhaAZCg5y95eWtZkY`)

**Audience:** Angela (Project Cost Monitoring).
**Length:** 1,684 chars.

**Core message:** PCM has been converted from an uploaded XLSX to a native Google Sheet. Top section per store is where Angela types budgets. Bottom section auto-fills from AP Master `CAPEX` tab via the `_CAPEX_FROM_AP_MASTER` live-feed tab. Angela's old manual paid/owed columns are RETIRED — do not re-add.

**What it links to:**
- PCM (`1_5BSZeNL...`)
- BGF, INVESTMENTS and CAPEX (`1dfIyAeGH_...`) — separate sheet for Partner Reserve, Franchise Fee, BGF capital

## Card 4 — Finance + Compliance for Juanna, Denise, Cayla, Luwi (`1VPDdnra8oPc-...`)

**Audience:** Finance + Compliance team.
**Length:** 1,875 chars.

**Core message:** Operational responsibilities split:
- **Finance (Juanna→Denise):** Manage FPM `RFP Summary` tab. Tag status (`WITH FINANCE`, `FOR REVIEW`, `FOR APPROVAL`, `FOR FUNDING`, `READY FOR ONLINE`, `CHECK RELEASED`, `Paid/ Cleared`). RFP No. assignment. Check No./Ref No. when issued. The hourly sync propagates these to AP Master.
- **Compliance (Cayla/Luwi):** Manage Compliance AppSheet Database `PO Items` and `Advance Invoices` tabs. Tag VAT and EWT per line. The hourly sync propagates these to AP Master columns Q/R/S.

**What it links to:**
- FPM, Compliance AppSheet, AP Master, plus the AP Flow Diagram

## Card 5 — BEI AP Flow Diagram (PNG, `1F6IzUYzHE2G2cVyU9x07GH_D9wohXKUr`)

**Audience:** Everyone — visual reference.
**Format:** PNG image (267 KB).

The visual flow diagram showing how a supplier invoice moves from:
1. Supplier submits paper invoice / electronic SOA
2. → Ms. Mel types into AP Master `Suppliers SOA` / `Head Office` / `CAPEX`
3. → Cayla/Luwi adds VAT/EWT tagging in Compliance
4. → Denise creates RFP in FPM
5. → Mae/Luwi review and approve
6. → Sam approves (sole approver while CFO seat vacant)
7. → Denise releases check / PESONet
8. → BDO weekly reconciliation flips status to `Paid/ Cleared`
9. → AP Master summary tabs (`PAID`, `Check Released`, etc.) update via v3 sync

## Card 6 — BEI Receiving Team Playbook (`1XOBZ1J4SO_OAkh9AG1UiB9V1wdvTDuF_ncGk60VSbBs`)

**Audience:** Cayla + Ian + Denise (the receiving team).
**Length:** 10,121 chars.

This is the S210 sprint deliverable for the **DR → GR → RFP receiving infrastructure**. See `/dr-gr-rfp` skill for full details.

The connection to AP: once a GR is created (via the receiving pipeline) and an RFP is generated, it lands in FPM → which then flows to AP Master via the v3 sync.

## Card 7 — BEI Deliveries 3PL Dock Card (`1zlb5ZAXmyN1Y_HaXOJl_rNc-6cXy-Q1d2Uw3xbIq5EY`)

**Audience:** 3MD + Pinnacle dock staff.
**Length:** 2,464 chars.

Operational dock card for logging deliveries. S210 sprint deliverable. See `/dr-gr-rfp`.

## Card 8 — BEI Supplier SI Upload FAQ (`1YERz3hHrekYoOVORTnRTumjjnMRch0hjVjLyFe3Qd9A`)

**Audience:** 98 BEI suppliers.
**Length:** 2,998 chars.

FAQ for suppliers on how to upload their Sales Invoice (SI) PDF after delivery. S210 sprint deliverable. See `/dr-gr-rfp`.

## How the cards stack together

```
Card 6 (Receiving Playbook)        — Cayla, Ian, Denise
Card 7 (3PL Dock Card)             — 3MD + Pinnacle staff
Card 8 (Supplier SI Upload FAQ)    — 98 suppliers
   ↓ flow
GR exists → RFP created in FPM
   ↓
Card 4 (Finance + Compliance)      — Denise tags status in FPM
                                   — Cayla/Luwi tag VAT in Compliance
   ↓ hourly v3 sync
Card 1 (AP Master Team Guide)      — Ms. Mel keeps invoice list current
Card 2 (CAPEX filing)              — Ms. Mel files contractor invoices
Card 3 (PCM Workbook)              — Angela monitors per-store budget
Card 5 (Flow Diagram)              — visual reference for everyone
   ↓
Sam approves → Denise releases check → BDO reconciliation flips status → AP Master PAID tab updates
```

## Critical operational rules from these cards

1. **Five-minute daily spot check** (Card 1, Section 5):
   - Open AP Master → All Liabilities
   - Pick 5 invoices, sort by aging
   - Confirm Status column matches FPM
   - Verify BILLED TO, VATABLE, VAT, EWT are filled
   - Any invoice > ₱50,000 with VAT = 0 is a BIR input VAT capture gap
   - **If anything looks off: screenshot + timestamp → Sam directly. Do not try to fix it yourself.**

2. **Approval hierarchy (Card 1, Section 6 + Card 5):**
   - Sam = sole approver (CFO seat vacant since Butch's resignation)
   - Mae = procurement-side RFP approver (≤ ₱500K direct; > ₱500K → Sam)
   - Denise = finance lead but cannot approve solo
   - Luwi = pre-approval reviewer

3. **Classification escalation (Card 1, Section 7):**
   - How to classify Supplier vs HO vs CAPEX → Juanna (until 04-27) / Denise (from 04-28)
   - VAT or EWT missing → Cayla / Luwi
   - PCM question → Angela
   - System not behaving → Sam (with screenshot + timestamp)

## Storage location on Drive

All cards are in Sam's My Drive, in the root folder. They are NOT in a "Training" subfolder (separate from the S210 training docs which are in `ERP Project / Generated Documents / Training`).

The plain-text extracts (.txt versions) are in `tmp/finance_ap_audit/extracted_text/*.txt` for quick grep.

The DOCX backups are in `tmp/finance_ap_audit/files/*.docx`.
