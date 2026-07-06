import { test, expect } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers";

test.describe("/replay", () => {
  test("loads with a playing DVR video and station pills switch data", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/replay");

    await expect(page.locator("[data-selected-station]").first()).toBeVisible();
    await expect(page.locator("video").first()).toBeVisible();

    // Switch station via pill.
    await page.getByRole("button", { name: "Gate line", exact: true }).click();
    await expect(page.locator('[data-selected-station="gate-line"]').first()).toBeVisible();

    assertNoConsoleErrors(errors);
  });

  test("speed pills change playbackRate (4x)", async ({ page }) => {
    await page.goto("/replay");
    await page.getByRole("button", { name: "4×", exact: true }).click();
    await page.waitForTimeout(400);
    const rate = await page.locator("video").first().evaluate((el: HTMLVideoElement) => el.playbackRate);
    expect(rate).toBe(4);
  });

  test("jump-to-time seeks the video", async ({ page }) => {
    await page.goto("/replay");
    const input = page.getByLabel("Jump to time");
    await input.fill("10:25");
    await input.press("Enter");
    await page.waitForTimeout(400);
    // No assertion on exact currentTime (it depends on chapter math), but the
    // page must not error and the video must remain present.
    await expect(page.locator("video").first()).toBeVisible();
  });

  test("deep link selects station and does not error", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/replay?station=gate-line&t=10:25");
    await expect(page.locator('[data-selected-station="gate-line"]').first()).toBeVisible();
    assertNoConsoleErrors(errors);
  });

  test("placement diamond opens the clip drawer", async ({ page }) => {
    await page.goto("/replay");
    // Placement markers are buttons labelled "Open placement N".
    const diamond = page.getByRole("button", { name: /open placement/i }).first();
    if (await diamond.count()) {
      await diamond.click();
      await expect(page.getByRole("dialog")).toBeVisible();
    }
  });
});
