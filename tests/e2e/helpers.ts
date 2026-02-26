import { Page, expect } from "@playwright/test";

const DEFAULT_HQ_URL = "https://hq.bebang.ph";
const DEFAULT_PORTAL_URL = "https://my.bebang.ph";

export const HQ_URL = process.env.HQ_URL || process.env.TEST_HQ_URL || DEFAULT_HQ_URL;
export const PORTAL_URL = process.env.PORTAL_URL || process.env.TEST_PORTAL_URL || DEFAULT_PORTAL_URL;
export const SCREENSHOT_DIR = process.env.E2E_SCREENSHOT_DIR || "scratchpad/e2e_run2_2026-02-08";

export const ACCOUNTS = {
  hq_user: { email: "test.hr@bebang.ph", password: "BeiTest2026!" },
  store_staff: { email: "test.staff@bebang.ph", password: "BeiTest2026!" },
  store_supervisor: { email: "test.supervisor@bebang.ph", password: "BeiTest2026!" },
  area_supervisor: { email: "test.area@bebang.ph", password: "BeiTest2026!" },
  warehouse: { email: "test.warehouse@bebang.ph", password: "BeiTest2026!" },
  commissary: { email: "test.commissary@bebang.ph", password: "BeiTest2026!" },
} as const;

export type AccountKey = keyof typeof ACCOUNTS;

/**
 * Check if session is still valid. If redirected to /login, re-authenticate.
 * Use this in beforeEach hooks to prevent session-expiry cascades.
 */
export async function ensureLoggedIn(page: Page, account: AccountKey) {
  const url = page.url();
  if (url.includes("/login") || url === "about:blank") {
    await login(page, account);
  } else {
    // Quick check: navigate to dashboard and see if we get redirected to login
    const response = await page.request.get(`${PORTAL_URL}/api/auth/session`, {
      failOnStatusCode: false,
    }).catch(() => null);
    if (!response || response.status() === 401 || response.status() === 403) {
      await login(page, account);
    }
  }
}

/**
 * Login via my.bebang.ph UI login form.
 * Uses the actual form to ensure proper session cookies are set in the browser.
 */
export async function login(page: Page, account: AccountKey) {
  const { email, password } = ACCOUNTS[account];

  // Navigate to login page
  await page.goto(`${PORTAL_URL}/login`);
  await page.waitForLoadState("networkidle");

  // Fill login form - the input has placeholder "Administrator or you@company.com"
  const emailInput = page.locator('input[autocomplete="username"]').first();
  const passwordInput = page.locator('input[autocomplete="current-password"]').first();

  await emailInput.waitFor({ state: "visible", timeout: 10000 });
  await emailInput.fill(email);
  await passwordInput.fill(password);

  // Click Sign in (type="submit" button)
  await page.locator('button[type="submit"]:has-text("Sign in")').click();

  // Wait for redirect to dashboard
  await page.waitForURL(/dashboard/, { timeout: 30000 }).catch(() => {});

  // If still on login page, try API approach + manual cookie injection
  if (page.url().includes("/login")) {
    const loginResp = await page.request.post(`${PORTAL_URL}/api/auth/login`, {
      data: { usr: email, pwd: password },
      headers: { "Content-Type": "application/json" },
    });

    // Extract cookies from the API response and inject into browser context
    const respHeaders = loginResp.headersArray().filter(h => h.name.toLowerCase() === "set-cookie");
    for (const h of respHeaders) {
      const parts = h.value.split(";")[0].split("=");
      if (parts.length >= 2) {
        const cookieName = parts[0].trim();
        const cookieValue = parts.slice(1).join("=").trim();
        if (cookieName && cookieValue && cookieValue !== "Guest") {
          await page.context().addCookies([
            { name: cookieName, value: cookieValue, domain: "my.bebang.ph", path: "/" },
          ]);
        }
      }
    }

    await page.goto(`${PORTAL_URL}/dashboard`);
    await page.waitForLoadState("networkidle");
  }
}

/**
 * Take a screenshot and save to the appropriate flow directory.
 */
export async function screenshot(page: Page, flow: string, name: string) {
  await page.screenshot({
    path: `${SCREENSHOT_DIR}/${flow}/${name}.png`,
    fullPage: true,
  });
}

/** API token for read-only data fetches - loaded from environment */
const FRAPPE_TOKEN = process.env.FRAPPE_TOKEN || `token ${process.env.FRAPPE_API_KEY || ""}:${process.env.FRAPPE_API_SECRET || ""}`;

/**
 * Frappe API call helper. Uses token auth for reliable access.
 */
export async function frappeApi(
  page: Page,
  endpoint: string,
  params?: Record<string, string>
) {
  const url = new URL(`${HQ_URL}/api/method/${endpoint}`);
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  }
  const response = await page.request.get(url.toString(), {
    headers: { "Authorization": FRAPPE_TOKEN },
  });
  return response.json();
}

/**
 * Frappe API POST helper with token auth.
 */
export async function frappeApiPost(
  page: Page,
  endpoint: string,
  data?: Record<string, unknown>
) {
  const url = `${HQ_URL}/api/method/${endpoint}`;
  const response = await page.request.post(url, {
    data,
    headers: {
      "Authorization": FRAPPE_TOKEN,
      "Content-Type": "application/json",
    },
  });
  return response.json();
}
