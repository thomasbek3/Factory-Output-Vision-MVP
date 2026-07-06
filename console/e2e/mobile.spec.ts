import { test, expect } from "@playwright/test";

test.use({ viewport: { width: 390, height: 844 } });

test.describe("G4 — mobile owner layout (390px)", () => {
  test("rail is hidden and hamburger owns nav", async ({ page }) => {
    await page.goto("/");
    // The fixed rail (aside) is hidden below lg.
    await expect(page.locator("aside")).toBeHidden();
    // Hamburger opens the mobile nav and reaches every tab.
    await page.getByRole("button", { name: "Open navigation" }).click();
    const nav = page.getByRole("dialog", { name: "Navigation" });
    await expect(nav).toBeVisible();
    for (const label of ["Live", "Replay", "Jobs", "Stations", "History", "Alerts", "Settings"]) {
      await expect(nav.getByRole("link", { name: label })).toBeVisible();
    }
    // Navigate via the sheet.
    await nav.getByRole("link", { name: "Jobs" }).click();
    await expect(page).toHaveURL(/\/jobs$/);
  });

  for (const path of ["/", "/jobs", "/replay"]) {
    test(`no horizontal scroll at 390px on ${path}`, async ({ page }) => {
      await page.goto(path);
      await page.waitForTimeout(500);
      const overflow = await page.evaluate(() => {
        const doc = document.documentElement;
        return { scrollWidth: doc.scrollWidth, clientWidth: doc.clientWidth };
      });
      // Allow 1px rounding slop.
      expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth + 1);
    });
  }
});
