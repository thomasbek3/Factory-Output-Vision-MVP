import { test, expect } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors, expectVideoPlaying } from "./helpers";

test.describe("/tv", () => {
  test("wall view pins and shows playing videos", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/tv?view=wall");

    await expect(page.locator("[data-tv-route='ready']")).toBeVisible();
    await expect(page.locator("[data-tv-view='wall']")).toBeVisible();

    const videos = page.locator('video[data-camera-state="live"]');
    await expect(videos.first()).toBeVisible();
    const advanced = await expectVideoPlaying(page, 'video[data-camera-state="live"]');
    expect(advanced).toBe(true);

    assertNoConsoleErrors(errors);
  });

  test("tv counts match Live (single source)", async ({ page }) => {
    // Read a station count from Live.
    await page.goto("/");
    const liveCount = Number(
      (await page.getByTestId("station-count").first().textContent())?.trim() ?? "-1",
    );

    // Read the same first count on TV wall.
    await page.goto("/tv?view=wall");
    const tvCount = Number(
      (await page.getByTestId("station-count").first().textContent())?.trim() ?? "-2",
    );

    // Time advances a second or two between loads; allow a small drift.
    expect(Math.abs(tvCount - liveCount)).toBeLessThanOrEqual(3);
  });
});
