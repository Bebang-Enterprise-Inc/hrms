# Playwright Skill Improvement Plan

## Current State
- Skill: `.claude/skills/playwright-bei-erp/SKILL.md` (1108 lines)
- Uses Python examples exclusively, but S120 testing proved Node.js .mjs files work better for bei-tasks
- No BEI-specific patterns for my.bebang.ph (login URL, shadcn selectors, combobox patterns)

## What Failed in S120 Testing (Real Incidents)

1. **Login URL wrong** — skill has no BEI login URL reference. Agent tried `/auth/login`, actual is `/login`
2. **No shadcn selector guide** — agent guessed `[cmdk-item]` when actual is `[role="option"]` for shadcn Command component
3. **Combobox interaction pattern missing** — shadcn Popover + Command combobox needs: click trigger → wait → type in input → wait for debounce → click option. Agent didn't know the sequence.
4. **Inline scripts fail** — complex Playwright scripts in bash break due to escaping. Need .mjs file pattern.
5. **Toast timing** — default 5s wait lets toasts auto-dismiss. Need 2s pattern with immediate read.
6. **agent-browser vs Playwright** — agent-browser Chrome wouldn't start headless on Windows. Playwright worked. Skill should note this.
7. **No Node.js examples** — skill only has Python sync_api examples. All S120 tests used Node.js ESM.

## Specific Additions Needed

### Section: BEI my.bebang.ph Patterns
```javascript
// Login
await page.goto('https://my.bebang.ph/login', { waitUntil: 'networkidle' });
await page.fill('input[name="email"]', email);
await page.fill('input[name="password"]', password);
await page.click('button[type="submit"]');
await page.waitForURL('**/dashboard**', { timeout: 30000, waitUntil: 'domcontentloaded' });

// Shadcn Combobox (Item Search, Department, etc.)
await page.locator('button[role="combobox"]').nth(INDEX).click();
await page.waitForTimeout(500);
await page.locator('input[placeholder*="search text"]').first().fill('query');
await page.waitForTimeout(2000); // debounce
const options = page.locator('[role="option"]');
await options.first().click();

// Shadcn Dialog
await page.locator('[role="dialog"] button:has-text("Confirm")').click();

// Toast reading (read fast, before auto-dismiss)
await page.waitForTimeout(2000); // NOT 5s
const toasts = await page.locator('[data-sonner-toast]').allTextContents();
```

### Section: Node.js .mjs Pattern
```javascript
// Save as scripts/testing/l3_xxx.mjs — NEVER inline in bash
import { chromium } from 'playwright';
const browser = await chromium.launch({ headless: true });
// ... test code ...
await browser.close();
```
Run: `node scripts/testing/l3_xxx.mjs`

### Section: Selector Discovery (before guessing)
```javascript
// ALWAYS inspect the page before interacting
const buttons = await page.locator('button').all();
for (const btn of buttons) {
  console.log(await btn.textContent());
}
```

## Test Cases for Eval

See: `playwright-bei-erp-workspace/evals/evals.json`
