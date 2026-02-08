import { Page, Locator, expect } from "@playwright/test";

/**
 * Fill a text input field found by its label.
 */
export async function fillField(
  page: Page,
  label: string,
  value: string
): Promise<void> {
  const input = page.getByLabel(label, { exact: false }).first();
  await input.waitFor({ state: "visible", timeout: 10000 });
  await input.clear();
  await input.fill(value);
}

/**
 * Fill a number input by its ID.
 */
export async function fillNumberById(
  page: Page,
  id: string,
  value: number
): Promise<void> {
  const input = page.locator(`input#${id}`);
  await input.waitFor({ state: "visible", timeout: 10000 });
  await input.clear();
  await input.fill(value.toString());
}

/**
 * Select an option from a Shadcn Select (combobox) component.
 * Clicks the trigger, types to filter, then selects the matching option.
 */
export async function selectOption(
  page: Page,
  label: string,
  optionText: string
): Promise<void> {
  // Find the select trigger near the label
  const labelEl = page.locator(`text="${label}"`).first();
  const trigger = labelEl
    .locator("xpath=ancestor::div[.//button[@role='combobox']]")
    .locator("button[role='combobox']")
    .first();

  await trigger.waitFor({ state: "visible", timeout: 10000 });
  await trigger.click();
  await page.waitForTimeout(500);

  // Type to filter if the popover has a search input
  const searchInput = page.locator("[role='listbox'] input, [cmdk-input]").first();
  if (await searchInput.isVisible({ timeout: 1000 }).catch(() => false)) {
    await searchInput.fill(optionText);
    await page.waitForTimeout(500);
  }

  // Click the matching option
  const option = page.locator(`[role="option"]:has-text("${optionText}")`).first();
  await option.waitFor({ state: "visible", timeout: 5000 });
  await option.click();
  await page.waitForTimeout(300);
}

/**
 * Select a store from the store selector dropdown.
 * Store selectors use SelectTrigger + SelectValue pattern.
 */
export async function selectStore(
  page: Page,
  storeName?: string
): Promise<void> {
  // Click the store select trigger (gracefully skip if not visible - store may be pre-selected)
  const trigger = page.locator("button[role='combobox']").first();
  const isVisible = await trigger.isVisible({ timeout: 5000 }).catch(() => false);
  if (!isVisible) {
    return; // Store selector not present - likely pre-selected
  }
  await trigger.click();
  await page.waitForTimeout(500);

  if (storeName) {
    const option = page.locator(`[role="option"]:has-text("${storeName}")`).first();
    await option.click();
  } else {
    // Select first available store
    const firstOption = page.locator("[role='option']").first();
    if (await firstOption.isVisible({ timeout: 3000 }).catch(() => false)) {
      await firstOption.click();
    }
  }
  await page.waitForTimeout(300);
}

/**
 * Toggle a checkbox by its label text or ID.
 */
export async function toggleCheckbox(
  page: Page,
  labelOrId: string
): Promise<void> {
  // Try by ID first
  let checkbox = page.locator(`button[role="checkbox"]#${labelOrId}`);
  if (await checkbox.count() === 0) {
    // Try finding by label text
    const label = page.locator(`label:has-text("${labelOrId}")`).first();
    const htmlFor = await label.getAttribute("for");
    if (htmlFor) {
      checkbox = page.locator(`#${htmlFor}`);
    } else {
      checkbox = label.locator("xpath=preceding-sibling::button[@role='checkbox'] | following-sibling::button[@role='checkbox'] | ../button[@role='checkbox']").first();
    }
  }
  await checkbox.waitFor({ state: "visible", timeout: 5000 });
  await checkbox.click();
}

/**
 * Check all checkboxes in a container (for checklist forms).
 * Returns the number of checkboxes toggled.
 */
export async function checkAllCheckboxes(
  page: Page,
  containerSelector: string = "main"
): Promise<number> {
  const checkboxes = page.locator(`${containerSelector} button[role="checkbox"][data-state="unchecked"]`);
  const count = await checkboxes.count();
  for (let i = 0; i < count; i++) {
    await checkboxes.nth(0).click(); // Always nth(0) since checked ones change selector
    await page.waitForTimeout(200);
  }
  return count;
}

/**
 * Fill a denomination grid for cash counting.
 * Grid has inputs for each denomination (1000, 500, 200, 100, 50, 20, 10, 5, 1, 0.25).
 * Input IDs follow pattern: {prefix}_{denomination} e.g., "pcf_1000", "del_500"
 */
export async function fillDenominationGrid(
  page: Page,
  prefix: string,
  amounts: Record<string, number>
): Promise<void> {
  for (const [denom, qty] of Object.entries(amounts)) {
    const inputId = `${prefix}_${denom}`;
    const input = page.locator(`input#${inputId}, input[name="${inputId}"]`).first();
    if (await input.isVisible({ timeout: 2000 }).catch(() => false)) {
      await input.clear();
      await input.fill(qty.toString());
    }
  }
}

/**
 * Fill an inventory spot check row.
 * @param page - Playwright page
 * @param itemName - Display name of the inventory item
 * @param expected - Expected quantity
 * @param actual - Actual counted quantity
 */
export async function fillInventoryRow(
  page: Page,
  itemName: string,
  expected: number,
  actual: number
): Promise<void> {
  const row = page.locator(`text="${itemName}"`).first()
    .locator("xpath=ancestor::div[contains(@class, 'grid')]");

  const expectedInput = row.locator("input[placeholder='Expected']").first();
  const actualInput = row.locator("input[placeholder='Actual']").first();

  if (await expectedInput.isVisible({ timeout: 2000 }).catch(() => false)) {
    await expectedInput.clear();
    await expectedInput.fill(expected.toString());
  }
  if (await actualInput.isVisible({ timeout: 2000 }).catch(() => false)) {
    await actualInput.clear();
    await actualInput.fill(actual.toString());
  }
}

/**
 * Click the submit button and wait for success.
 */
export async function submitForm(
  page: Page,
  buttonText: string = "Submit"
): Promise<void> {
  const btn = page.locator(`button:has-text("${buttonText}")`).first();
  await btn.waitFor({ state: "visible", timeout: 10000 });
  await expect(btn).toBeEnabled({ timeout: 10000 });
  await btn.click();
  await page.waitForTimeout(2000);
}

/**
 * Wait for a toast notification (Sonner).
 * @returns The toast text content.
 */
export async function waitForToast(
  page: Page,
  type: "success" | "error" | "info" = "success",
  timeout: number = 15000
): Promise<string> {
  const toast = page.locator(`[data-sonner-toast][data-type="${type}"]`).first();
  await toast.waitFor({ state: "visible", timeout });
  const text = await toast.textContent() || "";
  return text;
}

/**
 * Check if a toast appeared (non-blocking).
 */
export async function hasToast(
  page: Page,
  type: "success" | "error" = "success",
  timeout: number = 5000
): Promise<boolean> {
  const toast = page.locator(`[data-sonner-toast][data-type="${type}"]`).first();
  return toast.isVisible({ timeout }).catch(() => false);
}

/**
 * Wait for the page to finish loading (network idle + no skeletons).
 */
export async function waitForPageReady(
  page: Page,
  timeout: number = 15000
): Promise<void> {
  await page.waitForLoadState("domcontentloaded", { timeout });
  // Wait for skeletons to disappear
  const skeletons = page.locator("[class*='skeleton'], [data-skeleton]");
  if (await skeletons.count() > 0) {
    await skeletons.first().waitFor({ state: "hidden", timeout: 10000 }).catch(() => {});
  }
}

/**
 * Get the progress percentage from a progress bar.
 */
export async function getProgress(page: Page): Promise<number> {
  const progressBar = page.locator("[role='progressbar']").first();
  const value = await progressBar.getAttribute("aria-valuenow");
  return value ? parseInt(value, 10) : 0;
}

/**
 * Fill a textarea by its ID.
 */
export async function fillTextarea(
  page: Page,
  id: string,
  value: string
): Promise<void> {
  const textarea = page.locator(`textarea#${id}`);
  await textarea.waitFor({ state: "visible", timeout: 10000 });
  await textarea.clear();
  await textarea.fill(value);
}

/**
 * Click a switch/toggle by its ID.
 */
export async function toggleSwitch(
  page: Page,
  id: string
): Promise<void> {
  const switchEl = page.locator(`button[role="switch"]#${id}`);
  await switchEl.waitFor({ state: "visible", timeout: 5000 });
  await switchEl.click();
}
