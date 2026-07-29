import { expect, test } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers";

const required = [
  "FV_OWNER_QA_EMAIL",
  "FV_OWNER_QA_PASSWORD",
  "FV_OWNER_QA_FACTORY_ID",
  "NEXT_PUBLIC_SUPABASE_URL",
  "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
] as const;
const missing = required.filter((name) => !process.env[name]);
const requireLive = process.env.FV_REQUIRE_LIVE_OWNER_QA === "1";

if (requireLive && missing.length) {
  throw new Error(
    `Live owner QA is required, but these variables are missing: ${missing.join(", ")}`,
  );
}

test.describe("Owner V2 authenticated QA", () => {
  test.skip(missing.length > 0, "Live owner QA credentials are not configured.");

  test("uses the authenticated owner state and renders only durable owner truth", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    const factoryId = encodeURIComponent(
      process.env.FV_OWNER_QA_FACTORY_ID as string,
    );
    const routes = [
      ["/", "Today"],
      ["/projects", "Projects"],
      [
        "/stations",
        /^(Stations|No stations configured|No project assigned|.+ station performance)$/,
      ],
      ["/workforce", "Workforce"],
      ["/history", "History"],
      ["/alerts", "Alerts"],
      ["/settings", "Settings"],
    ] as const;

    for (const [pathname, heading] of routes) {
      await page.goto(`${pathname}?factory_id=${factoryId}`);
      await expect(
        page.getByRole("heading", {
          name: heading,
          exact: typeof heading === "string",
        }),
      ).toBeVisible();
      await expect(page.getByText("Preview data", { exact: true })).toHaveCount(0);
      await expect(
        page.getByText("No demo or estimated values have been substituted.", {
          exact: false,
        }),
      ).toHaveCount(0);
    }
    await page.goto(`/?factory_id=${factoryId}`);
    await expect(page.getByRole("heading", { name: "Today" })).toBeVisible();
    await page.screenshot({
      path: "e2e-audit/shots/owner-v2-live-authenticated.png",
      fullPage: false,
    });
    assertNoConsoleErrors(errors);
  });
});
