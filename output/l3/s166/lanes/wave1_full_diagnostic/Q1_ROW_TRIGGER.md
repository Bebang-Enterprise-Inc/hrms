# Q1 — EmployeeDetailDialog Row Trigger

**Verdict: FOUND**

## Root Cause of Wave 0 Failure

The Wave 0 runner used `table tbody tr` clicks. The shadcn data-table on `/dashboard/hr/employee-master` IS a real `<table>` with `<tbody><tr>` (100 rows visible) — so the selector was structurally correct. **The problem:** clicking the `<tr>` itself does NOT trigger the dialog. The row's first cell contains a `<button>` whose accessible name is the employee's display name (e.g., "Aaron Jan P. Bautista"). The Bio ID (`9000746`) is rendered as a separate text node beneath the button, not inside its accessible name — which is why `getByRole('button', { name: /9\d{6}/ })` also fails.

## DOM Structure (first row)

```
<tr class="border-b align-top hover:bg-muted/20 h-16">
  <td class="sticky left-0 ...">1</td>
  <td>
    <button>Aaron Jan P. Bautista</button>   ← THIS opens the dialog
    9000746                                    ← plain text, not in button
  </td>
  ... 9 more <td>s ...
  <td><button>Actions</button></td>          ← row-level menu (NOT dialog trigger)
</tr>
```

- `tbody tr` count: 100
- `[role="row"]` count: 0  ← table does NOT use ARIA role
- buttons per row: 2 (employee-name button, Actions button)
- first row class: `border-b align-top hover:bg-muted/20 h-16`

## Working Snippet

```javascript
// Wait for table to populate (TanStack Query, 5-8s on cold load)
await page.goto(`${BASE}/dashboard/hr/employee-master`, { waitUntil: 'networkidle' });
await page.waitForSelector('tbody tr', { timeout: 30000 });
await page.waitForTimeout(2000); // settle

// Click the employee-name button (NOT the row, NOT the Actions button)
await page.locator('tbody tr').first().locator('button').first().click();

// Dialog opens within ~1s
await page.waitForSelector('[role="dialog"]', { timeout: 5000 });
```

To target a specific employee by name:
```javascript
await page.locator('tbody tr')
  .filter({ hasText: 'Aaron Jan P. Bautista' })
  .first()
  .locator('button').first()
  .click();
```

To target by Bio ID (Bio ID is in the same `<td>` as the name):
```javascript
await page.locator('tbody tr')
  .filter({ hasText: '9000746' })
  .first()
  .locator('button').first()
  .click();
```

## Dialog Contents (verified)

- Title: `<h2>` with employee name
- Sections: PERSONAL INFO, EMPLOYMENT, COMPENSATION, GOV IDs & DOCUMENTS, RECENT CHANGES
- Edit buttons: PERSONAL INFO → Edit, EMPLOYMENT → Edit, COMPENSATION → "Edit Compensation"
- Compensation read-only fields: Base Salary, Daily Rate, Gross Pay, Comm, De Min, Hon, Meal, Gas, Other, SSS, PhilHealth, Pag-IBIG, Tax, Net Take-Home, Company Cost, Bank, Account No.
- Gov IDs: TIN/SSS/PhilHealth/Pag-IBIG (masked) + "use the Sensitive Changes queue (dual-control approval required)" hint
- Footer: "Open in HRMS" link, Close button
- 0 `<input>` elements visible (Edit buttons trigger inline form switches — not pre-rendered)
- 0 `<role="tab">` — sections are collapsible accordions, not tabs

## Implication for Lane A

EMP-EDIT-* and EMP-DETAIL-VIEW-* scenarios are RUNNABLE. EMP-COMPENSATION-* scenarios can be initiated from this dialog via the "Edit Compensation" button (not via the broken `/compensation-setup` list-page modal). The Lane A agent brief should be updated to:

1. Use the snippet above to open EmployeeDetailDialog.
2. Click `Edit` next to PERSONAL INFO / EMPLOYMENT to mutate those sections.
3. Click `Edit Compensation` to launch the comp editor (whatever that opens — needs probing inside Lane A).
4. Use the "Open in HRMS" link only as a fallback.

## Screenshots

- `screenshots/q1_employee_master_loaded.png`
- `screenshots/q1_first_row_name_button_OPENED.png`
