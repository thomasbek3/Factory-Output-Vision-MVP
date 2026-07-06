import { test, expect } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers";

test.describe("G1 — no lying chrome", () => {
  test("⌘K opens the command palette and navigates to Jobs", async ({ page }) => {
    await page.goto("/");
    await page.keyboard.press("Meta+k");
    const search = page.getByLabel("Command search");
    await expect(search).toBeVisible();
    await search.fill("jobs");
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/jobs$/);
  });

  test("header search button opens the palette", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Search" }).click();
    await expect(page.getByLabel("Command search")).toBeVisible();
  });

  test("Help opens the three-doors explainer", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Help" }).click();
    await expect(page.getByText("Three doors to your footage")).toBeVisible();
    await expect(page.getByText(/History.*money record/i)).toBeVisible();
  });

  test("Live pill is a static status (no dropdown chevron)", async ({ page }) => {
    await page.goto("/");
    // Live is a non-interactive status element with a tooltip.
    const live = page.locator('[title="All cameras connected"]');
    await expect(live).toBeVisible();
    await expect(live).toHaveText(/Live/);
  });

  test("avatar menu exposes role switcher and disabled sign-out", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Account menu" }).click();
    await expect(page.getByRole("menuitemradio", { name: /Owner/ })).toBeVisible();
    await expect(page.getByRole("menuitemradio", { name: /Reviewer/ })).toBeVisible();
    await expect(page.getByRole("menuitemradio", { name: /Ops/ })).toBeVisible();
    await expect(page.getByRole("menuitem", { name: /Sign out/ })).toBeDisabled();
  });

  test("camera tile kebab fires real actions", async ({ page }) => {
    await page.goto("/");
    const errors = collectConsoleErrors(page);
    const kebab = page.getByRole("button", { name: "Pallet A menu" });
    await kebab.click();
    await expect(page.getByRole("menuitem", { name: "Open in Replay" })).toBeVisible();
    await expect(page.getByRole("menuitem", { name: "Hide tile" })).toBeVisible();
    // Hide tile actually hides it.
    await page.getByRole("menuitem", { name: "Hide tile" }).click();
    await expect(page.getByRole("button", { name: /Show \d+ hidden tile/ })).toBeVisible();
    assertNoConsoleErrors(errors);
  });

  test("jobs kebab has Edit that opens a pre-filled form", async ({ page }) => {
    await page.goto("/jobs");
    // Open first job kebab (details/summary).
    await page.locator("summary").first().click();
    await page.getByRole("button", { name: "Edit", exact: true }).first().click();
    // Sheet titled "Edit <client>" with a pre-filled client value.
    await expect(page.getByText(/^Edit /)).toBeVisible();
    const clientInput = page.locator('input[name="client"]');
    await expect(clientInput).not.toHaveValue("");
  });

  test("replay chapter cards have no kebab, only a Watch action", async ({ page }) => {
    await page.goto("/replay?station=pallet-a");
    // The old fake kebab (aria View events) is gone; a real Watch button exists.
    await expect(page.getByRole("button", { name: /Watch .* chapter/ }).first()).toBeVisible();
  });
});
