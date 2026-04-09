# S175 Locked Decisions + Fee Routing Matrix

**All decisions are locked as of 2026-04-09 23:00 PHT.** Every decision cites its source (chat, contract, audit, or this session). Any change requires a new `COA-175-###` decision block that supersedes an existing one — never silent edit.

---

## Section A: Locked Decisions

### COA-175-001 — Master COA template source
**Decision:** The canonical GL Sales Accounts Set-up is Butch Formoso's 2026-04-08 10:18 AM PHT table in the Accounting Private chat space.
**Scope:** 4000000 Sales tree structure (see `01_CANONICAL_COA_TEMPLATE.md` Section A).
**Source:** `data/_CLEANROOM/chat_evidence/2026-04-08_butch_gl_sales/DL97trTZUFA.DL97trTZUFA__Screenshot_2026-04-08_at_10.17.04_AM.png` (image attachment in Butch's chat message) + `data/_CLEANROOM/chat_evidence/2026-04-08_butch_gl_sales/transcript.md` (full thread).
**Verification:** Chat harvest 2026-04-09 via service-account-impersonate-sam with Chat API. **SUPPORTED with nuance** — the plan v1 template captured all of Butch's explicit rows; expansion slots (4000124+, 4000236+, 4000300-4000800) are now preserved per `01_CANONICAL_COA_TEMPLATE.md` Section C.

### COA-175-002 — DISCOUNTS AND PROMO renumber
**Decision:** `DISCOUNTS AND PROMO` moves from `4000200` (which becomes `BKI SALES`) to `4000900` as a contra-revenue range. Child accounts renumber to `4000901-4000908`.
**Source:** Butch Formoso, Accounting Private chat, 2026-04-08 21:48:41 PHT (verbatim): *"Option A under 4000900 so that all contra-revenue such as SC/PWD/employee/free halo-halo/refund will be presented together. Plus, if there is a new revenue stream, the company can use the 4000300 group to 4000800 group. This is just my take. God Bless always."*
**Verification:** SUPPORTED via chat harvest.
**Supersedes:** Butch's 2026-02-12 COA-004 lock (Sales Discounts 4000201-4000207 + Employee Benefit Expense 4000208).

### COA-175-003 — Uniform COA across all 40 companies
**Decision:** Every Frappe Company in the Bebang Group gets the FULL 27-account structural Sales tree. Each company populates only its relevant sub-tree (see `01_CANONICAL_COA_TEMPLATE.md` Section D).
**Source:** Sam Karazi architectural decision, 2026-04-08, this session. No Butch veto.
**Rationale:** Enables PFRS 10 consolidation, intercompany eliminations, store-vs-store comparability, audit efficiency, new-entity quick-start, operator mobility across entities.

### COA-175-004 — INTERIM revenue recognition policy — SUPERSEDED BY COA-175-013
**Decision (original):** All franchise fees settle to BEI until BFC has an operating bank account; BFC's FEES sub-tree empty as hot standby.
**Source:** Sam Karazi pragmatic decision 2026-04-09 after Butch confirmed BFC has no bank account.
**Status:** **SUPERSEDED by COA-175-013 (Fork 1)** — see below. The decision-point was whether to book BEI's interim cash receipts as BEI revenue or as a liability to BFC. We picked liability (Fork 1).

### COA-175-005 — Phase 2 cutover pattern
**Decision:** When BFC's operating bank account opens, franchisees pay BFC directly per signed contracts. BFC→BEI intercompany services agreement drafted separately (out of S175 scope).
**Source:** Butch Formoso, Accounting Private chat, 2026-04-09 10:37:14 PHT (verbatim): *"If the contract with franchise states that all fees will be payable to BFC, and BFC will just pay BEI, then this should be the standard process to be embedded in our ERP."*
**Verification:** SUPPORTED via chat harvest.
**Supersedes:** Butch's 2026-04-08 PM directive (Royalty→BFC, Management/Marketing/E-Comm→BEI).

### COA-175-006 — BFC legal entity facts
**Decision:** BFC legal entity exists under the name **BEBANG FRANCHISE CORP.** (not "Inc.").
- SEC Reg No: `2025030195371-03` (27 March 2025)
- BIR TIN: `672-618-804-00000` (3 April 2025)
- RDO: 044 — Taguig/Pateros (Revenue Region 08B — South NCR)
- Taxpayer type: Domestic Corporation, VAT-registered
- Principal Office: 2409 Capital House, 9th Avenue corner Lane S, Fort Bonifacio, Taguig City
- Authorized capital: PHP 6,000,000.00 (60,000 shares @ PHP 100 par)
- Subscribed/Paid-up: PHP 1,500,000.00 (15,000 shares, all paid in cash)
- Ownership: **BEI 79.97%** (11,996 shares via Bebang Enterprise Inc. rep Daymae Salumbides Karazi) + **Samer Karazi 20.00%** (3,000 shares) + 4 qualifying shares 0.03%
- Treasurer: Daymae Salumbides Karazi
- Board: Samer Karazi, Daymae Salumbides Karazi, Hernando Diokno Hernandez, Paolo Miguel Gatan Sunga, Michaelvin Gabrielle Rosales Chiong (5 directors)
**Source:** `data/_CLEANROOM/2026-04-08_franchise_corp_extract/00_INDEX.md` (verified against `01_COI.md`, `02_AOI.md`, `03_BYLAWS.md`, `04_BIR_2303.md` extracted from originals in `F:\Downloads\FRANCHISE_CORP-20260408T110843Z-3-001\`).

### COA-175-007 — JV fees flow permanently to BEI
**Decision:** The Grand Central Gabaldon JV Agreement routes all fees to BEI:
- **5% Brand Marketing** (Sec 8.1) → BEI
- **5% E-Commerce Platform** (Sec 9.1) → BEI
- **₱2,000,000 Brand Growth Fee** (Sec 2) → BEI (one-time, paid within 15 days of execution)

This is **permanent**, not interim. JV fees post to BEI's `4000234 MARKETING FEES` and `4000235 E-COMMERCE FEES` (and a dedicated `4000005 BRAND GROWTH FEE INCOME - BEI` kept for legacy GL).
**Source:** `data/_CLEANROOM/2026-04-09_franchise_agreements/01_JV_Agreement_Grand_Central_Gabaldon.md` (PDF-verified 20/20 claims) — signed **3 January 2025** (not 2026 as plan v1 mistakenly stated).
**Verification:** SUPPORTED via direct PDF fact-check (`tmp/s175_fact_check/01_jv_gabaldon.txt` line 1141).

### COA-175-008 — Franchise fees contractually flow to BFC (corrected)
**Decision:** Per the signed Franchise Agreement template (unexecuted), **4 fees** flow to BFC:
- **₱2,000,000 Franchise Fee + VAT** (§I.A) → BFC (one-time, upon franchise execution)
- **7% Continuing Services and Royalty Fee** (§XIII.A) → BFC (monthly, gross of VAT)
- **5% Marketing Support Fee** (§XI.A) → BFC (monthly, gross of VAT)
- **5% E-Commerce Platform Contribution** (§XI.I, §XV.R) → BFC (monthly)

Plus **1 additional fee** from the separate Franchise Management Agreement template (also unexecuted):
- **2.5% Management Fee** (§5.1) → BFC (MANAGER = BFC per recitals)

**Total: 4 fees in Franchise Agreement + 1 fee in Management Agreement = 5 fees.** (Plan v1 said "5 fees in the Franchise Agreement" which was a factual error. Corrected here.)

**BEI is named NOWHERE in either contract** — verified by grep of both PDFs.

**Source:** `data/_CLEANROOM/2026-04-09_franchise_agreements/03_Franchise_Agreement_BFC.md` + `02_Franchise_Management_Agreement_BFC.md` — both PDF-verified 20/20.

### COA-175-009 — Both BFC contracts are UNEXECUTED templates
**Decision:** The Franchise Agreement template (2025-05-23) and Franchise Management Agreement template (undated) are DRAFTs with placeholder FRANCHISEE fields. No franchisees have signed either document. This makes Fork 1 collection-agent routing safe — there is no live franchisee whose signed contract is being operationally overridden.
**Source:** Agent extract 2026-04-09 reading both PDFs; grep of placeholder fields + absence of execution/notarization pages.

### COA-175-010 — COA-004 supersession
**Decision:** Butch's 2026-02-12 COA-004 lock (Sales Discounts `4000201-4000207` + Employee Benefit Expense `4000208`) is **SUPERSEDED** by COA-175-002's renumber to `4000901-4000908`.
**Source:** `data/_CONSOLIDATED/01_FINANCE/DECISIONS.md` COA-004 + 2026-04-08 Butch chat supersession.

### COA-175-011 — BKI population rules
**Decision:** BKI is the commissary. It populates ONLY the `4000200 BKI SALES` sub-tree (DELIVERIES + LOGISTICS). No in-store sales, no online sales, no franchise income.
**Source:** Sam Karazi explicit clarification 2026-04-08 (this session): *"BKI doesn't have in store sales, online sales and franchise income."*
**Implication:** BKI `4000001 IN-STORE SALES`, `4000002 ONLINE SALES`, and the entire `4000300 FRANCHISE INCOME` tree are DELETE targets (verified by Phase A audit: all 0 GL entries).

### COA-175-012 — BEI 6xxxxxx Income → Expense bulk fix (verified)
**Decision:** 134 of 136 BEI `6xxxxxx` accounts have `root_type='Income'` (should be 'Expense'). Zero GL entries on any. Bulk SQL UPDATE is safe.
**Source:** Phase A live audit `output/s175/preflight_audit.md#2`:
```
Total 6xxxxxx: 136 (134 Income + 2 Expense)
Total GL entries: 0
```
**Verification:** LIVE-CONFIRMED. The plan v1 said "134 of 136" which matches the live audit exactly. The concern about off-by-one against the Feb-2026 design CSV (135 rows) was a CSV-vs-live discrepancy, not a plan error — live has one extra 6xxxxxx row added post-CSV.
**Action:** Single SQL UPDATE in Phase 7 after re-verifying 0 GL entries at execution time.

### COA-175-013 — Structural scaffolding ready, routing policy deferred (REVISED 2026-04-09)
**Decision:** S175 creates the **full Fork 1 structural scaffolding** on disk + in Frappe (BFC Company, the `4000231-4000235 FEES` sub-tree on BFC, `2104200 DUE TO BFC - BEI`, `1104200 DUE FROM BEI - BFC`, `2102205 OUTPUT VAT PAYABLE - BFC`) but **does NOT enforce any revenue-routing policy during this sprint**. The Finance team (Butch + Sam + controller) will later decide — via the Butch questionnaire at `tmp/butch_s175_questionnaire.docx` — whether to:
- **Route new franchise fees through Fork 1** (collection-agent model, requires signed collection-agent letter + operational BFC OR booklet), OR
- **Continue routing through BEI's existing accounts** until BFC has its own bank account, then flip at cutover, OR
- **Some hybrid** (e.g., new franchisees onboarded to BFC directly, historical franchisees grandfathered on BEI).

**What S175 delivers:** The GL STRUCTURE that makes any of those routing choices trivial to implement later. No routing policy enforcement in this sprint.

**Accounting flow (preserved for future reference — NOT enforced in S175 execution):**
- **Fork 1 agent model:** `Dr Cash on Hand - BEI / Cr 2104200 DUE TO BFC - BEI`, mirror on BFC
- **Fork 2 interim model:** `Dr Cash on Hand - BEI / Cr 4000231-235 (appropriate fee) - BEI`, no BFC involvement
- Both models are **operable** once the structural scaffolding exists — choice is Finance's, not S175's

**Contracts prerequisite:** NONE for S175. The Collection Agent Letter draft (`data/_CLEANROOM/2026-04-09_franchise_agreements/04_BEI_BFC_Collection_Agent_Letter_DRAFT.md`) remains in cleanroom as a **future artifact**. It is not a prerequisite for S175 execution. It becomes a prerequisite only if Finance later chooses Fork 1.

**Source:** Sam Karazi decision 2026-04-09 PM (this session) after recognizing the policy-vs-structure conflation. BEI has been operationally collecting franchise fees for ~1 year; the structural work must not be gated by a policy debate.

**Rationale:** Separates what MUST be fixed (uniform COA, BFC Company, BEI 6xxxxxx bug, S168 legacy accounts) from what CAN BE DEBATED (revenue routing policy). Structural work proceeds autonomously; Butch's answers become inputs to a future Finance decision session, not a block on S175 execution.

**Supersedes:** Plan v2's "Fork 1 from day 1" framing. The Fork 1 JE patterns in `04_INTERCOMPANY_ACCOUNTING.md` remain valid as reference material for the future policy decision.

### COA-175-014 — Interim OR/VAT issuer policy (NEW)
**Decision:** During the Fork 1 interim period, every Official Receipt for a franchise fee is issued by **BFC**, using BFC's own BIR-registered OR booklet at RDO 044. BFC files its own 2550Q. BEI never issues an OR for a franchise fee.
**Source:** Fork 1 accounting treatment (COA-175-013) requires this to preserve substance-over-form.
**Pre-condition:** BFC's BIR OR booklet must be operational before first collection (see OQ-1 in `05_OPEN_QUESTIONS_FOR_BUTCH.md`).

### COA-175-015 — Intercompany scaffolding accounts (NEW)
**Decision:** Three new accounts are created to implement Fork 1:
- `2104200 DUE TO BFC - BEI` (Liability, Payable) on BEI
- `1104200 DUE FROM BEI - BFC` (Asset, Receivable) on BFC
- `2102205 OUTPUT VAT PAYABLE - BFC` (Liability, Tax) on BFC

Phase A audit confirmed `2104100 SHORT TERM DEBT` and `2104101 LOANS PAYABLE - CURRENT` exist on BEI — `2104200` is a clean number.
**Source:** Sam Karazi decision 2026-04-09, future-safe collection-agent scaffolding.

### COA-175-016 — Brand Growth Fee treatment (new, was flagged W8)
**Decision:** The `4000005 BRAND GROWTH FEE INCOME - BEI` account is kept as a **BEI-specific extension** outside the canonical template (legacy 6-digit number). It receives the ₱2M one-time JV Brand Growth Fee per signed JV §2. PFRS 15 recognition is point-in-time (license-granted model) — the full ₱2M is recognized on the execution date of the JV Agreement, not amortized over the JV term.
**Source:** Sam Karazi + Claude finance synthesis, this session.
**Rationale:** Brand Growth Fee is described in JV §3.4 as "for the perpetual license... granting The Store the right to utilize the brand's trademarks, operational processes, and marketing materials" — this is a right-to-use license, point-in-time recognition per PFRS 15.B58.

---

## Section B: Fee Routing Matrix (Contract → Entity → GL Account)

### B.1 Current (Fork 1 interim — BFC bank account not yet open)

| Fee | Per contract | Collected by | Recognized on | GL account | Customer Group |
|---|---|---|---|---|---|
| JV 5% Marketing (Gabaldon) | BEI (JV §8.1) | BEI (own cash) | BEI revenue | `4000234 MARKETING FEES - BEI` | JV Partners |
| JV 5% E-Commerce (Gabaldon) | BEI (JV §9.1) | BEI (own cash) | BEI revenue | `4000235 E-COMMERCE FEES - BEI` | JV Partners |
| JV ₱2M Brand Growth Fee (Gabaldon) | BEI (JV §2) | BEI (own cash) | BEI revenue (point-in-time) | `4000005 BRAND GROWTH FEE INCOME - BEI` | JV Partners |
| BFC Franchise Fee ₱2M (§I.A) | BFC | BEI (agent) | **BFC** revenue (Fork 1) | `4000233 FRANCHISE FEES - BFC` | BFC Franchisees |
| BFC Royalty 7% (§XIII.A) | BFC | BEI (agent) | **BFC** revenue (Fork 1) | `4000231 ROYALTY FEES - BFC` | BFC Franchisees |
| BFC Marketing 5% (§XI.A) | BFC | BEI (agent) | **BFC** revenue (Fork 1) | `4000234 MARKETING FEES - BFC` | BFC Franchisees |
| BFC E-Commerce 5% (§XI.I/§XV.R) | BFC | BEI (agent) | **BFC** revenue (Fork 1) | `4000235 E-COMMERCE FEES - BFC` | BFC Franchisees |
| BFC Management 2.5% (Mgmt §5.1) | BFC | BEI (agent) | **BFC** revenue (Fork 1) | `4000232 MANAGEMENT FEES - BFC` | BFC Franchisees |

### B.2 After Cutover (BFC bank account opens)

All BFC rows above: Collected by BFC directly. BEI-as-agent role auto-terminates per collection-agent letter §5. JV rows unchanged (JV fees permanently BEI's).

### B.3 Store-level sales (not fees)

| Revenue | Entity | GL account | Notes |
|---|---|---|---|
| BEI direct retail (in-store) | BEI | `4000110 IN-STORE SALES - BEI` | BEI HO retail if any |
| Each store corp's in-store retail | That store corp | `4000110 IN-STORE SALES - <STORE>` | Per Sam's "each store is its own entity" model |
| BEI website sales | BEI | `4000121 BEI WEBSITE - BEI` | BEI operates the website for the group |
| Food Panda (per store) | Each store corp | `4000122 FOOD PANDA - <STORE>` | Each store's own FP orders |
| GrabFood (per store) | Each store corp | `4000123 GRAB - <STORE>` | Each store's own Grab orders |
| BKI commissary → store deliveries | BKI | `4000210 DELIVERIES - BKI` | External sale model per S168 |
| BKI logistics services | BKI | `4000221 DELIVERY INCOME - BKI` or `4000222 LOGISTICS INCOME - BKI` | Delivery fee billing per S168 |
| JV store retail | JV company | `4000110 IN-STORE SALES - JV` | JV Gabaldon retail proper |
| Managed Franchise store retail | MF company | `4000110 IN-STORE SALES - MF` | Managed stores under MF company |

---

## Section C: What NOT to do (guardrails)

1. **NEVER** book a franchise fee receipt as BEI revenue during Fork 1 interim. Always `Cr 2104200 DUE TO BFC - BEI`.
2. **NEVER** let BEI issue an OR for a franchise fee. BFC issues all franchise fee ORs.
3. **NEVER** populate BFC's `4000100 STORE SALES` or `4000200 BKI SALES` trees. BFC is a franchisor, not a retailer or commissary.
4. **NEVER** delete an account that has non-zero GL entries, even if the plan says to delete it. Re-verify live before every delete. HARD BLOCKERS HB-1 through HB-4 enforce this.
5. **NEVER** rename an account via SQL UPDATE. Always use `frappe.rename_doc("Account", old, new)` — SQL UPDATE breaks incoming Link references.
6. **NEVER** use the `4000300-4000800` range for discounts or any S175 purpose. Reserved for future revenue streams per Butch's 2026-04-08 21:48 PHT message.
7. **NEVER** exceed Butch's 5-fee taxonomy within `4000230 FEES` without adding a `4000236+` Butch-approved expansion row first.
8. **NEVER** treat the JV Brand Growth Fee as recurring. It's a one-time point-in-time recognition per JV §3.4.
