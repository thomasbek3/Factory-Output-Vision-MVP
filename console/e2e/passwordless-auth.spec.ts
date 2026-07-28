import { expect, test } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers";

test("reviewer requests a sign-in link without a password", async ({ page }) => {
  const errors = collectConsoleErrors(page);
  let requestBody: Record<string, unknown> | null = null;

  await page.addInitScript(() => {
    window.localStorage.setItem("factoryvision-review-language", "en");
  });
  await page.route("**/api/review/session", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ user: null }),
      });
      return;
    }
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ sent: true }),
    });
  });

  await page.goto("/review");
  await expect(page.locator("[data-review-route='auth']")).toBeVisible();
  await expect(page.getByText("No password needed.")).toBeVisible();
  await expect(page.getByLabel("Password")).toHaveCount(0);
  await page.screenshot({
    path: "e2e-audit/shots/passwordless-auth-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "e2e-audit/shots/passwordless-auth-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.getByLabel("Email").fill("worker@example.com");
  await page.getByRole("button", { name: "Email me a sign-in link" }).click();
  await expect(page.getByRole("status")).toContainText("Check your email");
  expect(requestBody).toEqual({
    action: "requestPasswordless",
    email: "worker@example.com",
    language: "en",
  });
  assertNoConsoleErrors(errors);
});

test("passwordless callback exchanges tokens for the reviewer session", async ({
  page,
}) => {
  const errors = collectConsoleErrors(page);
  let requestBody: Record<string, unknown> | null = null;
  await page.route("**/api/review/session", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user: { id: "passwordless-reviewer", email: "worker@example.com" },
      }),
    });
  });

  await page.goto(
    "/review/welcome?mode=login&lang=en#access_token=access-token&refresh_token=refresh-token&expires_in=1800",
  );
  await expect(page.getByRole("heading", { name: "Signed in" })).toBeVisible();
  expect(await page.evaluate(() => window.location.hash)).toBe("");
  expect(requestBody).toEqual({
    action: "completePasswordless",
    accessToken: "access-token",
    refreshToken: "refresh-token",
    expiresIn: 1800,
  });
  assertNoConsoleErrors(errors);
});
