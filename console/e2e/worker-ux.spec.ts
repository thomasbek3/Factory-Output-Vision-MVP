import path from "node:path";
import { expect, test } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers";

test("ops account can preview the employee portal without reviewer enrollment", async ({
  page,
}) => {
  const errors = collectConsoleErrors(page);
  let mfaRequestCount = 0;

  await page.addInitScript(() => {
    window.localStorage.setItem("factoryvision-review-language", "en");
  });
  await page.route("**/api/review/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user: { id: "ops-preview", email: "owner@example.com" },
      }),
    });
  });
  await page.route("**/api/review/onboarding", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ state: "unregistered" }),
    });
  });
  await page.route("**/api/review/preview", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ allowed: true }),
    });
  });
  await page.route("**/api/review/mfa", async (route) => {
    mfaRequestCount += 1;
    await route.fulfill({ status: 500, body: "MFA_SHOULD_NOT_BE_CALLED" });
  });

  await page.goto("/review");
  await expect(page.locator("[data-review-route='today']")).toBeVisible();
  await expect(
    page.getByText(
      "Practice with real footage. Your clicks are not saved as training data.",
    ),
  )
    .toBeVisible();
  await expect(page.getByText("Preview mode")).toBeVisible();
  await expect(page.getByText("No assignments waiting")).toBeVisible();
  await expect(page.getByText("Protect your account")).toHaveCount(0);
  expect(mfaRequestCount).toBe(0);
  await page.screenshot({
    path: "e2e-audit/shots/worker-ops-preview-no-mfa.png",
    fullPage: true,
  });
  assertNoConsoleErrors(errors);
});

test("build-phase test accounts skip authenticator enrollment", async ({ page }) => {
  const errors = collectConsoleErrors(page);
  let onboardingPostCount = 0;
  let mfaRequestCount = 0;

  await page.addInitScript(() => {
    window.localStorage.setItem("factoryvision-review-language", "en");
  });
  await page.route("**/api/review/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user: { id: "build-reviewer", email: "build@example.com" },
      }),
    });
  });
  await page.route("**/api/review/mfa", async (route) => {
    mfaRequestCount += 1;
    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ error: "MFA_SHOULD_NOT_BE_CALLED" }),
    });
  });
  await page.route("**/api/review/onboarding", async (route) => {
    if (route.request().method() === "POST") {
      const payload = route.request().postDataJSON() as { step?: string };
      expect(payload.step).toBe("mfa_verified");
      onboardingPostCount += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          userId: "build-reviewer",
          displayName: "Build Reviewer",
          email: "build@example.com",
          locale: "en",
          state: "terms_required",
          mfaVerifiedAt: "2026-07-27T22:30:00Z",
          currentAal: "aal1",
          isTestAccount: true,
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        userId: "build-reviewer",
        displayName: "Build Reviewer",
        email: "build@example.com",
        locale: "en",
        state: "mfa_required",
        mfaVerifiedAt: null,
        currentAal: "aal1",
        isTestAccount: true,
      }),
    });
  });

  await page.goto("/review");
  await expect(page.getByRole("heading", { name: "Protect the information" }))
    .toBeVisible();
  await expect(page.getByText("Protect your account")).toHaveCount(0);
  expect(onboardingPostCount).toBe(1);
  expect(mfaRequestCount).toBe(0);
  await page.screenshot({
    path: "e2e-audit/shots/reviewer-test-account-mfa-skip.png",
    fullPage: true,
  });
  assertNoConsoleErrors(errors);
});

test("employee can understand and complete the assigned-work flow", async ({ page }) => {
  const errors = collectConsoleErrors(page);
  let started = false;
  let submitted = false;
  let activeCount = 0;

  await page.addInitScript(() => {
    window.localStorage.setItem("factoryvision-review-language", "en");
  });
  await page.route("**/api/review/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user: { id: "worker-ux-reviewer", email: "worker@example.com" },
      }),
    });
  });
  await page.route("**/api/review/onboarding", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        userId: "worker-ux-reviewer",
        displayName: "Jordan Lee",
        email: "worker@example.com",
        locale: "en",
        state: "active",
        currentAal: "aal1",
        isTestAccount: true,
      }),
    });
  });
  await page.route("**/api/review/rpc/worker_register_active_device", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
  });
  await page.route("**/api/review/rpc/worker_daily_progress", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ready: submitted ? 0 : started ? 0 : 1,
        inProgress: started && !submitted ? 1 : 0,
        completedToday: submitted ? 1 : 0,
        observedAt: "2026-07-27T17:00:00Z",
      }),
    });
  });
  await page.route("**/api/review/rpc/claim_worker_assignment", async (route) => {
    started = true;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        assignment: {
          id: "4821c9d2-8e75-4eb0-9f0f-836109b8ad77",
          leaseToken: "fixture-lease",
          leaseExpiresAt: "2026-07-27T18:00:00Z",
          chunk: {
            id: "fixture-chunk",
            stationId: "gate-line",
            stationName: "Gate line",
            factoryTimezone: "America/New_York",
            startIso: "2026-07-27T14:15:00Z",
            endIso: "2026-07-27T14:30:00Z",
            sourceStartMs: 5_000,
            sourceEndMs: 900_000,
            renditionSourceStartMs: 0,
            renditionSourceEndMs: 900_150,
            sourceSha256: "a".repeat(64),
            renditionId: "fixture-rendition",
            mediaUrl: "https://worker-ux.fixture/clip.mp4",
            posterUrl: null,
          },
          actions: [],
          coverage: null,
        },
      }),
    });
  });
  await page.route("https://worker-ux.fixture/clip.mp4", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "video/mp4",
      path: path.resolve("demo-media/review/gate-line-20260709-1208.mp4"),
    });
  });
  await page.route("**/api/review/rpc/append_worker_action", async (route) => {
    const payload = route.request().postDataJSON() as { p_action_type: string };
    activeCount += payload.p_action_type === "tally" ? 1 : -1;
    await route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
  });
  for (const operation of [
    "heartbeat_worker_assignment",
    "save_worker_coverage",
    "authorize_worker_media",
    "worker_close_work_session",
  ]) {
    await page.route(`**/api/review/rpc/${operation}`, async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
    });
  }
  await page.route("**/api/review/rpc/worker_touch_work_session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ sessionId: "fixture-session" }),
    });
  });
  await page.route("**/api/review/rpc/submit_worker_assignment_v2", async (route) => {
    submitted = true;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ totalCount: activeCount, alreadySubmitted: false }),
    });
  });

  await page.goto("/review");
  await expect(page.locator("[data-review-route='today']")).toBeVisible();
  await expect(page.getByRole("heading", { name: /Jordan/ })).toBeVisible();
  await expect(page.getByText("1 video is ready")).toBeVisible();
  await expect(page.getByText("15-minute video review")).toBeVisible();
  await expect(page.getByText("Today's progress")).toBeVisible();
  await page.getByRole("button", { name: "Open account menu" }).click();
  await expect(page.getByRole("menu", { name: "Account" })).toBeVisible();
  await expect(page.getByText("worker@example.com")).toBeVisible();
  await page.screenshot({
    path: "e2e-audit/shots/worker-account-menu-desktop.png",
    fullPage: true,
  });
  await page.getByRole("menuitem", { name: "Profile and settings" }).click();
  await expect(page.getByRole("dialog", { name: "Account settings" })).toBeVisible();
  await expect(page.getByText("Email link")).toBeVisible();
  await expect(page.getByText("Test account")).toBeVisible();
  await page.getByRole("button", { name: "Español" }).click();
  await expect(page.getByRole("dialog", { name: "Configuración de cuenta" })).toBeVisible();
  await page.getByRole("button", { name: "English" }).click();
  await page.getByRole("button", { name: "Done" }).click();
  await expect(page.getByRole("dialog", { name: "Account settings" })).toHaveCount(0);
  await page.screenshot({
    path: "e2e-audit/shots/worker-ux-today-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("button", { name: "Start next video" })).toBeVisible();
  await page.screenshot({
    path: "e2e-audit/shots/worker-ux-today-mobile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Open account menu" }).click();
  await page.getByRole("menuitem", { name: "Profile and settings" }).click();
  await expect(page.getByRole("dialog", { name: "Account settings" })).toBeVisible();
  await page.screenshot({
    path: "e2e-audit/shots/worker-settings-mobile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Done" }).click();
  await page.setViewportSize({ width: 1280, height: 720 });

  await page.getByRole("button", { name: "Start next video" }).click();
  await expect(page.locator("[data-review-route='ready']")).toBeVisible();
  await expect(page.getByText("Gate line")).toBeVisible();
  await expect(page.getByText("factory time", { exact: false })).toBeVisible();
  await expect(page.getByText("Task #4821c9d2")).toBeVisible();
  await expect(page.getByRole("button", { name: "+1 Output" })).toBeDisabled();
  await expect(page.getByText("Context from the previous video. Do not count here.")).toBeVisible();
  for (const rate of ["1x", "2x", "5x", "10x", "15x", "20x"]) {
    await expect(page.getByRole("button", { name: rate, exact: true })).toBeVisible();
  }
  await page.getByRole("button", { name: "20x", exact: true }).click();
  await expect.poll(async () => {
    if (await page.getByText(/left at 20x/).isVisible()) return "20";
    if (
      await page.getByRole("status").filter({
        hasText: "That speed did not work. The video will use a lower speed.",
      }).isVisible()
    ) return "15";
    return "pending";
  }).toMatch(/^(15|20)$/);
  await page.getByRole("button", { name: "5x", exact: true }).click();
  await page.locator("body").click();
  await page.keyboard.press("Space");
  await expect(page.getByRole("button", { name: "Pause" })).toBeVisible();
  await expect(page.getByRole("button", { name: "+1 Output" })).toBeEnabled();
  await page.keyboard.press("Space");
  await expect(page.getByRole("button", { name: "Play", exact: true })).toBeVisible();
  await expect(page.getByTestId("running-tally")).toHaveText("0");
  await page.evaluate(() => {
    window.dispatchEvent(new KeyboardEvent("keydown", {
      key: "j",
      repeat: true,
      bubbles: true,
    }));
  });
  await expect(page.getByTestId("running-tally")).toHaveText("0");
  await page.keyboard.press("j");
  await page.keyboard.press("j");
  await expect(page.getByTestId("running-tally")).toHaveText("2");
  await page.evaluate(() => {
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "z", bubbles: true }));
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "z", bubbles: true }));
  });
  await expect(page.getByTestId("running-tally")).toHaveText("0");
  await page.keyboard.press("j");
  await page.getByRole("button", { name: "+1 Output" }).click();
  await expect(page.getByTestId("running-tally")).toHaveText("2");
  await page.screenshot({
    path: "e2e-audit/shots/worker-ux-review-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("button", { name: "+1 Output" })).toBeVisible();
  await page.screenshot({
    path: "e2e-audit/shots/worker-ux-review-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1280, height: 720 });

  await page.getByRole("button", { name: "Finish video" }).click();
  await expect(page.getByRole("heading", { name: "Review your count" })).toBeVisible();
  await page.getByRole("button", { name: "Delete event 1" }).click();
  await expect(page.getByText("1 event", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Submit count" }).click();

  await expect(page.locator("[data-review-route='today']")).toBeVisible();
  await expect(page.getByRole("status")).toContainText("submitted");
  await expect(page.getByText("Completed", { exact: true })).toBeVisible();
  await expect(page.getByTestId("completed-today")).toHaveText("1");
  await page.getByRole("button", { name: "Open account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page.locator("[data-review-route='auth']")).toBeVisible();
  assertNoConsoleErrors(errors);
});
