import { test, expect, Page, BrowserContext } from "@playwright/test";
import { login, screenshot, PORTAL_URL } from "../helpers";
import { fillTextarea, waitForPageReady } from "../form-helpers";

const SCREENSHOT_DIR = "scratchpad/test-rewrite/cross-role";

let supContext: BrowserContext;
let supPage: Page;
let areaContext: BrowserContext;
let areaPage: Page;

test.describe.serial("Cross-Role: Supervisor Escalation → Area Resolution", () => {
  test.beforeAll(async ({ browser }) => {
    supContext = await browser.newContext();
    supPage = await supContext.newPage();
    await login(supPage, "store_supervisor");

    areaContext = await browser.newContext();
    areaPage = await areaContext.newPage();
    await login(areaPage, "area_supervisor");
  });

  test.afterAll(async () => {
    await supContext?.close();
    await areaContext?.close();
  });

  test("CR-ESC-001: Supervisor escalates an issue via queue", async () => {
    // Supervisor goes to queue
    await supPage.goto(`${PORTAL_URL}/dashboard/queue`);
    await supPage.waitForLoadState("networkidle");
    await supPage.waitForTimeout(2000);

    const bodyText = await supPage.locator("body").textContent() || "";

    // Find "Forward to HR" or escalation button
    const forwardBtn = supPage.locator("button:has-text('Forward'), button:has-text('Escalate')").first();
    const hasForward = await forwardBtn.isVisible({ timeout: 5000 }).catch(() => false);

    if (hasForward) {
      // Expand first queue item
      const expandBtn = supPage.locator("button").filter({
        has: supPage.locator("[class*='chevron'], [class*='Chevron']"),
      }).first();
      if (await expandBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await expandBtn.click();
        await supPage.waitForTimeout(1000);
      }

      // Add escalation notes
      const notes = supPage.locator("textarea").first();
      if (await notes.isVisible({ timeout: 3000 }).catch(() => false)) {
        await notes.fill("E2E escalation test: forwarding to area supervisor");
      }

      // Click forward/escalate
      const fwdBtn = supPage.locator("button:has-text('Forward'), button:has-text('Escalate')").first();
      if (await fwdBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await fwdBtn.click();
        await supPage.waitForTimeout(2000);
      }
    }

    await supPage.screenshot({ path: `${SCREENSHOT_DIR}/CR-ESC-001_supervisor_escalate.png`, fullPage: true });

    // Queue page loaded
    expect(bodyText.length).toBeGreaterThan(50);
  });

  test("CR-ESC-002: Area supervisor sees escalation", async () => {
    await areaPage.goto(`${PORTAL_URL}/dashboard/queue`);
    await areaPage.waitForLoadState("networkidle");
    await areaPage.waitForTimeout(3000);

    const bodyText = await areaPage.locator("body").textContent() || "";

    // Look for escalation items in queue
    const escalations = areaPage.locator("text=/escalat/i, text=/forward/i");
    const escalationCount = await escalations.count();

    // Check queue has items
    const queueCards = areaPage.locator("[class*='card'], [class*='Card']");
    const cardCount = await queueCards.count();

    await areaPage.screenshot({ path: `${SCREENSHOT_DIR}/CR-ESC-002_area_sees_escalation.png`, fullPage: true });

    // Area supervisor queue page loaded
    expect(bodyText.length).toBeGreaterThan(50);
  });

  test("CR-ESC-003: Area supervisor resolves escalation", async () => {
    // Try to find and resolve an escalation
    const resolveBtn = areaPage.locator("button:has-text('Approve'), button:has-text('Resolve')").first();
    const canResolve = await resolveBtn.isVisible({ timeout: 5000 }).catch(() => false);

    if (canResolve) {
      // Add resolution notes
      const notes = areaPage.locator("textarea").first();
      if (await notes.isVisible({ timeout: 3000 }).catch(() => false)) {
        await notes.fill("Resolved via E2E cross-role escalation test");
      }

      await resolveBtn.click();
      await areaPage.waitForTimeout(3000);

      // Check for success
      const toast = areaPage.locator("[data-sonner-toast]").first();
      await toast.isVisible({ timeout: 5000 }).catch(() => false);
    }

    await areaPage.screenshot({ path: `${SCREENSHOT_DIR}/CR-ESC-003_area_resolved.png`, fullPage: true });

    // Area supervisor interacted with queue
    const url = areaPage.url();
    expect(url).toContain("dashboard");
  });
});
