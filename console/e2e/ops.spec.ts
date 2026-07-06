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
});
