# V15 Billing Chain Audit — 49 Sales Invoices

## Verdict

**49/49 SIs are billed to the correct per-store Customer (the BD-registered corporation).** The single flagged "mismatch" is fixture metadata staleness, not a billing defect.

## Methodology

For each of the 49 SIs created during the v15 sweep, verified 7 properties:

| Check | Pass count |
|---|---|
| `SI.customer` matches fixture per-store Customer | **49/49** |
| `SI.company` is BKI (seller per ICT-005) | **49/49** |
| GL Entry `party=Customer` debits the per-store Customer (DM-1) | **49/49** |
| Customer record exists with valid `customer_name` | **49/49** |
| `Customer.tax_id` matches fixture `tin` | 48/49 (1 stale fixture) |
| `SI.tax_id` matches fixture `tin` | 48/49 (same store) |
| `Company.parent_company` matches fixture `parent_company` | **49/49** |

## What "billing to the correct corporation" means in this audit

Each store has **four canonical records** with matching `name` strings (per `STORE_COMPANY_CANONICAL.md`):
1. Per-store **Company** — the BIR-registered legal entity (e.g., `ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC`)
2. Per-store **Warehouse** — the stock-holding location, owned by that Company
3. Per-store **Customer** — the buyer entity Bebang Kitchen Inc. invoices for intercompany transfers
4. Per-store **Internal Customer** — for inter-company recognition

The per-store Company has a `parent_company` field linking it to the **BD/holding corporation** (e.g., `TUNGSTEN CAPITAL HOLDINGS OPC` for ARANETA GATEWAY franchises).

For billing correctness:
- The **SI buyer** must be the per-store Customer (not the parent corporation directly)
- The per-store Customer's `tax_id` must match the BIR-registered TIN of the per-store legal entity
- The Company's `parent_company` must match the BD-registered holding entity for ledger consolidation

All 49 SIs satisfy these constraints.

## The 1 stale-fixture finding (not a billing bug)

**Store**: ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC
**SI**: ACC-SINV-2026-00732

| Field | Fixture (stale) | Production (current) |
|---|---|---|
| Customer name | ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC | ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC ✓ |
| Customer TIN | `""` (empty) + `allowEmptyTin: true` | `688-721-280-00000` |
| SI buyer | per-store Customer ✓ | per-store Customer ✓ |
| SI TIN | (matches Customer) | `688-721-280-00000` |
| GL party | per-store Customer ✓ | per-store Customer ✓ |

The fixture was created when BEIFRANCHISE FOOD OPC had no BIR TIN yet. A TIN has since been registered (`688-721-280-00000`) and stamped on the Customer record. The SI correctly inherits that TIN. **Recommended follow-up**: update fixture `s204_all_stores.json` to set `tin: "688-721-280-00000"` and `allowEmptyTin: false` for ORTIGAS GREENHILLS — but this is documentation, not a billing fix.

## Per-store Customer + Company + parent_company snapshot (sample)

Some examples confirming the BD corporation chain is correct:

| Store | Per-store Customer (SI buyer) | Customer TIN | Company.parent_company (BD holding) |
|---|---|---|---|
| ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC | (same) | 679-843-234-00000 | TUNGSTEN CAPITAL HOLDINGS OPC |
| AYALA EVO CITY - BEBANG MEGA INC. | (same) | 010-885-436-00000 | BEBANG MEGA INC. |
| AYALA FAIRVIEW TERRACES - BEBANG FT INC. | (same) | 663-440-106-00000 | BEBANG ENTERPRISE INC. |
| THE GRID ROCKWELL - TASTECARTEL CORP. | (same) | (per BIR registration) | (none — direct ownership) |
| SM MARIKINA - BEBANG SM MARIKINA INC. | (same) | (per BIR) | BEBANG ENTERPRISE INC. |
| STA. LUCIA EAST GRAND MALL - BEBANG SM MARIKINA INC. | (same) | (per BIR) | SM MARIKINA - BEBANG SM MARIKINA INC. |

Full per-store details in `v15_billing_audit.json`.

## Independent verification of GL impact

For all 49 SIs, the GL Entry with `party_type=Customer` had `party=<per-store Customer>`. This means:
- Receivable was booked **against the per-store legal entity's account** (e.g., `Debtors - ARGW` for ARANETA GATEWAY)
- Revenue was booked to BKI's income account
- Inter-company DM-1 invariant satisfied (party = customer name = legal entity name)

No SI booked the receivable against a parent holding entity.
No SI booked the receivable against the wrong legal entity.

## Audit script

`scripts/s225/audit_v15_billing.py` (committed in PR #704). Re-runnable against any future sweep ledger.
