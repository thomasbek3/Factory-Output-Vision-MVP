import { test, expect } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers";

test.describe("/ops", () => {
  test("stat cards render from the snapshot", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/ops");

    await expect(page.locator("[data-ops-route='ready']")).toBeVisible();
    await expect(page.getByText(/factories/i)).toBeVisible();
    await expect(page.getByText(/cameras up/i)).toBeVisible();
    await expect(page.getByText(/events today/i)).toBeVisible();

    await expect(page.getByText("Queue health only")).toBeVisible();
    await expect(page.getByText(/model agreement/i)).toHaveCount(0);
    await expect(page.getByText(/held-out exam/i)).toHaveCount(0);
    await expect(page.getByText(/golden accuracy/i)).toHaveCount(0);
    await expect(page.getByRole("button", { name: /export labels/i })).toHaveCount(0);

    assertNoConsoleErrors(errors);
  });

  test("legacy ungated label export route is absent", async ({ request }) => {
    const response = await request.post("/api/ops/labels/export");
    expect(response.status()).toBe(404);
  });

  // G8 — ops legibility.
  test("stat cards have explanatory subtitles", async ({ page }) => {
    await page.goto("/ops");
    await expect(page.getByText("demo review delay behind source time")).toBeVisible();
    await expect(page.getByText(/seeded review events on \w+ \d+/)).toBeVisible();
    await expect(page.getByText("Queue health only")).toBeVisible();
  });

  // G5 — internal back-link.
  test("has a Console back-link", async ({ page }) => {
    await page.goto("/ops");
    await expect(page.getByRole("link", { name: /Console/ }).first()).toBeVisible();
    await page.getByRole("link", { name: /Console/ }).first().click();
    await expect(page).toHaveURL(/\/$/);
  });
});
