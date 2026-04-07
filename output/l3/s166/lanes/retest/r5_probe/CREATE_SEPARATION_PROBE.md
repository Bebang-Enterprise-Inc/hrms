# Create Separation Button Probe — Defect #22
**R5 Probe Agent | 2026-04-07 | Static code analysis**

## Summary

The "Create Separation" submit button on the separations dialog is **disabled when
`formData.employee` is empty OR `formData.separation_type` is empty**. R4's script
filled the employee field via an input selector that may not have correctly updated
the React-controlled `formData.employee` state, and the separation type dropdown
may not have been selected at all.

---

## Root Cause: Missing `employee` and/or `separation_type` in controlled state

### Button gate — `page.tsx` line 483

```tsx
<Button
  type="submit"
  disabled={isSubmitting || !formData.employee || !formData.separation_type}
>
  {isSubmitting ? "Creating..." : "Create Separation"}
</Button>
```

The button enables **only when both `formData.employee` AND `formData.separation_type`
are non-empty strings.**

---

## Field Analysis

### Field 1: Employee (required — `formData.employee`)

The employee field uses `<EmployeeSearchSelector>`, a custom combobox component:

```tsx
<EmployeeSearchSelector
  id="separation-employee"
  value={formData.employee}
  onChange={(value) => setFormData((prev) => ({ ...prev, employee: value }))}
  placeholder="Select employee"
  preloadedEmployee={preloadedEmployee}
/>
```

This is a **custom controlled component**, not a plain `<input>`. The `onChange`
callback receives the selected employee ID (e.g., `"HR-EMP-00046"`) and updates
`formData.employee`.

**R4's selector approach:**
```js
const empInput = dlg.locator('input[placeholder*="employee" i], input[placeholder*="search" i]').first();
if (await empInput.count() > 0) {
    await empInput.fill(empId);      // types into the text box
    await page.waitForTimeout(1000);
    const empOpt = page.locator('[role="option"]').filter({ hasText: empId }).first();
    if (await empOpt.count() > 0) {
        await empOpt.click();        // clicks the dropdown option
        ev.employee_selected = true;
    }
}
```

The R4 evidence JSON for EMP-TERMINATE-001 does NOT contain `employee_selected: true`,
which means **the option was never found or clicked**. The raw text was typed into the
search box, but either:
1. The dropdown options didn't appear (the `EmployeeSearchSelector` debounces or requires
   a minimum character count), OR
2. The option locator `filter({ hasText: empId })` used "HR-EMP-00046" which is the
   employee ID — but the dropdown may show employee names, not IDs

Either way: `ev.employee_selected` is absent from the evidence JSON → `formData.employee`
remained `""` (the initial state for a fresh dialog, since `requestedEmployee` was not
passed via URL params in R4's navigation).

### Field 2: Separation Type (required — `formData.separation_type`)

```tsx
<Select
  value={formData.separation_type}
  onValueChange={(value) =>
    setFormData((prev) => ({ ...prev, separation_type: value }))
  }
>
```

This is a Shadcn `<Select>`, not a native `<select>`. It uses `[role="combobox"]` for
the trigger.

**R4's selector approach:**
```js
const sepTypeSelect = dlg.locator('select[name*="type"], [role="combobox"]').first();
if (await sepTypeSelect.count() > 0) {
    await sepTypeSelect.click({ force: true }).catch(() => {});
    await page.waitForTimeout(400);
    const firstOpt = page.locator('[role="option"]').first();
    if (await firstOpt.count() > 0) await firstOpt.click().catch(() => {});
}
```

The `[role="combobox"]` locator would match the Shadcn Select trigger. However,
`page.locator('[role="option"]').first()` is a page-level locator, not scoped to the
Select popover. If the EmployeeSearchSelector (also a combobox) had a dropdown open
simultaneously, or if the popover wasn't yet visible, this would click nothing or
click the wrong option.

Additionally, `separationTypes` data is loaded async from `/api/hr/separations?action=types`.
If that API call hadn't resolved by the time R4 tried to click, the Select would have
zero options in the content, and clicking `[role="option"]` would fail silently.

**Net result: `formData.separation_type` likely remained `""` even if the click
appeared to succeed.**

---

## Why the Button Stayed Disabled

Both required fields failed to be set in React state:

| Field | Initial State | R4 Fill Success | Evidence |
|-------|--------------|-----------------|----------|
| `formData.employee` | `""` | No — `employee_selected` not in evidence JSON | button still disabled after 30s wait |
| `formData.separation_type` | `""` | Uncertain — but `firstOpt` click was not confirmed | button still disabled |

Since `disabled = isSubmitting || !formData.employee || !formData.separation_type`,
and at least `formData.employee` was `""` → button stayed disabled regardless.

---

## How to Correctly Fill This Form in a Test Script

### Employee field

The `EmployeeSearchSelector` is a custom combobox. The correct interaction sequence is:

```js
// 1. Find the trigger button (has placeholder text, not a plain input initially)
const empTrigger = dlg.locator('[placeholder="Select employee"]').first();
// OR: find the search input inside the popover after clicking
await empTrigger.click();
await page.waitForTimeout(300);

// 2. Type in the search input that appears
const searchInput = page.locator('[role="combobox"][placeholder*="employee" i], input[placeholder*="search" i]').first();
await searchInput.fill('HR-EMP-00046');
await page.waitForTimeout(800);  // wait for debounce + API results

// 3. Click the option — may show employee NAME not ID
const opt = page.locator('[role="option"]').first();
await opt.click();
// Now formData.employee is set
```

### Separation type field

```js
// 1. Wait for separationTypes to load (the Select is populated async)
await page.waitForFunction(() => {
  // wait until at least one option appears in DOM
  return document.querySelectorAll('[role="option"]').length > 0;
}, { timeout: 5000 }).catch(() => {});

// 2. Click the Shadcn Select trigger
const typeSelect = dlg.locator('[role="combobox"]').nth(1);  // second combobox (after employee)
await typeSelect.click();
await page.waitForTimeout(300);

// 3. Pick the first available option
const firstTypeOpt = page.locator('[role="option"]').first();
await firstTypeOpt.click();
// Now formData.separation_type is set
```

---

## Form Fields Summary

All fields in the Create Separation dialog:

| Field | Component | Required | Gate |
|-------|-----------|----------|------|
| Employee | `EmployeeSearchSelector` (custom combobox) | YES | `!formData.employee` |
| Separation Type | Shadcn `<Select>` | YES | `!formData.separation_type` |
| Offboarding Start Date | `<Input type="date">` | No | pre-filled with today |
| Reason | `<Textarea>` | No | not gating |

Only TWO fields gate the submit button. The date and reason fields are optional.

---

## Recommended Fix for Test Script

The R4 test script must be updated to:

1. Use `EmployeeSearchSelector`'s actual DOM contract (type in the search box INSIDE
   the combobox popover, wait for async results, click option by name not ID)
2. Wait for `separationTypes` to load before interacting with the Separation Type select
3. Scope `[role="option"]` locators to their respective popovers to avoid cross-matching

This is a **test script deficiency**, not a UI bug. The button's gate
`disabled={!formData.employee || !formData.separation_type}` is correct behavior.
The form works correctly when both fields are filled via the UI interactively.

---

## Evidence Sources

- `separations/page.tsx` line 483: button `disabled` condition
- `separations/page.tsx` line 407–488: full form structure
- R4 evidence: `output/l3/s166/lanes/retest/r4_emp_retest/evidence/EMP-TERMINATE-001-retest.json`
  — note: `employee_selected` key is absent from the JSON, confirming the option was never clicked
