# S201 — Frappe Backend Audit Findings

**Auditor:** Claude (Frappe-backend domain auditor)
**Date:** 2026-04-17 PHT
**Plan file:** `docs/plans/2026-04-17-sprint-201-per-store-employee-billing-foundation.md`
**Shipped code base:** PR #603 + PR #604 (merged)
**DM rules source:** `.claude/rules/frappe-development.md`

---

## Finding 1 — DM-1: Party Fields on GL Entries

**Severity:** [N/A]

S201 does not post any Journal Entries or Payment Entries. The plan explicitly states:
> "S201 is the foundation. S202 will add punch-based reliever allocation (month-end JE reclassification)."

No GL-posting code exists in any shipped file. DM-1 does not apply to this sprint.

**Recommended amendment:** None. Add a note to the S202 plan to enforce DM-1 on all inter-Company reclassification JEs.

---

## Finding 2 — DM-2: Backfill Patch Atomicity

**Severity:** [WARNING]

The Phase 7 backfill patch (`hrms/patches/v16_0/s201_backfill_employee_company.py`) iterates ~510 employees and issues individual `UPDATE tabEmployee SET company=%s WHERE name=%s` statements in a for-loop, then calls `frappe.db.commit()` once at the end. There is **no savepoint** wrapping the batch.

Plan text:
> "UPDATE tabEmployee SET company = <target> (direct SQL, bypassing Employee validate to avoid hook re-firing)"

If the patch fails mid-loop (e.g., disk error, deadlock, timeout), the commit is never reached and MariaDB rolls back the uncommitted transaction — **this is actually safe for a single-session patch** because all the UPDATEs sit in one implicit transaction. The rollback behaviour is correct here.

However, there is a subtler risk: the patch calls `frappe.db.commit()` **once at the very end**. If `frappe.db.commit()` itself is preceded by any auto-commit from the Frappe ORM in the pre-loop query (`frappe.get_all("Employee", ...)`) — which uses a read-only query and does not commit — the batch UPDATEs would still be inside the same transaction boundary.

DM-2 was designed for multi-doc creations (JV + Payment Request + GR) where each doc's `save()` triggers its own commit. A raw `frappe.db.sql()` loop in a patch does not trigger intermediate commits, so the scenario DM-2 guards against does not apply here.

**The real risk** is that if the patch is re-run after a partial failure (e.g., process killed between UPDATE calls), some employees have already been updated in memory but not committed. On re-run, the idempotency check `if target == current` (line ~119) correctly skips already-updated rows, so re-run is safe.

**Recommended amendment:** Add a comment in the patch clarifying why savepoint is not needed (single-transaction batch, not multi-doc creation). Also add a safety check: if `len(errors) > 0` after the loop, log a WARNING and do NOT call `frappe.db.commit()` — force the caller to investigate before committing a partial batch.

Code currently:
```python
frappe.db.commit()
summary["totals"]["applied"] = applied
```

Should be:
```python
if errors:
    frappe.logger().warning(f"[S201] {len(errors)} errors; NOT committing partial batch.")
    summary["totals"]["applied"] = 0
    # Do not commit — let Frappe rollback on exit.
    return
frappe.db.commit()
```

---

## Finding 3 — DM-3: EWT + VAT

**Severity:** [N/A]

S201 creates no Payment Entry or Journal Entry. No money changes hands. EWT and VAT are irrelevant. DM-3 does not apply.

---

## Finding 4 — DM-4: Link vs Data Fields

**Severity:** [N/A]

`Employee.company` is a standard Frappe `Link` field pointing to the `Company` DocType (upstream erpnext). No new fields are added in S201. DM-4 does not apply.

---

## Finding 5 — DM-5: Computed vs Stored — Validate-Hook Pattern

**Severity:** [INFO]

The plan uses a validate-hook approach (`derive_company_from_branch`) to auto-populate `Employee.company` as a **stored** field. This appears to conflict with DM-5 ("don't store values that can be derived"). However, the DM-5 intent is to prevent stale copied values from linked docs (e.g., copying PO grand_total onto another DocType). This is a **different pattern**.

`Employee.company` is not a copy of data from a linked doc — it is the **authoritative legal entity assignment** derived from a rule, not fetched from a parent. It must be stored because:

1. `Salary Slip` and `GL Entries` read `employee.company` at submission time — they need a stable value, not a dynamic derivation.
2. Frappe payroll runs batch queries: `SELECT company FROM tabEmployee WHERE ...` — computing on-read is not possible at payroll scale.
3. The `validate` hook re-derives on every save, so the stored value is kept fresh.

**This is the correct pattern for S201.** The stored + validate-hook approach is the standard Frappe idiom for this type of "derived configuration" field. DM-5 does not apply as written.

**Recommended amendment to plan:** Add a note in Phase 4 clarifying *why* stored + validate is preferred over on-read derivation. This prevents future agents from flagging it as a DM-5 violation.

---

## Finding 6 — DM-6: Reclassification JVs

**Severity:** [N/A]

S201 explicitly defers all inter-Company JE reclassification to S202. No JEs are created in this sprint. DM-6 does not apply.

---

## Finding 7 — DM-7: Sentry Observability

**Severity:** [INFO]

The plan states:
> "Add Frappe Sentry context per DM-7 if the hook becomes an `@frappe.whitelist()` endpoint — currently it's a validate hook so Sentry auto-captures via `frappe.log_error`."

This is correct for the validate hook. The `derive_company_from_branch` function in `employee_master.py` is not `@frappe.whitelist()` decorated and is called by Frappe's event system — any unhandled exceptions would propagate through `frappe.log_error` which feeds Sentry.

`create_transfer` in `transfers.py` correctly calls `set_backend_observability_context(module="hr", action="create_transfer", mutation_type="create")` as the first line after the decorator.

**Gap identified:** The two patches (`s201_rename_branches.py` and `s201_backfill_employee_company.py`) are invoked via `bench execute` — they run as server-side scripts, not HTTP requests. Sentry's Frappe monkey-patch **does** capture `frappe.log_error()` calls from these scripts, so errors in the patch are captured. However, the patches use `frappe.logger().error()` rather than `frappe.log_error()` for failure reporting. `frappe.logger()` is a Python logging call — it does NOT feed Sentry. Only `frappe.log_error()` creates an Error Log doc that Sentry captures.

In `s201_rename_branches.py` (line 67):
```python
frappe.logger().error(f"[S201] branch_company_map.csv missing at {path}")
```

And in `s201_backfill_employee_company.py` (line 44):
```python
frappe.logger().error(f"[S201] No map rows loaded; aborting.")
```

**Recommended amendment:** Change `frappe.logger().error(...)` to `frappe.log_error(title="...", message="...")` for critical failure paths in both patches so Sentry captures them. Non-critical progress logs can stay as `frappe.logger().info()`.

---

## Finding 8 — Employee DocType Override Safety / Hook Order

**Severity:** [WARNING]

The `EmployeeMaster.validate()` override in `hrms/overrides/employee_master.py` contains the S172 BEI-EMP preservation fix:

```python
def validate(self):
    saved_employee = (self.employee or "")
    is_bei_id = saved_employee.startswith("BEI-EMP-")
    super().validate()  # upstream runs self.employee = self.name here
    if is_bei_id and self.employee != saved_employee:
        self.employee = saved_employee
```

S201 adds `derive_company_from_branch` as a **doc_events** hook on `Employee.validate`:

```python
"Employee": {
    "validate": [
        "hrms.overrides.employee_master.validate_onboarding_process",
        "hrms.utils.bio_id_validation.validate_employee_bio_id",
        "hrms.overrides.employee_master.derive_company_from_branch",  # S201
    ],
```

**Frappe hook execution order:** When a DocType is subclassed AND doc_events handlers are registered, Frappe calls them in this sequence:
1. `DocType.validate()` (the class method — `EmployeeMaster.validate()` here, which includes `super().validate()`)
2. All `doc_events["Employee"]["validate"]` handlers, in list order

This means `derive_company_from_branch` runs **after** `EmployeeMaster.validate()` has already restored the BEI-EMP id. The hook order is safe with respect to S172.

**However**, there is a subtle ordering issue within the doc_events list: `validate_onboarding_process` runs FIRST, then `validate_employee_bio_id`, then `derive_company_from_branch`. This ordering is correct — `derive_company_from_branch` should run last (after bio_id validation and onboarding checks) so it has access to a fully-validated branch and department.

**One real concern:** the `derive_company_from_branch` hook checks:
```python
is_hr_manager = "HR Manager" in frappe.get_roles(frappe.session.user)
manual_override = bool(getattr(doc, "flags", {}).get("company_manual_override"))
```

The `doc.flags` check reads from `doc.flags` as if it were a dict (`getattr(doc, "flags", {})`), but in Frappe, `doc.flags` is a `frappe._dict` (a dict subclass). The `.get()` call is correct. However, `flags.company_manual_override` is never set by any other part of the code — neither in the form JS nor in the API. The HR Manager bypass condition is therefore **never triggered** in practice. The code path is dead until a mechanism to set `doc.flags.company_manual_override = True` is implemented.

**Recommended amendment:** Either implement the flag-setting mechanism (form JS or explicit API call) or document it clearly with a TODO comment in the code. Without the setter, the bypass is broken-by-design, and HR Managers cannot override company even when they need to.

---

## Finding 9 — Cache Invalidation Race Condition

**Severity:** [INFO]

The plan says:
> "Wire `on_update` hook on Branch doctype and Company doctype to call `clear_cache()`."

The shipped code wires `Branch.on_update` to `company_lookup.clear_cache()` (hooks.py lines 201-204). This is correct.

The potential race condition is:
1. In-flight `Employee.validate()` calls `_ensure_fresh()` at time T, gets cached map with old branch value.
2. A Branch rename completes at time T+1ms, firing `clear_cache()`.
3. The in-flight validate() continues with stale cached data, writes old company to the doc.

This is an **accepted race** in Frappe cache patterns — the 60-second TTL means a stale result is possible during the rename window. The impact is bounded: the next save of the employee document will recompute the correct company. For a rename event, this is acceptable.

**The more serious scenario** would be if a Branch rename fires during a backfill patch run. The backfill patch does NOT use the cache (it calls `resolve_branch_to_company()` which uses `_ensure_fresh()`, but the patch runs in a single bench-execute session). If a rename happens concurrently during backfill, one employee might get the old company. This is an edge case since the rename patch and backfill patch are run sequentially with Sam approval between them.

**Recommended amendment:** Add a comment in the backfill patch warning that it should not be run concurrently with the rename patch. The plan already addresses this through the sequential phase structure (Phase 6 before Phase 7), but it is not explicitly called out in the patch code.

---

## Finding 10 — Patch Idempotency

**Severity:** [INFO]

Both patches implement idempotency correctly:

**s201_rename_branches.py:**
- `old == new` case is explicitly detected and logged as "already canonical" (line 81). No rename attempt is made.
- If `old != new` but the rename was already applied: `exists_old` would be False (old branch no longer exists), causing the entry to be logged as "source branch missing" (line 131). This is benign — the rename already happened.

**s201_backfill_employee_company.py:**
- The check `if target == current` (line ~119) correctly skips employees already at their target company. Re-running after full apply is a no-op.

Both patches are safe to re-run after apply. No finding — just confirming this is correctly implemented.

---

## Finding 11 — rename_doc Safety with merge=True

**Severity:** [WARNING]

The plan uses `frappe.rename_doc("Branch", old, new, force=True, merge=True)` when the target branch name already exists.

Plan text:
> "For each `(old_branch, new_branch)` pair where old ≠ new: `frappe.rename_doc("Branch", old, new, force=True, merge=True)`"

**What `merge=True` does:** Frappe's `rename_doc` with `merge=True` will:
1. Reassign all child records (Employees, Attendance, etc.) that reference `old` to reference `new` instead.
2. Then delete the `old` Branch document.

**The risk:** If `old_branch` and `new_branch` are two **distinct physical branches** (e.g., `BGC` store and `BRITTANY HOTEL` store are two separate locations that happen to get merged into one canonical name), then all Employees on `BGC` will be reassigned to `BRITTANY HOTEL` silently. Their attendance records, leave applications, and any other Branch-linked docs also get reassigned.

Looking at the CSV, the merge case most likely occurs with HO variants (MYTOWN → MY TOWN, BRITTANY OFFICE → BRITTANY HOTEL) where the "old" and "new" are the **same physical location** just renamed. However, if two branches have different Warehouses or different Cost Centers, the merge will combine them into one Branch record that carries only the target's metadata — the source's Warehouse/Cost Center links are dropped.

**Specific risky rows in branch_company_map.csv:**
- `BRITTANY OFFICE` → `BRITTANY HOTEL` (HO): if both existed as Branches pointing to different Warehouses/Cost Centers, employees on BRITTANY OFFICE would be moved to BRITTANY HOTEL but BRITTANY OFFICE's Warehouse reference is lost.

The shipped code in `s201_rename_branches.py` does check `exists_new` and sets `will_merge` correctly, and the dry-run report includes a `merges` count. The plan requires Sam to review the dry-run report before executing. This is adequate governance.

**Recommended amendment:** Add a pre-merge validation step in the dry-run report: for every pair marked `will_merge=True`, list the Warehouse and Cost Center linked to BOTH the old and new Branch docs. If they differ, flag them as `MERGE_CONFLICT` requiring manual review. Currently the dry-run only counts employees — it does not surface the Warehouse/Cost Center divergence risk.

---

## Finding 12 — Employee.company Update Method: Direct SQL Safety

**Severity:** [WARNING]

The backfill patch updates Employee.company via:
```python
frappe.db.sql(
    "UPDATE `tabEmployee` SET company=%s WHERE name=%s",
    (ch["new_company"], ch["employee"]),
)
```

**Is this safe given Employee's `track_changes`?**

Per Frappe/ERPNext standard, the Employee DocType has `track_changes = 1` enabled. When `track_changes` is enabled, Frappe creates a `Version` document recording field changes on every `doc.save()`. **Direct SQL bypasses this mechanism entirely** — no `Version` document is created, no audit trail exists for the company change.

For a one-time backfill, this is an acceptable trade-off (the plan explicitly acknowledges this: "direct SQL, bypassing Employee validate to avoid hook re-firing"). The patch itself generates a `backfill_log.csv` with before/after per employee, which serves as a substitute audit trail.

**However**, the plan should explicitly acknowledge that:
1. No `Version` docs are created for the ~510 company changes.
2. The `backfill_log.csv` is the only audit trail.
3. Using `frappe.db.set_value()` would have been an alternative that respects `track_changes` but triggers validate hook re-firing.

**Could `frappe.db.set_value()` have been used instead?**

`frappe.db.set_value("Employee", name, "company", new_company, update_modified=False)` does NOT trigger validate but DOES update `modified`/`modified_by` fields. It also does NOT create Version docs (it's still a raw SQL wrapper). The behaviour with respect to audit trail is identical to the direct SQL approach. The plan's choice of direct SQL is therefore equivalent to `frappe.db.set_value()` for audit purposes.

**Employee is NOT submittable** (docstatus is always 0 in standard ERPNext Employee DocType). The concern about submittable doc integrity is therefore not applicable here.

**Recommended amendment to plan:** Add a note in Phase 7 acknowledging that direct SQL bypasses `track_changes` versioning and that `backfill_log.csv` is the authoritative audit record for this operation. No code change needed.

---

## Finding 13 — LD-3 Commissary Routing: Plan vs Code Mismatch

**Severity:** [WARNING]

**The plan (Phase 4) states:**
> "Elif `department in {"Commissary"}` (case-insensitive): set `doc.company = get_commissary_company()` (BKI)."

This reads as if **all** employees with `department=Commissary` route to BKI, regardless of branch.

**The shipped code is more nuanced.** In `company_lookup.py`, the commissary routing logic is:

```python
if category == CATEGORY_COMMISSARY:
    if hint == "DEPT_DRIVEN":
        if _normalize(department) == "COMMISSARY":
            return BKI_COMMISSARY_COMPANY
        return BEI_PARENT_COMPANY
    if hint:
        return hint
    return BKI_COMMISSARY_COMPANY
```

And in `non_store_billing.py`:
- `SCM` department → `True` (routes to BEI parent, not BKI)
- `SHAW COMMISSARY - LOGISTICS` branch → `HO` category → BEI parent (even if dept=Commissary)
- `SHAW COMMISSARY - RD QC` branch → `HO` category → BEI parent

The `is_non_store_billing()` check runs **first** in `derive_company_from_branch()`. So an employee with `department=Commissary` AND `branch=SHAW COMMISSARY - LOGISTICS` would pass the `is_non_store_billing` check (because the branch maps to `HO`) and route to BEI parent — NOT BKI.

**This is correct per Sam's decision (2026-04-17):**
> "SCM team at commissary (branch SHAW COMMISSARY - LOGISTICS) -> BEI parent"
> "R&D at commissary (SHAW COMMISSARY - RD QC) -> BEI parent"

But the **plan text at Phase 4 bullet 2** (`Elif department in {"Commissary"} → BKI`) does NOT document these exceptions. An agent reading the plan would implement a simple `dept == Commissary → BKI` rule and miss the branch-overrides.

**Plan-code mismatch confirmed:** The plan says "Commissary dept → BKI" without the branch exception. The code correctly implements the exception but the plan text is incomplete.

**Recommended amendment:** Update Phase 4 bullet 2 in the plan to:
```
Elif department == "Commissary" AND branch is NOT in {SHAW COMMISSARY - LOGISTICS, SHAW COMMISSARY - RD QC}:
    → BKI (BEBANG KITCHEN INC.)
Elif department == "Commissary" AND branch IS in {SHAW COMMISSARY - LOGISTICS, SHAW COMMISSARY - RD QC}:
    → BEI parent (handled by is_non_store_billing via HO branch category)
```

Or more concisely: document that `is_non_store_billing()` is evaluated first and can redirect Commissary-dept employees to BEI parent if their branch category is HO.

---

## Summary

| # | Title | Severity |
|---|-------|----------|
| 1 | DM-1 GL Party Fields | [N/A] |
| 2 | DM-2 Backfill Atomicity — partial-apply commit should be blocked on errors | [WARNING] |
| 3 | DM-3 EWT + VAT | [N/A] |
| 4 | DM-4 Link vs Data | [N/A] |
| 5 | DM-5 Computed vs Stored — validate-hook is correct pattern | [INFO] |
| 6 | DM-6 Reclassification JVs | [N/A] |
| 7 | DM-7 Sentry — patches use logger() not log_error(); Sentry misses critical failures | [INFO] |
| 8 | Hook Order — safe, but HR Manager bypass flag is never set (dead code path) | [WARNING] |
| 9 | Cache Invalidation Race — bounded/acceptable, add comment | [INFO] |
| 10 | Patch Idempotency — correctly implemented | [INFO] |
| 11 | rename_doc merge=True — no Warehouse/Cost Center conflict check in dry-run | [WARNING] |
| 12 | Direct SQL bypasses track_changes — Employee is not submittable; backfill_log is audit trail | [WARNING] |
| 13 | LD-3 Plan-Code Mismatch — Phase 4 doesn't document branch-override exceptions for Commissary dept | [WARNING] |

**CRITICAL: 0, WARNING: 5, INFO: 4, N/A: 6**
