---
name: playwright-bei-erp
description: Use when running Playwright browser tests, generating E2E tests, verifying user flows, or debugging browser automation failures.
---



# Playwright CLI Testing Skill

Run browser tests from Claude Code sessions using Playwright CLI. No MCP servers needed — each session gets its own lightweight browser process.

**Key capability:** Browser-session API verification via `page.evaluate(fetch(...))` — tests APIs with the real user's session cookies, catching backend bugs that UI-only testing misses. See [Section 11](#11-browser-session-api-verification-critical).

---

## Quick Reference

```bash
# Run all E2E tests
npx playwright test

# Run specific test file
npx playwright test tests/e2e/login.spec.ts

# Run with AI-friendly JSON output
npx playwright test --reporter=json

# Run specific test by name
npx playwright test -g "login page loads"

# Run headed (visible browser)
npx playwright test --headed

# Run with specific browser
npx playwright test --project=chromium
npx playwright test --project=firefox

# Generate test from browser recording
npx playwright codegen https://your-app.com

# View last HTML report
npx playwright show-report
```

---

## 1. Browser Choice

### Memory Per Instance (Benchmarks)

| Browser | Headless | Headed | Speed vs Chromium |
|---------|----------|--------|-------------------|
| **Chromium** | ~700 MB | ~1,100 MB | Baseline (fastest) |
| **Firefox** | ~826 MB | ~874 MB | ~70% slower |
| **WebKit** | ~588 MB | ~590 MB | 2-3x slower |

Sources: [Playwright Browser Footprint](https://datawookie.dev/blog/2025/06/playwright-browser-footprint/), [Cross-Browser Analysis](https://ray.run/blog/cross-browser-analysis-of-playwright-testing-efficiency)

### Recommendations

| Priority | Browser | When to Use |
|----------|---------|-------------|
| **Speed** | Chromium | Default choice. Fastest execution, best error messages, best DevTools |
| **Stability** | Firefox | Slightly less RAM in headed mode. Good alternative if Chromium has issues |
| **Low memory** | WebKit | 45% less RAM than Chromium. Use when memory is tight but speed isn't critical |

### Switching Browser

```bash
# One-off
npx playwright test --project=firefox

# In playwright.config.ts
projects: [
  { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
]
```

### CRITICAL: Version Pinning

**DO NOT upgrade past Playwright v1.56.x** without checking [GitHub #38489](https://github.com/microsoft/playwright/issues/38489).

Playwright v1.57+ switched from open-source Chromium to "Chrome for Testing" which has a memory bug: **~20GB per instance** vs ~1GB with Chromium. As of February 2026, this is closed but unresolved.

```json
// package.json - pin version
"@playwright/test": "1.56.1"
```

**If you accidentally upgrade:**
```bash
npm install -D @playwright/test@1.56.1
npx playwright install
```

**When to reconsider:** Monitor the GitHub issue. Once the Playwright team fixes the Chrome for Testing memory regression, upgrading becomes safe.

---

## 2. Parallel Sessions

### How It Works

Each `npx playwright test` from a separate Claude Code session is a **completely independent OS process**. They don't share browsers, ports, state, or files. They don't know about each other.

```
Session 1 → npx playwright test tests/auth.spec.ts       → own browser (~700MB)
Session 2 → npx playwright test tests/dashboard.spec.ts  → own browser (~700MB)
Session 3 → npx playwright test tests/checkout.spec.ts   → own browser (~700MB)
Session 4 → npx playwright test tests/settings.spec.ts   → own browser (~700MB)
```

**This is NOT Playwright's internal parallelism** (workers). The flakiness bugs reported on GitHub are about multiple workers inside ONE test run fighting over shared state. Separate sessions running separate tests have zero interaction.

### Memory Budget

| Sessions | Chromium (headless) | Firefox | WebKit |
|----------|-------------------|---------|--------|
| 1 | ~700 MB | ~826 MB | ~588 MB |
| 2 | ~1.4 GB | ~1.7 GB | ~1.2 GB |
| 3-4 | ~2.1-2.8 GB | ~2.5-3.3 GB | ~1.8-2.4 GB |
| 8 | ~5.6 GB | ~6.6 GB | ~4.7 GB |

For comparison: MCP browser servers typically use **8-10 GB** across 8 sessions for the same functionality.

### Rules for Parallel Sessions

1. **Each session runs different test files** — don't run the same file from 2 sessions simultaneously
2. **Use 1 worker per session** — parallelism is across sessions, not within
3. **Tests against a remote URL are safe** — multiple sessions hitting the same server is fine
4. **Tests that mutate the same database record may conflict** — use different test data per session
5. **Report output**: use different output directories or filenames per session

### Avoiding Report File Conflicts

```bash
# Session 1
npx playwright test auth.spec.ts --output=test-results/session1

# Session 2
npx playwright test dashboard.spec.ts --output=test-results/session2
```

Or use JSON reporter with different filenames:

```bash
# Session 1
npx playwright test auth.spec.ts --reporter=json > results-auth.json 2>&1

# Session 2
npx playwright test dashboard.spec.ts --reporter=json > results-dashboard.json 2>&1
```

---

## 3. AI-Friendly Test Output

### Reporter Options

| Reporter | Best For | Token Usage |
|----------|----------|-------------|
| `line` | Real-time progress, minimal output | Lowest |
| `json` | AI parsing failures programmatically | Medium |
| `list` | Human readability | Medium |
| `html` | Human debugging with screenshots | N/A (file) |
| `dot` | CI/CD (minimal console noise) | Lowest |

### Recommended AI Workflow

```bash
# Step 1: Quick pass/fail check
npx playwright test --reporter=line

# Step 2: If failures, get structured details
npx playwright test --reporter=json

# Step 3: Parse JSON for error messages, stack traces, file paths
# JSON includes: test name, status, duration, error messages, file locations
```

### JSON Output Structure

```json
{
  "suites": [{
    "title": "Login Flow",
    "specs": [{
      "title": "should login with valid credentials",
      "ok": true,
      "tests": [{
        "status": "passed",
        "duration": 1234
      }]
    }]
  }]
}
```

### The AI Fix Loop

```
1. Run:    npx playwright test --reporter=line
2. Fail?   Re-run failed test with --reporter=json
3. Parse:  Read error messages and stack traces
4. Fix:    Edit source code causing the failure
5. Verify: npx playwright test <specific-file> --reporter=line
6. Repeat until all pass
```

### Multiple Reporters (Best of Both Worlds)

```typescript
// playwright.config.ts
reporter: [
  ['line'],                                        // Console output
  ['json', { outputFile: 'test-results.json' }],   // AI parsing
  ['html', { open: 'never' }],                     // Human debugging
],
```

---

## 4. Configuration

### Minimal Config

```typescript
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30000,
  use: {
    baseURL: process.env.TEST_BASE_URL || "https://your-app.com",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
```

### Optimized for Multi-Session AI Testing

```typescript
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  workers: 1,                              // 1 worker per session (parallelize across sessions)
  retries: process.env.CI ? 2 : 0,
  timeout: 30000,

  reporter: [
    ["line"],
    ["json", { outputFile: "test-results.json" }],
  ],

  use: {
    baseURL: process.env.TEST_BASE_URL || "https://your-app.com",
    headless: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        launchOptions: {
          args: [
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-extensions",
          ],
        },
      },
    },
  ],
});
```

### CLI Overrides (No Config Changes Needed)

```bash
# Force 1 worker
npx playwright test --workers=1

# Force headless
npx playwright test --headed=false

# Force specific reporter
npx playwright test --reporter=json

# Force specific browser
npx playwright test --project=firefox

# Increase timeout
npx playwright test --timeout=60000
```

---

## 5. Writing Tests

### Test Template (L2 — UI Only)

```typescript
import { test, expect } from "@playwright/test";

test.describe("Feature Name", () => {
  test("should do something specific", async ({ page }) => {
    await page.goto("/login");
    await page.waitForLoadState("networkidle");

    await page.getByLabel("Email").fill("user@example.com");
    await page.getByLabel("Password").fill("password123");
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page.getByText("Dashboard")).toBeVisible();
  });
});
```

### Test Template (L4 — Full Verification, PREFERRED)

```typescript
import { test, expect } from "@playwright/test";

test.describe("Feature Name", () => {
  test("should submit form and verify backend record", async ({ page }) => {
    // 1. Login as real user
    await page.goto("https://hq.bebang.ph/login");
    await page.fill('input[name="usr"]', 'test.staff@bebang.ph');
    await page.fill('input[name="pwd"]', 'BeiTest2026!');
    await page.click('button[type="submit"]');
    await page.waitForNavigation();

    // 2. Navigate to feature
    await page.goto("https://my.bebang.ph/dashboard/feature");
    await page.waitForLoadState("networkidle");

    // 3. Fill and submit form
    await page.getByLabel("Field").fill("Test Value");
    await page.getByRole("button", { name: "Submit" }).click();

    // 4. Verify API response (L3)
    const apiResult = await page.evaluate(async () => {
      const r = await fetch('/api/frappe/api/method/hrms.api.module.get_record', {
        headers: { 'Accept': 'application/json' },
      });
      const text = await r.text();
      let json = null;
      try { json = JSON.parse(text); } catch {}
      return { ok: r.ok, status: r.status, json };
    });
    expect(apiResult.ok).toBe(true);

    // 5. Verify database record (L4)
    const record = await page.evaluate(async () => {
      const params = new URLSearchParams({
        filters: JSON.stringify([["field", "=", "Test Value"]]),
        limit_page_length: "1",
        order_by: "creation desc",
      });
      const r = await fetch(`/api/frappe/api/resource/DocType?${params}`, {
        headers: { 'Accept': 'application/json' },
      });
      const data = await r.json();
      return data?.data?.[0] || null;
    });
    expect(record).not.toBeNull();
    expect(record.field).toBe("Test Value");

    // 6. Screenshot evidence
    await page.screenshot({ path: "scratchpad/qa/feature_submit_verified.png" });
  });
});
```

### Selector Best Practices

```typescript
// BEST - Role-based (stable, semantic, recommended by Playwright team)
page.getByRole("button", { name: "Submit" });
page.getByLabel("Email address");
page.getByPlaceholder("Enter your name");
page.getByText("Welcome back");

// GOOD - Test IDs (stable, explicit)
page.getByTestId("checkout-button");

// AVOID - CSS selectors (brittle, break on refactors)
page.locator("div > button:nth-child(3)");
page.locator(".btn-primary");
page.locator("#submit-form");
```

### Generating Tests with Codegen

```bash
# Record browser actions → generates test code
npx playwright codegen https://your-app.com

# Record on mobile viewport
npx playwright codegen --viewport-size=375,667 https://your-app.com

# Record with specific device emulation
npx playwright codegen --device="iPhone 12" https://your-app.com
```

Codegen opens a browser and records clicks/inputs as Playwright code. Copy the output into a `.spec.ts` file, then refine selectors and add assertions.

---

## 6. Debugging Failures

### Tools

```bash
# Interactive HTML report with screenshots and traces
npx playwright show-report

# Step-by-step trace replay
npx playwright show-trace test-results/*/trace.zip

# Debug mode (Playwright Inspector — step through test)
npx playwright test --debug tests/e2e/login.spec.ts

# Headed mode (watch the browser)
npx playwright test --headed tests/e2e/login.spec.ts
```

### Common Failure Patterns

| Error | Cause | Fix |
|-------|-------|-----|
| `Timeout 30000ms exceeded` | Element not found or page slow | Increase timeout, add `waitForLoadState`, check selector |
| `Element not visible` | Element hidden or offscreen | Check viewport, use `scrollIntoViewIfNeeded` |
| `Navigation interrupted` | Page navigated during interaction | Add `waitForURL` after navigation triggers |
| `Browser closed` | Browser crashed (usually memory) | Reduce workers, check RAM, use headless |
| `net::ERR_CONNECTION_REFUSED` | Target server unreachable | Verify server is running |
| `Element is not stable` | Element moving/animating | Wait for animation to complete |

### Retry on Failure

```typescript
// playwright.config.ts
retries: 2,  // Retry failed tests up to 2 times
```

---

## 7. Resource Management

### Memory Optimization Flags (Chromium)

```typescript
launchOptions: {
  args: [
    '--disable-dev-shm-usage',    // Use /tmp instead of shared memory
    '--disable-gpu',               // Skip GPU rendering
    '--disable-extensions',        // No browser extensions
    '--disable-background-networking',
    '--no-first-run',
  ]
}
```

### Block Unnecessary Resources (Faster + Less Memory)

```typescript
// In test setup — skip images, fonts, media
await page.route('**/*.{png,jpg,jpeg,gif,svg,woff,woff2,mp4}', route => route.abort());
```

### Proper Cleanup (Prevents Memory Leaks)

```typescript
test.afterEach(async ({ context }) => {
  // Always close context to prevent memory leaks
  // Playwright does this automatically per-test, but be explicit in custom setups
  await context.close();
});
```

### Kill Orphaned Browsers (Windows)

If a test crashes and leaves browsers running:

```powershell
# Find orphaned Playwright browsers
Get-Process | Where-Object { $_.Path -match 'ms-playwright' } | Select-Object Id, ProcessName, @{N='MB';E={[math]::Round($_.WorkingSet64/1MB)}}

# Kill them
Get-Process | Where-Object { $_.Path -match 'ms-playwright' } | Stop-Process -Force
```

### Kill Orphaned Browsers (macOS/Linux)

```bash
# Find
ps aux | grep ms-playwright | grep -v grep

# Kill
pkill -f ms-playwright
```

---

## 8. Multi-Session Workflow

### Assigning Tests Across Claude Code Sessions

Each Claude Code session can independently test its area:

```
Session 1 (Auth team)       → npx playwright test tests/e2e/auth.spec.ts
Session 2 (Dashboard team)  → npx playwright test tests/e2e/dashboard.spec.ts
Session 3 (Checkout team)   → npx playwright test tests/e2e/checkout.spec.ts
Session 4 (Settings team)   → npx playwright test tests/e2e/settings.spec.ts
```

### Session Isolation Checklist

- [x] Each session runs its own `npx playwright test` process
- [x] Each gets its own browser instance (separate PID, separate memory)
- [x] No shared ports, files, or browser state
- [x] All sessions can hit the same remote URL safely
- [x] Tests that CREATE data should use unique identifiers per session

### Preventing Data Conflicts

When multiple sessions test against the same app:

```typescript
// Generate unique test data per run
const uniqueEmail = `test-${Date.now()}@example.com`;
const uniquePhone = `917${Math.floor(Math.random() * 10000000).toString().padStart(7, '0')}`;
```

---

## 9. NPM Scripts (Add to Your Project)

```json
{
  "scripts": {
    "test:e2e": "playwright test",
    "test:e2e:headed": "playwright test --headed",
    "test:e2e:debug": "playwright test --debug",
    "test:e2e:codegen": "playwright codegen",
    "test:e2e:report": "playwright show-report"
  }
}
```

---

## 10. Known Issues & Workarounds

| Issue | Impact | Workaround | Source |
|-------|--------|------------|--------|
| Chrome for Testing 20GB memory (v1.57+) | Critical | Stay on v1.56.x | [#38489](https://github.com/microsoft/playwright/issues/38489) |
| Memory leak with context reuse | Moderate | Close contexts in `afterEach` | [#6319](https://github.com/microsoft/playwright/issues/6319) |
| ~70% higher memory in v1.40.1 | Moderate | Use v1.56.1 (fixed) | [#28942](https://github.com/microsoft/playwright/issues/28942) |
| Firefox flaky input elements | Low | Use role-based selectors | [#9307](https://github.com/microsoft/playwright/issues/9307) |
| WebKit 2-3x slower execution | Low | Use Chromium/Firefox for speed | [#18119](https://github.com/microsoft/playwright/issues/18119) |
| Windows UI freezes during tests | Low | Always use headless mode | [#28261](https://github.com/microsoft/playwright/issues/28261) |
| Port not released on crash | Low | Kill orphaned processes | [#19520](https://github.com/microsoft/playwright/issues/19520) |
| `beforeAll` runs per-worker | Low | Use 1 worker per session | [Docs](https://playwright.dev/docs/test-parallel) |
| Tests pass local, fail CI | Common | Match CI resources, use retries | [#20664](https://github.com/microsoft/playwright/issues/20664) |

---

## 11. Browser-Session API Verification (CRITICAL)

### The Problem

UI-only testing (checking toasts, URL changes, element visibility) misses **65% of backend failures**. A button can show a success toast while the server returns a 500 error — the frontend might catch the error and show something, or it might silently fail.

**The fix:** After every form submission or action that hits the server, **call the API directly from the browser** using `page.evaluate(fetch(...))` — this uses the real user's session cookies and CSRF token, exactly matching how the app works in production.

### Pattern: page.evaluate(fetch(...))

```typescript
// TypeScript Playwright
const result = await page.evaluate(async () => {
  const response = await fetch('/api/frappe/api/method/hrms.api.shift_tracking.get_active_punch', {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
  });
  const text = await response.text();
  let json = null;
  try { json = JSON.parse(text); } catch {}
  return { ok: response.ok, status: response.status, json, body: text.substring(0, 2000) };
});

expect(result.ok).toBe(true);
expect(result.status).toBe(200);
expect(result.json?.message).toBeDefined();
```

```python
# Python sync_playwright
result = page.evaluate("""
    async () => {
        const response = await fetch('/api/frappe/api/method/hrms.api.shift_tracking.get_active_punch', {
            method: 'GET',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        });
        const text = await response.text();
        let json = null;
        try { json = JSON.parse(text); } catch {}
        return { ok: response.ok, status: response.status, json: json, body: text.substring(0, 2000) };
    }
""")
assert result["ok"] is True
assert result["status"] == 200
```

### Why page.evaluate, NOT Python requests?

| Approach | Auth Context | Catches Backend Bugs? | Matches Production? |
|----------|-------------|----------------------|---------------------|
| `page.evaluate(fetch(...))` | Real user session cookies | **YES** | **YES** — same auth path |
| Python `requests` with API token | Administrator/API key | Partially | NO — different user, different permissions |
| Checking toast/URL change | None | **NO** | N/A — UI only |

### Proxy URL Pattern (MANDATORY for BEI)

When testing against a Next.js frontend that proxies to a Frappe backend, **always use the proxy URL**, not the direct backend URL:

```
CORRECT:  /api/frappe/api/method/hrms.api.shift_tracking.punch_in
WRONG:    https://hq.bebang.ph/api/method/hrms.api.shift_tracking.punch_in
```

**Why:** The proxy URL uses the same cookies/CSRF the browser already has. Direct backend URLs cause CORS errors and use different auth.

### POST with Body

```typescript
const result = await page.evaluate(async (body) => {
  const response = await fetch('/api/frappe/api/method/hrms.api.shift_tracking.punch_in', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify(body),
  });
  const text = await response.text();
  let json = null;
  try { json = JSON.parse(text); } catch {}
  return { ok: response.ok, status: response.status, json, body: text.substring(0, 2000) };
}, { latitude: 14.5995, longitude: 120.9842, accuracy: 10, selfie_base64: "data:image/jpeg;base64,..." });
```

### Verify Database Record After Action

After any create/update/delete, verify the record actually exists in the database:

```typescript
const record = await page.evaluate(async (doctype) => {
  const params = new URLSearchParams({
    filters: JSON.stringify([["employee", "=", "TEST-STAFF-001"]]),
    fields: JSON.stringify(["name", "status", "punch_in_time"]),
    limit_page_length: "1",
    order_by: "creation desc",
  });
  const response = await fetch(`/api/frappe/api/resource/${doctype}?${params}`, {
    headers: { 'Accept': 'application/json' },
  });
  const data = await response.json();
  return data?.data?.[0] || null;
}, "BEI Shift Record");

expect(record).not.toBeNull();
expect(record.status).toBe("In Progress");
```

### Error Diagnosis Pattern

When the API call fails, extract the Frappe server error message:

```javascript
if (!result.ok) {
  // Frappe wraps errors in _server_messages
  const serverMsg = result.json?._server_messages;
  if (serverMsg) {
    const messages = JSON.parse(serverMsg);
    const first = typeof messages[0] === 'string' ? JSON.parse(messages[0]) : messages[0];
    console.log('Server error:', first.message);
  }
  // Also check exception field
  if (result.json?.exception) {
    console.log('Exception:', result.json.exception);
  }
}
```

---

## 12. Network Interception — Passive API Capture

### Use Case

Verify that a UI action (button click, form submit) actually triggers the expected API call, without manually calling the API yourself.

### Pattern: page.on('response')

```typescript
// TypeScript
const apiResponses: Array<{url: string, status: number, body: any}> = [];

// Set up listener BEFORE the action
page.on('response', async (response) => {
  if (response.url().includes('/api/method/hrms.api')) {
    apiResponses.push({
      url: response.url(),
      status: response.status(),
      body: await response.json().catch(() => null),
    });
  }
});

// Do the UI action
await page.getByRole('button', { name: 'Submit' }).click();

// Wait for API call to complete
await page.waitForTimeout(2000);

// Assert the API was called and succeeded
expect(apiResponses.length).toBeGreaterThan(0);
expect(apiResponses[0].status).toBe(200);
expect(apiResponses[0].body?.message?.status).toBe('success');

// Clean up listener
page.removeAllListeners('response');
```

```python
# Python sync_playwright
captured = []

def on_response(response):
    if "/api/method/hrms.api" in response.url:
        try:
            captured.append({
                "url": response.url,
                "status": response.status,
                "body": response.json(),
            })
        except:
            captured.append({"url": response.url, "status": response.status, "body": None})

page.on("response", on_response)

# Do the action
page.click("button:has-text('Submit')")
page.wait_for_timeout(2000)

assert len(captured) > 0, "Expected API call was not made"
assert captured[0]["status"] == 200

page.remove_listener("response", on_response)
```

### When to Use Interception vs Direct API Call

| Scenario | Use Interception | Use Direct API Call |
|----------|-----------------|---------------------|
| Verify button click triggers correct API | Yes | No |
| Verify API response after form fill | No | Yes (more reliable) |
| Debug what APIs the page is calling | Yes | No |
| Test API with specific parameters | No | Yes |
| Verify no unexpected API errors during navigation | Yes | No |

---

## 13. Full User Path Testing — The L1-L4 Methodology

### Test Levels

Every test should be classified by depth:

| Level | Name | What It Proves | Example |
|-------|------|----------------|---------|
| **L1** | Visual | Element exists on page | `expect(page.getByText("Dashboard")).toBeVisible()` |
| **L2** | UI State | Click → toast/URL/dialog changes | Click Submit → success toast shows |
| **L3** | API Verified | API call returns correct status + data | `page.evaluate(fetch(...))` → 200 + record data |
| **L4** | Full Round-Trip | API call + database record verified | API → 200, then query DB record exists with correct fields |

### Mandatory Minimum Levels

| Action Type | Minimum Level |
|-------------|--------------|
| Page loads, navigation | L1 |
| Button clicks (non-submit) | L2 |
| Form submissions, creates | **L4** (API + DB verify) |
| Updates, deletes | **L4** (API + DB verify) |
| Approval workflows | **L3** (API verified) |
| RBAC / permission checks | L2 |
| Validation / negative tests | **L3** (API returns error) |

### The Gold Standard Test Pattern

```
1. Login as real user          → Auth context established
2. Navigate to the page        → L1 (page loaded)
3. Fill the form               → L2 (fields accept input)
4. Set up API interceptor      → Passive capture ready
5. Click submit                → L2 (button responds)
6. Verify intercepted API call → L3 (API returned 200)
7. Verify API response data    → L3 (correct status, message)
8. Query database record       → L4 (record exists, fields match)
9. Screenshot evidence         → Audit trail
```

### Quality Score

After running all tests, calculate:

```
Quality Score = (L3 + L4 tests) / total tests × 100

≥70% = ACCEPTABLE
<70% = WEAK COVERAGE — upgrade L1/L2 tests
```

**L1-only tests that PASS should be flagged as WEAK** — they prove the page renders but NOT that the feature works.

---

## 14. Auth Context for Real User Sessions

### Why Real Users, Not API Tokens

API tokens authenticate as Administrator or a service account. This bypasses:
- Role-based access control (RBAC)
- Employee-linked data (e.g., "my punches" requires Employee record linked to user)
- Row-level permissions
- Workflow state restrictions

**Always test with the actual user role** that will use the feature in production.

### Login Pattern (Frappe + Next.js)

When the app uses a Next.js frontend proxying to Frappe, login at the Frappe backend first, then navigate to the frontend — session cookies are shared.

```typescript
// TypeScript
await page.goto('https://hq.bebang.ph/login');
await page.fill('input[name="usr"]', 'test.staff@bebang.ph');
await page.fill('input[name="pwd"]', 'BeiTest2026!');
await page.click('button[type="submit"]');
await page.waitForNavigation();

// Now navigate to the frontend — session cookies carry over
await page.goto('https://my.bebang.ph/dashboard');
```

```python
# Python
page.goto("https://hq.bebang.ph/login")
page.fill('input[name="usr"]', "test.staff@bebang.ph")
page.fill('input[name="pwd"]', "BeiTest2026!")
page.click('button[type="submit"]')
page.wait_for_load_state("networkidle")

# Session cookies are now set — navigate to frontend
page.goto("https://my.bebang.ph/dashboard")
```

### Switching Users Mid-Test

```typescript
// Logout
await page.goto('https://hq.bebang.ph/api/method/logout');
await page.waitForLoadState('networkidle');

// Login as different user
await page.goto('https://hq.bebang.ph/login');
await page.fill('input[name="usr"]', 'test.supervisor@bebang.ph');
await page.fill('input[name="pwd"]', 'BeiTest2026!');
await page.click('button[type="submit"]');
await page.waitForNavigation();
```

### Browser Context with Geolocation + Camera

For features that require GPS and camera:

```typescript
const context = await browser.newContext({
  permissions: ['camera', 'geolocation'],
  geolocation: { latitude: 14.5995, longitude: 120.9842, accuracy: 10 },
  locale: 'en-PH',
  timezoneId: 'Asia/Manila',
});
```

### Fake Camera in Headless Mode

```typescript
const browser = await chromium.launch({
  headless: true,
  args: [
    '--use-fake-device-for-media-stream',
    '--use-fake-ui-for-media-stream',
    // Optional: custom video feed instead of color bars
    '--use-file-for-fake-video-capture=test_data/camera.y4m',
  ],
});
```

---

## 15. Python sync_playwright Patterns

### Why Python?

The BEI E2E test suite uses Python (not TypeScript) because:
- Tests run as standalone scripts, not as part of a Node.js test framework
- Python integrates easily with Frappe API verification (requests library)
- Test helpers share a single `helpers.py` module

### Basic Structure

```python
from playwright.sync_api import sync_playwright, Page, expect

def run_test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=[
            '--disable-dev-shm-usage',
            '--disable-gpu',
        ])
        context = browser.new_context(
            permissions=['geolocation'],
            geolocation={'latitude': 14.5995, 'longitude': 120.9842},
        )
        page = context.new_page()

        try:
            # Login
            page.goto('https://hq.bebang.ph/login')
            page.fill('input[name="usr"]', 'test.staff@bebang.ph')
            page.fill('input[name="pwd"]', 'BeiTest2026!')
            page.click('button[type="submit"]')
            page.wait_for_load_state('networkidle')

            # Test
            page.goto('https://my.bebang.ph/dashboard')
            expect(page.locator('text=Dashboard')).to_be_visible(timeout=10000)

            # Browser-session API verification
            result = page.evaluate("""async () => {
                const r = await fetch('/api/frappe/api/method/hrms.api.shift_tracking.get_active_punch');
                const text = await r.text();
                let json = null;
                try { json = JSON.parse(text); } catch {}
                return { ok: r.ok, status: r.status, json };
            }""")
            assert result['ok'], f"API failed: {result}"

        finally:
            page.screenshot(path='scratchpad/qa/test_evidence.png')
            context.close()
            browser.close()

if __name__ == '__main__':
    run_test()
```

### Python API Call Helper

The `helpers.py` in `scratchpad/e2e_scripts/` provides reusable functions:

```python
from helpers import browser_api_call, browser_verify_record, intercept_api_calls

# Call API with browser session
result = browser_api_call(page, "POST", "/api/frappe/api/method/hrms.api.shift_tracking.punch_out", {
    "latitude": 14.5995,
    "longitude": 120.9842,
    "accuracy": 10,
})
assert result["ok"], f"Punch-out failed: {result.get('error') or result.get('body')}"

# Verify record in database
record = browser_verify_record(page, "BEI Shift Record", [
    ["employee", "=", "TEST-STAFF-001"],
    ["status", "=", "Completed"],
])
assert record is not None, "Shift record not found"
assert record.get("total_hours") is not None

# Passive API interception
with intercept_api_calls(page, ["/api/method/hrms.api"]) as interceptor:
    page.click("button:has-text('Submit')")
    page.wait_for_timeout(2000)

assert not interceptor.errors, f"API errors captured: {interceptor.errors}"
```

---

## 16. Playwright CLI vs MCP — When to Use What

| Scenario | Use CLI | Use MCP |
|----------|---------|---------|
| Running existing test suites | Yes | No |
| CI/CD pipelines | Yes | No |
| Multiple parallel sessions | Yes | Problematic ([#893](https://github.com/microsoft/playwright-mcp/issues/893)) |
| Resource-constrained machines | Yes (~700MB) | No (~1.1GB + node overhead) |
| Exploratory testing (ad-hoc clicking) | No | Yes |
| Self-healing autonomous loops | No | Yes |
| AI writing + running + fixing tests | Yes | Overkill |

**Bottom line:** Use CLI for everything except exploratory/autonomous testing where you need the AI to freely navigate and click around a live browser.

---

## 17. Integration with /test-full-cycle

When using this skill as part of the `/test-full-cycle` autonomous QA loop:

### Required Imports (Python)

```python
from helpers import (
    browser_api_call,        # PRIMARY: API calls via browser session
    browser_verify_record,   # PRIMARY: DB verification via browser session
    intercept_api_calls,     # Passive network capture
    assert_api_success,      # Convenience assertion
    TEST_SELFIE_BASE64,      # Fake selfie for headless camera bypass
    verify_frappe_record,    # SECONDARY: API-token verification (cross-check only)
    call_frappe_api,         # SECONDARY: API-token calls
)
```

### Test Result Classification

Every test must declare its level in `add_test()`:

```python
results.add_test(
    test_id="A1",
    test_name="Punch In - Happy Path",
    status="PASS",
    details="API returned 200, shift record created",
    test_level=4,  # L4: API + DB verified
    screenshot="punch_in_success.png",
)

results.add_test(
    test_id="A2",
    test_name="Dashboard loads",
    status="PASS",
    details="Dashboard page visible",
    test_level=1,  # L1: Visual only — will be flagged as WEAK
)
```

### Banned Patterns

| Pattern | Why It's Banned | Use Instead |
|---------|-----------------|-------------|
| `# MANUAL TEST REQUIRED` | Hides gaps in automation | Create `[GAP]` task with reason |
| Toast-only verification for form submit | Can't detect 500 errors | `browser_api_call()` + `browser_verify_record()` |
| Python `requests` as primary | Wrong auth context | `browser_api_call()` (browser session) |
| Skipping test silently when button is disabled | Hides missing prerequisites | Create `[GAP]` task or fix the prerequisite |
| `test_level` not specified | Defaults to L1, inflates false confidence | Always declare level explicitly |

### Report Quality Gate

After all tests run, the report includes:
- **Quality Score** = (L3 + L4 tests) / total × 100
- Tests below L3 flagged as **WEAK**
- **Minimum 70% quality score required** for the feature to be considered tested

---

## Authorization

### You ARE authorized to:
- Run `npx playwright test` with any flags
- Run `npx playwright codegen` to record new tests
- Read and parse test result JSON/HTML
- Edit test files in the test directory
- Fix source code based on test failures
- Kill orphaned browser processes
- Use `page.evaluate(fetch(...))` for browser-session API verification
- Intercept network responses via `page.on('response')`

### You MUST NOT:
- Upgrade Playwright past v1.56.x without explicit user approval
- Run more than 1 worker within a session (parallelism is across sessions)
- Modify `playwright.config.ts` without user awareness
- Leave orphaned browser processes running after completion
- Use Python `requests` as the primary API verification method (use `page.evaluate(fetch(...))` instead)
- Report a form submission test as PASS based only on UI feedback (toast, URL change) without API verification



---

## 12. BEI my.bebang.ph Patterns (S120 Lessons, 2026-03-26)

Proven patterns from 30+ real browser tests during S120 procurement testing.

### Login (CRITICAL — Use my.bebang.ph for L3 Testing)

For L3 browser tests on my.bebang.ph (the employee/procurement app):
- URL: `https://my.bebang.ph/login`
- Email field: `input[name="email"]`
- Password field: `input[name="password"]`

Do NOT use hq.bebang.ph for L3 browser tests. hq.bebang.ph is the Frappe backend — API calls go there, but browser tests go to my.bebang.ph.

```javascript
await page.goto('https://my.bebang.ph/login', { waitUntil: 'networkidle' });
await page.fill('input[name="email"]', email);
await page.fill('input[name="password"]', password);
await page.click('button[type="submit"]');
await page.waitForURL('**/dashboard**', { timeout: 30000, waitUntil: 'domcontentloaded' });
```

### Shadcn Combobox

Shadcn uses Radix Popover + Command. Interaction sequence:

1. `await page.locator('button[role="combobox"]').nth(INDEX).click()` — click trigger
2. `await page.waitForTimeout(500)` — wait for popover
3. `await page.locator('input[placeholder*="search"]').first().fill('SAGO')` — type query
4. `await page.waitForTimeout(2000)` — wait for debounce + API
5. `await page.locator('[role="option"]').nth(i).click()` — select result

Results use `[role="option"]`, NOT `[cmdk-item]`.

PR form combobox indexes: 0=Department, 1=Item search, 2=UOM.

### Toast Reading (MANDATORY after every submit/save action)

After EVERY button click that triggers a mutation (Create PR, Save price, Submit for Approval), ALWAYS read the toast within 2 seconds:

```javascript
await page.waitForTimeout(2000);
const toasts = await page.locator('[data-sonner-toast]').allTextContents();
```

### Alert/Banner — Verify Content, Not Existence

```
BAD:  await banner.count() > 0
GOOD: const text = await banner.first().textContent();
      text.includes('42.35') && text.includes('reason')
```

### Selector Discovery First

Before clicking anything on a new page, list interactive elements:

```javascript
const buttons = await page.locator('button').all();
for (const btn of buttons) console.log(await btn.textContent());
```

### Always .mjs Files

Never inline complex Playwright in bash — escaping breaks. Save as `.mjs`, run with `node`.

### Headless Only

Always `headless: true`. agent-browser may fail on Windows — use Playwright directly.

### Test Accounts

All passwords: `BeiTest2026!` — test.commissary (procurement), test.warehouse, mae (CPO), test.area (no procurement access).
