---
sprint_id: S238
sprint_title: ICT-003 Store-Side Purchase Invoice Generator
plan_branch: s238-ict003-store-pi-generator
status: PLANNED
version: 1
created_date: 2026-05-07
canonical_scope: in
canonical_model_reference: docs/STORE_COMPANY_CANONICAL.md
canonical_preflight: required
depends_on: none
supersedes: docs/plans/2026-05-05-sprint-236-intercompany-auto-trade.md
evidence_committed:
  - output/s238/SUMMARY.md
  - output/s238/verification/before_state.json
  - output/s238/verification/after_state.json
  - output/s238/verification/aranetatrial_pi.json
  - output/s238/verification/historical_si_regression.json
  - output/s238/verification/canonical_post_check.log
evidence_transient:
  - tmp/s238/probe_*.py
  - tmp/s238/probe_*.json
  - tmp/s238/seed_dry_run_*.log
sprint_registry_row: |
  | `S238` | Sprint 238 | `s238-ict003-store-pi-generator` | TBD | PLANNED 2026-05-07 — ICT-003 Store-Side Purchase Invoice Generator | `docs/plans/2026-05-07-sprint-238-ict003-store-pi-generator.md` |
---

# S238 — ICT-003 Store-Side Purchase Invoice Generator

> **Canonical model reference:** `docs/STORE_COMPANY_CANONICAL.md`
> **Supersedes:** `docs/plans/2026-05-05-sprint-236-intercompany-auto-trade.md` (S236 v2 — wrong architecture, see Design Rationale).

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

Audit 2026-05-05 + 2026-05-07 found a clear implementation gap:

- ICT-003 (CFO Butch Formoso, 2026-02-20, still binding): "BKI issues Sales Invoice (SI) and BEI receives Purchase Invoice (PI) for each hub transfer. Both documents required since separate legal entities."
- Built today: **BKI's SI side works** (839 SIs, ICT-001/002/007 all wired via `commissary.py:build_bki_store_sale_invoice`).
- Missing today: **the store-side PI was never built.** Stores have 0 PI from BKI in the entire production database. Each per-store BIR Form 2550Q is missing the Input VAT claim from BKI purchases; each store's books of accounts is missing AP-BKI + Inventory-from-Commissary entries.

This sprint closes the gap: when an SI on BKI's books submits, a **separate Draft Purchase Invoice** is auto-generated on the receiving store's books, ready for review + submission by Denise's team.

### Why this is NOT S236 v2 (the wrong path)

S236 v2 tried to use ERPNext's atomic auto-mirror feature (`Make Inter Company Invoice` button) which would have flipped 49 billing Customers to `is_internal_customer=1`. Audit found:
- **Violates ICT-001** — the Customer flag stays at 0 because stores ARE separate legal entities (per `commissary.py:1137` + `billing.py:595` hardcoded `si.is_internal_customer = 0` with comment "EXTERNAL sale per ICT-001").
- **Violates ICT-003** — the auto-mirror creates an *atomic two-company transaction* which conflates legal independence; Butch said "both documents required" precisely because they should be SEPARATE.
- **Would silently break S206** — `labor_allocation.py:324-339` looks up Internal Customers by `{represents_company, is_internal=1}` with no name-suffix filter; flipping billing Customers makes that lookup ambiguous.

S236 v2's framing of "consolidated group vs arm's-length" was a false dichotomy. BEI is BOTH:
- Legally arm's-length (49 + 1 separate BIR-registered corporations) → each entity needs its own complete books per ICT-003
- Operationally one accounting team (Denise's team manages all 50 sets in-house) → centralized review + submission workflow

The right architecture is **separate documents** on separate Companies, with **operational pairing** via a backend hook, NOT atomic auto-mirroring.

### Architecture summary

When `Sales Invoice on_submit` fires AND `company == BEBANG KITCHEN INC.` AND `customer` matches a per-store billing Customer:

1. Identify the buyer Company (the per-store Company) from the SI's customer name (canonical model: `Customer.name == per-store Company.name`).
2. Look up the per-store CoA: `Inventory-from-Commissary` (Asset), `Input VAT - BKI Inter-Co` (Asset), `AP-Trade-BKI` (Liability) — all numbered per existing BEI CoA convention (`1xxxx`/`2xxxx` series, parent=Stock-in-Hand / Current Liabilities).
3. Construct a **Draft Purchase Invoice** on the buyer Company with:
   - `supplier` = `BEBANG KITCHEN INC. - Trade` (a NEW non-internal Supplier record, `is_internal_supplier=0`, `Allowed To Transact With` = all 49 per-store Companies)
   - `posting_date` = SI's posting_date (per ICT-007 — Incoterm Destination: SI date is the delivery acceptance date)
   - `bill_no` = SI's name (the BKI-side SI)
   - `bill_date` = SI's posting_date
   - Line items mirror SI items (item code, qty, rate including the 2.75%/8% markup already in the SI)
   - Taxes mirror SI's tax breakdown (12% Input VAT lands on store's books per ICT-001)
   - `update_stock=1` so Inventory-from-Commissary increases on the per-store warehouse
   - Custom field `bki_si_reference` linking back to the SI for traceability
4. Insert as Draft (do NOT submit) — Denise's team reviews + submits via Frappe Desk.
5. `is_internal_customer/_supplier` flags ALL stay at 0 (no canonical model rewrite).

### Why use a NEW Supplier record (not the existing `BEBANG KITCHEN INC. (Internal)`)

Audit 2026-05-05 found a Supplier already exists named "Bebang Kitchen Inc." with `is_internal_supplier=1, represents_company=BEBANG KITCHEN INC.`. **That record is for S206 labor cost-sharing JEs, NOT for trade.** Re-using it would conflict with S206 lookup logic. New record:

- `name` (docname): `BEBANG KITCHEN INC. - Trade`
- `supplier_name`: `BEBANG KITCHEN INC.` (display name shown on PI print format — BIR-compliant)
- `is_internal_supplier`: 0
- `represents_company`: NULL (not internal)
- `tax_id`: BKI's TIN (preserved on SI's print format — same TIN as BKI's billing entity)
- `Allowed To Transact With`: 49 per-store Companies + holdco

### Source references

- `data/_CONSOLIDATED/01_FINANCE/DECISIONS.md:193-200` — ICT-001 through ICT-008 (CFO-locked, still binding per 2026-05-07 banner)
- `data/_CONSOLIDATED/01_FINANCE/questionnaires/CFO_INTERCOMPANY_Butch_Formoso_2026-02-20.md:35-42` — Q3 verbatim "we need to maintain the SI and PI for each hub transfer"
- `hrms/api/commissary.py:864-988, 973-1248` — existing `build_bki_store_sale_invoice` (the SI side; UNCHANGED)
- `hrms/api/commissary.py:1137`, `hrms/api/billing.py:595` — `si.is_internal_customer = 0` hardcoded; UNCHANGED
- `hrms/utils/labor_allocation.py:324-339` — S206 Internal Customer lookup; UNCHANGED
- Audit findings: `output/plan-audit/s236-intercompany-auto-trade/AUDIT_SUMMARY.md`, `tmp/CANONICAL_COVERAGE_AUDIT_SUMMARY.md`, `tmp/pi_probe.json`
- S168 SI implementation history: `docs/plans/2026-04-07-sprint-168-bki-store-sale-billing-on-delivery.md`

---

## Canonical Model Preflight (Mandatory)

Executing agent MUST run before the first code change:

```bash
python scripts/verify_canonical_structure.py 2>&1 | tee tmp/s238/canonical_preflight.log
```

If the verifier prints `VIOLATIONS FOUND`, STOP and ask Sam. Post-implementation verifier (Phase 6) MUST also pass.

**Canonical law (this sprint preserves it intact):**
- 49 per-store Companies + Warehouses + billing Customers + S206 Internal Customers — UNCHANGED.
- `is_internal_customer/_supplier` flags — ALL UNCHANGED (no flips).
- `resolve_store_buyer_entity` — UNCHANGED (no resolver changes).
- Existing `BEBANG KITCHEN INC. (Internal)` Supplier (S206) — UNCHANGED.
- `commissary.py:1137`, `billing.py:595` — UNCHANGED.

**Forbidden in this plan:**
- Flipping `is_internal_customer` on any Customer.
- Modifying any existing Supplier record's `is_internal_supplier` flag.
- Modifying `resolve_store_buyer_entity` or any code under `hrms/utils/supply_chain_contracts.py`.
- Modifying `hrms/utils/labor_allocation.py`.
- Modifying canonical Rules in `docs/STORE_COMPANY_CANONICAL.md`.
- Touching the existing 839 historical BKI SIs.
- Modifying `build_bki_store_sale_invoice` in commissary.py.

**Scope claim — what this plan creates / mutates:**
- INSERT 1 Supplier: `BEBANG KITCHEN INC. - Trade` (`is_internal_supplier=0`).
- INSERT 49 entries to `BEBANG KITCHEN INC. - Trade.companies` child table (Allowed To Transact With per-store Companies).
- INSERT 3 GL accounts × 49 stores = 147 accounts under existing parent groups (`Stock in Hand`, `Current Liabilities`, `Current Assets`).
- INSERT 1 Custom Field on `Purchase Invoice`: `bki_si_reference` (Link → Sales Invoice, read-only).
- INSERT 1 row in `BEI Settings` (or extend existing settings doc): `enable_bki_store_pi_generator` (toggle, default 1).
- ADD 1 hook in `hrms/hooks.py`: `Sales Invoice on_submit → hrms.api.bki_store_pi_generator.maybe_generate_store_pi`.
- ADD new module `hrms/api/bki_store_pi_generator.py` with the generator logic.

## Canonical Model Binding

This feature binds to the canonical model as follows:

- Reads `Customer.name == warehouse.company == per-store Company.name` to map SI customer → buyer Company.
- Reads `Sales Invoice` doc submitted on BKI's books for the line items + tax breakdown to clone.
- Reads per-store Company's CoA to find the right `Inventory-from-Commissary` / `Input VAT - BKI Inter-Co` / `AP-Trade-BKI` accounts.
- Reads new `BEBANG KITCHEN INC. - Trade` Supplier on each per-store Company's books.
- Writes a Draft Purchase Invoice (docstatus=0) on the per-store Company's books.
- Does NOT touch any Customer, Company, or Warehouse records.
- Does NOT touch the existing S206 Internal Customer or its Supplier counterpart.
- Does NOT call `resolve_store_buyer_entity` or any S206-binding utility.

## Worktree Isolation & Evidence Split

Worktree path: `F:/Dropbox/Projects/BEI-ERP-s238-ict003-pi-generator`

```yaml
evidence_committed:
  - output/s238/SUMMARY.md
  - output/s238/verification/before_state.json
  - output/s238/verification/after_state.json
  - output/s238/verification/aranetatrial_pi.json
  - output/s238/verification/historical_si_regression.json
  - output/s238/verification/canonical_post_check.log
evidence_transient:
  - tmp/s238/probe_*.py
  - tmp/s238/probe_*.json
  - tmp/s238/seed_dry_run_*.log
```

---

## Test Data Seeding Contract (Mandatory per S229)

**Records the scenarios depend on:**
- 49 per-store Companies + Warehouses + billing Customers + S206 Internal Customers — must exist (verified via canonical preflight).
- Existing `BEI Settings.bki_sales_income_account` set per ICT-008 — must exist.
- Per-store CoA must include parent groups: `Stock in Hand`, `Current Liabilities`, `Current Assets` — verified via probe.
- 3 NEW GL accounts × 49 stores = 147 accounts (seeded by this sprint).
- 1 NEW `BEBANG KITCHEN INC. - Trade` Supplier with 49 Allowed To Transact With entries (seeded by this sprint).
- 1 NEW Custom Field `bki_si_reference` on `Purchase Invoice` (seeded by this sprint).
- Test SI: created in Phase 4 trial (1 small ARANETA SI, ~PHP 1.00) via existing BKI flow; tracked in teardown ledger.

**Pre-test seeding plan (all idempotent, all use `frappe.db.savepoint`):**
- `scripts/s238/seed_pi_generator_accounts.py --dry-run|--apply` — 147 accounts.
- `scripts/s238/seed_bki_trade_supplier.py --dry-run|--apply` — 1 Supplier + 49 Allowed entries.
- `scripts/s238/install_bki_si_reference_field.py --dry-run|--apply` — 1 Custom Field.

**Teardown plan:**
- Test SI + auto-generated Draft PI: cancel both via Frappe Desk; teardown removes ledger entries.
- Seeded accounts: keep (idempotent, harmless).
- New Supplier: keep (this is the production change).
- New Custom Field: keep (this is the production change).
- Hook in hooks.py: keep (this is the production change).

If sprint is **rolled back**: revert the PR; cancel + delete the new Supplier; remove the Custom Field via `bench remove-from-installed-apps` pattern OR drop the field manually via SQL with savepoint.

**Teardown ledger:** `output/l3/s238/teardown_ledger.json` (per-record before/after).
**Teardown verification:** `output/l3/s238/teardown_complete.json` (closeout).

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|---|---|---|---|
| Administrator | Run `scripts/s238/seed_pi_generator_accounts.py --apply` | 147 accounts created (or already exist), zero errors | Account seed broken |
| Administrator | Run `scripts/s238/seed_bki_trade_supplier.py --apply` | 1 Supplier `BEBANG KITCHEN INC. - Trade` created with `is_internal_supplier=0` and 49 Allowed To Transact With entries | Supplier seed broken |
| Administrator | Run `scripts/s238/install_bki_si_reference_field.py --apply` | 1 Custom Field on Purchase Invoice (`bki_si_reference`, Link → Sales Invoice, read-only) | Custom field install broken |
| Administrator | Submit a real BKI→ARANETA SI via existing `complete_receiving` flow (small amount, ~PHP 1.00) | SI submits successfully on BKI's books. ALSO: 1 Draft PI created on ARANETA's books with `supplier=BEBANG KITCHEN INC. - Trade`, `bill_no=<SI name>`, `bki_si_reference=<SI name>`, `update_stock=1`, posting_date=SI posting_date | Hook didn't fire OR PI generator broken |
| Administrator | Open the auto-generated Draft PI; verify line items match SI; verify tax breakdown shows 12% Input VAT | Items 1:1 match. Tax row shows Input VAT amount that mirrors SI's Output VAT. | Tax/item mirroring broken |
| Denise (or test.finance) | Submit the Draft PI from Frappe Desk | PI submits. SLE created on per-store warehouse with `actual_qty>0`, `valuation_rate=<from PI>`. GL Entry rows: DR Inventory-from-Commissary, DR Input VAT - BKI Inter-Co, CR AP-Trade-BKI (with `party_type=Supplier, party=BEBANG KITCHEN INC. - Trade` per DM-1) | Stock or GL recognition broken |
| test.area@bebang.ph | Open per-store P&L for ARANETA via `Profit and Loss Statement` report | COGS-from-Commissary line shows non-zero value (after the inventory is consumed via POS / Stock Entry — note: PI alone increases Inventory, not COGS; COGS recognition happens at POS/consumption time) | P&L wiring broken |
| Administrator | Sample 5 random PRE-S238 historical SIs (ACC-SINV-2026-00100, 00300, 00500, 00700, 00900) | All 5 readable, customer field unchanged, `bki_si_reference` does NOT appear (Custom Field is forward-only on the PI side; SI is unchanged) | Path B regression on historical |
| Administrator | Submit a NEW BKI SI to a DIFFERENT store (e.g. SM TANZA, 5 random stores) | All 5 produce a Draft PI on each respective store's books with correct supplier + accounts | Cross-store regression |
| test.scm@bebang.ph | Run S206 labor JE creation for one store (existing flow) | S206 labor JE creates against the existing `(Internal)` Customer (UNTOUCHED). `BEBANG KITCHEN INC. - Trade` Supplier is NOT involved. | Resolver / S206 broke |
| Administrator | Cancel the test SI from earlier | SI cancels. The matching Draft PI: option 1 — auto-cancels via cascade hook; option 2 — flagged as `cancellation_pending` for manual cancel by Denise. (Decision: auto-cancel if Draft, flag if Submitted.) | Cancel cascade broken |
| Administrator | Run `python scripts/verify_canonical_structure.py` post-implementation | `ALL CANONICAL` (zero new violations) | Canonical drift introduced |
| Administrator | Disable the toggle: `BEI Settings.enable_bki_store_pi_generator=0`; submit another BKI SI | NO PI auto-generated. SI submits cleanly. | Toggle broken (kill switch) |

**Evidence files contract:**
```
output/l3/s238/form_submissions.json
output/l3/s238/api_mutations.json
output/l3/s238/state_verification.json
output/l3/s238/teardown_ledger.json
output/l3/s238/teardown_complete.json
output/l3/s238/historical_si_regression.json
```

**Failure Response (mandatory):**
- **Mode A (app/Frappe bug):** hook fires but PI not created / GL Entry missing party fields. File `[BUG] s238 — <symptom>`. Halt sprint.
- **Mode B (test/data bug):** account names mismatched, Custom Field SQL malformed, supplier collision. Fix the migration script.
- **Mode C (brittleness):** intermittent timing on hook firing. Fix LIBRARY wait helpers. No `waitForTimeout` masking.

---

## Phases

### Phase 0 — Boot, Worktree Spawn, Pre-State Probe (4 units)

**0-T1** Read this plan fully.

**0-T2** Spawn HRMS worktree (already done at plan creation; confirm):
```bash
cd F:/Dropbox/Projects/BEI-ERP-s238-ict003-pi-generator
git status --short    # must be clean other than this plan + registry
mkdir -p tmp/s238 output/s238/verification output/l3/s238
git rev-parse origin/production > tmp/s238/remote_truth_baseline_hrms.sha
```

**0-T3** Run canonical preflight + capture baseline:
```bash
python scripts/verify_canonical_structure.py 2>&1 | tee tmp/s238/canonical_preflight.log
```
If violations, STOP.

**0-T4** Probe production state via SSM — write `output/s238/verification/before_state.json` with:
- BKI SI total count
- PI count where company in (49 per-store Cos) AND supplier matches BKI pattern (expected: 0)
- Existing Suppliers matching `BEBANG KITCHEN%` pattern (verify ONLY the S206 internal one exists, no Trade variant yet)
- Existence of 3 needed account templates per per-store CoA (sample 3 stores)
- Existence of `bki_si_reference` Custom Field on Purchase Invoice (expected: false)
- Existence of `enable_bki_store_pi_generator` setting (expected: false)
- `BEI Settings.bki_sales_income_account` value (must be set per ICT-008; if missing, STOP)

**MUST_MODIFY:** `output/s238/verification/before_state.json`
**MUST_CONTAIN:** `"bki_si_total"`, `"existing_bki_supplier_count"`, `"bki_trade_supplier_exists"`, `"custom_field_exists"`, `"bki_sales_income_account"`

**Phase 0 verify:**
```python
import os, json, sys
errs = []
for f in ["tmp/s238/canonical_preflight.log", "output/s238/verification/before_state.json"]:
    if not os.path.exists(f): errs.append(f"MISSING: {f}")
log = open("tmp/s238/canonical_preflight.log", encoding="utf-8", errors="replace").read()
if "VIOLATIONS FOUND" in log: errs.append("Canonical preflight violations")
if os.path.exists("output/s238/verification/before_state.json"):
    s = json.load(open("output/s238/verification/before_state.json"))
    if s.get("bki_trade_supplier_exists") is True:
        errs.append("BKI Trade Supplier already exists — investigate before seeding")
    if not s.get("bki_sales_income_account"):
        errs.append("BEI Settings.bki_sales_income_account not set — ICT-008 prerequisite missing, STOP")
print("PASS" if not errs else "\n".join(errs))
sys.exit(0 if not errs else 1)
```

---

### Phase 1 — GL Account Seeder (5 units)

**1-T1** Write `scripts/s238/seed_pi_generator_accounts.py` (NEW):
- For each per-store Company (49), seed 3 accounts under appropriate parent groups:
  - `<numeric>1 Inventory-from-Commissary` — under `Stock in Hand` parent, account_type=`Stock`, root_type=Asset, report_type=Balance Sheet
  - `<numeric>2 Input VAT - BKI Inter-Co` — under `VAT Input - <Co>` or `Current Assets`, account_type=`Tax`, root_type=Asset, report_type=Balance Sheet
  - `<numeric>3 AP-Trade-BKI` — under `Accounts Payable` or `Current Liabilities`, account_type=`Payable`, root_type=Liability, report_type=Balance Sheet
- Numeric prefix: discover from existing CoA (use parent's prefix + 3 next-available leaves). Do NOT invent prefixes; survey actual per-store CoA via SSM probe.
- `frappe.db.savepoint("s238_account_seed_<co>")` per Company (DM-2).
- `--dry-run` (default) and `--apply` modes.
- Idempotent: skip if account already exists with same name pattern.
- All accounts logged to `output/l3/s238/teardown_ledger.json`.

**MUST_MODIFY:** `scripts/s238/seed_pi_generator_accounts.py` (NEW)
**MUST_CONTAIN:** `frappe.db.savepoint`, `Inventory-from-Commissary`, `Input VAT - BKI Inter-Co`, `AP-Trade-BKI`, `--dry-run`, `--apply`

**1-T2** Dry-run on production via SSM, capture log to `tmp/s238/seed_dry_run_accounts.log`. Manually inspect — verify parent_account assignments make sense for each per-store CoA. If any store has an unusual CoA structure (e.g., missing `Stock in Hand` parent), STOP and ask Sam.

**1-T3** Apply on production. Re-probe. Verify 147 accounts exist (49 × 3).

---

### Phase 2 — Supplier + Custom Field + Toggle (5 units)

**2-T1** Write `scripts/s238/seed_bki_trade_supplier.py` (NEW):
- Create Supplier:
  - `name`: `BEBANG KITCHEN INC. - Trade`
  - `supplier_name`: `BEBANG KITCHEN INC.` (display name on PI print)
  - `is_internal_supplier`: 0
  - `represents_company`: NULL
  - `tax_id`: BKI's TIN (read from existing BKI Customer record's tax_id or BKI Company's tax_id)
  - `supplier_group`: existing default
- Add 49 entries to `companies` child table (`Allowed To Transact With`) — one per per-store Company.
- Idempotent + savepoint + ledger.

**MUST_MODIFY:** `scripts/s238/seed_bki_trade_supplier.py` (NEW)
**MUST_CONTAIN:** `is_internal_supplier`, `represents_company`, `BEBANG KITCHEN INC. - Trade`, `tax_id`, `companies`

**2-T2** Write `scripts/s238/install_bki_si_reference_field.py` (NEW):
- Install Custom Field on `Purchase Invoice`:
  - `fieldname`: `bki_si_reference`
  - `label`: `BKI Sales Invoice Reference`
  - `fieldtype`: Link
  - `options`: Sales Invoice
  - `read_only`: 1
  - `insert_after`: `bill_no`
- Idempotent.

**MUST_MODIFY:** `scripts/s238/install_bki_si_reference_field.py` (NEW)
**MUST_CONTAIN:** `bki_si_reference`, `Link`, `Sales Invoice`, `read_only`

**2-T3** Add toggle to BEI Settings (existing single doctype):
- `enable_bki_store_pi_generator` (Check, default 1)
- `auto_submit_store_pi` (Check, default 0 — Draft for review by default)

Add via `scripts/s238/install_bei_settings_toggles.py` (NEW) OR extend existing settings install script.

**MUST_MODIFY:** `scripts/s238/install_bei_settings_toggles.py` (or amend existing)
**MUST_CONTAIN:** `enable_bki_store_pi_generator`, `auto_submit_store_pi`

**2-T4** Apply all seeds on production. Verify post-seed state in `output/s238/verification/after_state.json`.

---

### Phase 3 — PI Generator Implementation (10 units)

**3-T1** Create `hrms/api/bki_store_pi_generator.py` (NEW):

```python
"""S238 — Generate store-side Draft Purchase Invoice when a BKI Sales Invoice submits.

Implements ICT-003: each BKI→store SI must have a paired PI on the receiving
store's books for BIR per-entity bookkeeping. NOT an atomic auto-mirror — the
PI is a SEPARATE document on a SEPARATE Company, awaiting Denise's team review.
"""
import frappe
from frappe import _
from frappe.utils import flt
from hrms.utils.sentry import set_backend_observability_context

BKI_TRADE_SUPPLIER = "BEBANG KITCHEN INC. - Trade"

def maybe_generate_store_pi(doc, method=None):
    """S238: Sales Invoice on_submit hook — generates store-side PI."""
    set_backend_observability_context(
        module="billing",
        action="maybe_generate_store_pi",
        mutation_type="create",
        extras={"si_name": doc.name, "company": doc.company, "customer": doc.customer},
    )
    # Filter: only BKI -> store SIs trigger the generator
    if doc.company != "BEBANG KITCHEN INC.": return
    settings = frappe.get_single("BEI Settings")
    if not getattr(settings, "enable_bki_store_pi_generator", 1): return
    # Identify buyer Company (per canonical: Customer.name == per-store Company.name)
    buyer_company = doc.customer if frappe.db.exists("Company", doc.customer) else None
    if not buyer_company: return  # Customer is not a per-store Company; ignore
    # Idempotency: skip if a PI already exists referencing this SI
    if frappe.db.exists("Purchase Invoice", {"bki_si_reference": doc.name}): return
    try:
        frappe.db.savepoint("s238_pi_gen")
        pi = build_store_pi(doc, buyer_company)
        pi.insert(ignore_permissions=True)
        if getattr(settings, "auto_submit_store_pi", 0):
            pi.submit()
        frappe.db.release_savepoint("s238_pi_gen")
        # Add a comment on the SI for audit trail
        si_comment = frappe.get_doc({
            "doctype": "Comment", "comment_type": "Comment",
            "reference_doctype": "Sales Invoice", "reference_name": doc.name,
            "content": f"S238: Store-side PI auto-generated → {pi.name} (Draft). "
                       f"Awaiting review by Finance team.",
        })
        si_comment.insert(ignore_permissions=True)
    except Exception:
        frappe.db.rollback_to_savepoint("s238_pi_gen")
        frappe.log_error(
            f"S238: PI generation failed for SI {doc.name}: {frappe.get_traceback()}",
            "S238 Store PI Generator Error",
        )
        # Do NOT block the SI submit — log and surface via Sentry only.

def build_store_pi(si, buyer_company):
    """Construct the Draft PI mirroring the SI's items + taxes."""
    inv_account = resolve_account(buyer_company, "Inventory-from-Commissary")
    vat_account = resolve_account(buyer_company, "Input VAT - BKI Inter-Co")
    ap_account  = resolve_account(buyer_company, "AP-Trade-BKI")

    pi = frappe.new_doc("Purchase Invoice")
    pi.company = buyer_company
    pi.supplier = BKI_TRADE_SUPPLIER
    pi.posting_date = si.posting_date
    pi.bill_no = si.name
    pi.bill_date = si.posting_date
    pi.bki_si_reference = si.name
    pi.update_stock = 1
    pi.credit_to = ap_account
    # ... mirror items + taxes from SI; details in implementation
    return pi

def resolve_account(company, name_substring):
    """Find the per-Company account by name LIKE pattern."""
    rows = frappe.db.sql(
        "SELECT name FROM `tabAccount` WHERE company=%s AND account_name LIKE %s "
        "AND disabled=0 LIMIT 1",
        (company, f"%{name_substring}%"), as_dict=True,
    )
    if not rows:
        frappe.throw(_(f"S238: account matching '{name_substring}' not found on {company}"))
    return rows[0]["name"]
```

**MUST_MODIFY:** `hrms/api/bki_store_pi_generator.py` (NEW)
**MUST_CONTAIN:** `maybe_generate_store_pi`, `set_backend_observability_context`, `frappe.db.savepoint`, `BEBANG KITCHEN INC. - Trade`, `bki_si_reference`, `update_stock = 1`, `posting_date = si.posting_date`, `enable_bki_store_pi_generator`, `auto_submit_store_pi`

**3-T2** Add hook to `hrms/hooks.py`:
```python
"Sales Invoice": {
    "on_submit": "hrms.api.bki_store_pi_generator.maybe_generate_store_pi",
},
```

**MUST_MODIFY:** `hrms/hooks.py`
**MUST_CONTAIN:** `bki_store_pi_generator.maybe_generate_store_pi`

**3-T3** Implement item + tax mirroring logic in `build_store_pi`:
- For each `si.items` row → append to `pi.items` with same `item_code, qty, rate, item_name, description, uom`. Override `expense_account = inv_account` (per-store Inventory-from-Commissary, not BKI's).
- For each `si.taxes` row → if Output VAT 12%, append corresponding Input VAT row on PI with `account_head = vat_account`, `add_deduct_tax = "Add"`, `category = "Total"`, mirror the rate and tax_amount.
- Preserve `total`, `grand_total`, `outstanding_amount` calculations via Frappe's standard validate.

**3-T4** Write unit tests in `hrms/tests/test_s238_pi_generator.py` (NEW):
- Test 1: SI on BKI to ARANETA Customer → 1 Draft PI created on ARANETA Co with right supplier + accounts.
- Test 2: SI on BKI to a non-Company Customer (e.g., Walk-in, holdco) → NO PI created (filter works).
- Test 3: SI on BKI with toggle OFF → NO PI created.
- Test 4: Resubmit SI scenario → PI not duplicated (idempotency via `bki_si_reference` check).
- Test 5: SI on a non-BKI Company → NO PI created (filter works).

**MUST_MODIFY:** `hrms/tests/test_s238_pi_generator.py` (NEW)
**MUST_CONTAIN:** all 5 test docstrings

**3-T5** Run unit tests via `/local-frappe`:
```bash
bench --site hq.bebang.ph run-tests --module hrms.tests.test_s238_pi_generator
```
All 5 must pass.

**Phase 3 verify:**
```python
import sys, os
errs = []
src = open("hrms/api/bki_store_pi_generator.py", encoding="utf-8").read()
for m in ["maybe_generate_store_pi", "set_backend_observability_context",
          "frappe.db.savepoint", "BEBANG KITCHEN INC. - Trade", "bki_si_reference",
          "update_stock = 1", "posting_date = si.posting_date",
          "enable_bki_store_pi_generator", "auto_submit_store_pi"]:
    if m not in src: errs.append(f"generator MUST_CONTAIN: {m}")
hooks = open("hrms/hooks.py", encoding="utf-8").read()
if "bki_store_pi_generator.maybe_generate_store_pi" not in hooks:
    errs.append("hooks.py missing on_submit hook")
if not os.path.exists("hrms/tests/test_s238_pi_generator.py"):
    errs.append("Unit tests file missing")
print("PASS" if not errs else "\n".join(errs))
sys.exit(0 if not errs else 1)
```

---

### Phase 4 — Single-Store Trial (ARANETA) (8 units)

**4-T1** Deploy code to local-frappe via `/local-frappe` first. Run unit tests.

**4-T2** Submit BKI→ARANETA SI via the existing `complete_receiving` flow on local-frappe (or production with `auto_submit_store_pi=0` so PI stays Draft):
- Small amount (~PHP 1.00, 1 line item from existing catalog)
- Verify SI submits successfully
- Verify Draft PI auto-created on ARANETA's books

**4-T3** Open the auto-created Draft PI in Frappe Desk:
- `supplier=BEBANG KITCHEN INC. - Trade` ✓
- `bill_no=<SI name>` ✓
- `bki_si_reference=<SI name>` ✓
- `update_stock=1` ✓
- `posting_date=<SI posting_date>` ✓
- Line items match SI 1:1
- Tax row shows 12% Input VAT with `account_head=Input VAT - BKI Inter-Co`

**4-T4** Submit the Draft PI manually (test.finance@bebang.ph). Verify:
- SLE created on ARANETA's per-store warehouse with `actual_qty>0`, `voucher_type=Purchase Invoice, voucher_no=<PI name>`
- GL Entries: DR Inventory-from-Commissary, DR Input VAT - BKI Inter-Co, CR AP-Trade-BKI (with `party_type=Supplier, party=BEBANG KITCHEN INC. - Trade`)

**4-T5** Run per-store P&L for ARANETA — verify Inventory-from-Commissary line is on Balance Sheet (not COGS yet — COGS happens at consumption).

Write to `output/s238/verification/aranetatrial_pi.json`:
```json
{
  "test_si": "<SI name>",
  "test_pi": "<PI name>",
  "pi_supplier": "BEBANG KITCHEN INC. - Trade",
  "pi_update_stock": true,
  "pi_bki_si_reference": "<SI name>",
  "sle_count": 1,
  "sle_actual_qty": <value>,
  "gl_entries": [<rows>],
  "input_vat_account": "<account>",
  "ap_account": "<account>",
  "trial_pass": true
}
```

**4-T6** Cancel the test PI then test SI; verify clean state.

**Phase 4 verify:**
```python
import json, sys
state = json.load(open("output/s238/verification/aranetatrial_pi.json"))
errs = []
required = ["test_si", "test_pi", "pi_supplier", "pi_update_stock", "pi_bki_si_reference",
            "sle_count", "gl_entries", "trial_pass"]
for k in required:
    if k not in state: errs.append(f"missing {k}")
if state.get("pi_supplier") != "BEBANG KITCHEN INC. - Trade":
    errs.append(f"wrong supplier: {state.get('pi_supplier')}")
if state.get("sle_count", 0) != 1: errs.append(f"expected 1 SLE, got {state.get('sle_count')}")
if not state.get("trial_pass"): errs.append("trial_pass=false")
print("PASS" if not errs else "\n".join(errs))
sys.exit(0 if not errs else 1)
```

---

### Phase 5 — 5-Store Regression + Historical SI Verification + S206 Sanity (5 units)

**5-T1** Pick 5 stores spanning diverse legal entities: ARANETA (TUNGSTEN), AYALA EVO CITY (BEBANG MEGA), CTTM TOMAS MORATO (B CUBED VENTURES), ORTIGAS GREENHILLS (BEIFRANCHISE), SM TANZA (BEBANG MEGA).

**5-T2** Sample 5 random PRE-S238 historical SIs. Verify:
- Still readable; customer field unchanged.
- `bki_si_reference` does not appear on the historical SI (it's a Custom Field on PI only).
- The historical SIs have NO matching PI (existing 0-PI state preserved for historicals — backfill is out of scope).
- Standard SI print format renders correctly with TIN intact.

Write `output/s238/verification/historical_si_regression.json` with the results.

**5-T3** For each of the 5 trial stores, submit a NEW BKI SI (small amount, immediately cancel). Verify each generates a Draft PI on each respective store's books with the right supplier + accounts. Cancel each Draft PI.

**5-T4** S206 sanity check: trigger labor JE creation for one of the 5 trial stores via existing S206 path:
- Labor JE creates against the existing `(Internal)` Customer (UNTOUCHED).
- The new `BEBANG KITCHEN INC. - Trade` Supplier is NOT involved.
- JE submits correctly.

**5-T5** Run full canonical verifier post-trial:
```bash
python scripts/verify_canonical_structure.py 2>&1 | tee output/s238/verification/canonical_post_check.log
```
Must show `ALL CANONICAL`. No new violations vs Phase 0 baseline.

---

### Phase 6 — Closeout (3 units)

**6-T1** Push branch + open PR with all changes (single PR):
```bash
git push -u origin s238-ict003-store-pi-generator
GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms --base production \
  --head s238-ict003-store-pi-generator \
  --title "feat(S238): ICT-003 store-side Purchase Invoice generator" \
  --body-file output/s238/PR_BODY.md
```

PR description calls out:
- ICT-003 implementation gap closed (per Butch's 2026-02-20 directive, still binding).
- 147 GL accounts seeded + 1 new BKI Trade Supplier + 1 Custom Field + 1 BEI Settings toggle + 1 hook + 1 generator module.
- Trial + 5-store regression + S206 sanity all green.
- `is_internal_customer/_supplier` flags ALL untouched.
- Backfill of 839 historical SI deferred (separate sprint if BIR Q1 amendment needed).

**6-T2** Update plan YAML → `status: COMPLETED`, `completed_date`, `pr`, `execution_summary`. Mark S236 v2 as SUPERSEDED in its YAML (`status: SUPERSEDED_BY_S238`).

**6-T3** Update `docs/plans/SPRINT_REGISTRY.md`:
- S238 row → COMPLETED with PR # + verification proof
- S236 row → already PLANNED v2; amend to SUPERSEDED_BY_S238 with explanation

**6-T4** Write `output/s238/SUMMARY.md` — closeout artifact.

**6-T5** Worktree closeout:
```bash
cd F:/Dropbox/Projects/BEI-ERP-s238-ict003-pi-generator && git status --short
cd F:/Dropbox/Projects/BEI-ERP
git worktree remove F:/Dropbox/Projects/BEI-ERP-s238-ict003-pi-generator
```

---

## Phase Budget Contract

| Phase | Units |
|---|---:|
| Phase 0 — Boot + state probe | 4 |
| Phase 1 — Account seeder | 5 |
| Phase 2 — Supplier + Custom Field + Toggle | 5 |
| Phase 3 — PI generator implementation | 10 |
| Phase 4 — ARANETA trial | 8 |
| Phase 5 — 5-store regression + S206 sanity | 5 |
| Phase 6 — Closeout | 3 |
| **Total** | **40 units** |

40 units total — well under 80-unit ceiling. No phase exceeds 12 units. Single-session executable.

---

## Surface Ownership Matrix (S087)

| Surface | Owner | Allowed mutations |
|---|---|---|
| `hrms/api/bki_store_pi_generator.py` | S238 | NEW file |
| `hrms/hooks.py` | S238 | ADD `Sales Invoice on_submit` hook entry |
| `hrms/tests/test_s238_pi_generator.py` | S238 | NEW file (5 tests) |
| `scripts/s238/seed_pi_generator_accounts.py` | S238 | NEW |
| `scripts/s238/seed_bki_trade_supplier.py` | S238 | NEW |
| `scripts/s238/install_bki_si_reference_field.py` | S238 | NEW |
| `scripts/s238/install_bei_settings_toggles.py` | S238 | NEW (or amend existing) |
| `tabAccount` | S238 | INSERT 147 accounts (3 × 49 stores) |
| `tabSupplier` | S238 | INSERT 1 record (`BEBANG KITCHEN INC. - Trade`) + 49 Allowed To Transact With entries |
| `Custom Field` on `Purchase Invoice` | S238 | INSERT 1 field (`bki_si_reference`) |
| `BEI Settings` | S238 | INSERT 2 toggle fields |
| `hrms/api/commissary.py` | NOT S238 | UNCHANGED — including line 1137 hardcode |
| `hrms/api/billing.py` | NOT S238 | UNCHANGED — including line 595 hardcode |
| `hrms/utils/supply_chain_contracts.py` | NOT S238 | UNCHANGED |
| `hrms/utils/labor_allocation.py` | NOT S238 | UNCHANGED |
| `docs/STORE_COMPANY_CANONICAL.md` | NOT S238 | UNCHANGED |
| `tabCustomer` | NOT S238 | UNCHANGED — no flag flips |
| Existing `BEBANG KITCHEN INC. (Internal)` Supplier | NOT S238 | UNCHANGED |
| Existing 839 historical BKI SIs | NOT S238 | UNCHANGED — no backfill |
| `tabCompany` / `tabWarehouse` | NOT S238 | UNCHANGED |

---

## Anti-Rewind / Concurrent-Run Protection

- **protected_surfaces:**
  - 49 per-store billing Customers — UNCHANGED
  - 49 S206 Internal Customers — UNCHANGED
  - 839 historical BKI SI records — UNCHANGED
  - Canonical Rules 1-8 — UNCHANGED
  - `commissary.py:1137`, `billing.py:595` (`is_internal_customer = 0` hardcodes) — UNCHANGED
  - `labor_allocation.py:324-339` (S206 lookup) — UNCHANGED
  - `resolve_store_buyer_entity` — UNCHANGED
- **remote_truth_baseline:** `tmp/s238/remote_truth_baseline_hrms.sha`
- **pretouch_backup:** none required (no master-data mutations on existing records)
- **supersession_map:** S236 v2 → S238 (S236 v2 was wrong architecture; S238 follows ICT-003 correctly)

---

## Requirements Regression Checklist

Executing agent MUST verify before each PR:

- [ ] Canonical preflight ran clean BEFORE any code change (Phase 0)
- [ ] `BEI Settings.bki_sales_income_account` exists (ICT-008 prerequisite verified at Phase 0)
- [ ] 147 accounts seeded across 49 per-store Companies (3 × 49) with proper `account_type` / `root_type` / `report_type` / `parent_account` per per-store CoA
- [ ] 1 NEW Supplier `BEBANG KITCHEN INC. - Trade` created with `is_internal_supplier=0` and `tax_id` populated
- [ ] 49 Allowed To Transact With entries on the new Supplier
- [ ] 1 Custom Field `bki_si_reference` on Purchase Invoice (Link → Sales Invoice, read-only)
- [ ] 2 BEI Settings toggles installed (`enable_bki_store_pi_generator`, `auto_submit_store_pi`)
- [ ] `hrms/api/bki_store_pi_generator.py` implements `maybe_generate_store_pi` with all MUST_CONTAIN strings
- [ ] `hrms/hooks.py` has `Sales Invoice on_submit → maybe_generate_store_pi` entry
- [ ] 5 unit tests in `test_s238_pi_generator.py` all pass
- [ ] Sentry observability — `set_backend_observability_context` called with `module=billing`, `action=maybe_generate_store_pi`
- [ ] ARANETA trial: SI submits, Draft PI auto-created with `supplier=BEBANG KITCHEN INC. - Trade`, `update_stock=1`, `bki_si_reference` populated
- [ ] PI submit creates SLE on per-store warehouse + GL Entries with `party_type=Supplier, party=BEBANG KITCHEN INC. - Trade` (DM-1)
- [ ] PI carries 12% Input VAT mirroring SI's Output VAT
- [ ] 5-store regression: each generates Draft PI correctly
- [ ] S206 labor JE flow STILL works (no resolver/Customer/Supplier collision)
- [ ] Toggle off → no PI generated (kill switch works)
- [ ] Idempotency: re-running generator on same SI → no duplicate PI
- [ ] Canonical post-check `ALL CANONICAL` (zero new violations)
- [ ] DM-1 / DM-2 / DM-3 / DM-4 / DM-5 / DM-6 — verified per checklist
- [ ] No flips to `is_internal_customer/_supplier` anywhere
- [ ] No modifications to `commissary.py:1137`, `billing.py:595`, `labor_allocation.py`, `supply_chain_contracts.py`, `STORE_COMPANY_CANONICAL.md`
- [ ] Worktree closeout clean
- [ ] Test SI + Draft PI cancelled; teardown ledger complete

---

## Autonomous Execution Contract

- **completion_condition:**
  - All 6 phases complete with verify scripts PASS
  - 147 accounts + 1 Supplier + 1 Custom Field + 2 toggles + 1 hook + 1 module shipped
  - ARANETA trial PASS
  - 5-store regression PASS
  - S206 sanity PASS
  - Canonical post-check `ALL CANONICAL`
  - PR opened, plan YAML status: COMPLETED, registry updated, S236 v2 marked SUPERSEDED_BY_S238
- **stop_only_for:**
  - Canonical preflight returns violations (pre or post)
  - `BEI Settings.bki_sales_income_account` not set (ICT-008 prerequisite missing)
  - Per-store CoA structure inconsistent (some stores missing parent groups for the 3 new accounts)
  - 5-store regression reveals existing SI flow regression
  - S206 labor JE flow broken
  - Three failed attempts at the same migration step
  - Sam explicitly requests halt
- **continue_without_pause_through:**
  - Plan write → audit → execute Phases 0→6 → PR creation → closeout
- **blocker_policy:**
  - Hook not firing → debug Frappe hook registration; bench restart; retry
  - PI insert blocked by validation → check accounts + supplier + party fields; retry
  - 3 consecutive trial failures → STOP and reassess
- **signoff_authority:** `single-owner` (Sam)
- **canonical_closeout_artifacts:**
  - `output/s238/SUMMARY.md`
  - `output/s238/verification/before_state.json`
  - `output/s238/verification/after_state.json`
  - `output/s238/verification/aranetatrial_pi.json`
  - `output/s238/verification/historical_si_regression.json`
  - `output/s238/verification/canonical_post_check.log`
  - `docs/plans/2026-05-07-sprint-238-ict003-store-pi-generator.md` (status COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (S238 row → COMPLETED, S236 row → SUPERSEDED_BY_S238)

---

## Status Reconciliation Contract

Whenever counts, blockers, stage, or status changes, update in the same work unit:
1. `output/s238/SUMMARY.md`
2. plan YAML status line + `execution_summary`
3. `SPRINT_REGISTRY.md` S238 row + S236 supersession note
4. `output/s238/verification/*.json` files
5. teardown ledger
6. canonical post-check log

---

## Signoff Model

- **mode:** `single-owner`
- **approver_of_record:** Sam Karazi (CEO) — CFO seat vacant indefinitely per 2026-05-07 update to DECISIONS.md
- **signoff_artifact:** `output/s238/SUMMARY.md`
- **note:** Sam approved the architecture in conversation 2026-05-07. No further sign-off required during execution unless one of the `stop_only_for` conditions trips.

---

## Ground-Truth Lock

- **evidence_sources:**
  - `data/_CONSOLIDATED/01_FINANCE/DECISIONS.md:193-200` (ICT-001..008 verbatim)
  - `data/_CONSOLIDATED/01_FINANCE/questionnaires/CFO_INTERCOMPANY_Butch_Formoso_2026-02-20.md:35-42` (Q3 verbatim)
  - `hrms/api/commissary.py:864-988, 973-1248` (existing SI builder)
  - `tmp/CANONICAL_COVERAGE_AUDIT_SUMMARY.md` (audit findings)
  - `tmp/pi_probe.json` (839 SI / 0 PI on store side)
  - `output/plan-audit/s236-intercompany-auto-trade/AUDIT_SUMMARY.md` (S236 v2 audit, the basis for v1→S238 reframe)
- **count_method:**
  - SI count: `SELECT COUNT(*) FROM tabSales Invoice WHERE company='BEBANG KITCHEN INC.'`
  - PI count: `SELECT COUNT(*) FROM tabPurchase Invoice WHERE supplier LIKE 'BEBANG KITCHEN%'`
  - Account count: `SELECT COUNT(*) FROM tabAccount WHERE account_name LIKE '%Inventory-from-Commissary%' OR ...`
  - basis: live SQL via SSM-Frappe
- **authoritative_sections:** Sections "Design Rationale" + "Phases 0-6" + "Surface Ownership" + "Requirements Regression Checklist" are authoritative for execution
- **normalization_required:** any amendment changing seed counts, hook surface, or canonical impact must update authoritative sections in the same edit
- **unresolved_value_policy:** operator-facing unknowns → `[UNVERIFIED — requires resolution]`
- **normalization_artifacts:** `output/s238/verification/before_state.json`, `output/s238/verification/after_state.json`

---

## Execution Skills Reference

- Test Python changes: `/local-frappe`
- Deploy changes: `/deploy-frappe`
- Full workflow: `/agent-kickoff`
- E2E testing: `/e2e-test`
- Bulk data ops: `/frappe-bulk-edits` (use for the 3 idempotent seed scripts)

---

## Sprint Registry Row (Evidence of Lock)

```
| `S238` | Sprint 238 | `s238-ict003-store-pi-generator` | TBD | PLANNED 2026-05-07 — ICT-003 Store-Side Purchase Invoice Generator | `docs/plans/2026-05-07-sprint-238-ict003-store-pi-generator.md` |
```

Cross-checked: `git branch -a | grep s238` returned no matches before reservation; `ls docs/plans/ | grep sprint-238` empty.

---

## Execution Authority

Single agent, single session. Phase 0 through Phase 6, end to end. 40 units. Stop only for items in `stop_only_for`. Sam has pre-approved the architecture; no Phase-0 decision gate needed.
