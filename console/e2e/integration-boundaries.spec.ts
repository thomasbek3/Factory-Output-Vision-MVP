import { expect, test, type Page } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers";

const factoryId = "10000000-0000-0000-0000-000000000001";

async function clearRoleCookies(page: Page) {
  await page.context().clearCookies();
}

async function setRoleCookie(
  page: Page,
  name: "fv_owner_access" | "fv_review_access" | "fv_ops_access",
  baseURL: string,
) {
  await clearRoleCookies(page);
  await page.context().addCookies([
    {
      name,
      value: `${name}-test-token`,
      url: new URL(baseURL).origin,
      httpOnly: true,
      sameSite: "Strict",
    },
  ]);
}

test.describe("surface integration boundaries", () => {
  test("anonymous owner and ops surfaces fail closed while retired routes stay absent", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);

    await page.goto("/");
    await expect(page).toHaveURL(/\/sign-in$/);

    await page.goto("/ops");
    await expect(page).toHaveURL(/\/ops\/sign-in$/);

    expect((await page.request.get(`/api/owner/projects?factory_id=${factoryId}`)).status())
      .toBe(401);
    expect((await page.request.get("/api/ops/snapshot")).status()).toBe(401);
    expect((await page.request.get("/api/jobs")).status()).toBe(404);
    expect((await page.request.get("/tv")).status()).toBe(404);
    expect((await page.request.get("/replay")).status()).toBe(404);

    assertNoConsoleErrors(errors);
  });

  test("foreign role cookies never satisfy owner or ops middleware", async ({
    page,
    baseURL,
  }) => {
    if (!baseURL) throw new Error("Playwright baseURL is required.");
    await setRoleCookie(page, "fv_review_access", baseURL);
    expect((await page.request.get(`/api/owner/projects?factory_id=${factoryId}`)).status())
      .toBe(401);
    expect((await page.request.get("/api/ops/snapshot")).status()).toBe(401);

    await setRoleCookie(page, "fv_owner_access", baseURL);
    expect((await page.request.get("/api/ops/snapshot")).status()).toBe(401);

    await setRoleCookie(page, "fv_ops_access", baseURL);
    expect((await page.request.get(`/api/owner/projects?factory_id=${factoryId}`)).status())
      .toBe(401);
  });

  test("review handlers deny anonymous, owner-only, and ops-only requests", async ({
    page,
    baseURL,
  }) => {
    if (!baseURL) throw new Error("Playwright baseURL is required.");
    for (const roleCookie of [
      null,
      "fv_owner_access",
      "fv_ops_access",
    ] as const) {
      if (roleCookie) await setRoleCookie(page, roleCookie, baseURL);
      else await clearRoleCookies(page);

      expect(
        (
          await page.request.post(
            "/api/review/rpc/worker_daily_progress",
            { data: {} },
          )
        ).status(),
      ).toBe(401);
      expect(
        (await page.request.post("/api/review/password", {
          data: { password: "not-a-reviewer-session" },
        })).status(),
      ).toBe(401);
      expect((await page.request.get("/api/review/onboarding")).status()).toBe(401);
      expect((await page.request.get("/api/review/mfa")).status()).toBe(401);
    }
  });

  test("review remains publicly routable but exposes no work without reviewer authorization", async ({
    page,
    baseURL,
  }) => {
    if (!baseURL) throw new Error("Playwright baseURL is required.");
    const errors = collectConsoleErrors(page);
    for (const roleCookie of [null, "fv_owner_access"] as const) {
      if (roleCookie) await setRoleCookie(page, roleCookie, baseURL);
      else await clearRoleCookies(page);
      await page.goto("/review");
      await expect(
        page.getByRole("heading", { name: "Today's work" }),
      ).toBeVisible();
      await expect(
        page.getByText("Enter your email. No password needed."),
      ).toBeVisible();
      await expect(page.locator("[data-review-route='ready']")).toHaveCount(0);
    }
    assertNoConsoleErrors(errors);
  });

  test("preview surfaces are labeled, read-only, and make no live role API requests", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    const liveRequests: string[] = [];
    page.on("request", (request) => {
      const pathname = new URL(request.url()).pathname;
      if (
        pathname.startsWith("/api/owner/")
        || pathname.startsWith("/api/ops/")
      ) {
        liveRequests.push(pathname);
      }
    });

    const previews = [
      ["/owner-preview", "Today"],
      ["/owner-preview/stations", "Press Bay North station performance"],
      ["/owner-preview/history", "History preview"],
      ["/owner-preview/tv", "Owner display preview"],
      ["/ops-preview", "FactoryVision ops"],
    ] as const;

    for (const [path, heading] of previews) {
      await page.goto(path);
      await expect(page.getByRole("heading", { name: heading })).toBeVisible();
      await expect(page.getByText("Preview data", { exact: true })).toBeVisible();
      if (path === "/owner-preview/tv") {
        await expect(page.getByText(/read-only factory-floor display/i)).toBeVisible();
      }
    }

    expect(liveRequests).toEqual([]);
    assertNoConsoleErrors(errors);
  });
});
