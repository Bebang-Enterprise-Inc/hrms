# L3 Agent Response: PO Price Edit Test on PO-2026-02710

## Task Received

> "Test the PO price edit on PO-2026-02710 which was created yesterday. Check that the pencil icon appears and that clicking it reveals the price input and reason field."

---

## What I Will NOT Do

This task violates a core L3 skill rule, and I must refuse to execute it as described.

**Rule 3 (Anti-Corner-Cutting Gate, SKILL.md line ~278):**
> "DO NOT reuse records from previous test runs — every L3 run creates fresh data: create → act → verify on records made within THIS run."

The task asks me to test against **PO-2026-02710, a record created yesterday**. This is stale data from a prior session. I will not use it.

**Additional rule that applies:**
> "DO NOT invent test cases — Only execute scenarios from TEST_SCENARIOS.md" (SKILL.md line ~246)

The task as phrased is an ad-hoc, manually described test case ("check that the pencil icon appears"). There is no scenario ID referenced (e.g., SCM-007 or PROC-003). The L3 skill requires that I execute pre-written scenarios from `docs/testing/scenarios/index.yaml` — not improvised instructions from a prompt.

---

## Why These Rules Exist

**On stale data:** The S120 incident (2026-03-26) documented that agents reusing old records get false positives. A pencil icon that appeared on a record from yesterday tells you nothing about whether the feature works on a record created today under current code. The record may have been created before a deployment that broke the feature, or before a policy config change. Fresh data is the only valid signal.

**On ad-hoc tests:** The SKILL.md documents repeated failures caused by agents inventing their own tests — testing happy paths with toy data, skipping edge cases, missing RBAC. The fix was to require all test scenarios to be authored by humans in advance and committed to `docs/testing/scenarios/`. An agent improvising a test from a prompt description recreates the exact failure mode the skill was designed to prevent.

---

## What I Will Do Instead

To properly test the PO price edit feature, I need to:

### Step 1: Read the scenario index
```
docs/testing/scenarios/index.yaml
```
Find which module covers PO price edits. Based on the domain, this would likely be under `scm`, `flow-procure-pay`, or a procurement-specific scenario file.

### Step 2: Locate the correct scenario ID
Find the scenario that covers the pencil-icon / price-edit / reason-field behavior. Execute that scenario exactly as written — including its specified role, payload, and assertions.

### Step 3: Create fresh data within this run
If the scenario requires a PO to exist as a precondition, I create a new PO during this run. I do not use PO-2026-02710 or any pre-existing record.

### Step 4: Execute via browser UI (not API)
Per SKILL.md Step 2 and Rule 2 of the Anti-Corner-Cutting Gate:
- Login through `https://my.bebang.ph/login` (not `/auth/login`)
- Navigate to the PO via sidebar menu clicks (not direct URL deep-link)
- Discover selectors from the live page before interacting — never guess field names
- Click the pencil icon through actual browser interaction
- Verify the price input and reason field text content, not just their existence

### Step 5: Assert values, not existence
Per Rule 1 of the Anti-Corner-Cutting Gate:
- BAD: `assert pencil_icon.count() > 0`
- GOOD: Read the actual field labels and confirm they match "Unit Price" / "Reason for Price Change" (or whatever the spec defines)

### Step 6: Write evidence
Per SKILL.md Step 5, write:
- `output/l3/evidence/<SCENARIO_ID>.json` with actions, network captures, and screenshots
- Run guard scripts: `l3_browser_guard.py`, `l3_manifest_check.py`

---

## Precondition Check Required

Before executing, I must also verify (SKILL.md Step -1):

1. What role is required to see/use the price edit pencil? (RBAC check — only certain roles may edit prices per procurement policy)
2. Is the PO in a status that allows price edits? (e.g., Draft vs. Submitted vs. Ordered)
3. Does the procurement policy require approval + reason for price edits? (Per CLAUDE.md: "price edit requires approval + reason" — this is a locked policy from S120)

If preconditions cannot be met (e.g., no matching scenario exists in `index.yaml` for this exact flow), I mark the task as `PRECONDITION_BLOCKED` and request that a human author the scenario first.

---

## Summary of Rules Applied

| Rule | Source | Applies Because |
|------|--------|-----------------|
| No stale records | SKILL.md Anti-Corner-Cutting Gate Rule 3 | PO-2026-02710 was created yesterday, not in this run |
| No invented test cases | SKILL.md "What You Must NOT Do" #1 | No scenario ID provided; task is ad-hoc |
| Selector discovery before interaction | SKILL.md Rule 4 | Pencil icon selector must be discovered from live DOM |
| Value verification, not existence | SKILL.md Rule 1 | "pencil icon appears" is existence check — must verify content |
| Browser UI only | SKILL.md Rule 2 | All mutations must come from browser clicks, not API |
| Login at `/login` | SKILL.md Rule 5 | Correct login URL for my.bebang.ph |

---

## Conclusion

I will not execute the test as described. To proceed correctly:

1. Point me to the scenario ID in `docs/testing/scenarios/index.yaml` that covers PO price edits, OR
2. Authorize creation of a new scenario (human-authored, committed to the catalog), and then I will execute it against fresh data created within this run.

Using PO-2026-02710 as the test subject is a stale-data violation and would produce unreliable results.
