import { Page, expect } from "@playwright/test";
import * as path from "path";

const ASSETS_DIR = path.join(process.cwd(), "tests", "e2e", "assets");

const TEST_IMAGES = {
  photo1: path.join(ASSETS_DIR, "test-photo-1.jpg"),
  photo2: path.join(ASSETS_DIR, "test-photo-2.jpg"),
  receipt: path.join(ASSETS_DIR, "test-receipt.jpg"),
};

/**
 * Inject a photo into a PhotoCapture component via its hidden file input.
 * PhotoCapture renders: <input type="file" accept="image/*" capture="environment" class="hidden">
 *
 * @param page - Playwright page
 * @param containerSelector - CSS selector for the container holding the PhotoCapture (e.g., section, form)
 * @param nthInput - 0-based index if multiple file inputs exist in the container
 * @param imagePath - Path to test image file
 */
export async function injectPhoto(
  page: Page,
  containerSelector: string,
  nthInput: number = 0,
  imagePath: string = TEST_IMAGES.photo1
): Promise<void> {
  // Find all hidden file inputs within the container
  const fileInputs = page.locator(`${containerSelector} input[type="file"]`);
  const count = await fileInputs.count();
  if (count === 0) {
    throw new Error(`No file inputs found in "${containerSelector}"`);
  }
  const input = fileInputs.nth(Math.min(nthInput, count - 1));
  await input.setInputFiles(imagePath);
  // Wait for watermarking/validation to complete
  await page.waitForTimeout(2000);
}

/**
 * Inject a photo into a specific photo slot by its label text.
 * Finds the PhotoCapture component containing the label and injects a file.
 */
export async function injectPhotoByLabel(
  page: Page,
  label: string,
  imagePath: string = TEST_IMAGES.photo1
): Promise<void> {
  // PhotoCapture renders a label element with the photo name
  // Find the closest container that has both the label and the file input
  const labelEl = page.locator(`text="${label}"`).first();
  await labelEl.waitFor({ state: "visible", timeout: 10000 });

  // Navigate up to find the file input in the same section
  // PhotoCapture structure: div > label + (button | img) + input[type=file].hidden
  const container = labelEl.locator("xpath=ancestor::div[.//input[@type='file']]").first();
  const fileInput = container.locator("input[type='file']").first();
  await fileInput.setInputFiles(imagePath);
  await page.waitForTimeout(2000);
}

/**
 * Inject photos into all PhotoCapture slots that have a "Take Photo" button visible.
 * Returns the count of photos injected.
 */
export async function injectAllPhotos(
  page: Page,
  containerSelector: string = "main",
  imagePath: string = TEST_IMAGES.photo1
): Promise<number> {
  const fileInputs = page.locator(`${containerSelector} input[type="file"]`);
  const count = await fileInputs.count();
  for (let i = 0; i < count; i++) {
    await fileInputs.nth(i).setInputFiles(imagePath);
    await page.waitForTimeout(1500);
  }
  return count;
}

/**
 * Inject a document scan into a DocumentScanner component.
 * DocumentScanner also uses file input but may have different accept attributes.
 */
export async function injectDocument(
  page: Page,
  buttonText: string,
  imagePath: string = TEST_IMAGES.receipt
): Promise<void> {
  const scanBtn = page.locator(`button:has-text("${buttonText}")`).first();
  await scanBtn.waitFor({ state: "visible", timeout: 10000 });
  // Click the scan button to trigger the file dialog
  // The DocumentScanner component has a hidden input[type="file"]
  const container = scanBtn.locator("xpath=ancestor::div[.//input[@type='file']]").first();
  const fileInput = container.locator("input[type='file']").first();
  await fileInput.setInputFiles(imagePath);
  await page.waitForTimeout(2000);
}

/**
 * Verify a photo was uploaded by checking for a preview image or thumbnail.
 */
export async function verifyPhotoUploaded(
  page: Page,
  containerSelector: string,
  nthPhoto: number = 0
): Promise<boolean> {
  // After upload, PhotoCapture shows an img preview or canvas
  const previews = page.locator(`${containerSelector} img[src^="data:"], ${containerSelector} img[src^="blob:"]`);
  const count = await previews.count();
  return count > nthPhoto;
}

/**
 * Count how many photo slots have been filled vs total.
 */
export async function countPhotos(
  page: Page,
  containerSelector: string = "main"
): Promise<{ filled: number; total: number }> {
  const allInputs = page.locator(`${containerSelector} input[type="file"]`);
  const total = await allInputs.count();

  // Filled = has a preview image nearby
  const previews = page.locator(`${containerSelector} img[src^="data:"], ${containerSelector} img[src^="blob:"]`);
  const filled = await previews.count();

  return { filled, total };
}

export { TEST_IMAGES };
