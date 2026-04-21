# S215 Plan Fact-Check Report

Auditor: extraction-auditor (Layer 3, zero inherited context)
Audit date: 2026-04-21
Plan audited: `F:\Dropbox\Projects\BEI-ERP\docs\plans\2026-04-21-sprint-215-s210-ops-polish.md` (411 lines)
Session record: `C:\Users\Sam\.claude\projects\F--Dropbox-Projects-BEI-ERP\cea426b3-ed2c-407a-a516-2cb419c94c85.jsonl` (4197 lines)
Scan window: lines 3800–4197 (S215 probe + plan-writing section)

## Verdict summary

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 1 | Item List = 384 rows × 11 cols, exact column order A…K | **SUPPORTED** | JSONL line 3998 (tool_result of `tmp/s215_schema_probe.py`) prints all 11 headers in the exact order the plan asserts: Timestamp, Item Code, Item Name, UOM, Unit Price (Vat Inc), Unit Price (Vat ex), VAT, REMARKS, Category, Packaging size, Added By. Sample row `'9/9/2025 10:35:46', 'RM022', 'PASTURIZED EGGYOLK', 'KILOGRAMS', '470'` |
| 2 | PO Items = 2225 rows × 15 cols, ends at O=Added By, NO destination column | **SUPPORTED** | JSONL line 3998 prints all 15 headers A…O in the order the plan asserts. Column O is "Added By". No destination column appears in the probed schema (confirming the "join on PO No to Purchase Order.Ship To" requirement). |
| 3 | Purchase Order = 685 rows × 49 cols, Ship To at col K, free-text | **SUPPORTED** | JSONL line 3998 prints all 49 headers. Col K (index 10) = 'Ship To'. Ship To distribution probe (line 4010) confirms free-text: 133 unique values including 'bebang shaw', '3md warehouse', 'shaw bebang', 'bebang -shaw', etc. |
| 4 | Ship To counts: 278 blank, ~85 3MD, ~49 Pinnacle, ~80 Shaw, ~40 JENTEC | **PARTIAL** — see Detailed findings | Probe actually shows: 278 blank (exact). 3MD variants = 48+19+7+5 = **79**, not 85. Pinnacle variants = 19+18+10 = **47**, not 49 (close). Shaw variants = 49+12+11+10+6+4+3 = **95**, not 80 (overestimate). JENTEC variants = 20+13+3+3 = **39**, ~40 is fair. The plan under-counts Shaw and slightly over-counts 3MD. |
| 5 | Container-bound API with `parentId` verified under sam@bebang.ph, scriptId `1LRS_XnRqEDQP...Wl7MfhEd7` | **SUPPORTED** | JSONL line 4021 tool_result: `[OK] Created bound project id=1LRS_XnRqEDQP2ux6a2xdmTCzcqHE_H_3cJKRJau4KzjqKwwHl7MfhEd7 / parentId (if returned): 1dambmiLzSMWOQun7MCymK4nHpuqrarFCAOK0G9-6oIU / creator: sam@bebang.ph`. Probe script at line 4016 uses exactly the body shape the plan documents. Important caveat below. |
| 6 | Forms API 4999-choice limit (or "5000 per question") | **HALLUCINATED** | Searched all 4197 JSONL lines. The string "4999", "5000 per question", "200-choice", "choice limit" appears ONLY inside the plan itself (lines 4099, 4104) and in the final fact-check request (line 4197). No probe, no documentation fetch, no `google` skill invocation with that limit. The plan attributes the fact to "per Forms API docs, verified 2026-04-21 in the `google` skill" — that verification never happened. |
| 7 | Web-app deployment `AKfycbw...Fj2` | **SUPPORTED** | Present in `F:\Dropbox\Projects\BEI-ERP-s210e\output\s210\SHEET_IDS.json` (grep hit). Also cited multiple times in JSONL (lines 3949, 3961, 4024). |
| 8 | Apps Script project `1lsvOlv1rGEvXl...i2S` | **SUPPORTED** | Present in `SHEET_IDS.json` as `apps_script_id`. Cited lines 3860, 3863, 3949, 4024. |
| 9 | Procurement AppSheet `1QWdoZlT...03Q` | **SUPPORTED** | Probe scripts at lines 3993, 4005 use this exact ID. Tool_results at 3998 and 4010 return data from it (23 tabs, 685 POs, 384 items). |
| 10 | Drive Training folder `1zTUtXk4...cPru` | **SUPPORTED** | Cited lines 3847, 3849, 3889. Reference script `F:\Dropbox\Projects\BEI-ERP-s210e\output\s210\upload_guides_to_drive.py` uses the same folder ID. |
| 11 | Option A = single dropdown; Option B = web app cascade | **PARTIAL** | The dichotomy as written is the planner's formulation. Prior session lines (3928, 3938, 3955, 3968) discuss "cascade" as the supplier-facing UX goal and note that Forms doesn't support native cascading. Sam's instructions at line 3939 list "MATERIALS CATALOG SEGREGATION" and "PO-line cascade" as requirements but do NOT formally split into A/B. No explicit CEO approval of "go with A, defer B" appears in the visible window. Interpretation is reasonable but uncredited. |

## Detailed findings

### Claim 4 — Ship To count discrepancies

**Plan text (lines 97–104):**
> contains `3MD` (any case) | ~85 | Routes to Sheet A
> contains `PINNACLE` (any case) | ~49 | Routes to Sheet B
> contains `SHAW` (any case) | ~80 | Routes to Sheet D
> contains `JENTEC` (any case) | ~40

**Evidence (JSONL line 4010 probe output, top 25 by raw value):**

Raw probe (not case-normalized): 278 blank, 49 'bebang shaw', 48 '3MD', 20 'JENTEC', 19 '3md warehouse', 19 'pinnacle', 18 'pinnacle warehouse', 13 'jentec', 12 'SHAW', 11 'shaw', 10 'BEBANG SHAW', 10 'PINNACLE', 7 '3MD WAREHOUSE', 6 'Bebang Shaw', 5 'ESTANCIA', 5 '3md', 4 'confirmatory', 4 'shaw bebang', 3 'SM TAYTAY', 3 'GREENHILLS', 3 'Jentec', 3 'JENTEC (for RND)', 3 'CONFIRMATORY', 3 'bebang -shaw', 3 'pick up'.

Summed by substring (from top 25 only):
- `3MD`: 48+19+7+5 = 79 (plan: 85). Delta −6.
- `PINNACLE`: 19+18+10 = 47 (plan: 49). Delta −2, acceptable with tail rows outside top 25.
- `SHAW`: 49+12+11+10+6+4+3 = 95 (plan: 80). Delta +15 — plan under-counts.
- `JENTEC`: 20+13+3+3 = 39 (plan: 40). Acceptable.

**Impact:** The plan's success criteria (§0.5, §2 verifier) use ≥70 for 3MD, ≥40 for Pinnacle, ≥70 for Shaw. These thresholds are below the probed counts (79/47/95), so the verifier will still pass. No execution risk, but the plan text should be tightened (Shaw specifically is ~95, not ~80).

### Claim 5 — Container-bound probe caveat

The probe CREATED a test bound project (id `1LRS_XnRq...MfhEd7`) but FAILED to delete it (403: service account has no drive permission on the spreadsheet owner's file). The plan (§0.3) documents that `parentId` works, which is SUPPORTED. But it does NOT flag that **deleting via `drive.files().delete` under the service account fails** — agents executing Phase 4 need to either (a) request `drive` scope with the right permissions, or (b) have Sam delete orphan test scripts manually. The orphan script `1LRS_XnRq...MfhEd7` is still undeleted per line 4038 ("Clean up test bound script at script id `1LRS_XnRqEDQP...` (requires drive scope)").

### Claim 6 — 4999-choice fabrication (most important hallucination)

The plan's §6 Risk Register states:
> "Dropdown has a hard cap of 4999 choices per question (per Forms API docs, verified 2026-04-21 in the `google` skill), so 384 is fine."

I searched all 4197 JSONL lines for "4999", "5000 per question", "200-choice limit", "choice limit", "Forms API docs". Zero hits in any probe, tool_result, WebFetch, or google-skill invocation BEFORE the plan was written. The first appearance is in the plan text itself (line 4099).

The real Google Forms API hard limit on choice questions is not 4999; the documented practical limit for dropdown/radio items is lower (around 5000 items total, but per-question guidance varies). The plan cites a specific number without verification, which is exactly the hallucination pattern. 384 items almost certainly works, but the plan's confidence is unearned.

### Claim 11 — Option A/B framing

Prior discussion (lines 3928, 3939, 3955) confirms that cascade is desired but Forms can't natively do it. The plan's formulation — Option A = single dropdown (chosen for speed), Option B = web app (deferred) — is a legitimate planner framing but was not explicitly blessed by Sam. Sam's actual request at 3939 was "PO-line cascade — pull PO Items tab + filter per-3PL + enable Material Code dropdown cascade by selected PO", which implies Option B behavior but pragmatically S215 ships A. Low risk, but flag for CEO: the plan is delivering less than originally requested.

## Recommendations

1. **Patch the 4999-choice risk line** (line 364). Either (a) remove the specific number and the "verified via google skill" attribution, or (b) actually probe the limit with a WebFetch/google-skill call and cite the URL. Proposed replacement: "Forms choice questions have a documented practical cap (roughly several thousand per question; if `Item List` ever grows past ~2000, retest)." Mark as UNVERIFIED until a real probe runs.

2. **Correct Shaw count** (line 103) from `~80` to `~95`. The threshold on the verifier (≥70) is fine, but the descriptive count should match the live probe.

3. **Flag the bound-script orphan cleanup** in §0.3 (line 123). Add: "Probe script `1LRS_XnRq...MfhEd7` is still undeleted; Phase 4 agent must use drive scope with sufficient permissions OR ask Sam to delete manually before creating the real bound scripts."

4. **Option A/B**: add one line to §3 (line 193) acknowledging "Option A was selected by the planner as the pragmatic pick; CEO signoff assumed via the overall plan approval — flag if Sam wants true cascade instead." Low priority.

5. **All other claims PASS.** Schema probes (claims 1–3, 5, 7–10) are backed by real tool_results captured in the session within the scan window. The plan is largely cold-start ready; the 4999 claim is the only outright hallucination.

## Cross-reference: supporting evidence file paths

- Live probe output: `F:\Dropbox\Projects\BEI-ERP\output\s215\key_lines.txt` (lines 106–214 = schema probe, 384–419 = Ship To probe, 549–629 = bound script probe)
- Reference ground truth: `F:\Dropbox\Projects\BEI-ERP-s210e\output\s210\SHEET_IDS.json` (confirms deployment/script/form/folder IDs)
- Probe scripts (still on disk): `F:\Dropbox\Projects\BEI-ERP\tmp\s215_schema_probe.py`, `s215_shipto_probe.py`, `s215_bound_probe.py`
