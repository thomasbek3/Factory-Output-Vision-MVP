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

    // Reviewers table header present.
    await expect(page.getByText(/golden accuracy/i)).toBeVisible();

    assertNoConsoleErrors(errors);
  });

  test("export labels writes a file and toasts", async ({ page }) => {
    await page.goto("/ops");
    await page.getByRole("button", { name: /export labels/i }).click();
    await expect(page.getByText(/wrote .*labels|export failed/i)).toBeVisible();
  });

  // G8 — ops legibility.
  test("stat cards have explanatory subtitles", async ({ page }) => {
    await page.goto("/ops");
    await expect(page.getByText("how far behind live the human counts are")).toBeVisible();
    await expect(page.getByText(/verified placements on \w+ \d+/)).toBeVisible();
    await expect(page.getByText("held-out recall — the honest score on unseen footage")).toBeVisible();
  });

  // G5 — internal back-link.
  test("has a Console back-link", async ({ page }) => {
    await page.goto("/ops");
    await expect(page.getByRole("link", { name: /Console/ }).first()).toBeVisible();
    await page.getByRole("link", { name: /Console/ }).first().click();
    await expect(page).toHaveURL(/\/$/);
  });
});
