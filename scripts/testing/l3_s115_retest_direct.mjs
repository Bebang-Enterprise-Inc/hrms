/**
 * L3-01/02 retest: direct URL navigation to confirm wizard works.
 * The landing card mis-links to /review-output (S113 defect).
 */
import { chromium } from "playwright";
import { writeFileSync, mkdirSync } from "fs";
import { join } from "path";

const BASE = "https://my.bebang.ph";
const OUT = join(process.cwd(), "output", "l3", "S115", "artifacts");
mkdirSync(OUT, { recursive: true });

async function run() {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 }, ignoreHTTPSErrors: true });
  const page = await ctx.newPage();

  // Capture API calls
  const apiCalls = [];
  page.on("response", async (r) => {
    if (r.url().includes("/api/") && (r.url().includes("readiness") || r.url().includes("blocker"))) {
      let body = ""; try { body = await r.text(); } catch {}
      apiCalls.push({ url: r.url(), status: r.status(), body });
    }
  });

  // Login
  console.log("Login...");
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(2000);
  await page.locator('input[autocomplete="username"], input[name="email"], input[type="email"]').first().pressSequentially("test.hr@bebang.ph", { delay: 30 });
  await page.locator('input[type="password"]').first().pressSequentially("BeiTest2026!", { delay: 30 });
  await page.locator('button[type="submit"]').first().click();
  await page.waitForURL("**/dashboard**", { timeout: 30000 });
  console.log("Logged in");

  // ── L3-01 RETEST: direct URL ──
  console.log("\n━━━ L3-01 RETEST: Direct URL /processing ━━━");
  await page.goto(`${BASE}/dashboard/hr/payroll/processing`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(5000);
  await page.screenshot({ path: join(OUT, "RETEST_01_processing_direct.png"), fullPage: true });

  const body = await page.innerText("body");
  const steps = ["Select Period", "Readiness Check", "Generate Slips", "Review Output", "Submit Slips", "Bank File"];
  const found = steps.filter(s => body.includes(s) || body.includes(s.split(" ")[0]));
  console.log(`Step labels found: ${found.length}/6: ${found.join(", ")}`);
  console.log(`URL: ${page.url()}`);

  // Verify date picker
  const datePicker = page.locator('button:has-text("Mar"), [class*="calendar"], [class*="date"]');
  const dpCount = await datePicker.count();
  console.log(`Date picker elements: ${dpCount}`);

  // ── L3-02 RETEST: interact with date picker, click Next ──
  console.log("\n━━━ L3-02 RETEST: Interact with date picker → click Next ━━━");

  // Look for date-related buttons and click to interact
  if (dpCount > 0) {
    await datePicker.first().click();
    await page.waitForTimeout(1000);
    await page.screenshot({ path: join(OUT, "RETEST_02a_datepicker_open.png") });
    console.log("Opened date picker");

    // Try a preset or just close
    const preset = page.locator('button:has-text("This Month"), button:has-text("Last")').first();
    if (await preset.isVisible().catch(() => false)) {
      await preset.click();
      console.log("Selected preset");
      await page.waitForTimeout(1000);
    } else {
      await page.keyboard.press("Escape");
    }
  }

  // Click Next
  const nextBtn = page.locator('button:has-text("Next")').first();
  console.log(`Next button visible: ${await nextBtn.isVisible().catch(() => false)}`);

  if (await nextBtn.isVisible()) {
    console.log("Clicking Next...");
    await nextBtn.click();
    await page.waitForTimeout(8000);
    await page.screenshot({ path: join(OUT, "RETEST_02b_step2.png"), fullPage: true });

    const step2 = await page.innerText("body");
    const checks = {
      "Blockers heading": step2.includes("Blocker") || step2.includes("Must Be Resolved"),
      "Payroll Payable": step2.includes("Payroll Payable"),
      "Salary Structure": step2.includes("Salary Structure"),
      "Owner info": step2.includes("Finance Team") || step2.includes("HR Team"),
      "Employee table": step2.includes("Employee") && (step2.includes("Ready") || step2.includes("Blocked")),
    };

    for (const [name, passed] of Object.entries(checks)) {
      console.log(`  ${passed ? "✓" : "✗"} ${name}`);
    }

    console.log(`\nAPI calls captured: ${apiCalls.length}`);
    for (const c of apiCalls) {
      console.log(`  ${c.status} ${c.url.split("method/")[1] || c.url}`);
      try {
        const msg = JSON.parse(c.body).message;
        if (msg.is_ready !== undefined) console.log(`    is_ready: ${msg.is_ready}, blockers: ${msg.blockers?.length}`);
        if (msg.blocked_count !== undefined) console.log(`    blocked: ${msg.blocked_count}, ready: ${msg.ready_count}, total: ${msg.total_employees}`);
      } catch {}
    }

    // ── L3-03: Verify blocked ──
    console.log("\n━━━ L3-03: Verify Next is disabled ━━━");
    const nextBtn2 = page.locator('button:has-text("Next")').first();
    const disabled = await nextBtn2.isDisabled();
    console.log(`Next disabled: ${disabled}`);

    if (disabled) {
      // Force click
      try { await nextBtn2.click({ force: true }); } catch {}
      await page.waitForTimeout(1000);
      const stillStep2 = (await page.innerText("body")).includes("Readiness") || (await page.innerText("body")).includes("Blocker");
      console.log(`After force-click, still on Step 2: ${stillStep2}`);
      await page.screenshot({ path: join(OUT, "RETEST_03_force_click.png"), fullPage: true });
    }

    // Scroll to see employee table
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(1000);
    await page.screenshot({ path: join(OUT, "RETEST_02c_scrolled.png"), fullPage: true });
  }

  // ── Check landing card links ──
  console.log("\n━━━ COLLATERAL: Check what Processing card links to ━━━");
  await page.goto(`${BASE}/dashboard/hr/payroll`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(3000);

  const allLinks = await page.locator("a").evaluateAll(links =>
    links.map(l => ({ text: l.innerText.trim().substring(0, 50), href: l.href }))
      .filter(l => l.href.includes("payroll"))
  );
  console.log("Payroll landing links:");
  for (const l of allLinks) console.log(`  "${l.text}" → ${l.href}`);

  await browser.close();
  console.log("\nDone.");
}

run().catch(e => { console.error("FATAL:", e); process.exit(1); });
