import { expect, test } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers";

test("reviewer sign-in is bilingual, persistent, and usable on mobile", async ({
  page,
}) => {
  const errors = collectConsoleErrors(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() => {
    if (!window.localStorage.getItem("factoryvision-review-language")) {
      window.localStorage.setItem("factoryvision-review-language", "en");
    }
  });

  await page.goto("/review");
  await expect(page.locator("[data-review-route='auth']")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Today's work" }),
  ).toBeVisible();
  await expect(page.getByLabel("Email")).toBeVisible();

  await page.getByRole("button", { name: "es", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Trabajo de hoy" }),
  ).toBeVisible();
  await expect(page.getByLabel("Correo")).toBeVisible();
  await expect(page.getByText("No necesitas contraseña.")).toBeVisible();

  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Trabajo de hoy" }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.screenshot({
    path: "e2e-audit/shots/reviewer-sign-in-spanish-mobile.png",
    fullPage: true,
  });

  await page.getByRole("button", { name: "en", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Today's work" }),
  ).toBeVisible();
  assertNoConsoleErrors(errors);
});
