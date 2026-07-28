import { test, expect } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers";

const opsQaEmail = process.env.FV_OPS_QA_EMAIL;
const opsQaPassword = process.env.FV_OPS_QA_PASSWORD;
const requireLiveQa = process.env.FV_REQUIRE_LIVE_QA === "1";

test.describe("/ops", () => {
  test("workforce metrics stay behind ops authentication", async ({ page, request }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/ops");

    await expect(page.locator("[data-ops-route='ready']")).toBeVisible();
    await expect(page.getByText("Sign in to manage reviewers")).toBeVisible();
    await expect(page.getByText("Open queue")).toHaveCount(0);
    const snapshot = await request.get("/api/ops/snapshot");
    expect(snapshot.status()).toBe(401);
    const reviewerAdmin = await request.get("/api/ops/reviewers");
    expect(reviewerAdmin.status()).toBe(403);
    const inviteAttempt = await request.post("/api/ops/reviewers", {
      data: {
        requestKey: "bd58d672-86f8-4f02-84d2-6b94bb8a29ea",
        email: "unauthenticated-proof@paverturf.com",
        displayName: "Unauthorized proof",
        locale: "en",
        factoryId: "3a4d8990-6616-47f2-8d99-fb1ff3463ec1",
      },
    });
    expect(inviteAttempt.status()).toBe(403);
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

  // G5 — internal back-link.
  test("has a Console back-link", async ({ page }) => {
    await page.goto("/ops");
    await expect(page.getByRole("link", { name: /Console/ }).first()).toBeVisible();
    await page.getByRole("link", { name: /Console/ }).first().click();
    await expect(page).toHaveURL(/\/$/);
  });

  test("authenticated ops can inspect the reviewer roster and invitation email", async ({
    page,
  }) => {
    if ((!opsQaEmail || !opsQaPassword) && requireLiveQa) {
      throw new Error(
        "FV_OPS_QA_EMAIL and FV_OPS_QA_PASSWORD are required when FV_REQUIRE_LIVE_QA=1",
      );
    }
    test.skip(
      !opsQaEmail || !opsQaPassword,
      "FV_OPS_QA_EMAIL and FV_OPS_QA_PASSWORD are required",
    );
    const errors = collectConsoleErrors(page);
    await page.goto("/ops");
    await page.getByLabel("Email").fill(opsQaEmail ?? "");
    await page.getByLabel("Password").fill(opsQaPassword ?? "");
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page.getByText("Operations command center")).toBeVisible();
    await expect(page.getByRole("button", { name: "Review queue" }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Label output" }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "AI evaluation" }).first()).toBeVisible();
    await expect(page.getByText("Attention required")).toBeVisible();
    await expect(page.getByText("Recent label output")).toBeVisible();
    await expect(page.getByText("Email setup required", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Worker support" })).toBeVisible();
    await expect(
      page.getByText("QA support request from live worker flow.").first(),
    ).toBeVisible();
    await page.getByRole("button", { name: "Label output" }).first().click();
    await expect(page.getByText("Human label output")).toBeVisible();
    await page.getByRole("row", { name: /Gate line/ }).first().click();
    await expect(page.getByRole("dialog", { name: "Label round details" })).toBeVisible();
    await expect(page.getByText("Source SHA-256")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Human submissions" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "AI comparison" })).toBeVisible();
    await page.getByRole("button", { name: "Close details" }).click();
    await page.getByRole("button", { name: "AI evaluation" }).first().click();
    await expect(page.getByText("No AI runs ingested yet")).toBeVisible();
    await page.getByRole("button", { name: "Overview" }).first().click();
    await page.screenshot({
      path: "e2e-audit/shots/ops-worker-support.png",
      fullPage: true,
    });
    const acknowledge = page.getByRole("button", { name: "Acknowledge" });
    if (await acknowledge.count()) {
      await acknowledge.first().click();
      await expect(page.getByRole("status")).toContainText(
        "Support request acknowledged.",
      );
    } else {
      await expect(page.getByText("acknowledged", { exact: true }).first()).toBeVisible();
    }
    await page.getByRole("button", { name: "Reviewers" }).first().click();
    await expect(page.getByText("Reviewer accounts")).toBeVisible();
    await page.getByRole("button", { name: "Invite reviewer" }).last().click();
    await expect(page.getByRole("dialog", { name: "Invite reviewer" })).toBeVisible();
    await page.getByRole("button", { name: "Preview email" }).click();

    const preview = page.frameLocator("iframe[title='Invitation email']");
    await expect(preview.getByText("Hola Ana Rivera,")).toBeVisible();
    await expect(preview.getByText("Activar mi cuenta")).toBeVisible();
    await expect(preview.getByText(/FactoryVision nunca te pedirá/)).toBeVisible();
    await page.screenshot({
      path: "e2e-audit/shots/reviewer-invitation-email.png",
      fullPage: true,
    });

    assertNoConsoleErrors(errors);
  });

  test("authenticated ops workspace remains usable on mobile", async ({ page }) => {
    if ((!opsQaEmail || !opsQaPassword) && requireLiveQa) {
      throw new Error(
        "FV_OPS_QA_EMAIL and FV_OPS_QA_PASSWORD are required when FV_REQUIRE_LIVE_QA=1",
      );
    }
    test.skip(
      !opsQaEmail || !opsQaPassword,
      "FV_OPS_QA_EMAIL and FV_OPS_QA_PASSWORD are required",
    );
    const errors = collectConsoleErrors(page);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/ops");
    await page.getByLabel("Email").fill(opsQaEmail ?? "");
    await page.getByLabel("Password").fill(opsQaPassword ?? "");
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page.getByText("Operations command center")).toBeVisible();
    await expect(page.getByRole("button", { name: "Label output" }).first()).toBeVisible();
    await expect(page.getByText("Attention required")).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(390);
    await page.screenshot({
      path: "e2e-audit/shots/ops-command-center-mobile.png",
      fullPage: true,
    });

    assertNoConsoleErrors(errors);
  });
});
