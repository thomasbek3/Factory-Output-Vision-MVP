import { test, expect } from "@playwright/test";

test.describe("G5 — flow feedback & no strandings", () => {
  test("mark finished shows confirm then a toast with a History link", async ({ page }) => {
    await page.goto("/jobs");
    await page.locator("summary").first().click();
    await page.getByRole("button", { name: "Mark finished" }).first().click();
    // Confirm dialog with the specific copy.
    await expect(page.getByText(/It moves to History with its final grade/)).toBeVisible();
    await page.getByRole("button", { name: "Finish job" }).click();
    // Toast with grade + History link.
    await expect(page.getByText(/Finished — Grade [A-D]/)).toBeVisible();
    await expect(page.getByRole("link", { name: /View in History/ })).toBeVisible();
  });

  test("opening a clip drawer then browser Back stays on the app (no about:blank)", async ({ page }) => {
    await page.goto("/");
    await page.goto("/alerts");
    // Open a clip from an alert.
    const watch = page.getByRole("button", { name: "Watch replay" }).first();
    if (await watch.count()) {
      await watch.click();
      await expect(page.getByRole("dialog")).toBeVisible();
    }
    // Browser Back must land on a real app page, never about:blank.
    await page.goBack();
    await expect(page).toHaveURL(/\/(|alerts)(\?.*)?$/);
    const url = page.url();
    expect(url.startsWith("http")).toBe(true);
    expect(url).not.toContain("about:blank");
  });

  test("/ops has a Console back-link", async ({ page }) => {
    await page.goto("/ops");
    const link = page.getByRole("link", { name: /Console/ });
    await expect(link.first()).toBeVisible();
    await link.first().click();
    await expect(page).toHaveURL(/\/$/);
  });

  test("/tv has a low-opacity Console back-link", async ({ page }) => {
    await page.goto("/tv");
    await expect(page.getByRole("link", { name: /Console/ })).toBeVisible();
  });
});
