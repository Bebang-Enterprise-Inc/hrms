# S191 Plan Audit — Cold-Start Readiness Findings
**Plan:** `docs/plans/2026-04-14-sprint-191-foodpanda-unified-source.md`
**Audited:** 2026-04-12
**Source file verified:** `hrms/api/sales_dashboard.py` (3640 lines, read directly)

---

## Summary Scorecard

| Category | Score | Blocker Count |
|---|---|---|
| Cold-Start Self-Containment | PASS with gaps | 2 CRITICAL, 1 WARNING |
| Zero-Skip Enforcement | PASS | 0 |
| Machine-Verifiable Phase Gates | PASS with gaps | 1 CRITICAL, 1 WARNING |
| L3 Scenario Contract | PASS | 0 |
| Closeout Contract | PASS | 0 |
| Branch & PR Isolation | PASS | 0 |
| Sentry Observability | PASS with gap | 1 WARNING |
| Requirements Regression Checklist | PASS | 0 |
| Data Integrity | CRITICAL gaps | 3 CRITICAL |

**Total: 5 CRITICAL, 3 WARNING, several INFO**

Any CRITICAL = BLOCKER. Fix before handing to execution agent.

---

## 1. Cold-Start Self-Containment

### CRITICAL-1: `_get_store_channel_split_map` return shape mismatch — plan assumes `{gross, net_wo_vat, orders}` but actual return is `{net_wo_vat}` only

**Evidence from source code (lines 1067–1122):**
The SQL at line 1067 only selects `net_wo_vat` — there is NO `gross` or `orders` column in this query. The return dict is keyed by `_S182_MOSAIC_CHANNEL_KEYS` which are plain floats (not nested dicts). The consumer at line 2499–2510 treats each bucket as a plain `float`, not `{"gross": ..., "net_wo_vat": ..., "orders": ...}`.

**Plan claim (task 3.2):**
> Returns `dict[location_id, dict[channel_key, {"gross", "net_wo_vat", "orders"}]]`
> For each location_id, sum all its business_date entries to get a single per-store FP aggregate `{gross, net_wo_vat, orders}`

**The problem:** `_get_unified_foodpanda_totals` returns `{gross, net_wo_vat, orders}` per (store, day). When the plan says to "override `result[location_id]["foodpanda"]`" in `_get_store_channel_split_map`, it is overriding a plain `float` (the existing `net_wo_vat` value) with a nested dict. That will silently corrupt all downstream consumers that do `float(mosaic.get("foodpanda", 0.0))` at line 2502.

**Resolution required before execution:** The agent must either:
(a) Override only the `net_wo_vat` float (dropping gross/orders from the per-store surface — acceptable since leaderboard only uses `channel_mix` net values), OR
(b) Change `_S182_MOSAIC_CHANNEL_KEYS` and all consumers to use nested dicts (major scope expansion).
Option (a) is the minimal-correct fix but the plan must say so explicitly. As written, a cold-start agent will write code that breaks the leaderboard.

**Severity: BLOCKER**

---

### CRITICAL-2: `_apply_mosaic_channel_split` headline totals re-computation is NOT addressed

**Evidence from source code (lines 998–1027):**
`_apply_mosaic_channel_split` uses `fp_bucket["gross"]` and `fp_bucket["net_wo_vat"]` in `true_net_wo_vat` and `true_gross` summation that recomputes `net_sales_without_vat`, `gross_sales`, and `net_sales_with_vat` for the entire fleet. After task 2.1, `fp_bucket` is replaced with `fp_unified` from the new helper. This is correct for the FoodPanda line items.

**The problem the plan does NOT address:** The existing `_apply_mosaic_channel_split` summation (lines 1000–1020) builds `true_gross` by summing `fp_bucket["gross"] + gf_bucket["gross"] + ...`. After S191, `fp_bucket` = `fp_unified` (which includes legacy gross approximated as `subtotal` from `foodpanda_orders`). But `gf_bucket`, `wd_bucket`, `pos_bucket`, and `other_*` are still from `_get_mosaic_channel_split` — which is also being called at line 946 (`split = _get_mosaic_channel_split(...)`). That call will still return a `foodpanda` key in `split` (from Mosaic), which gets popped at line 948. The plan says "The Mosaic-only `split["foodpanda"]` (if present) is discarded." This is correct.

**BUT:** The plan does NOT explicitly state that `fp_bucket["net_wo_vat"]` in the headline sum (lines 989–996, `delivery_sales_without_vat`) and in `true_net_wo_vat` (line 1000) must also come from `fp_unified`. Task 2.1 says to replace the `fp_bucket = split.pop(...)` line but does NOT tell the agent to verify that ALL downstream uses of `fp_bucket` in the same function automatically switch over. A cold-start agent might only replace the assignment and not trace all six uses of `fp_bucket` in `_apply_mosaic_channel_split`.

**This is marginal** (a careful agent will trace all uses), but the plan should include an explicit "trace all 6 uses of `fp_bucket` in this function" instruction or a MUST_CONTAIN assertion for the count.

**Severity: WARNING** (not a blocker if agent is careful, but high risk)

---

### WARNING-1: PostgREST fallback in `_get_unified_foodpanda_totals` (task 1.2) requires Python-side FULL OUTER JOIN semantics — no implementation guide given

**Plan claim:** "fetch from both sources separately, then merge in Python using the same (location_id, business_date) FULL OUTER JOIN semantics."

**The problem:** This is a non-trivial Python merge. The SQL FULL OUTER JOIN has exact semantics (Mosaic wins on overlap). The plan does not provide pseudocode or a Python snippet for the fallback merge. A cold-start agent may implement it differently (e.g., prefer legacy instead of Mosaic, or union without dedup). The SQL version is fully specified; the fallback is not.

**Severity: WARNING** — The fallback is degraded-mode only, but if SUPABASE_MGMT_TOKEN is absent during verification, the test will run against the fallback and may produce wrong numbers silently.

---

### INFO-1: Line number claims verified accurate against actual source

All claimed line numbers were verified:
- `_get_mosaic_channel_split`: line 825 — CORRECT
- `_apply_mosaic_channel_split`: line 910 — CORRECT
- `_get_store_channel_split_map`: line 1049 — CORRECT
- `_get_mosaic_channel_split_per_day`: line 1962 — CORRECT
- `_FOODPANDA_MOSAIC_START`: line 31 — CORRECT
- `_supabase_query_sql`: line 229 — CORRECT
- `_cache_get_or_set`: line 380 — CORRECT
- `SupabaseMgmtTokenMissing`: line 220 — CORRECT
- Freshness warning reference to `_FOODPANDA_MOSAIC_START`: line 1296 — CORRECT

All column names in `foodpanda_orders` (plan line 144) and `v_pos_orders_live` (plan line 145) match the code's existing queries.

---

### INFO-2: FULL OUTER JOIN SQL in Design Rationale is paste-ready

The SQL block (lines 76–103 of plan) is complete with both CTEs, all WHERE clauses, the JOIN condition, the COALESCE/source column, and variable placeholders ($start, $end, $locations). A cold-start agent can adapt it with f-string interpolation matching the existing pattern at lines 858–871 of source. No missing clauses.

---

### INFO-3: `_get_mosaic_channel_split_per_day` return shape correctly noted

The plan (task 3.4) says the return shape is `dict[date_iso, dict[channel_key, {"gross", "net_wo_vat", "orders"}]]`. The actual return (lines 2015–2020) is `dict[date_iso, dict[channel_key, float]]` — plain floats, not nested dicts. **However**, the plan's task 3.5 only says to aggregate across all stores per day and override `result[date_iso]["foodpanda"]` — if the result is `float`, the agent must override with a float (net_wo_vat), not a dict. Same root issue as CRITICAL-1 but in a different function. The per-day function returns floats for `net_wo_vat` only (no gross, no orders). The daily time-series chart presumably only needs net_wo_vat.

**Severity: WARNING** — same shape mismatch as CRITICAL-1, but the daily chart only needs net values so it may not cause a visible break. Still: task 3.5 says to put `{gross, net_wo_vat, orders}` into `result[date_iso]["foodpanda"]` which is a type mismatch. The agent needs explicit guidance to use only the `net_wo_vat` float.

---

## 2. Zero-Skip Enforcement

### PASS

- Zero-Skip Enforcement section present (plan lines 297–322): CONFIRMED
- Forbidden behaviors list: 8 items explicitly listed — CONFIRMED
- Phase completion checklist format: `output/s191/phase_N_completion.md` per phase — CONFIRMED
- PR gate: "PR cannot be created until PASS" on verify_s191.py — CONFIRMED
- Forbidden behaviors include GrabFood and frontend explicitly — CONFIRMED

---

## 3. Machine-Verifiable Phase Gates

### CRITICAL-3: Phase 2.1 lacks a MUST_MODIFY assertion for the headline totals computation change

Phase 2.1 says to "replace `fp_bucket = split.pop(...)` at line 948 with `fp_bucket = fp_unified`." The MUST_MODIFY evidence is:
> `grep -c "_get_unified_foodpanda_totals_aggregate" hrms/api/sales_dashboard.py` in `_apply_mosaic_channel_split` section ≥ 1

**The problem:** This grep confirms the call was added, but does NOT verify that the old `split.pop("foodpanda", ...)` line was removed. If an agent inserts the new call but leaves the old pop in place, `fp_bucket` will be assigned twice and the second assignment (the old Mosaic-only one) will silently overwrite the unified value. The grep passes, but the code is wrong.

**Required fix:** Add assertion: `grep -c 'split.pop("foodpanda"' hrms/api/sales_dashboard.py` = 0 (the old pop must be gone, replaced by `fp_unified`).

**Severity: BLOCKER**

---

### WARNING-2: verify_s191.py anti-regression grabfood count check has no baseline value documented

The verification script (plan line 319) says:
> `grep -c "grabfood" hrms/api/sales_dashboard.py` unchanged (count must equal pre-S191 count)

The pre-S191 count is **28** (verified from source). This exact number is not written in the plan. The script needs a hardcoded expected value to be machine-verifiable. Without it, the script author must count it themselves, introducing a cold-start failure mode.

**Required fix:** Add to verification script spec: `assert grabfood_count == 28`.

**Severity: WARNING**

---

### INFO-4: All other grep assertions are specific, correct, and verifiable

Tasks 1.1, 1.2, 1.3, 2.4, 3.2, 3.5, 4.6 all have `grep -c` assertions with exact expected values (≥1 or = 0). These are filesystem-verifiable. AST parse check at 1.4 and 3.7 is correct. The Phase 0.3 baseline audit has 6 named metrics requirement. These are all well-formed.

---

### INFO-5: Verification script required and scoped correctly

Task 4.1 specifies `output/s191/verify_s191.py` with all pattern checks enumerated. The script uses `git diff` + `grep` as required by the S154 rule. PASS.

---

## 4. L3 Scenario Contract

### PASS — Backend-only adaptation is correct

- 12 scenarios defined with concrete user, action, and expected outcome — CONFIRMED
- Each scenario has specific ₱ thresholds (not vague "higher than before") — CONFIRMED
- `form_submissions.json` specified as empty array with explicit rationale (page loads only) — this is the correct pattern for read-only analytics sprints per S092
- `api_mutations.json` specified as empty array — CONFIRMED
- `state_verification.json` carries the 12 scenarios with pass/fail + actual ₱ amounts — CONFIRMED
- Screenshots required per scenario — CONFIRMED

**INFO-6:** L3-191-04 (April date range, Mosaic-only, no double-count) is the most important regression scenario and is correctly included. The threshold "~₱9.5M" matches the Mosaic Apr 2026 number from the plan's own audit table.

**INFO-7:** L3-191-08 (overlap zone ₱500K–₱1.5M/day) provides a reasonable sanity range. The plan does not explain how this was derived (₱4.7M Mosaic over ~5 days = ~₱940K/day average; ₱1.5M is roughly 1.6× the average — plausible headroom). This is acceptable.

---

## 5. Closeout Contract

### PASS

- Plan YAML has `status: PLANNED`, `completed_date: null`, `execution_summary: null` — update to DEPLOYED required at closeout, fields present — CONFIRMED
- Closeout phase (Phase 4.4) specifies plan YAML update + SPRINT_REGISTRY.md update — CONFIRMED
- `git add -f docs/plans/` explicitly noted at task 4.4 — CONFIRMED
- `completion_condition` in Autonomous Execution Contract includes registry update — CONFIRMED

---

## 6. Branch & PR Isolation

### PASS

- Branch `s191-foodpanda-unified-source` reserved in registry row in plan YAML — CONFIRMED
- Branch checkout command in Agent Boot Sequence step 2 — CONFIRMED
- PR creation at task 4.3 with `GH_TOKEN=""` prefix — CONFIRMED
- PR registry update at task 4.4 — CONFIRMED

---

## 7. Sentry Observability

### PASS with WARNING

- Task 4.6 correctly notes no new `@frappe.whitelist()` endpoints are introduced — CONFIRMED
- Task 4.6 says to verify `set_backend_observability_context` is present on existing endpoints — CONFIRMED
- The verification grep `grep -c "set_backend_observability_context" hrms/api/sales_dashboard.py` ≥ 4 is specified

**Verified from source:** Current count is **5** (lines 22 import + 3 function calls at 3061, 3089, 3171, 3321). The plan says "≥ 4 (unchanged from pre-S191)". The actual pre-S191 baseline is 5 (not 4). The ≥ 4 assertion will pass even if S191 accidentally removes one call (5-1=4 still passes). The assertion should be `== 5` not `≥ 4`.

**Severity: WARNING** — The check as written won't catch accidental removal of one Sentry call.

---

## 8. Requirements Regression Checklist

### PASS

- Checklist present (plan lines 180–194) — CONFIRMED
- HARD BLOCKER items included:
  - Mosaic wins overlap — CONFIRMED (item 2: "When both Mosaic and legacy have data...")
  - GrabFood untouched — CONFIRMED (item 9: "Is GrabFood logic completely untouched? (HARD BLOCKER)")
  - Cache prefix invalidation — CONFIRMED (item 11: "Does the cache key distinguish the new unified FP totals...")
- 14 checklist items covering all major behavioral requirements — CONFIRMED

---

## 9. Data Integrity

### CRITICAL-4: Phase 0 baseline threshold ₱1M total variance may be too tight given VAT approximation

**The math:** Legacy net is `subtotal / 1.12`. Mosaic net is `net_sales` (exact VAT per order). On overlap days, the difference per order is: `(actual_vat - approximated_vat)`. If FoodPanda VAT-exempt orders (SC/PWD discounts) represent even 5% of March volume, the approximation error per exempt order is `subtotal × (1 - 1/1.12) ≈ subtotal × 0.107`. On ₱4.7M Mosaic gross with 5% exempt, the systematic VAT mis-approximation alone is ~₱25K. But across 8,477 March Mosaic orders vs 34,337 legacy orders, the overlap period has only ~8,477 orders. If those orders average ₱555 subtotal, and 5% are VAT-exempt, the approximation bias is: `8477 × 0.05 × 555 × 0.107 ≈ ₱25K`. That is well under ₱1M.

**Conclusion:** ₱1M total variance threshold is NOT too tight for the VAT-approximation concern alone. The concern raised is valid in principle but the magnitude is small enough that the ₱1M threshold is safe.

**However:** The plan does NOT explain why ₱1M was chosen. A cold-start agent triggering HARD BLOCKER 0-1 (e.g., finding ₱1.2M variance) would stop without context to evaluate whether it's a real data integrity issue or an expected approximation artifact. The threshold rationale is missing.

**Required addition:** Add to Phase 0 rationale: "The ₱1M threshold is approximately 21% of the Mosaic March total (₱4.7M). Variance above this threshold suggests a source-level discrepancy (duplicate rows, wrong status filter) rather than rounding/VAT-approximation noise (expected to be <₱50K). If HARD BLOCKER 0-1 triggers with variance of ₱50K-₱1M, review the per-store breakdown before escalating."

**Severity: BLOCKER** — Without this rationale, an agent that finds ₱1.05M variance will stop and escalate when the correct response might be "investigate, then likely proceed."

---

### CRITICAL-5: `foodpanda_orders` deduplication by `order_id` not addressed

**The plan's FULL OUTER JOIN** uses:
```sql
SELECT location_id, business_date, SUM(subtotal) gross, ...
FROM foodpanda_orders
WHERE LOWER(order_status) = 'delivered'
GROUP BY 1, 2
```

**The problem:** If `foodpanda_orders` has duplicate `order_id` rows (e.g., re-sync artifacts from the Google Sheet import), `SUM(subtotal)` will double-count those orders. The plan does not dedupe before aggregation. The correct pattern is either:
```sql
SUM(DISTINCT subtotal) -- wrong (dedupes by amount, not by order)
```
or:
```sql
-- correct: dedupe at row level before aggregating
WITH deduped AS (
  SELECT DISTINCT ON (order_id) order_id, location_id, business_date, subtotal
  FROM foodpanda_orders
  WHERE LOWER(order_status) = 'delivered'
  ORDER BY order_id
)
SELECT location_id, business_date, SUM(subtotal), ...
FROM deduped GROUP BY 1, 2
```

The plan's Phase 0 baseline audit (task 0.3) queries the source data but does NOT include a dedup check (`SELECT order_id, COUNT(*) FROM foodpanda_orders GROUP BY order_id HAVING COUNT(*) > 1`). If 50,525 orders has even 500 duplicates averaging ₱600, that's ₱300K phantom revenue that would pass both the HARD BLOCKER threshold and the ≥₱20M post-fix check.

**Required addition:** Add dedup check to Phase 0.3 baseline audit. Add `DISTINCT ON (order_id)` or equivalent to the legacy CTE in the FULL OUTER JOIN SQL.

**Severity: BLOCKER**

---

### CRITICAL-6: March math (₱17M gap) is correct but ₱21.7M legacy figure is gross (subtotal), not net

**The plan states:** "March legacy = ₱21.7M subtotal / 34,337 orders." The Mosaic March = ₱4.7M net. The dashboard fix target is ≥ ₱20M (plan: "foodpanda_sales_without_vat ≥ 18M" at task 2.5).

**The math:**
- Legacy March gross (subtotal) = ₱21.7M
- Legacy March net (subtotal/1.12) = ₱21.7M / 1.12 ≈ ₱19.4M
- Mosaic March net (already net) = ₱4.7M (but this overlaps with legacy — don't add)
- Unified March net (legacy pre-cutover days + Mosaic post-cutover days) = legacy net MINUS overlap legacy days net + Mosaic overlap days net

The plan's Phase 2.5 smoke test says `foodpanda_sales_without_vat ≥ 18M`. This is approximately correct (₱19.4M minus some Mosaic overlap substitution). The ≥18M lower bound is conservative.

**But the Executive Summary says** "₱21.7M (legacy Google Sheet)" and the L3 scenarios say "FoodPanda ≥ ₱20M." The ₱20M threshold in L3-191-01 and L3-191-05 is comparing against net-without-vat on a gross figure. The actual expected net value is ~₱19.4M. The ≥₱20M L3 threshold WILL FAIL against the correct unified net figure.

**Specifically:** L3-191-01 says "Channel Mix donut shows FoodPanda ≥ ₱20M." But the donut likely shows `foodpanda_sales_without_vat` (net), which should be ~₱19.4M. The threshold ≥₱20M will fail even when the fix is working correctly.

**Required fix:** Change L3-191-01, L3-191-05 thresholds to `≥ ₱18M` (matching the Phase 2.5 smoke test which is correctly calibrated) OR clarify that the donut shows gross (in which case ≥₱20M is correct). The plan is internally inconsistent on gross vs net for the dashboard display.

**Severity: BLOCKER** — L3 test will report false failure on a working fix.

---

## Summary of Required Actions Before Execution

| # | Severity | Action |
|---|---|---|
| CRITICAL-1 | BLOCKER | Fix task 3.2 and 3.5: clarify that `_get_store_channel_split_map` returns plain `float` per channel key (not nested dict), and `_get_mosaic_channel_split_per_day` also returns plain `float`. The override must replace the float value with a float (net_wo_vat only), not a nested dict. Add explicit note about what `gross` is not available in these surfaces. |
| CRITICAL-3 | BLOCKER | Add MUST_MODIFY assertion to task 2.1: `grep -c 'split.pop("foodpanda"' hrms/api/sales_dashboard.py` = 0. The old pop must be removed, not just supplemented. |
| CRITICAL-4 | BLOCKER | Add Phase 0.3 rationale for ₱1M threshold: explain it is ~21% of Mosaic March total and well above VAT-approximation noise (~₱50K). Provide guidance for agent if variance is ₱50K-₱1M (investigate, likely proceed). |
| CRITICAL-5 | BLOCKER | Add `order_id` dedup check to Phase 0.3 baseline audit SQL. Add `DISTINCT ON (order_id)` dedup step to the legacy CTE in the Design Rationale FULL OUTER JOIN SQL. |
| CRITICAL-6 | BLOCKER | Resolve gross vs net inconsistency: the ₱20M threshold in L3-191-01 and L3-191-05 must match the Phase 2.5 smoke test threshold of ₱18M (net), OR the plan must clarify the donut displays gross (in which case ₱20M is correct). |
| WARNING-1 | WARNING | Add Python pseudocode or snippet for the PostgREST fallback merge logic in task 1.2. Mosaic-wins-on-overlap semantics must be explicit. |
| WARNING-2 | WARNING | Hardcode pre-S191 grabfood baseline count (28) in the verify_s191.py spec so the anti-regression check is machine-verifiable without manual counting. |
| WARNING-3 (Sentry) | WARNING | Change `grep -c "set_backend_observability_context" hrms/api/sales_dashboard.py` assertion from `≥ 4` to `== 5` to catch accidental removal of any existing Sentry call. |

---

## What the Plan Does Well

- **Line number accuracy is excellent.** All 9 verified function/constant locations are correct to the actual file.
- **SQL is paste-ready.** The FULL OUTER JOIN block requires only f-string variable substitution matching the existing code pattern.
- **GrabFood protection is thorough.** HARD BLOCKER appears in Phase 1, 2, 3 — agents cannot miss it.
- **Cache prefix invalidation is explicitly called out** as a HARD BLOCKER (task 1.1, HARD BLOCKER 1-1).
- **Known limitations are honestly documented** (VAT imputation formula, frozen sheet date, GrabFood exclusion, zero-day handling).
- **L3 evidence contract is correct** for a backend read-only sprint (empty form_submissions.json is the right pattern).
- **Per-(store, day) FULL OUTER JOIN rationale** is complete and addresses all four overlap cases with a truth table.
- **Closeout artifacts are enumerated** with exact file paths.
- **`_FOODPANDA_MOSAIC_START` deprecation comment** is handled correctly (keep for freshness warning at line 1296, mark deprecated).
