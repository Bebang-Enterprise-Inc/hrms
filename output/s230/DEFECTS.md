# S230 Defect Register

## Defects detected during execution

### DEFECT-1 (PRE-EXISTING — not caused by S230, flagged for follow-up)
**System:** Frappe `tabEmployee`
**Affected:** 4 Estancia crew (Bio IDs 9001827, 9001830, 9001832, 9001835)
**Description:** All 4 are present in Master CSV (`data/_FINAL/EMPLOYEE_MASTER.csv`) with `store_location=ESTANCIA` and `Active` status, but missing from Frappe `tabEmployee`. They have ADMS USERINFO commands ACKED on most C2 cluster devices but no Frappe Employee record. This means:
  - They can punch and ADMS records the punches
  - Payroll cannot process them (no Frappe Employee → no payroll cycle inclusion)
**Root cause:** Anomaly class A1 in S228's plan (Bio IDs reserved in Master CSV but missing from Frappe production). S228's Phase 4 (Frappe inserts) is intentionally held by Sam pending HR audit.
**Action:** Out of scope for S230 per Sam directive 2026-04-29. Tracked in S228 scope. Will be addressed when HR completes Master audit and S228 P4 is greenlit.

### NOTE-1 (NOT a defect — informational)
**System:** ADMS `adms_device_cmd`
**Affected:** UDP3252900249 (Estancia home device)
**Description:** Device has 54 PRESERVED PENDING commands from 2026-03-30 (roving-employee batch enrolled before device was deployed). Plus 4 PENDING from earlier Estancia 4-crew cluster cross-enrollment. Total ~58 PENDING. All will replay when device heartbeats.
**Action:** No action — preserved by design (S230 supersession_truth: "this sprint does NOT supersede any prior packet").

### NOTE-2 (NOT a defect — informational)
**System:** ADMS `adms_device_cmd`
**Affected:** Estancia crew already on UDP3252900305 (Vista Mall Taguig — C1, NOT C2)
**Description:** Live audit found 9001827, 9001830, 9001835 ACKED on UDP3252900305 (Vista Mall Taguig). That device is in Cluster 1, not Cluster 2 (where Estancia belongs). This is pre-existing stray cross-enrollment, possibly from an earlier batch.
**Action:** No action this sprint. Could be cleaned up via `DATA DELETE USERINFO` in a future hygiene sprint if Sam wants strict cluster isolation.

## No defects caused by S230 execution.

All 48 INSERT operations succeeded (`INSERT 0 48` confirmed). All MUST_MODIFY assertions passed. No rollback events triggered.
