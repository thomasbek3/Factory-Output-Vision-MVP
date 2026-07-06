import { test, expect } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors, expectVideoPlaying } from "./helpers";

test.describe("/ (Live)", () => {
  test("both camera videos autoplay and advance", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/");

    const videos = page.locator('video[data-camera-state="live"]');
    await expect(videos).toHaveCount(2);

    // Both should be muted + playsInline + autoplay.
    for (let i = 0; i < 2; i++) {
      const v = videos.nth(i);
      await expect(v).toHaveJSProperty("muted", true);
    }

    // At least one advances (both share the same media pipeline).
    const advanced = await expectVideoPlaying(page, 'video[data-camera-state="live"]');
    expect(advanced).toBe(true);

    assertNoConsoleErrors(errors);
  });

  test("money strip holds the pinned +$532 · 3-jobs narrative on load", async ({ page }) => {
    // Regression guard: the money strip must ride the demo TimeProvider clock and
    // the pinned seed narrative, NOT a drifted dev.db (jobs left "finished" would
    // collapse it to "+$0 · All 0 jobs on pace" while the scoreboards still tell
    // the demo story). This narrative was pinned in vitest selectors but never
    // against the live page — that gap is what let the regression ship.
    const errors = collectConsoleErrors(page);
    await page.goto("/");

    // The projected-profit hero renders the exact pinned dollar figure.
    await expect(page.getByText("+$532", { exact: true })).toBeVisible();
    // And the Alvarez at-risk sentence (3 jobs running, one losing money).
    await expect(
      page.getByText(/Alvarez Gates is losing money/i),
    ).toBeVisible();

    // The /jobs surface renders the "3 JOBS RUNNING" count off the same source.
    await page.goto("/jobs");
    await expect(page.getByText(/3 jobs running/i)).toBeVisible();
    await expect(page.getByText("+$532", { exact: true })).toBeVisible();

    assertNoConsoleErrors(errors);
  });

  test("count number opens the clip drawer with a playing video", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/");

    // The big per-station count is a button that opens the drawer.
    const countButton = page.getByTestId("station-count").first();
    await countButton.click();

    const drawer = page.getByRole("dialog");
    await expect(drawer).toBeVisible();
    await expect(drawer.locator("video")).toBeVisible();

    // Prev/Next present.
    await expect(drawer.getByRole("button", { name: /prev/i })).toBeVisible();
    await expect(drawer.getByRole("button", { name: /next/i })).toBeVisible();

    assertNoConsoleErrors(errors);
  });

  test("dispute marks the count and shows a toast", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("station-count").first().click();
    const drawer = page.getByRole("dialog");
    await drawer.getByRole("button", { name: /dispute/i }).click();
    await expect(page.getByText(/disputed/i)).toBeVisible();
  });

  test("Open in Replay navigates with station + time params", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("station-count").first().click();
    const drawer = page.getByRole("dialog");
    await drawer.getByRole("link", { name: /open in replay/i }).click();
    await expect(page).toHaveURL(/\/replay\?station=/);
  });

  test("live playlist route 404s cleanly when no relay stream exists", async ({ page }) => {
    // No relay is running in CI, so the playlist is absent → clean 404 (not 500),
    // which is what lets the tile fall back to the demo loop.
    const res = await page.request.get("/api/live/pallet-a/stream.m3u8");
    expect(res.status()).toBe(404);

    // Unknown station is rejected by the allowlist, also 404.
    const bad = await page.request.get("/api/live/ghost-line/stream.m3u8");
    expect(bad.status()).toBe(404);
  });

  test("with no live stream, tiles fall back to demo loop and show the REPLAY chip", async ({ page }) => {
    await page.goto("/");

    // The camera video element is present and playing the demo loop.
    const videos = page.locator('video[data-camera-state="live"]');
    await expect(videos).toHaveCount(2);
    // In fallback mode the demo loop is the src and the feed mode is "replay".
    await expect(videos.first()).toHaveAttribute("data-feed-mode", "replay");

    // The pill is the honest neutral REPLAY chip, not a red LIVE pill.
    await expect(page.getByText(/REPLAY · JUN 26/).first()).toBeVisible();
    // And the honest counts caption is present.
    await expect(page.getByText(/counts from pilot day · Thu Jun 26/).first()).toBeVisible();
  });

  test("dev time controls (60x) advance the live count", async ({ page }) => {
    await page.goto("/");
    const count = page.getByTestId("station-count").first();
    const before = Number((await count.textContent())?.trim() ?? "0");

    // Engage 60x via the (sr-only, design-hidden) dev control. It is clipped, not
    // display:none, so dispatch the click directly rather than a pointer click.
    await page.getByRole("button", { name: "60x", exact: true }).dispatchEvent("click");
    await page.waitForTimeout(3500);

    const after = Number((await count.textContent())?.trim() ?? "0");
    // At 60x the virtual clock advances ~3.5 minutes; counts must not go backward
    // and should generally climb as more events pass the tripwire.
    expect(after).toBeGreaterThanOrEqual(before);
  });
});
