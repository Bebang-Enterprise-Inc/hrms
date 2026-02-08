import { test as base, expect, Page, BrowserContext, Browser } from "@playwright/test";
import { login, ACCOUNTS, AccountKey, PORTAL_URL } from "./helpers";
import * as path from "path";
import * as fs from "fs";

const AUTH_DIR = path.join(process.cwd(), "test-results", ".auth");

export type RoleName = "staff" | "supervisor" | "area" | "hr" | "warehouse" | "commissary";

const ROLE_TO_ACCOUNT: Record<RoleName, AccountKey> = {
  staff: "store_staff",
  supervisor: "store_supervisor",
  area: "area_supervisor",
  hr: "hq_user",
  warehouse: "warehouse",
  commissary: "commissary",
};

function authPath(role: RoleName): string {
  return path.join(AUTH_DIR, `${role}.json`);
}

/**
 * Get an authenticated page for a specific role.
 * Caches storageState to disk so login only happens once per role per run.
 */
async function getAuthenticatedPage(
  browser: Browser,
  role: RoleName
): Promise<{ context: BrowserContext; page: Page }> {
  const storagePath = authPath(role);

  // Reuse cached auth if available
  if (fs.existsSync(storagePath)) {
    const context = await browser.newContext({ storageState: storagePath });
    const page = await context.newPage();
    // Verify session is still valid
    await page.goto(`${PORTAL_URL}/dashboard`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    if (!page.url().includes("/login")) {
      return { context, page };
    }
    // Session expired, re-login below
    await context.close();
  }

  // Fresh login
  const context = await browser.newContext();
  const page = await context.newPage();
  await login(page, ROLE_TO_ACCOUNT[role]);

  // Save auth state
  fs.mkdirSync(AUTH_DIR, { recursive: true });
  await context.storageState({ path: storagePath });

  return { context, page };
}

/**
 * SharedState for passing data between tests in serial describe blocks.
 * Use for cross-role workflows (e.g., staff submits -> supervisor reviews).
 */
export const SharedState = new Map<string, string>();

/**
 * Extended test fixture with multi-role support.
 */
export const test = base.extend<{
  staffPage: Page;
  staffContext: BrowserContext;
  supervisorPage: Page;
  supervisorContext: BrowserContext;
  areaPage: Page;
  areaContext: BrowserContext;
  warehousePage: Page;
  warehouseContext: BrowserContext;
  hrPage: Page;
  hrContext: BrowserContext;
}>({
  staffPage: async ({ browser }, use) => {
    const { context, page } = await getAuthenticatedPage(browser, "staff");
    await use(page);
    await context.close();
  },
  staffContext: async ({ browser }, use) => {
    const { context, page } = await getAuthenticatedPage(browser, "staff");
    await use(context);
    await page.close();
    await context.close();
  },
  supervisorPage: async ({ browser }, use) => {
    const { context, page } = await getAuthenticatedPage(browser, "supervisor");
    await use(page);
    await context.close();
  },
  supervisorContext: async ({ browser }, use) => {
    const { context, page } = await getAuthenticatedPage(browser, "supervisor");
    await use(context);
    await page.close();
    await context.close();
  },
  areaPage: async ({ browser }, use) => {
    const { context, page } = await getAuthenticatedPage(browser, "area");
    await use(page);
    await context.close();
  },
  areaContext: async ({ browser }, use) => {
    const { context, page } = await getAuthenticatedPage(browser, "area");
    await use(context);
    await page.close();
    await context.close();
  },
  warehousePage: async ({ browser }, use) => {
    const { context, page } = await getAuthenticatedPage(browser, "warehouse");
    await use(page);
    await context.close();
  },
  warehouseContext: async ({ browser }, use) => {
    const { context, page } = await getAuthenticatedPage(browser, "warehouse");
    await use(context);
    await page.close();
    await context.close();
  },
  hrPage: async ({ browser }, use) => {
    const { context, page } = await getAuthenticatedPage(browser, "hr");
    await use(page);
    await context.close();
  },
  hrContext: async ({ browser }, use) => {
    const { context, page } = await getAuthenticatedPage(browser, "hr");
    await use(context);
    await page.close();
    await context.close();
  },
});

export { expect, getAuthenticatedPage };
export type { Page, BrowserContext, Browser };
