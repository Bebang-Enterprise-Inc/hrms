# Sprint Numbering Policy
**Effective Date:** 2026-03-01  
**Owner:** BEI ERP Program Governance  
**Status:** Active SSOT

## 1) Purpose
Establish one continuous sprint numbering system for the BEI ERP program and prevent future drift between numeric, alphabetic, and domain-specific sprint labels.

## 2) Canonical Format
1. Canonical sprint ID format is `S###` (zero-padded).
2. Human-readable display format is `Sprint NN` (for example, `Sprint 15`).
3. Optional parallel lane suffix is allowed only as `S###A`, `S###B`, `S###C`.
4. `run_id` and `run_group_id` are execution identifiers, not sprint numbers.

## 3) Numbering Rules
1. Sprint numbers never reset for this project.
2. New sprint numbers must increment by one from the latest canonical sprint.
3. A sprint number can have multiple lanes (`A/B/C`) only when explicitly declared in the registry.
4. Done sprint numbers are immutable and cannot be reused.
5. Any document using a legacy sprint label must include its canonical mapping in `docs/plans/SPRINT_REGISTRY.md`.

## 4) File Naming Rules (Forward Standard)
1. Canonical sprint plan filename:
   - `docs/plans/YYYY-MM-DD-sprint-NN-<slug>.md`
2. Canonical sprint lane filename:
   - `docs/plans/YYYY-MM-DD-sprint-NN<lane>-<slug>.md`
3. Legacy files are not renamed unless required by a dedicated cleanup change.

## 5) Legacy Mapping Decisions (Locked)
1. Historical canonical sequence `S001` to `S013` remains unchanged.
2. Legacy lettered closures (`Sprint A/B/C`, dated 2026-02-28) are mapped to `S014A`, `S014B`, `S014C`.
3. The 2026-03-01 end-to-end mapping refresh run is mapped to `S015`.

## 6) Required Process Before Starting a New Sprint
1. Add a new row in `docs/plans/SPRINT_REGISTRY.md`.
2. Reserve the next canonical sprint ID.
3. Add canonical sprint metadata block to the new sprint plan.
4. Reference the canonical ID in all related run artifacts and closeout notes.

## 7) Compliance Check
A sprint plan is non-compliant if any of the following is true:
1. Uses only `Sprint A/B/C` with no canonical mapping.
2. Reuses an existing canonical sprint ID.
3. Introduces a sprint number lower than the latest registry entry.
4. Omits canonical sprint metadata for new sprint plans.

## 8) Validation Command
Run before opening a new sprint plan:

```bash
python scripts/audit/sprint_numbering/validate_sprint_numbering.py
```
