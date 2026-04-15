# Phase 1 Finding — JL TRADE OPC may not be stale

**Source:** `hrms/api/company_master.py:1143` _STORE_OVERRIDES map

**Finding:** `JL TRADE OPC` is referenced in `_STORE_OVERRIDES` as:
```
"JL TRADE OPC": {"store": "SM San Jose Del Monte", "tin": "775-842-763-00003", "rdo": "25B"}
```

This means `JL TRADE OPC` is the legal operator / BIR-registered entity for **SM San Jose Del Monte** store, with TIN `775-842-763-00003` and RDO `025B`.

**Conflict with audit v3 plan:**

The S196 plan (under "Predecessor work" + Phase 2 Step H) describes deleting `JL TRADE OPC` as "stale, 0 transactions, abbr BSS2 confusion with BSS (BEBANG SM SANGANDAAN), not in team sheet".

But `_STORE_OVERRIDES` shows it's the BIR-registered operator for SM SJDM. Also note:
- `LEGACY77 FOOD CORP.` (abbr L77) owns the `SJDM - BEI` warehouse currently (per earlier Phase 0 inventory)
- `JL TRADE OPC` (abbr BSS2) has 5 template warehouses, 0 orderable
- Both Companies appear to be linked to the same store (SM SJDM)

**Hypothesis:** `JL TRADE OPC` is the REAL legal corp (has a real TIN + RDO). `LEGACY77 FOOD CORP.` might be a DBA / legacy label that was created first and never retired. OR JL TRADE OPC was created recently to replace Legacy77 (the `SM San Jose Del Monte` team sheet entry says `Legacy77 Food Corp` but that could be a trade name).

**Recommendation for Phase 2:**
- **DO NOT DELETE** `JL TRADE OPC` in Phase 2 Step H
- Instead, treat this as a data reconciliation issue outside S196 scope
- Update Phase 2 plan to scope H as "review JL TRADE OPC vs Legacy77 linkage — decision deferred to Sam"
- Add to out-of-scope section

**Action taken in this session:**
- `JL TRADE OPC` entry in `_STORE_OVERRIDES` is PRESERVED (not modified in Phase 1)
- Phase 2 Step H will SKIP the JL TRADE OPC deletion and produce `output/s196/state/JL_TRADE_DECISION_PENDING.md` for Sam

**Evidence:**
- Team sheet row for SM SJDM: `SM San Jose Del Monte,Legacy77 Food Corp,Managed Franchise,SJDM - Bebang Enterprise Inc.,BKI_TO_STORE_INTERCOMPANY,active`
- `_STORE_OVERRIDES:1143` maps `JL TRADE OPC` → `SM San Jose Del Monte` with `tin=775-842-763-00003 rdo=25B`
- Production: `LEGACY77 FOOD CORP.` (L77) has 1 orderable warehouse `SJDM - BEI`; `JL TRADE OPC` (BSS2) has 0 orderable
