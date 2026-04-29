# S230 Phase 0 Provenance

Captured 2026-04-29 11:35 PHT during /execute-plan-bei-erp execution.

## Sam's answers (Phase 0 task 0-4 user-input gate):

- xentro_serial: UDP3254701502
- xentro_serial_source: Archie (BEI IT) — provided to Sam, relayed in conversation
- xentro_crew_mode: roster (12 employees, all already in Master CSV + Frappe tabEmployee)
- xentro_branch_name: XENTROMALL MONTALBAN (with MALL, matches Frappe tabEmployee.branch for all 12 existing crew)
- estancia_branch_name: ORTIGAS ESTANCIA (matches Frappe tabBranch + per-store Warehouse short form)
- enrollment_mode: cross_cluster (Sam confirmed Q4=b)

## Sam's directives that supersede v2 plan:

1. NO Frappe `tabEmployee` inserts in S230. S228 is waiting for HR audit; S230 follows the same pattern.
2. NO Google Sheet sync in S230 (implied — only Master CSV is needed).
3. "Make sure everyone is in employee master" — VERIFIED below.
4. ADMS enrollment is the only mutation surface for HR data.

## Roster verification (all 16 crew confirmed in Master CSV via live awk/csv):

### Xentro Mall (12 crew, branch=XENTROMALL MONTALBAN):
9001838 ESTUR, JOSHUA M.
9001839 CULPA, ALEXANDER A.
9001840 ALEJO, BINOE LOUISE M.
9001841 GIRAY, ARVIN A.
9001842 GEROLAO, MAE ANN B.
9001843 GABUYO, PRINCESS DIANE A.
9001844 LAMUD, ERALEEN JOYCE A.
9001845 MAHINAY, JELINA E.
9001846 POBLETE, MARIA NERISSA B.
9001847 YAGO, SIDRICK J.
9001865 DELA PEÑA, SHEILA MAE M.
9001866 ALONZO, BABIELYN G.

### Estancia (4 crew, branch=ORTIGAS ESTANCIA):
9001827 PAGSALIGAN, HAYDEE D.
9001830 MORALES, MAE PEARL GRACE E.
9001832 MARTILLANO, LUISA B.
9001835 VILLAREAL, JENNY A.

## Cluster assignments:

- Xentro Mall → Cluster 5 (Jocelyn Chan): SM East Ortigas, Marikina, Taytay, Sta Lucia, Robinsons Antipolo + Xentro (UDP3254701502) = 6 devices
- Estancia → Cluster 2 (Erick Montialto): Megamall, NEDSA, CTTM, Gateway + Greenhills + Estancia = 6 devices

## Existing ADMS state (live SSM 2026-04-29):

### Xentro 12 already ACKED on temp devices:
- All 12 ACKED on CNYG242061071 (SM Marikina)
- All 12 ACKED on UDP3251600245 (Brittany Office)
- All 12 ACKED on UDP3252900155 (Sta Lucia East)
- 8 of 12 actively punching there (last punch 2026-04-05/06)

### Estancia 4 already ACKED on most C2:
- All 4 ACKED on UDP3235200631 (Megamall), UDP3235200831 (NEDSA), UDP3252100384 (CTTM), UDP3252900251 (Greenhills), UDP3252900302 (Gateway)
- All 4 PENDING on UDP3252900249 (Estancia home — device offline since 2026-03-30)
- ZERO punches in last 30 days (waiting for home device or working elsewhere)
- Stray ACKED on UDP3252900305 (Vista Mall Taguig — C1 not C2; possible legacy enrollment)

## Net-new USERINFO commands needed for cross-cluster:

### Xentro 12 × 6 C5 devices = 72 cells, of which:
- 36 already ACKED on Marikina (6/12)... wait actually 12 each on Marikina, Brittany, Sta Lucia = 36, but Brittany is Head Office not C5.
- C5 devices: SM East Ortigas (UDP3251200193), Marikina (CNYG242061071), Taytay (UDP3252900048), Sta Lucia (UDP3252900155), Antipolo (UDP3235200594), Xentro (UDP3254701502)
- Already ACKED: 12 × Marikina + 12 × Sta Lucia = 24 cells
- Need new USERINFO: 12 × SM East Ortigas + 12 × Taytay + 12 × Antipolo + 12 × Xentro = 48 commands

### Estancia 4 × 6 C2 devices = 24 cells, of which:
- C2 devices: Megamall (UDP3235200631), NEDSA (UDP3235200831), CTTM (UDP3252100384), Gateway (UDP3252900302), Greenhills (UDP3252900251), Estancia (UDP3252900249)
- Already ACKED: 4 × 5 = 20 cells (everything except UDP3252900249 which is PENDING)
- Already PENDING: 4 × Estancia = 4 cells (will fire when device comes online)
- Need new USERINFO: 0 (cross-cluster already complete)

## Total new commands to push:
- 48 for Xentro (SM East Ortigas + Taytay + Antipolo + Xentro home)
- 0 for Estancia (already enrolled cross-cluster)
- Total: 48 new USERINFO commands across 4 devices

## S228 status (per Sam): 
Frappe inserts are INTENTIONALLY held pending HR audit. Same pattern adopted for S230.
