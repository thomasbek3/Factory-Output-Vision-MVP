import { test, expect, type BrowserContext, type Page } from "@playwright/test";
import {
  assertNoConsoleErrors,
  collectConsoleErrors,
  expectVideoPlaying,
} from "./helpers";

const qaPassword = process.env.FV_QA_PASSWORD;
const requireLiveQa = process.env.FV_REQUIRE_LIVE_QA === "1";
const qaEmails = [1, 2, 3].map(
  (index) => `thomas+factoryvision-reviewer${index}-20260726@paverturf.com`,
);

async function signIn(page: Page, email: string) {
  await page.addInitScript(() => {
    window.localStorage.setItem("factoryvision-review-language", "en");
  });
  const response = await page.request.post("/api/review/session", {
    data: { email, password: qaPassword },
  });
  expect(response.ok()).toBeTruthy();
  await page.goto("/review");
  await expect(page.locator("[data-review-route='today']")).toBeVisible({
    timeout: 20_000,
  });
  await page.getByRole("button", { name: /next video|resume video/i }).click();
  await expect(page.locator("[data-review-route='ready']")).toBeVisible({
    timeout: 20_000,
  });
}

test.describe("/review durable worker loop", () => {
  test.skip(
    !qaPassword && !requireLiveQa,
    "FV_QA_PASSWORD is required for live Supabase E2E",
  );

  test("three blind reviewers share one chunk through separate durable assignments", async ({
    browser,
  }) => {
    if (!qaPassword) {
      throw new Error("FV_QA_PASSWORD is required when FV_REQUIRE_LIVE_QA=1");
    }
    test.setTimeout(120_000);
    const contexts: BrowserContext[] = [];
    try {
      for (let index = 0; index < 3; index += 1) {
        contexts.push(
          await browser.newContext({
            viewport:
              index === 2
                ? { width: 390, height: 844 }
                : { width: 1366, height: 768 },
          }),
        );
      }
      const pages = await Promise.all(contexts.map((context) => context.newPage()));
      const consoleErrors = pages.map(collectConsoleErrors);
      await Promise.all(pages.map((page, index) => signIn(page, qaEmails[index])));

      const roots = pages.map((page) => page.locator("[data-review-route='ready']"));
      const chunkIds = await Promise.all(roots.map((root) => root.getAttribute("data-review-chunk")));
      const assignmentIds = await Promise.all(
        roots.map((root) => root.getAttribute("data-assignment-id")),
      );

      expect(new Set(chunkIds).size).toBe(1);
      expect(new Set(assignmentIds).size).toBe(3);
      expect(chunkIds[0]).toBeTruthy();
      expect(assignmentIds.every(Boolean)).toBeTruthy();
      expect(
        await pages[0].evaluate(() =>
          Object.keys(window.localStorage).some((key) => key.includes("session")),
        ),
      ).toBeFalsy();

      const serializedWorkerPage = await pages[0].locator("body").innerText();
      expect(serializedWorkerPage).not.toContain(qaEmails[1]);
      expect(serializedWorkerPage).not.toContain(qaEmails[2]);
      expect(serializedWorkerPage).not.toMatch(
        /peer|consensus|expected count|AI count|queue depth/i,
      );

      await expect(pages[0].locator("video")).toBeVisible();
      await expect(pages[0].locator("video")).toHaveAttribute(
        "src",
        /supabase\.co\/storage\/v1\/object\/sign\//,
      );
      await expect
        .poll(() =>
          pages[0].locator("video").evaluate((video: HTMLVideoElement) => video.readyState),
        )
        .toBeGreaterThanOrEqual(2);
      await pages[0].getByRole("button", { name: "Get help" }).click();
      await expect(pages[0].getByRole("dialog", { name: "Get help" })).toBeVisible();
      await pages[0].getByLabel("What do you need?").fill("QA support request from live worker flow.");
      await pages[0].getByRole("button", { name: "Send" }).click();
      await expect(pages[0].getByRole("status")).toContainText(
        "Your help request was sent.",
      );
      await pages[0].getByRole("button", { name: "Play video" }).click();
      expect(await expectVideoPlaying(pages[0], "video")).toBeTruthy();

      await pages[0].screenshot({
    path: "e2e-audit/shots/worker-live-review-desktop.png",
        fullPage: true,
      });
      await pages[2].screenshot({
    path: "e2e-audit/shots/worker-live-review-mobile.png",
        fullPage: true,
      });
      await pages[0].locator("video").evaluate((video: HTMLVideoElement) => video.pause());

      const worker = pages[0];
      await worker.locator("body").click();
      await worker.keyboard.press("Space");
      await expect(worker.getByTestId("running-tally")).toHaveText("0");
      await worker.keyboard.press("j");
      await worker.keyboard.press("j");
      await worker.keyboard.press("j");
      await worker.keyboard.press("z");
      await expect(worker.getByTestId("running-tally")).toHaveText("2");
      await expect(worker.getByTestId("save-state")).toContainText("Saved", {
        timeout: 15_000,
      });

      await worker.reload();
      await expect(worker.locator("[data-review-route='today']")).toBeVisible();
      await worker.getByRole("button", { name: "Resume video" }).click();
      await expect(worker.locator("[data-review-route='ready']")).toBeVisible();
      await expect(worker.getByTestId("running-tally")).toHaveText("2");

      consoleErrors.forEach(assertNoConsoleErrors);
      consoleErrors.forEach((errors) => errors.splice(0));
      await contexts[0].setOffline(true);
      await worker.keyboard.press("j");
      await expect(worker.getByTestId("running-tally")).toHaveText("3");
      await expect(worker.getByTestId("save-state")).toContainText("unsaved", {
        timeout: 10_000,
      });
      await contexts[0].setOffline(false);
      await worker.getByRole("button", { name: "Retry" }).click();
      await expect(worker.getByTestId("save-state")).toContainText("Saved", {
        timeout: 15_000,
      });
      expect(consoleErrors[0].length).toBeGreaterThan(0);
      expect(
        consoleErrors[0].every((message) =>
          /ERR_INTERNET_DISCONNECTED|ERR_FAILED/.test(message),
        ),
      ).toBeTruthy();
      consoleErrors[0].splice(0);

      await worker.reload();
      await expect(worker.locator("[data-review-route='today']")).toBeVisible();
      await worker.getByRole("button", { name: "Resume video" }).click();
      await expect(worker.locator("[data-review-route='ready']")).toBeVisible();
      await expect(worker.getByTestId("running-tally")).toHaveText("3");

      await worker.getByRole("button", { name: "Finish video" }).click();
      let committedResponseWasDropped = false;
      await worker.route("**/api/review/rpc/submit_worker_assignment_v2", async (route) => {
        const response = await route.fetch();
        expect(response.ok()).toBeTruthy();
        committedResponseWasDropped = true;
        await route.abort("failed");
      });
      await worker.getByRole("button", { name: "Submit count" }).click();
      await expect(worker.getByRole("status")).toContainText("Confirm failed");
      expect(committedResponseWasDropped).toBeTruthy();
      expect(consoleErrors[0].every((message) => /ERR_FAILED/.test(message))).toBeTruthy();
      consoleErrors[0].splice(0);

      await worker.unroute("**/api/review/rpc/submit_worker_assignment_v2");
      await worker.getByRole("button", { name: "Submit count" }).click();
      await expect(worker.locator("[data-review-route='today']")).toBeVisible({
        timeout: 15_000,
      });

      consoleErrors.forEach(assertNoConsoleErrors);
    } finally {
      await Promise.all(
        contexts.map((context) => context.close().catch(() => undefined)),
      );
    }
  });
});
