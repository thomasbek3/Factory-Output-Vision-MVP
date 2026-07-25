import { test, expect } from "@playwright/test";

/**
 * G3 — demo/dev language purge. Owner surfaces must never show demo/dev/pitch
 * jargon. We assert on what an owner can actually read: visible text plus the
 * hoverable/announced attributes (title, aria-label, placeholder). Raw asset
 * URLs like `/api/media/.../foo.mp4` in a `src=` attribute are not language and
 * are intentionally out of scope.
 */
const OWNER_ROUTES = ["/", "/replay", "/jobs", "/stations", "/settings", "/history", "/alerts"];
const FORBIDDEN = /checkpoint|\bv0\b|\bdemo\b|\bMP4\b|\bbucket\b|probe|smoke/i;

test.describe("G3 owner-surface language", () => {
  for (const route of OWNER_ROUTES) {
    test(`no demo/dev language on ${route}`, async ({ page }) => {
      await page.goto(route, { waitUntil: "domcontentloaded" });
      // Live media requests can remain open indefinitely; hydration is the gate.
      await page.locator("body").waitFor({ state: "visible" });
      await page.waitForTimeout(500);
      const readable = await page.evaluate(() => {
        const parts = [document.body.innerText];
        document.querySelectorAll("[title],[aria-label],[placeholder]").forEach((el) => {
          parts.push(
            el.getAttribute("title") ?? "",
            el.getAttribute("aria-label") ?? "",
            el.getAttribute("placeholder") ?? "",
          );
        });
        return parts.join("\n");
      });
      const offenders = readable
        .split("\n")
        .filter((line) => FORBIDDEN.test(line))
        .map((line) => line.trim());
      expect(offenders, `forbidden language on ${route}:\n${offenders.join("\n")}`).toEqual([]);
    });
  }

  test("no probe/smoke jobs reach the owner Jobs surface", async ({ page }) => {
    const response = await page.request.get("/api/jobs");
    expect(response.ok()).toBeTruthy();
    const { jobs } = (await response.json()) as { jobs: Array<{ client: string; title: string }> };
    const leaked = jobs.filter((job) => /probe|smoke/i.test(job.client) || /probe|smoke/i.test(job.title));
    expect(leaked, `probe/smoke jobs leaked: ${JSON.stringify(leaked)}`).toEqual([]);
  });
});
