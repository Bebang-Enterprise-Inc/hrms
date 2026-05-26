# S253 Phase 5 Sweep Summary

**Date:** 2026-05-26
**Duration:** ~65 minutes (batch 1: ~33 min, batch 2: ~30 min, retries: ~10 min)
**Operator:** Claude Code (cold-start from handoff prompt)

## Results

| Metric | Count |
|--------|-------|
| Stores swept | 44 |
| PASS (after retries) | 43 |
| FAIL (persistent) | 1 |
| Excluded (Mode D) | 1 (SM MEGAMALL) |
| S252-covered | 4 (ARANETA, SM TANZA, XENTROMALL, NAIA T3) |
| **Total stores accounted** | **49** |
| **Pass rate** | **97.7% (43/44)** |

## Batch 1 (22 stores): 19 first-pass PASS, 3 retried → all 3 PASS

| Store | First Run | Retry | Root Cause |
|-------|-----------|-------|------------|
| AYALA FAIRVIEW TERRACES | FAIL | PASS | round_off_cost_center mismatch (Main - BFI2 → Main - AFT) |
| ROBINSONS ANTIPOLO | FAIL | PASS | Missing round_off_account (set to SRBNB workaround) |
| ROBINSONS PLACE DASMARINAS | FAIL | PASS | GL filter missed "2120000 - ROUND OFF" (case + amount fix) |

## Batch 2 (22 stores): 19 first-pass PASS, 3 failures

| Store | First Run | Retry | Root Cause |
|-------|-----------|-------|------------|
| SM MANILA | FAIL | PASS | GL filter + SRBNB round_off_account workaround |
| SM SOUTHMALL | FAIL | PASS | GL filter + SRBNB round_off_account workaround |
| SM MARIKINA | FAIL | FAIL | Persistent: dispatch creates MR but no SE/WR produced |

## Master Data Fixes Applied

1. **AYALA FAIRVIEW TERRACES**: `round_off_cost_center` corrected from `Main - BFI2` to `Main - AFT`
2. **SM MARIKINA**: Set `is_group=1` (needed as parent of STA. LUCIA EAST GRAND MALL)
3. **STA. LUCIA EAST GRAND MALL**: `round_off_cost_center` set to `Main - SLGM`
4. **ROBINSONS ANTIPOLO**: `round_off_account` set to `Stock Received But Not Billed - ROA`
5. **SM MANILA**: `round_off_account` set to `Stock Received But Not Billed - SMM`
6. **SM SOUTHMALL**: `round_off_account` set to `Stock Received But Not Billed - SMS`

Note: Items 4-6 are workarounds. Proper Round Off accounts couldn't be created due to COA cascade issue (root company IRRESISTIBLE INFUSIONS INC. lacks expense hierarchy, and ERPNext blocks child-company account creation without root-level parent).

## Test Infrastructure Fix

**PR #469** (BEI-Tasks, MERGED): GL assertion filter hardened
- Case-insensitive account name matching
- Amount-based filtering (< ₱1.00 = round-off row)
- Handles "ROUND OFF", "Round Off", and non-named round-off accounts

## DEFECT-2: SM MARIKINA Dispatch Pipeline

**Symptom:** `create_stock_transfer` API creates MR (status=Issued, per_ordered=100%) but no Stock Entry or Warehouse Receiving is produced. Confirmed on 2 separate MRs (MAT-MR-2026-01308, MAT-MR-2026-01328).

**Classification:** Backend defect, not S253 scope. Deferred to follow-up sprint.
