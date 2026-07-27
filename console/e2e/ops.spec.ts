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

    await expect(page.getByText(/reviewer accounts/i)).toBeVisible();
    await expect(page.getByText("active factories you can manage")).toBeVisible();
    await expect(page.getByText("age of the oldest unfinished assignment")).toBeVisible();
    await expect(page.getByText("Email setup required")).toBeVisible();
    await expect(page.getByText("Worker support")).toBeVisible();
    await expect(
      page.getByText("QA support request from live worker flow."),
    ).toBeVisible();
    await page.screenshot({
      path: "e2e-audit/shots/ops-worker-support.png",
      fullPage: true,
    });
    await page.getByRole("button", { name: "Acknowledge" }).click();
    await expect(page.getByRole("status")).toContainText(
      "Support request acknowledged.",
    );
    await page.getByRole("button", { name: "Invite reviewer" }).click();
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
});
