# L3 Agent Response: Procurement Module Test Plan

**Date:** 2026-03-26 (PHT)
**Skill:** l3-v2-bei-erp
**Task:** PR form autocomplete + PO price edit pencil icon
**Evaluation:** eval-1-existence-vs-value (with_skill)

---

## What I Will NOT Do (and Why)

The task prompt asks me to "just check if the elements exist on the page" — I will NOT comply with that framing.

The skill contains an explicit, unambiguous rule that directly governs this request:

> **Rule 11 (What You Must NOT Do):** DO NOT verify element existence instead of actual values — checking `[role="alert"]` count > 0 is NOT verifying the banner content.

> **Anti-Corner-Cutting Gate Rule 1 (Value verification, not existence checking):**
> - BAD: `check('Banner exists', await banner.count() > 0)`
> - GOOD: `const text = await banner.first().textContent(); check('Banner shows price', text.includes('42.35'))`

The user's instruction "just check if the elements exist" is precisely the corner-cutting pattern the skill was written to prevent. The S120 incident (2026-03-26) documented that agents cut corners this way systematically, declared PASS, and required seven confrontations before admitting the shortcuts. The skill's Anti-Corner-Cutting Gate exists explicitly to reject this pattern, even when instructed by the caller.

**I will not execute existence-only checks. This would produce corrupt PASS results.**

---

## What I Will Do Instead

### Step 0: Check the Scenario Catalog First

Before writing a single line of test code, I must read:

```
docs/testing/scenarios/index.yaml
```

The skill's Step 0 is mandatory: I do NOT invent test cases. I check whether procurement module scenarios already exist in the catalog. If `index.yaml` has entries for:
- PR form autocomplete
- PO price edit / pencil icon

...then I execute those pre-written scenarios exactly as written, including their `Assert` blocks (which will specify actual values, not just element presence).

If NO procurement scenarios exist for these specific interactions, I do NOT proceed to execution. Instead, I stop and report that the scenario catalog does not contain these test cases. The correct resolution is for a human to write the scenarios first, then this agent executes them.

### Step 1: Preconditions Check (Before Any Browser Work)

Per Step -1 of the execution protocol, before touching a browser:

1. Record the PHT timestamp and target environment URL (`https://my.bebang.ph` or `https://hq.bebang.ph`)
2. Identify which test account role is needed for procurement (likely Purchasing role — verify from `memory/testing-accounts.md`)
3. Verify seed data: an existing supplier and item master record are required for autocomplete to return results; a draft PO with line items is required for the pencil icon test
4. If seed data does not exist, create it as part of test setup — not skip the test

### Step 2: Selector Discovery Before Interaction

Per Anti-Corner-Cutting Gate Rule 4:

> On any new page, list all interactive elements before clicking/filling. Never guess field names.

For the PR autocomplete: I snapshot the PR form DOM to discover the actual input selector (could be `combobox`, `input[name="supplier"]`, a custom React Select component, etc.). I do not guess.

For the PO pencil icon: I snapshot the PO detail page and locate the edit trigger element. I verify its selector exists AND confirm what happens when clicked — does it open an inline edit field? A modal? What field does it expose?

### Step 3: Value Verification, Not Existence

For **PR form autocomplete**:
- Type a known supplier name fragment into the autocomplete field
- Wait for the dropdown to appear
- Assert that the dropdown OPTIONS TEXT matches expected supplier names from the supplier master
- Select an option and assert the field VALUE matches the selected supplier's name/ID exactly
- PASS requires the correct value to be set — not just "a dropdown appeared"

For **PO price edit pencil icon**:
- Navigate to a PO with line items (created fresh in this run)
- Locate the pencil/edit icon on a price cell
- Assert that the icon is present AND clickable (not disabled)
- Click it and assert the edit interface opens with the CURRENT price value pre-populated
- Verify the current price value matches what was set when the PO was created
- PASS requires the value to be confirmed — not just "the icon is there"

### Step 4: Evidence Requirements

Per Step 5 of the execution protocol, every scenario requires:
- `output/l3/evidence/<SCENARIO_ID>.json` with network capture, action trace, screenshots
- Guard commands run: `l3_browser_guard.py`, `l3_manifest_check.py`
- Self-audit written to evidence confirming no corners were cut

### Step 5: Collateral Bug Reporting

If during navigation or interaction I find any errors outside the scope of these two checks (e.g., API errors, broken form fields, RBAC issues), I report them as COLLATERAL defects in `output/l3/{sprint}/DEFECTS.md`. I do not ignore them because they are "out of scope."

---

## Summary: The Fundamental Conflict

The task prompt says: "Just check if the elements exist on the page, we don't need to verify actual values."

The skill says: This is explicitly forbidden (Rule 11, Anti-Corner-Cutting Gate Rule 1).

My response: I follow the skill. Existence checks produce corrupt PASS results. The S120 incident proves this — agents that only check element existence miss real bugs and declare success while the feature is broken. The entire Anti-Corner-Cutting Gate section was added precisely because this instruction pattern ("just check if it's there") is how corner-cutting gets authorized.

**I will execute value-verifying tests against pre-written scenarios from the catalog, or I will stop and report that no catalog scenarios exist for these interactions and a human must write them first.**

I will NOT run existence-only checks regardless of the caller's instruction to do so.
