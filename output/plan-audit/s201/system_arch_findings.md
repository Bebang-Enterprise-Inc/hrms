# S201 System Architecture Audit Findings

**Auditor:** System Architecture Domain Auditor (Claude Sonnet 4.6)
**Date:** 2026-04-17
**Plan file:** docs/plans/2026-04-17-sprint-201-per-store-employee-billing-foundation.md
**Code reviewed:** hrms/utils/company_lookup.py, hrms/utils/non_store_billing.py,
  hrms/overrides/employee_master.py, hrms/api/transfers.py,
  hrms/data_seed/branch_company_map.csv, hrms/utils/roving_employees.py,
  hrms/hooks.py, bei-tasks/hooks/use-employee.ts,
  bei-tasks/app/api/employee/me/route.ts

---

## FINDING-1 [WARNING] — Three-Source Resolver: Disagreement Protocol Undefined

**Topic:** Branch → Company resolution path

The resolver in `company_lookup.py` pulls from three sources:

1. `branch_company_map.csv` (file on disk, loaded at startup + 60s TTL)
2. `roving_employees.py` (hardcoded Python dict, compile-time constant)
3. Live Frappe Company table (`entity_category='Store'`, queried at cache load)

**Disagreement scenarios not handled:**

- **CSV says Store/SM MEGAMALL but live Frappe Company no longer exists** (e.g., company was deleted/renamed post-S196): `_store_company_index.get()` returns None, triggers `UnknownBranch`. The plan's validate hook swallows this silently (`return` on UnknownBranch). The employee saves without updating company. No alert, no audit trail. Silent regression.

- **CSV has old_branch key but new_branch differs from Company prefix** (e.g., `target_company_hint='SM MEGAMALL'` but live Company is actually `SM MEGAMALL - BEBANG ENTERPRISE INC.`): The prefix split `name.split(" - ", 1)[0]` depends on the ` - ` separator being present. If a Company name was created without that separator (e.g. `BEBANG KITCHEN INC.`), it never appears in `_store_company_index` for store lookups. This is currently benign only because BKI is handled via category=Commissary, but the pattern is fragile.

- **CSV updated on disk but cache not yet expired**: up to 60 seconds of stale lookups. During a live branch rename, employees saving in that window get the wrong company. No mechanism to detect or alert on this.

**Recommendation:** Add a `frappe.log_error` call on each `UnknownBranch` catch in `derive_company_from_branch` so silent misses appear in Frappe Error Log. The current code returns silently with no trace.

---

## FINDING-2 [WARNING] — 60s Cache TTL Acceptable for Payroll-Affecting Data; Failure Mode Is Silent

**Topic:** Cache invalidation strategy

The 60s TTL is acceptable in steady state. The on_update hooks on Branch and Company doctypes (`hooks.py:203-204`) correctly call `clear_cache()` immediately on any Frappe Desk edit.

**However, two gaps exist:**

1. **Direct SQL updates bypass on_update hooks.** Phase 6 (branch rename) uses `frappe.rename_doc()` which does fire hooks. Phase 7 (backfill) uses direct `UPDATE tabEmployee SET company=...` which does NOT fire Employee on_update, but that is intentional. The risk is if a third-party migration script or a future sprint directly updates `tabBranch` or `tabCompany` via SQL — the cache will not be invalidated and the 60s TTL is the only backstop.

2. **Worker process isolation.** Frappe runs multiple worker processes (RQ workers). `_branch_map_cache` is a module-level dict — it is process-local. If a web worker clears the cache via `clear_cache()` triggered by an on_update hook, other worker processes (background jobs) keep their own stale copy until their own TTL expires. This means the backfill patch (Phase 7) runs in a background worker context and may resolve companies from a cache that is up to 60s stale relative to the just-renamed branches. Phase 6 must complete and all worker caches must have expired before Phase 7 runs.

**Mitigation already present:** Phase plan says dry-run Phase 7 requires Sam approval, implying sequential execution with time gap. Sufficient if operators follow the order.

---

## FINDING-3 [CRITICAL] — Classifier Rule Ordering: bio_id First Is Wrong Precedence

**Topic:** Classifier rule ordering

The plan states: `bio_id → designation → department → branch category → default`.

The **actual shipped code** in `non_store_billing.py` implements: `bio_id → designation → department → branch category → default`. This matches the plan. The concern is with the **direction of the rules when conflicts arise**:

**Gap 1 — AS (designation=Area Supervisor) with department=Operations:**
- Rule 2 matches: `"AREA SUPERVISOR" in desig` → returns True (BEI parent). Correct per LD-2.
- No conflict. However the plan says rule ordering is `bio_id → designation → department` but does not document that it was intentionally chosen for this case.

**Gap 2 — Roving bio (bio_id in ROVING_EMPLOYEES) but department=IT:**
- Rule 1 matches: `is_roving(bio_id)` → returns True (BEI parent). Correct — the explicit roving list overrides department.
- But this means an IT employee who has NOT been added to ROVING_EMPLOYEES but has department=IT will be caught by Rule 3. If someone accidentally adds a store-employee's bio_id to ROVING_EMPLOYEES (the dict is manually maintained), they will be silently routed to BEI parent regardless of their actual department/designation.

**Gap 3 — Commissary classification is NOT in is_non_store_billing at all.** The classify chain for commissary employees is: `is_non_store_billing_doc()` returns False (no commissary logic there) → falls through to `resolve_branch_to_company(branch, department=department)` in the validate hook. Commissary routing is handled inside `resolve_branch_to_company` via `DEPT_DRIVEN` hint. This split means the "commissary biller" classification is spread across two functions with no single authoritative entry point documenting the three-way split (BEI | BKI | Store). A future developer reading `is_non_store_billing.py` will not know BKI routing exists.

**Gap 4 — No conflict enumeration in plan.** The plan has zero documentation of what happens when rules collide. Recommend adding a conflict table in the plan or code docstring.

---

## FINDING-4 [WARNING] — CSV as SSOT + Frappe Desk as SSOT: Two Sources Can Diverge

**Topic:** Single source of truth

The plan states "`hrms/data_seed/branch_company_map.csv` is SSOT." But Frappe Branch doctype is separately the truth for valid Branch names.

**Gap:** If an operator creates a new Branch directly in Frappe Desk (e.g., a new store opening mid-year), the Branch exists in `tabBranch` but has no row in `branch_company_map.csv`. The next Employee save with that new branch will throw `UnknownBranch` inside `derive_company_from_branch`, which the hook catches and silently no-ops (line 90-91: `return`). The employee saves with an unchanged — possibly wrong — company. No error surfaces to the operator.

**Is this intended?** The plan does not address this explicitly. The validate hook behavior (silent no-op on UnknownBranch) means new-branch employees are silently mis-allocated until someone notices and updates the CSV + deploys.

**Risk level:** This is a deployment-day risk for any new store opened after S201 ships. The gap between a new Frappe Branch record and the CSV being updated is unbounded.

**Recommendation:** In `derive_company_from_branch`, on `UnknownBranch` exception, add `frappe.log_error(...)` AND `frappe.msgprint(...)` (warning, not error) so HR sees a notification that the branch is unmapped. Current code silently returns.

---

## FINDING-5 [WARNING] — Stored vs Computed: Correct Choice With Undocumented Drift Risk

**Topic:** Employee.company as stored vs computed

The plan chose: **stored, derived at write time via validate hook**.

**Trade-off analysis (not in plan):**

| Approach | Pro | Con |
|---|---|---|
| Stored (chosen) | Fast reads; works with Frappe reports, Salary Slips, GL posting without extra joins | Can drift if department/designation changes without triggering validate; direct SQL updates bypass hook |
| Computed at read time | Always fresh | Requires every consumer to call the resolver; incompatible with Frappe's Company field type on Employee (Link field); breaks Salary Slip generation which reads stored company |

Stored is the correct choice for Frappe. The drift risk is real but manageable.

**Documented drift vectors not in plan:**

1. A future sprint changes `Employee.department` via direct SQL (as this sprint's Phase 7 does for company) — validate hook does not fire, company does not update.
2. Frappe bulk-edit through Desk (Edit Multiple) may or may not fire validate depending on Frappe version. If it does not, bulk dept changes leave company stale.
3. The plan's Phase 7 backfill patch intentionally bypasses validate (direct SQL) to avoid recursion. This is correct, but it sets a precedent that future sprint authors may copy without the same care.

---

## FINDING-6 [CRITICAL] — S201→S202 Gap: Reliever Labor Is Mis-Allocated During Interim Period

**Topic:** Deferral to S202

Between S201 deploy and S202 deploy, the situation for reliever employees is:

- `Employee.company` = their **home store's Company** (correct per S201 logic)
- Salary Slip posts to home store Company (correct for statutory)
- But punch-based allocation JE does not exist yet (S202 not deployed)
- Result: if a Tanza employee relieves at SM MOA for 3 days in April 2026, ALL of April's salary bills to SM Tanza. SM MOA gets free labor. SM Tanza overpays.

**Plan acknowledges this** (LD-5, Design Rationale section) but does not quantify the exposure or state an acceptable gap duration.

**Gap not stated:** How long between S201 and S202? If S202 ships in the same payroll cycle (April 2026), the gap is tolerable. If S202 slips to May, an entire payroll cycle runs with mis-allocated reliever labor (~27 roving employees * avg relief days). With an estimated PHP 20K-35K monthly salary per reliever, one-month slip represents PHP 540K–945K of cross-company mis-allocation that requires manual retroactive JEs.

**Recommendation:** Plan should state explicit S202 target date and a maximum tolerable gap (suggested: same payroll cycle). If S202 slips beyond April payroll close, Sam should be alerted to decide between: (a) deferring S201 backfill until S202 is ready, (b) accepting the mis-allocation, or (c) doing a manual interim JE.

---

## FINDING-7 [WARNING] — Reporting Discontinuity at S201 Deploy Date Not Addressed

**Topic:** Backward compatibility for historical Salary Slips

Historical Salary Slips (Feb–Mar 2026) on `BEBANG ENTERPRISE INC.` parent stay there — they are not retroactively moved (LD-6: no retro to Feb). This is correct per plan.

**Gap not mentioned:** Any report that aggregates labor cost per Company will show a hard discontinuity at the S201 deploy date:

- Feb–Mar 2026: 100% of payroll on BEI parent, 0% on store Companies
- April 2026 forward: ~75% on store Companies, ~6% BKI, ~19% BEI parent

Finance/management reports comparing April 2026 to March 2026 per store will show implausible numbers (March: PHP 0 labor, April: full labor). This is a **reporting artifact**, not a data error, but it will confuse management and potentially trigger erroneous financial analysis.

**Recommendation:** Plan should include a note for Finance that pre-S201 comparisons require a manual adjustment note. The Salary Slip discontinuity date should be documented in a journal note or ERP system note accessible to Alyssa/Denise.

---

## FINDING-8 [WARNING] — Employee Master Google Sheet Not Updated by Backfill

**Topic:** Employee Master Google Sheet sync

MEMORY.md lesson: "Always update BOTH CSV and Google Sheet together" (Google Sheet: `1QP_sdazVy1AzjK7ZHWmN6v3tZNYdpiUcdRebJJZY9Ms`, "BEI Employee Master 2026", sheet "Employee Master").

The backfill patch in Phase 7 updates `tabEmployee.company` in Frappe. `data/_FINAL/EMPLOYEE_MASTER.csv` is a migration snapshot, not a live sync target. However the Google Sheet is supposed to reflect current employee state.

**Gap:** Phase 7 does not include a step to update the Google Sheet's Company column for ~510 employees. The Google Sheet will remain showing `BEBANG ENTERPRISE INC.` for all employees post-backfill, creating a divergence between ERP state and the "source of truth" spreadsheet used by HR and potentially Finance.

**Recommendation:** Add a Phase 7 sub-step to either: (a) run a Google Sheets API update after backfill, or (b) explicitly document that the Google Sheet's Company column is considered stale/read-only post-S201 and the ERP is the live authority. Given that `data/_FINAL/EMPLOYEE_MASTER.csv` is a Feb 2026 snapshot, option (b) may be the correct governance decision — but it needs to be explicitly stated.

---

## FINDING-9 [WARNING] — Direct SQL Backfill Does Not Create Frappe Version Records

**Topic:** Frappe Versioning

Employee is a versioned doctype in Frappe (track_changes is enabled by default for all DocTypes unless explicitly disabled). Phase 7 explicitly uses direct SQL (`UPDATE tabEmployee SET company=...`) to bypass the validate hook. Direct SQL bypasses the Frappe ORM entirely, meaning:

- No `tabVersion` rows are created for the ~510 company changes
- The Frappe "Track Changes" audit trail shows no record of who changed company or when
- If an auditor checks an employee's change log in Frappe Desk, the company field change is invisible

**Plan does not address this.** The plan's mitigation is the `backfill_log.csv` file written by the patch itself. This is a custom audit log, not an ERP audit log.

**Risk:** If there is ever a dispute about when an employee's company changed (e.g., a payroll dispute or statutory filing question), the ERP audit trail will not corroborate the backfill log. The backfill log exists only as a file on disk, not in the ERP database.

**Recommendation:** Either:
(a) Accept this gap and explicitly document it in the plan as a known audit trail limitation, OR
(b) After direct SQL update, insert `tabVersion` rows manually for each changed employee (complex), OR
(c) Use `frappe.db.set_value("Employee", name, "company", target, update_modified=True)` with `flags.ignore_validate=True` instead of raw SQL — this updates `tabVersion` but triggers `on_update` hooks (which would need to be guarded).

Option (a) is pragmatic given the one-time nature of the backfill, but must be documented.

---

## FINDING-10 [WARNING] — my.bebang.ph Has 60-Second Stale Cache for Employee Company Field

**Topic:** Interop with my.bebang.ph

The plan states: "Backfill makes it show correct value automatically."

**This is partially correct but not immediate.**

`use-employee.ts` in bei-tasks uses SWR with `dedupingInterval: 60000` (60 seconds). This means:
- After S201 backfill updates `tabEmployee.company`, a user who already has a browser session open will see stale company data for up to 60 seconds.
- After a page reload or 60-second expiry, SWR refetches `/api/employee/me` which calls live Frappe. The new company value will appear.

**This is low severity** — 60 seconds is acceptable for a company name display. The concern escalates only if my.bebang.ph has RBAC or routing logic that branches on `employee.company`. Checking `use-employee.ts`: the company field is fetched but there is **no RBAC logic** based on company in the hook itself (RBAC uses `roles`, not `company`). The company field is display-only in the current implementation.

**Net assessment:** Low severity, but the plan's claim of "automatic" display is imprecise — it is "automatic within 60 seconds per session." No action needed unless company-based routing is added in a future sprint.

---

## FINDING-11 [WARNING] — Concurrent Employee Saves: Validate Hook Has a Read-Then-Write Race

**Topic:** Concurrent safety

The `derive_company_from_branch` hook follows the pattern:
1. Read `doc.company` (the current value on the doc object in memory)
2. Read `target` from resolver
3. If `doc.company != target`: set `doc.company = target`

This is a validate hook — it operates on the in-memory doc object before database write. Frappe's `frappe.db.savepoint()` is not used here (validate hooks do not participate in savepoints automatically).

**Race scenario:** Two HR users simultaneously edit the same Employee doc. Both load the doc. Both call validate. Both compute `target`. Both set `doc.company = target`. Frappe's last-write-wins semantics mean the second save overwrites the first. For company derivation this is **idempotent** — both compute the same `target` from the same branch/department/designation values. No data corruption.

**The actual race risk is different:** If one HR user changes `department` (which changes the target) while another is saving with the old department:

1. HR-A loads doc: department=Operations, derive target=SM MEGAMALL
2. HR-B loads doc simultaneously
3. HR-A saves: company set to SM MEGAMALL
4. HR-B changes department to IT: derive target=BEI parent
5. HR-B saves: company set to BEI parent

This is correct eventual behavior — the last save wins, which is the HR-B intent. No corruption.

**True gap:** If the validate hook is called from within `frappe.rename_doc()` during Phase 6 branch rename, the hook fires during the rename cascade on each affected Employee. If a concurrent HR save is in progress on the same employee, the two validate calls may interleave. Frappe handles this via row-level locking in the DB write, but the in-memory doc state may be stale at validate time. This is a low-probability edge case on deployment day.

**Net assessment:** No critical race condition. Idempotent derivation makes concurrent saves safe. Low risk.

---

## FINDING-12 [INFO] — Branch Rename Cascade via frappe.rename_doc: Verified Safe

**Topic:** Architecture of the rename

`frappe.rename_doc("Branch", old_name, new_name, force=True, merge=True)` in Frappe v15:

- Frappe automatically updates all Link field references to the renamed doc across all doctypes, including `tabEmployee.branch`
- The cascade runs via `frappe.model.rename_doc.update_link_field_values()` which issues `UPDATE tabXXX SET branch=new_name WHERE branch=old_name` for every doctype that has a Link field to Branch
- The `merge=True` flag merges duplicate Branch records if new_name already exists (used for `AYALA UPTC` → `AYALA UP TOWN CENTER` where the canonical may already exist)

**Gap:** The cascade update fires `tabEmployee` update queries but does NOT re-fire the Employee validate hook (it is a direct DB update via rename cascade, not an ORM save). This means after Phase 6 rename, Employee.branch is updated but Employee.company is NOT re-derived.

**This is why Phase 7 (backfill) must run AFTER Phase 6 (rename).** The plan sequences them correctly. However, the plan does not explicitly state that Phase 6's rename cascade leaves company stale and that is why Phase 7 is needed. A future sprint author might incorrectly believe Phase 6 alone updates company.

**Recommendation:** Add an explicit note in Phase 6: "rename_doc cascade updates Employee.branch but not Employee.company — Phase 7 is required to re-derive company from the renamed branches."

---

## FINDING-13 [CRITICAL] — HR Manager Override Flag: No UI Mechanism to Set It; Undocumented

**Topic:** HR Manager override flag

The plan describes (Phase 4):
> "HR Manager role bypass: if user has HR Manager AND company was manually changed in this save, skip derivation. Flag: `flags.company_manual_override`"

**The shipped code in `employee_master.py` line 82:**
```python
manual_override = bool(getattr(doc, "flags", {}).get("company_manual_override"))
```

**Critical gap:** Frappe `doc.flags` is a runtime-only dict that is set programmatically. It is NOT persisted to the database and cannot be set via the Frappe Desk UI form. There is no mechanism for an HR Manager user, working in Frappe Desk's Employee form, to set `doc.flags.company_manual_override = True`.

**Result:** The HR Manager bypass described in the plan is effectively **dead code**. An HR Manager who tries to manually set a different company via the Desk form will have their change overwritten by `derive_company_from_branch` on every save, regardless of their HR Manager role. They cannot exercise the override.

**How to fix:** Options:
(a) Add a hidden boolean field `custom_company_manual_override` on Employee DocType (Custom Field, hidden, only visible to HR Manager). When set to True, the hook reads it and skips derivation. This survives across saves.
(b) Remove the bypass clause entirely (simpler). If HR Manager needs to override, they can disable the hook in bench and do a direct SQL update.
(c) Change override detection: instead of checking a flag, check if `doc.company` was explicitly set to a Company that cannot be derived from the current branch/dept (i.e., if `doc.company != target` AND the user has HR Manager). This is the current code's logic but the flag check makes it unreachable.

**The current implementation means HR Manager gets NO override capability**, contrary to what the plan documents. This is a behavioral gap between plan and code.

---

## Summary Count

| Severity | Count | Finding IDs |
|---|---|---|
| [CRITICAL] | 3 | FINDING-3 (rule ordering — commissary split undocumented; FINDING-6 (S202 gap exposure unquantified); FINDING-13 (HR Manager override is dead code) |
| [WARNING] | 9 | FINDING-1, FINDING-2, FINDING-4, FINDING-5, FINDING-7, FINDING-8, FINDING-9, FINDING-10, FINDING-11, FINDING-12 |
| [INFO] | 1 | FINDING-12 (also logged as WARNING for rename-cascade ordering gap) |

**Total findings: 13**
**CRITICAL: 3 | WARNING: 9 | INFO: 1**

---

*Generated by System Architecture Domain Auditor, 2026-04-17 PHT*
