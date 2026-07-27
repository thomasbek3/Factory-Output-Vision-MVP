import path from "node:path";
import { test, expect } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers";

test("qualification UI is obvious and usable before production activation", async ({
  page,
}) => {
  const errors = collectConsoleErrors(page);
  await page.route("**/api/review/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user: { id: "qualification-reviewer", email: "reviewer@example.com" },
      }),
    });
  });
  await page.route("**/api/review/onboarding", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        userId: "qualification-reviewer",
        displayName: "Qualification Reviewer",
        email: "reviewer@example.com",
        locale: "en",
        state: "qualification",
        termsAcceptedAt: "2026-07-27T00:00:00Z",
        mfaVerifiedAt: "2026-07-27T00:00:00Z",
        currentAal: "aal2",
        walkthroughCompletedAt: "2026-07-27T00:00:00Z",
        practiceCompletedAt: "2026-07-27T00:00:00Z",
        qualifiedAt: null,
        activatedAt: null,
        isTestAccount: false,
      }),
    });
  });
  await page.route(
    "**/api/review/rpc/worker_claim_reviewer_qualification",
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          qualification: {
            chunkId: "qualification-chunk",
            stationName: "Output line",
            sourceStartMs: 0,
            sourceEndMs: 900_150,
            renditionSourceStartMs: 0,
            renditionSourceEndMs: 900_150,
            mediaUrl: "https://qualification.fixture/clip.mp4",
          },
          attempts: 0,
        }),
      });
    },
  );
  await page.route("https://qualification.fixture/clip.mp4", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "video/mp4",
      path: path.resolve("demo-media/review/gate-line-20260709-1208.mp4"),
    });
  });

  await page.goto("/review");
  await expect(page.getByRole("heading", { name: "Count every finished piece" })).toBeVisible();
  await expect(page.getByText("Attempts used: 0 of 3")).toBeVisible();
  await expect(page.getByRole("button", { name: "+1" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Submit qualification" })).toBeDisabled();

  await page.getByRole("button", { name: "+1" }).click();
  await expect(page.getByText("1", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByText("0", { exact: true })).toBeVisible();
  await page.screenshot({
    path: "e2e-audit/shots/reviewer-qualification.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("button", { name: "+1" })).toBeVisible();
  await page.screenshot({
    path: "e2e-audit/shots/reviewer-qualification-mobile.png",
    fullPage: true,
  });
  assertNoConsoleErrors(errors);
});

test("qualification attempt limit has a clear help path", async ({ page }) => {
  const errors = collectConsoleErrors(page);
  await page.route("**/api/review/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user: { id: "qualification-reviewer", email: "reviewer@example.com" },
      }),
    });
  });
  await page.route("**/api/review/onboarding", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        userId: "qualification-reviewer",
        displayName: "Qualification Reviewer",
        email: "reviewer@example.com",
        locale: "en",
        state: "qualification",
        termsAcceptedAt: "2026-07-27T00:00:00Z",
        mfaVerifiedAt: "2026-07-27T00:00:00Z",
        currentAal: "aal2",
        walkthroughCompletedAt: "2026-07-27T00:00:00Z",
        practiceCompletedAt: "2026-07-27T00:00:00Z",
        qualifiedAt: null,
        activatedAt: null,
        isTestAccount: false,
      }),
    });
  });
  await page.route(
    "**/api/review/rpc/worker_claim_reviewer_qualification",
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          qualification: {
            chunkId: "qualification-chunk",
            stationName: "Output line",
            sourceStartMs: 0,
            sourceEndMs: 90_000,
            renditionSourceStartMs: 0,
            renditionSourceEndMs: 90_000,
            mediaUrl: "https://qualification.fixture/clip.mp4",
          },
          attempts: 3,
        }),
      });
    },
  );
  await page.route("**/api/review/rpc/worker_request_support", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify("support-request-id"),
    });
  });

  await page.goto("/review");
  await expect(page.getByRole("heading", { name: "Qualification paused" })).toBeVisible();
  await page.getByRole("button", { name: "Request help" }).click();
  await expect(page.getByRole("status")).toContainText("Request sent");
  assertNoConsoleErrors(errors);
});
