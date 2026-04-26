# ORTIGAS GREENHILLS TIN — Source-of-Truth Policy (S223)

**Decision (Sam directive 2026-04-25):** apply HQ TIN `688-721-280-00000` to `Customer.tax_id`.

**Both TINs belong to the same legal entity:**
- HQ TIN `688-721-280-00000` — BEIFRANCHISE FOOD OPC headquarters (chosen, applied here)
- branch TIN `688-721-280-00001` — Ortigas Greenhills physical location, RDO 042

**Applied:** 2026-04-25 PHT via `scripts/s223_ortigas_apply_tin.py`.

**Result:**
- `Customer.tax_id` for `ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC` was empty before; now `688-721-280-00000`.
- Canonical postcheck: 0 violations (was 1 — BILLING_CUST_TIN_EMPTY now resolved).
- Prior submitted Sales Invoices for this Customer: **0**. No BIR §237 retroactive review needed.

**Known follow-up (out of scope for S223):** existing auto-provision hook at `hrms/overrides/company.py` writes branch TIN to `Customer.tax_id` on new Company creation. This conflicts with the HQ-TIN policy chosen here. Mitigation:
- The hook only fires on NEW Company creation events.
- ORTIGAS GREENHILLS Company already exists, so the hook will not run for this record.
- Future fix can either (a) update the hook to read HQ TIN, or (b) keep the hook as-is if BIR/Finance conclude branch TIN is the correct semantic.

**Sources:**
- `hrms/data_seed/company_register_2026-04-14.csv` row 38 (line 77) — HQ TIN `688-721-280-00000` (chosen)
- `hrms/data_seed/ENTITY_TIN_RDO_2026-02-27.csv` row 49 (line 50) — branch TIN `688-721-280-00001` (not applied here)

**Evidence:**
- Before snapshot: `output/s223/verification/ortigas_customer_before.json`
- After snapshot: `output/s223/verification/ortigas_customer_after.json`
- SI history: `output/s223/verification/ortigas_si_history.json` (empty array — no prior SIs)
- Canonical postcheck: `output/s223/verification/canonical_postcheck_phase5.txt`
