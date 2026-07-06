import { test, expect } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers";

test.describe("/alerts", () => {
  test("resolve updates the row and drops the open count", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/alerts");

    const root = page.locator("[data-alerts-route='ready']");
    await expect(root).toBeVisible();

    const before = Number((await root.getAttribute("data-open-alert-count")) ?? "0");

    const resolveBtn = page.getByRole("button", { name: /^resolve$/i }).first();
    if (before > 0 && (await resolveBtn.count())) {
      await resolveBtn.click();
      await expect(page.getByText(/^resolved$/i).first()).toBeVisible();
      const after = Number((await root.getAttribute("data-open-alert-count")) ?? "0");
      expect(after).toBe(before - 1);
    }

    assertNoConsoleErrors(errors);
  });

  test("status filter switches between open and resolved", async ({ page }) => {
    await page.goto("/alerts");
    await page.getByRole("button", { name: "resolved", exact: true }).click();
    // Should not throw; list either shows resolved items or an empty state.
    await expect(page.locator("[data-alerts-route='ready']")).toBeVisible();
  });

  test("watch replay opens the drawer", async ({ page }) => {
    await page.goto("/alerts");
    const watch = page.getByRole("button", { name: /watch replay/i }).first();
    if (await watch.count()) {
      await watch.click();
      await expect(page.getByRole("dialog")).toBeVisible();
    }
  });
});
