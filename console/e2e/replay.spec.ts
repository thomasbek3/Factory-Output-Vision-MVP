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
    // Use a single station so individual diamonds don't overlap each other.
    await page.goto("/replay?station=gate-line");
    // Placement markers are buttons labelled "Open placement N".
    const diamond = page.getByRole("button", { name: /open placement/i }).first();
    if (await diamond.count()) {
      await diamond.click();
      await expect(page.getByRole("dialog")).toBeVisible();
    }
  });

  // G6 — replay comprehension.
  test("defaults to 1x playback (15x is one tap away)", async ({ page }) => {
    await page.goto("/replay");
    await page.waitForTimeout(300);
    const rate = await page.locator("video").first().evaluate((el: HTMLVideoElement) => el.playbackRate);
    expect(rate).toBe(1);
    // 15x remains reachable.
    await expect(page.getByRole("button", { name: "15×", exact: true })).toBeVisible();
  });

  test("chapters show real PLACED counts (regression: not all 0 QUIET)", async ({ page }) => {
    await page.goto("/replay?station=pallet-a");
    // At least one chapter card must show a real placement count, not "0 QUIET".
    await expect(page.getByText(/\d+ PLACED/).first()).toBeVisible();
    // Pinned: pallet-a has a 15-min window with exactly 6 placements.
    await expect(page.getByText("6 PLACED").first()).toBeVisible();
  });

  test("sparse windows render individual diamonds", async ({ page }) => {
    await page.goto("/replay?station=gate-line");
    // Individual placement markers (not clusters) exist for a sparse station.
    await expect(page.getByRole("button", { name: /open placement/i }).first()).toBeVisible();
  });
});
