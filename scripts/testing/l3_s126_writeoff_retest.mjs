/**
 * L3 S126 Write-Off Retest — verify batch bundle fix works
 * Tests S126-09 only: select expired batches, click Write Off Selected, verify toast + state change
 */
import { chromium } from "playwright";
import fs from "fs";

const BASE = "https://my.bebang.ph";
const OUT = "output/l3/S126";
const EVIDENCE = `${OUT}/evidence`;
const ARTIFACTS = `${OUT}/artifacts`;

for (const d of [OUT, EVIDENCE, ARTIFACTS]) {
  fs.mkdirSync(d, { recursive: true });
}

const formSubmissions = [];
const stateVerifications = [];
const results = [];

function record(id, status, detail) {
  results.push({ scenario: id, status, detail });
  console.log(`[${status}] ${id}: ${detail}`);
}

async function screenshot(page, name) {
  const p = `${ARTIFACTS}/${name}.png`;
  await page.screenshot({ path: p, fullPage: false });
  return p;
}

async function waitForToast(page, timeoutMs = 15000) {
  try {
    const toast = await page.waitForSelector("[data-sonner-toast]", { timeout: timeoutMs });
    await page.waitForTimeout(1000);
    const text = await toast.textContent();
    return text?.trim() || "";
  } catch { return ""; }
}

async function login(page) {
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.locator('input[autocomplete="username"], input[name="email"]').first().fill("test.commissary@bebang.ph");
  await page.locator('input[type="password"]').first().fill("BeiTest2026!");
  await page.locator('button[type="submit"]').first().click();
  await page.waitForURL("**/dashboard**", { timeout: 30000 });
  console.log("Logged in");
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();

  await login(page);

  // ===================== S126-09: Bulk Expiry Write-Off =====================
  await page.goto(`${BASE}/dashboard/commissary/expiring`, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(5000);
  await screenshot(page, "WO_01_page_loaded");

  // Read current counts from the page
  const criticalText = await page.locator("text=Critical").first().textContent().catch(() => "");
  console.log(`Page loaded. Critical section: "${criticalText}"`);

  // Count checkboxes
  const checkboxes = page.locator("button[role='checkbox']");
  const cbCount = await checkboxes.count();
  console.log(`Checkboxes found: ${cbCount}`);

  if (cbCount === 0) {
    record("S126-09-WO", "FAIL", "No checkboxes found on expiring page");
  } else {
    // Select first 2 batches
    const toSelect = Math.min(cbCount, 2);
    for (let i = 0; i < toSelect; i++) {
      await checkboxes.nth(i).click();
      await page.waitForTimeout(500);
    }

    // Verify "Write Off Selected" button appears
    await page.waitForTimeout(1000);
    await screenshot(page, "WO_02_selected");

    const woBtn = page.locator("button:has-text('Write Off Selected')").first();
    const woBtnVisible = await woBtn.isVisible({ timeout: 3000 }).catch(() => false);
    const woBtnText = woBtnVisible ? await woBtn.textContent() : "NOT FOUND";
    console.log(`Write Off button: "${woBtnText}"`);

    if (!woBtnVisible) {
      record("S126-09-WO", "FAIL", `Write Off button not visible after selecting ${toSelect} checkboxes`);
    } else {
      // Set up network capture
      const captured = [];
      page.on("response", async (resp) => {
        if (resp.url().includes("/api/commissary") && resp.request().method() === "POST") {
          try {
            const body = await resp.json();
            captured.push({ status: resp.status(), body });
          } catch {}
        }
      });

      // Handle confirm dialog
      page.once("dialog", async (dialog) => {
        const msg = dialog.message();
        console.log(`Confirm dialog: "${msg}"`);
        stateVerifications.push({
          scenario: "S126-09-WO", check: "Confirm dialog text",
          expected: "Write off N batches", actual: msg, method: "textContent()", passed: msg.includes("Write off")
        });
        await dialog.accept();
      });

      // Click Write Off Selected
      await woBtn.click();

      // Wait for sequential wastage calls (each batch processed one by one)
      console.log("Waiting for wastage processing...");
      await page.waitForTimeout(25000);

      // Try to capture toast
      const toastText = await waitForToast(page);
      await screenshot(page, "WO_03_after_writeoff");
      console.log(`Toast: "${toastText}"`);
      console.log(`Network captures: ${captured.length}`);

      // Check captures for success/failure
      let successCaptures = 0;
      let failCaptures = 0;
      for (const c of captured) {
        const body = c.body;
        if (body?.message?.success || body?.success) {
          successCaptures++;
          console.log(`  SUCCESS: ${JSON.stringify(body?.message?.data?.name || body?.data?.name || "?")}`);
        } else if (body?.message?.error || body?.exc) {
          failCaptures++;
          const err = body?.message?.error || body?.exc_type || "unknown";
          console.log(`  FAIL: ${err}`);
        }
      }

      const toastGood = toastText.includes("written off") || toastText.includes("batch");
      const networkGood = successCaptures > 0;
      const passed = toastGood || networkGood;

      stateVerifications.push({
        scenario: "S126-09-WO", check: "Write-off result",
        expected: "success toast or network success",
        actual: `toast="${toastText}", captures=${captured.length}, success=${successCaptures}, fail=${failCaptures}`,
        method: "textContent()+network", passed
      });

      formSubmissions.push({
        scenario_id: "S126-09-WO", form: "bulk_expiry_writeoff",
        submit_method: "browser_click",
        submit_button_selector: "button:has-text('Write Off Selected')",
        inputs: [{ field: "selected_count", value: String(toSelect) }],
        response: toastText, network_captured: captured.length > 0,
        network_details: captured.map(c => ({
          status: c.status,
          success: !!(c.body?.message?.success || c.body?.success),
          error: c.body?.message?.error || c.body?.exc_type || null
        }))
      });

      record("S126-09-WO", passed ? "PASS" : "FAIL",
        `Toast: "${toastText}", Network: ${successCaptures} success / ${failCaptures} fail / ${captured.length} total`);

      // If still failing, capture what the error is
      if (!passed && captured.length > 0) {
        console.log("\n=== DETAILED ERROR DUMP ===");
        for (const c of captured) {
          console.log(JSON.stringify(c.body, null, 2)?.slice(0, 1000));
        }
      }
    }
  }

  // Write evidence
  const existingFS = JSON.parse(fs.readFileSync(`${OUT}/form_submissions.json`, "utf8").catch?.(() => "[]") || "[]");
  const existingSV = JSON.parse(fs.readFileSync(`${OUT}/state_verification.json`, "utf8").catch?.(() => "[]") || "[]");

  // Overwrite with fresh data for this focused test
  fs.writeFileSync(`${OUT}/writeoff_retest_form_submissions.json`, JSON.stringify(formSubmissions, null, 2));
  fs.writeFileSync(`${OUT}/writeoff_retest_state_verification.json`, JSON.stringify(stateVerifications, null, 2));
  fs.writeFileSync(`${OUT}/writeoff_retest_results.json`, JSON.stringify(results, null, 2));

  console.log("\n=== SUMMARY ===");
  for (const r of results) {
    console.log(`[${r.status}] ${r.scenario}: ${r.detail}`);
  }

  await browser.close();
  process.exit(results.some(r => r.status === "FAIL") ? 1 : 0);
})();
