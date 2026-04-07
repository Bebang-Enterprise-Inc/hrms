# S167 Test Data Manifest

All data created during the S167 acceptance test, tracked for rollback verification.

## Created (all DELETED in Phase 6)

### PCF Funds (3)
| Name | Dept | Custodian | Created | Deleted |
|---|---|---|---|---|
| PCF-HR and Admin | HR and Admin - BEI | test.hr@bebang.ph | Phase 0.1 | Phase 6 ✅ |
| PCF-Supply Chain | Supply Chain - BEI | test.warehouse@bebang.ph | Phase 0.1 | Phase 6 ✅ |
| PCF-Commissary | Commissary - BEI | test.commissary@bebang.ph | Phase 0.1 | Phase 6 ✅ |

### Expense Requests (4)
| Name | Vendor | Amount | Fund | Deleted |
|---|---|---|---|---|
| BEI-EXP-2026-00078 | National Book Store | ₱480 | PCF-HR and Admin | Phase 6 ✅ |
| BEI-EXP-2026-00079 | Jollibee | ₱350 | PCF-HR and Admin | Phase 6 ✅ |
| BEI-EXP-2026-00080 | 7-Eleven | ₱250 | PCF-Commissary | Phase 6 ✅ |
| BEI-EXP-2026-00081 | Ace Hardware | ₱480 | PCF-Commissary | Phase 6 ✅ |

### PCF Batches (2)
| Name | Fund | Amount | Final Status | Deleted |
|---|---|---|---|---|
| BEI-PCF-2026-00003 | PCF-HR and Admin | ₱830 | Approved (COA + amount overrides) | Phase 6 ✅ |
| BEI-PCF-2026-00004 | PCF-Commissary | ₱730 | Rejected | Phase 6 ✅ |

## Modified (all RESTORED in Phase 6)

### Employee Department Reassignments
| Employee | Field | Original | Applied | Restored |
|---|---|---|---|---|
| TEST-HR-001 | department | Human Resources - BAG | HR and Admin - BEI | ✅ |
| TEST-COMMISSARY-001 | department | Dispatch - BAG | Commissary - BEI | ✅ |
| TEST-WAREHOUSE-001 | department | Dispatch - BAG | Supply Chain - BEI | ✅ |

## Untouched

- `PCF-TEST-STORE-BGC - BEI` (pre-existing, custodian test.supervisor) — referenced a missing warehouse (DEFECT-004) but not created, modified, or deleted by this run.
- All 44 other pre-existing store PCF funds.
- All Employee records not listed above.
- All Frappe user accounts and passwords.

## Transient corruption during run

- `BEI Expense Request BEI-EXP-2026-00079.internal_suggested_coa` was set to `6010100` by `classify_batch_items` during Phase 3.2a (DEFECT-009). Cleared to `""` during Phase 6 rollback before deletion. The defect remains in the classifier — any future batch classification will recreate the problem until DEFECT-009 is fixed.
- `BEI PCF Batch Item b7t6fc34lt.suggested_coa` was set to `6010100` by the same classifier. Cleared during Phase 3.2b retry.
