/**
 * L3 S131 — Expiring batch write-off E2E
 * Batch C1A23F7 (FG006, 3 KG, expiry 2026-03-27) was created via production SE.
 * With the v15 bundle fix, it should now show on the Expiring page.
 * Test: select it → Write Off Selected → confirm → verify success toast + SE created.
 */
import { chromium } from "playwright";
import fs from "fs";

const BASE = "https://my.bebang.ph";
const OUT = "output/l3/S131";
const ARTIFACTS = `${OUT}/artifacts`;
fs.mkdirSync(ARTIFACTS, { recursive: true });

const results = [];

function record(id, status, detail) {
  results.push({ scenario: id, status, detail });
  console.log(`[${status}] ${id}: ${detail}`);
}

async function ss(page, name) {
  await page.screenshot({ path: `${ARTIFACTS}/${name}.png`, fullPage: false });
}

async function pollToast(page, maxMs = 20000) {
  for (let elapsed = 0; elapsed < maxMs; elapsed += 500) {
    await page.waitForTimeout(500);
    try {
      const t = page.locator("[data-sonner-toast]").first();
      if (await t.isVisible({ timeout: 100 }).catch(() => false)) {
        const text = (await t.textContent())?.trim() || "";
        if (text) return text;
      }
    } catch {}
  }
  return "";
}

async function login(page) {
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.locator('input[autocomplete="username"], input[name="email"]').first().fill("test.commissary@bebang.ph");
  await page.locator('input[type="password"]').first().fill("BeiTest2026!");
  await page.locator('button[type="submit"]').first().click();
  await page.waitForURL("**/dashboard**", { timeout: 30000 });
  console.log("Logged in\n");
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
  await login(page);

  // ===== STEP 1: Open Expiring Stock page =====
  console.log("=== STEP 1: Open Expiring page ===");
  await page.goto(`${BASE}/dashboard/commissary/expiring`, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(5000);
  await ss(page, "E2E_01_expiring_page");

  // Read stat cards
  const statTexts = await page.evaluate(() => {
    const cards = document.querySelectorAll('div.text-3xl');
    return Array.from(cards).map(c => c.textContent?.trim());
  });
  console.log(`  Stat cards: ${statTexts.join(", ")}`);

  // Count checkboxes
  const checkboxes = page.locator("button[role='checkbox']");
  const cbCount = await checkboxes.count();
  console.log(`  Checkboxes: ${cbCount}`);

  // Look for our test batch (C1A23F7 or FG006/COCONUT JELLY)
  const pageText = await page.locator("main").textContent().catch(() => "");
  const hasFG006 = pageText.includes("FG006") || pageText.includes("COCONUT JELLY") || pageText.includes("C1A23F7");
  console.log(`  FG006/C1A23F7 found on page: ${hasFG006}`);

  if (cbCount === 0) {
    record("EXPIRING-VISIBLE", "FAIL", `No batches shown. Stats: ${statTexts.join(", ")}. FG006 found: ${hasFG006}`);
    // Try expanding the date range
    console.log("\n  Trying 30-day filter...");
    const filterBtn = page.locator("button[role='combobox']").last();
    if (await filterBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await filterBtn.click();
      await page.waitForTimeout(500);
      const opt30 = page.locator("[role='option']:has-text('30')").first();
      if (await opt30.isVisible({ timeout: 2000 }).catch(() => false)) {
        await opt30.click();
        await page.waitForTimeout(3000);
        const newCbCount = await checkboxes.count();
        const newStatTexts = await page.evaluate(() => {
          const cards = document.querySelectorAll('div.text-3xl');
          return Array.from(cards).map(c => c.textContent?.trim());
        });
        console.log(`  After 30-day filter — checkboxes: ${newCbCount}, stats: ${newStatTexts.join(", ")}`);
        await ss(page, "E2E_01b_30day_filter");
      }
    }
  } else {
    record("EXPIRING-VISIBLE", "PASS", `${cbCount} batches with checkboxes. FG006: ${hasFG006}`);
  }

  // ===== STEP 2: Select batch and Write Off =====
  const finalCbCount = await checkboxes.count();
  if (finalCbCount > 0) {
    console.log("\n=== STEP 2: Select batch and Write Off ===");

    // Select first checkbox
    await checkboxes.nth(0).click();
    await page.waitForTimeout(500);
    await ss(page, "E2E_02_selected");

    // Verify Write Off button appears
    const woBtn = page.locator("button:has-text('Write Off Selected')").first();
    const woBtnVisible = await woBtn.isVisible({ timeout: 3000 }).catch(() => false);
    const woBtnText = woBtnVisible ? await woBtn.textContent() : "NOT FOUND";
    console.log(`  Button: "${woBtnText}"`);

    if (!woBtnVisible) {
      record("WRITE-OFF-BUTTON", "FAIL", "Write Off Selected button not visible");
    } else {
      // Capture network
      const captured = [];
      page.on("response", async (resp) => {
        if (resp.url().includes("/api/commissary") && resp.request().method() === "POST") {
          try { captured.push(await resp.json()); } catch {}
        }
      });

      // Handle confirm dialog
      page.once("dialog", async (dialog) => {
        console.log(`  Confirm: "${dialog.message()}"`);
        await dialog.accept();
      });

      // Click Write Off Selected
      await woBtn.click();

      // Poll for toast
      const toast = await pollToast(page, 25000);
      await ss(page, "E2E_03_after_writeoff");

      console.log(`  Toast: "${toast}"`);
      console.log(`  Network responses: ${captured.length}`);

      // Check results
      let result = "unknown";
      let seName = null;
      for (const c of captured) {
        const msg = c?.message || c;
        if (msg?.success && msg?.data?.name) {
          result = "success";
          seName = msg.data.name;
          break;
        } else if (msg?.error) {
          result = `error: ${msg.error.slice(0, 150)}`;
          break;
        }
      }

      console.log(`  Result: ${result}`);
      if (seName) console.log(`  Wastage SE: ${seName}`);

      const passed = result === "success" || toast.includes("written off") || toast.includes("Wastage logged");
      record("WRITE-OFF-E2E", passed ? "PASS" : "FAIL",
        passed ? `SUCCESS! SE: ${seName}. Toast: "${toast}"` : `${result}. Toast: "${toast}"`);
    }
  } else {
    record("WRITE-OFF-E2E", "FAIL", "No batches available to write off after v15 bundle fix");
  }

  // ===== SUMMARY =====
  console.log(`\n${"=".repeat(55)}`);
  console.log(`L3 EXPIRY WRITE-OFF E2E (${new Date().toISOString().split("T")[0]})`);
  console.log("=".repeat(55));
  let pass = 0, fail = 0;
  for (const r of results) {
    console.log(`[${r.status}] ${r.scenario}: ${r.detail}`);
    if (r.status === "PASS") pass++; else fail++;
  }
  console.log(`\nTotal: ${pass}/${results.length} PASS, ${fail} FAIL`);

  fs.writeFileSync(`${OUT}/expiry_e2e_results.json`, JSON.stringify(results, null, 2));

  await browser.close();
  process.exit(fail > 0 ? 1 : 0);
})();
