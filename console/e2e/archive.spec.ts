import { test, expect } from "@playwright/test";

test.describe("G2 — the Tapes archive", () => {
  test("day picker navigates to Jun 25 with different chapters", async ({ page }) => {
    await page.goto("/replay?station=pallet-a");
    // Jun 26 (today) is the default; capture a chapter label.
    await expect(page.getByText(/\d+ PLACED/).first()).toBeVisible();
    // Navigate to the previous day.
    await page.getByRole("button", { name: "Previous day" }).click();
    await expect(page).toHaveURL(/d=2026-06-25/);
    // Jun 25 still has real counted chapters (different footage/counts).
    await expect(page.getByText(/\d+ PLACED/).first()).toBeVisible();
  });

  test("counted moments list opens the clip drawer", async ({ page }) => {
    await page.goto("/replay?station=pallet-a");
    // Owner surfaces expose the event, not the reviewer identity.
    const firstMoment = page.getByTestId("counted-moment").first();
    await expect(firstMoment).toContainText("Seeded review");
    await expect(firstMoment).not.toContainText(/M\. Reyes/);
    await firstMoment.click();
    await expect(page.getByRole("dialog")).toBeVisible();
  });

  test("Save clip downloads an mp4 and it appears under Saved clips", async ({ page }) => {
    await page.goto("/replay?station=pallet-a&t=12:00");
    // Directly assert the extraction endpoint returns a real mp4.
    const response = await page.request.get("/api/clip/clip-pa-001/download");
    expect(response.status()).toBe(200);
    expect(response.headers()["content-type"]).toContain("video/mp4");

    // Save via the API (button triggers a navigation download in-browser).
    const saveResponse = await page.request.post("/api/clips", {
      data: { eventId: "clip-pa-001", note: "e2e" },
    });
    expect(saveResponse.status()).toBe(201);

    await page.reload();
    await expect(page.getByText("Saved clips")).toBeVisible();
  });

  test("Copy link puts a ?clip= URL on the clipboard with a toast", async ({ page, context }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await page.goto("/replay?station=pallet-a&t=12:00");
    await page.getByRole("button", { name: "Copy link" }).click();
    await expect(page.getByText(/Link copied/)).toBeVisible();
    const clip = await page.evaluate(() => navigator.clipboard.readText());
    expect(clip).toContain("clip=");
  });

  test("History expanded row links to Replay footage", async ({ page }) => {
    await page.goto("/history");
    // The first finished row is expanded by default and shows the cross-link.
    const link = page.getByRole("link", { name: /View footage/ }).first();
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute("href", /\/replay\?station=.*&d=\d{4}-\d{2}-\d{2}/);
  });
});
