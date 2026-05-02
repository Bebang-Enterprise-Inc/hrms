# S231 Defects Ledger

**Status as of 2026-05-02 12:00 PHT:** none discovered during code-only phases.

The Phase B SSM sweep (`scripts/s231_fix_all_broken_defaults.py`) appends here
when a Company fails BOTH `retry_provision_company` AND null-only strategies.

The Phase E-3 BFC dedup script (`scripts/s231_dedup_bfc.py`) appends here when
the duplicate Company has more than 100 transactions and the HARD BLOCKER
trips.

Empty sections below mean nothing yet — file is committed at code-PR time so
the path exists for the SSM scripts to append to.

---

## Phase A defects

(none)

## Phase B defects (manual review required)

(none yet — populated by `s231_fix_all_broken_defaults.py` SSM run)

## Phase C defects

(none — atomicity wrapper + validate hook ship clean)

## Phase D defects

(none — pricing coupling code-complete)

## Phase E defects

(none yet — populated by `s231_dedup_bfc.py` SSM run if HARD BLOCKER trips)

## Test failures

(none — 23 unit tests added; the 6 markup_coupling tests pass under plain
`pytest` locally; the 17 Frappe-runtime tests will run via `bench --site
hq.bebang.ph run-tests` after deploy)
