import { test, expect } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers";

test.describe("/review", () => {
  test("chunk loads with video, spacebar tallies, Z undoes, confirm writes events", async ({ page, request }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/review");

    // Wait for a chunk to lease and render.
    const root = page.locator("[data-review-route='ready']");
    await expect(root).toBeVisible({ timeout: 15000 });

    // If a chunk leased, the running tally starts at 0.
    const chunkAttr = await root.getAttribute("data-review-chunk");
    test.skip(!chunkAttr, "no chunk available to review");

    // Ensure the video is present.
    await expect(page.locator("video").first()).toBeVisible();

    // Baseline eventsToday from the ops API.
    const before = await request.get("/api/ops/snapshot").then((r) => r.json());
    const beforeEvents = before.eventsToday as number;

    // Tally three clicks via keyboard (Space), then undo one with Z.
    await page.locator("body").click();
    await page.keyboard.press("Space");
    await page.keyboard.press("Space");
    await page.keyboard.press("Space");
    await page.keyboard.press("z"); // undo one -> net 2

    // Running tally in the aside reflects the net count.
    await expect(page.locator("aside").getByText("2", { exact: true })).toBeVisible();

    // End chunk -> summary -> CONFIRM writes the events.
    await page.getByRole("button", { name: /end chunk/i }).click();
    await page.getByRole("button", { name: /^confirm$/i }).click();

    // eventsToday increases (proves the confirm wrote events to the store).
    await expect
      .poll(async () => (await request.get("/api/ops/snapshot").then((r) => r.json())).eventsToday, {
        timeout: 15000,
      })
      .toBeGreaterThan(beforeEvents);

    assertNoConsoleErrors(errors);
  });

  // G7 — reviewer clarity.
  test("shows the instruction banner, humanized lag, hotkeys and walk-away note", async ({ page }) => {
    await page.goto("/review");
    const root = page.locator("[data-review-route='ready']");
    await expect(root).toBeVisible({ timeout: 15000 });
    const chunkAttr = await root.getAttribute("data-review-chunk");
    test.skip(!chunkAttr, "no chunk available to review");

    await expect(
      page.getByText("Tap +1 COUNT every time a finished piece lands on the pallet."),
    ).toBeVisible();
    await expect(page.getByText(/goes back to the queue after 5 minutes/)).toBeVisible();
    // Humanized lag ("N m" / "N h N m"), not "N min".
    await expect(page.getByText(/counting \d+ (h|m).* behind live · \d+ chunks waiting/)).toBeVisible();
    // Hotkey hints under the count button.
    await expect(page.getByText("count", { exact: false }).first()).toBeVisible();
    await expect(page.getByText("back 10s")).toBeVisible();
  });

  test("lease prevents a second session from getting the same chunk", async ({ request }) => {
    const a = await request
      .get("/api/review/chunks/next?reviewerId=lease-a")
      .then((r) => r.json());
    const b = await request
      .get("/api/review/chunks/next?reviewerId=lease-b")
      .then((r) => r.json());

    // Both sessions get a chunk, but never the SAME one (leases are exclusive).
    if (a.chunk && b.chunk) {
      expect(a.chunk.id).not.toBe(b.chunk.id);
    }
  });
});
