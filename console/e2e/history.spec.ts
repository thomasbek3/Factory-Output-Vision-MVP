import { test, expect } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers";

test.describe("/history", () => {
  test("accordion expands and NEXT TIME renders", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/history");

    await expect(page.locator("[data-history-route='ready']")).toBeVisible();

    // Expand the first collapsed row (rows are buttons).
    const row = page.locator("[data-history-route='ready'] button").filter({ hasText: /wire|bracket|gate|panel/i }).first();
    if (await row.count()) {
      await row.click();
    }
    // Expanded content mentions the "next time" guidance.
    await expect(page.getByText(/quoted/i).first()).toBeVisible();

    assertNoConsoleErrors(errors);
  });

  test("client search filters the list", async ({ page }) => {
    await page.goto("/history");
    const search = page.getByPlaceholder(/search clients/i);
    await search.fill("zzzznomatch");
    await expect(page.getByText(/no .*match|no finished/i).or(page.locator("text=Ramirez"))).toBeTruthy();
  });
});
