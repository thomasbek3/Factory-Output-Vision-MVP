import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { execFileSync } from "node:child_process";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers";

async function expectMobileTouchTargets(page: import("@playwright/test").Page) {
  const undersized = await page
    .locator("button:visible, a:visible, label:has(input):visible")
    .evaluateAll((elements) =>
      elements.flatMap((element) => {
        const box = element.getBoundingClientRect();
        if (box.height >= 44) return [];
        return [{
          element: element.tagName.toLowerCase(),
          name:
            element.getAttribute("aria-label")
            ?? element.textContent?.trim().replace(/\s+/g, " ")
            ?? "",
          height: box.height,
        }];
      }),
    );
  expect(undersized).toEqual([]);
}

async function settleVisual(page: import("@playwright/test").Page) {
  await page.mouse.move(1, 1);
  await page.waitForTimeout(300);
}

test.describe("Owner V2 preview", () => {
  test("renders the approved Today hierarchy without querying live owner APIs", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    const ownerApiRequests: string[] = [];
    page.on("request", (request) => {
      if (new URL(request.url()).pathname.startsWith("/api/owner/")) {
        ownerApiRequests.push(request.url());
      }
    });

    await page.setViewportSize({ width: 1536, height: 1024 });
    await page.goto("/owner-preview");

    await expect(page.getByRole("heading", { name: "Today" })).toBeVisible();
    await expect(page.getByText("Preview data", { exact: true })).toBeVisible();
    await expect(
      page.locator('[data-owner-nav-active="true"]:visible'),
    ).toHaveCount(1);
    await expect(page.locator("[data-owner-active-projects]")).toContainText(
      "Alvarez Gates",
    );
    await expect(
      page.getByRole("img", {
        name: "Alvarez Gates cumulative verified output versus required pace",
      }),
    ).toBeVisible();
    await expect(page.getByText("Verified through", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("after direct costs", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Press Bay North", { exact: true }).first()).toBeVisible();
    const projectRows = page.locator("[data-owner-active-projects] button");
    const chartExpectations = [
      { name: "Alvarez Gates", actual: "212", required: "185" },
      { name: "Omega Railings", actual: "315", required: "220" },
      { name: "Summit Frames", actual: "487", required: "270" },
    ];
    for (const expectation of chartExpectations) {
      await projectRows
        .filter({ hasText: expectation.name })
        .click();
      await expect(page.locator("[data-owner-pace-chart]")).toContainText(
        `Actual ${expectation.actual} · Required now ${expectation.required}`,
      );
    }
    await projectRows.filter({ hasText: "Alvarez Gates" }).click();
    expect(ownerApiRequests).toEqual([]);
    const stationTable = await page
      .locator("[data-owner-station-table]")
      .boundingBox();
    expect(stationTable).not.toBeNull();
    expect((stationTable?.y ?? 1024) + (stationTable?.height ?? 1)).toBeLessThanOrEqual(
      1024,
    );

    await settleVisual(page);
    await page.screenshot({
      path: "e2e-audit/shots/owner-v2-today-desktop.png",
      fullPage: false,
    });
    execFileSync(process.execPath, ["scripts/generate-owner-overlays.mjs", "today"], {
      cwd: process.cwd(),
      stdio: "pipe",
    });
    assertNoConsoleErrors(errors);
  });

  test("completes the three-step setup preview without persistence", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    const ownerApiRequests: string[] = [];
    page.on("request", (request) => {
      if (new URL(request.url()).pathname.startsWith("/api/owner/")) {
        ownerApiRequests.push(request.url());
      }
    });

    await page.setViewportSize({ width: 1536, height: 1024 });
    await page.goto("/owner-preview");
    await expect(page.locator("[data-owner-today]")).toHaveAttribute(
      "data-hydrated",
      "true",
    );
    const projectButton = page.getByRole("button", {
      name: "Project",
      exact: true,
    });
    await projectButton.click();
    assertNoConsoleErrors(errors);

    const drawer = page.getByTestId("new-project-drawer");
    await expect(drawer).toBeVisible();
    const drawerBox = await drawer.boundingBox();
    expect(drawerBox?.width).toBeGreaterThanOrEqual(620);
    expect(drawerBox?.width).toBeLessThanOrEqual(645);
    await expect(
      drawer.getByRole("heading", { name: "New production project" }),
    ).toBeVisible();
    await drawer.getByRole("button", { name: "Continue" }).click();
    const stationConfirmation = drawer.getByText(
      "Confirm suggested station",
      { exact: true },
    );
    await expect(stationConfirmation).toBeVisible();
    await stationConfirmation.click();
    await drawer.getByRole("button", { name: "Continue" }).click();
    await expect(
      drawer.getByRole("heading", { name: "Labor & goal" }),
    ).toBeVisible();
    await expect(drawer.getByText("Ana Torres", { exact: true })).toBeVisible();
    await expect(drawer.getByText("Planned margin after direct costs")).toBeVisible();

    await settleVisual(page);
    await page.screenshot({
      path: "e2e-audit/shots/owner-v2-new-project-desktop.png",
      fullPage: false,
    });
    execFileSync(process.execPath, ["scripts/generate-owner-overlays.mjs", "project"], {
      cwd: process.cwd(),
      stdio: "pipe",
    });
    await drawer.getByLabel("Loaded labor rate (optional)").fill("");
    await expect(
      drawer.getByText(
        "Add a loaded labor rate to compare output with labor expense.",
      ),
    ).toBeVisible();
    await drawer.getByRole("button", { name: "Start project" }).click();
    await expect(drawer.getByRole("alert")).toHaveText(
      "Preview data only. No project was created.",
    );
    expect(ownerApiRequests).toEqual([]);
    assertNoConsoleErrors(errors);
  });

  test("keeps Today usable without horizontal overflow on mobile", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/owner-preview");

    await expect(page.getByRole("heading", { name: "Today" })).toBeVisible();
    await expectMobileTouchTargets(page);
    await expect(page.getByRole("navigation", { name: "Owner mobile navigation" }))
      .toBeVisible();
    await page.getByRole("button", { name: "More", exact: true }).click();
    await expect(page.getByRole("link", { name: "Alerts", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Settings", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "More", exact: true }).click();
    await page.getByRole("button", { name: "Project", exact: true }).click();
    const drawer = page.getByTestId("new-project-drawer");
    await expect(drawer).toBeVisible();
    await expectMobileTouchTargets(page);
    const drawerBox = await drawer.boundingBox();
    expect(drawerBox?.width).toBeLessThanOrEqual(390);
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(390);
    await settleVisual(page);
    await page.screenshot({
      path: "e2e-audit/shots/owner-v2-today-mobile.png",
      fullPage: true,
    });
    await drawer.getByRole("button", { name: "Continue" }).click();
    await drawer
      .getByText("Confirm suggested station", { exact: true })
      .click();
    await expectMobileTouchTargets(page);
    await drawer.getByRole("button", { name: "Continue" }).click();
    await expectMobileTouchTargets(page);
    assertNoConsoleErrors(errors);
  });

  test("keeps every desktop preview destination distinct and singly active", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    await page.setViewportSize({ width: 1280, height: 800 });
    const destinations = [
      ["Projects", "/owner-preview/projects", "Projects preview"],
      ["Stations", "/owner-preview/stations", "Press Bay North station performance"],
      ["Workforce", "/owner-preview/workforce", "Workforce"],
      ["History", "/owner-preview/history", "History preview"],
      ["Alerts", "/owner-preview/alerts", "Alerts preview"],
      ["Settings", "/owner-preview/settings", "Settings preview"],
    ] as const;

    await page.goto("/owner-preview");
    for (const [label, pathname, heading] of destinations) {
      await page.getByRole("link", { name: label, exact: true }).click();
      await expect(page).toHaveURL(new RegExp(`${pathname}$`));
      await expect(page.getByRole("heading", { name: heading })).toBeVisible();
      await expect(
        page.locator('[data-owner-nav-active="true"]:visible'),
      ).toHaveCount(1);
    }
    assertNoConsoleErrors(errors);
  });

  test("matches the station and workforce hierarchy without leaking individual rankings", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    const ownerApiRequests: string[] = [];
    page.on("request", (request) => {
      if (new URL(request.url()).pathname.startsWith("/api/owner/")) {
        ownerApiRequests.push(request.url());
      }
    });
    await page.setViewportSize({ width: 1536, height: 1024 });
    await page.goto("/owner-preview/stations");
    await expect(
      page.getByRole("heading", {
        name: "Press Bay North station performance",
      }),
    ).toBeVisible();
    await expect(page.getByText("Verified good units", { exact: true })).toBeVisible();
    await expect(page.getByText("Production by 15-minute interval")).toBeVisible();
    await expect(page.getByText("Team on station")).toBeVisible();
    await expect(
      page.getByText(
        "Output is attributed to the station team unless a worker was alone and checked in.",
      ),
    ).toBeVisible();
    await expect(page.getByText("Solo interval · high confidence")).toBeVisible();
    await expect(page.getByText("Team contribution only").first()).toBeVisible();
    await expect(page.getByText(/leaderboard|ranking/i)).toHaveCount(0);
    await page.getByRole("button", { name: "Record downtime" }).click();
    const downtimeDialog = page.getByRole("dialog", {
      name: "Record downtime",
    });
    await expect(downtimeDialog).toBeVisible();
    await expect(
      downtimeDialog.getByText(
        "Preview data only. Downtime recording is disabled.",
      ),
    ).toBeVisible();
    await expect(
      downtimeDialog.getByRole("button", { name: "Preview only" }),
    ).toBeDisabled();
    await settleVisual(page);
    await page.screenshot({
      path: "e2e-audit/shots/owner-v2-downtime-desktop.png",
      fullPage: false,
    });
    await downtimeDialog
      .getByRole("button", { name: "Close downtime form" })
      .click();
    const stationAxe = await new AxeBuilder({ page })
      .include("[data-owner-station-workforce]")
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(
      stationAxe.violations.filter(
        (violation) =>
          violation.impact === "serious" || violation.impact === "critical",
      ),
    ).toEqual([]);
    await settleVisual(page);
    await page.screenshot({
      path: "e2e-audit/shots/owner-v2-station-desktop.png",
      fullPage: false,
    });
    execFileSync(process.execPath, ["scripts/generate-owner-overlays.mjs", "station"], {
      cwd: process.cwd(),
      stdio: "pipe",
    });
    await expect(page.locator("[data-owner-now-marker]")).toHaveCount(0);
    await expect(page.locator("[data-owner-verified-marker]")).toHaveCount(1);
    await page.goto("/owner-preview/stations?state=gap");
    const markerPositions = await page.evaluate(() => ({
      now: Number(
        document
          .querySelector("[data-owner-now-marker]")
          ?.getAttribute("x1"),
      ),
      verified: Number(
        document
          .querySelector("[data-owner-verified-marker]")
          ?.getAttribute("x1"),
      ),
    }));
    expect(markerPositions.now).toBeGreaterThan(markerPositions.verified);
    await expect(page.locator("[data-owner-station-workforce]")).toHaveAttribute(
      "data-owner-verification-state",
      "delayed",
    );
    await page.goto("/owner-preview/stations");
    await page.getByRole("combobox", { name: "Station", exact: true }).selectOption({
      label: "Weld Cell West",
    });
    await expect(page).toHaveURL(/station_id=20000000-0000-0000-0000-000000000002/);
    await expect(
      page.getByRole("heading", {
        name: "Weld Cell West station performance",
      }),
    ).toBeVisible();

    await page.goto("/owner-preview/workforce");
    await expect(page.getByRole("heading", { name: "Workforce" })).toBeVisible();
    await expect(page.getByText("Employee directory")).toBeVisible();
    await expect(page.getByText("Ana Torres", { exact: true })).toBeVisible();
    await expect(
      page.getByRole("columnheader", {
        name: /rank|score|individual output/i,
      }),
    ).toHaveCount(0);
    const workforceAxe = await new AxeBuilder({ page })
      .include("[data-owner-workforce]")
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(
      workforceAxe.violations.filter(
        (violation) =>
          violation.impact === "serious" || violation.impact === "critical",
      ),
    ).toEqual([]);
    await page.getByRole("button", { name: "Worker", exact: true }).click();
    const workerSheet = page.getByRole("dialog");
    await expect(
      workerSheet.getByRole("heading", { name: "Add employee" }),
    ).toBeVisible();
    await workerSheet.getByRole("button", { name: "Add employee" }).click();
    await expect(workerSheet.getByRole("alert")).toHaveText(
      "Enter the worker's name.",
    );
    await workerSheet.getByLabel("Full name").fill("Preview Worker");
    await workerSheet.getByRole("button", { name: "Add employee" }).click();
    await expect(workerSheet.getByRole("alert")).toHaveText(
      "Preview data only. No worker was added.",
    );
    expect(ownerApiRequests).toEqual([]);
    await page.screenshot({
      path: "e2e-audit/shots/owner-v2-workforce-desktop.png",
      fullPage: false,
    });
    assertNoConsoleErrors(errors);
  });

  test("keeps station and workforce controls touch-safe on mobile", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/owner-preview/stations");
    await expect(
      page.getByRole("combobox", { name: "Station", exact: true }),
    ).toBeVisible();
    await expectMobileTouchTargets(page);
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(390);
    await page.screenshot({
      path: "e2e-audit/shots/owner-v2-station-mobile.png",
      fullPage: true,
    });

    await page.goto("/owner-preview/workforce");
    await expectMobileTouchTargets(page);
    await page.getByRole("button", { name: "Worker", exact: true }).click();
    await expectMobileTouchTargets(page);
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(390);
    assertNoConsoleErrors(errors);
  });

  test("reconciles immutable closeouts through filters, expansion, evidence, and export", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    const ownerApiRequests: string[] = [];
    page.on("request", (request) => {
      if (new URL(request.url()).pathname.startsWith("/api/owner/")) {
        ownerApiRequests.push(request.url());
      }
    });
    await page.setViewportSize({ width: 1536, height: 1024 });
    await page.goto("/owner-preview/history");

    const surface = page.locator("[data-owner-history-surface]");
    await expect(surface).toBeVisible();
    await expect(page.getByText("Projects completed", { exact: true })).toBeVisible();
    await expect(page.getByText("Margin after direct costs", { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: /Alvarez Gates/ })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    await expect(page.getByText("closeout revision 2")).toBeVisible();
    await expect(page.getByText("Closeout corrected", { exact: true })).toBeVisible();
    await expect(page.getByText(/Units 404 → 407/)).toBeVisible();
    await settleVisual(page);
    await page.screenshot({
      path: "e2e-audit/shots/owner-v2-history-desktop.png",
      fullPage: false,
    });
    execFileSync(
      process.execPath,
      ["scripts/generate-owner-overlays.mjs", "history"],
      { cwd: process.cwd(), stdio: "pipe" },
    );
    const filterBar = await page
      .locator("[data-owner-history-filter-bar]")
      .boundingBox();
    expect(filterBar?.height).toBeGreaterThanOrEqual(60);
    expect(filterBar?.height).toBeLessThanOrEqual(64);
    const summaryHeights = await page
      .locator("[data-owner-history-summary-card]")
      .evaluateAll((elements) =>
        elements.map((element) => element.getBoundingClientRect().height),
      );
    expect(summaryHeights).toHaveLength(4);
    expect(summaryHeights.every((height) => height >= 124 && height <= 132)).toBe(true);
    const rowHeights = await page
      .locator("[data-owner-history-row]")
      .evaluateAll((elements) =>
        elements.map((element) => element.getBoundingClientRect().height),
      );
    expect(rowHeights.length).toBeGreaterThanOrEqual(6);
    expect(rowHeights.every((height) => height >= 56 && height <= 60)).toBe(true);
    await expect(page.locator("[data-owner-history-export]")).toHaveCSS(
      "background-color",
      "rgb(232, 116, 47)",
    );
    await expect(surface.locator(".text-good").first()).toHaveCSS(
      "color",
      "rgb(70, 194, 107)",
    );
    await expect(surface.locator(".text-bad").first()).toHaveCSS(
      "color",
      "rgb(229, 72, 77)",
    );
    await expect(surface.locator(".text-warn").first()).toHaveCSS(
      "color",
      "rgb(231, 161, 59)",
    );

    await page.getByRole("button", { name: /Omega Railings/ }).click();
    await expect(page.getByRole("button", { name: /Omega Railings/ })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    await expect(page.getByRole("button", { name: /Alvarez Gates/ })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    await page.getByRole("button", { name: /Summit Frames/ }).click();
    await expect(
      page.getByRole("button", { name: /Evidence expired/ }),
    ).toBeDisabled();
    await page.getByRole("button", { name: /Ironwood Balusters/ }).click();
    const zeroLine = page.locator("[data-owner-history-zero-line]");
    await expect(zeroLine).toBeVisible();
    await expect(page.getByText("-9", { exact: true })).toBeVisible();
    const signedAxis = await zeroLine.evaluate((element) => {
      const line = element.getBoundingClientRect();
      const chart = element.parentElement?.getBoundingClientRect();
      return chart
        ? {
            lineY: line.y,
            chartTop: chart.y,
            chartBottom: chart.y + chart.height,
          }
        : null;
    });
    expect(signedAxis).not.toBeNull();
    expect(signedAxis?.lineY).toBeGreaterThan(signedAxis?.chartTop ?? 0);
    expect(signedAxis?.lineY).toBeLessThan(signedAxis?.chartBottom ?? 0);

    await page.getByLabel("Customer").selectOption("Alvarez Contracting");
    await expect(page).toHaveURL(/customer=Alvarez(?:\+|%20)Contracting/);
    await expect(page.getByRole("button", { name: /Alvarez Gates/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Omega Railings/ })).toHaveCount(0);
    await page.getByLabel("Status").selectOption("positive_margin");
    await expect(page).toHaveURL(/status=positive_margin/);
    await page.goBack();
    await expect(page).toHaveURL(/customer=Alvarez(?:\+|%20)Contracting/);
    await expect(page).not.toHaveURL(/status=positive_margin/);
    await expect(page.getByLabel("Customer")).toHaveValue("Alvarez Contracting");
    await expect(page.getByRole("button", { name: /Omega Railings/ })).toHaveCount(0);

    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Export", exact: true }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe("factoryvision-history.csv");
    const downloadStream = await download.createReadStream();
    let csv = "";
    for await (const chunk of downloadStream) {
      csv += chunk.toString();
    }
    expect(csv).toContain("Alvarez Gates");
    expect(csv).not.toContain("Omega Railings");
    expect(csv.trim().split(/\r?\n/)).toHaveLength(2);

    const evidenceButton = page.getByRole("button", { name: /Evidence clips 12/ });
    await evidenceButton.focus();
    await evidenceButton.press("Enter");
    await expect(page.getByRole("dialog", { name: "Alvarez Gates" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Close", exact: true })).toBeFocused();
    await page.screenshot({
      path: "e2e-audit/shots/owner-v2-history-evidence-drawer.png",
      fullPage: false,
    });
    await page.keyboard.press("Tab");
    const openEvidenceLink = page.getByRole("link", { name: "Open" });
    await expect(openEvidenceLink).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByRole("button", { name: "Close", exact: true })).toBeFocused();
    await page.keyboard.press("Shift+Tab");
    await expect(openEvidenceLink).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(evidenceButton).toBeFocused();

    const axe = await new AxeBuilder({ page })
      .include("[data-owner-history-surface]")
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(
      axe.violations.filter(
        (violation) =>
          violation.impact === "serious" || violation.impact === "critical",
      ),
    ).toEqual([]);
    expect(ownerApiRequests).toEqual([]);
    assertNoConsoleErrors(errors);
  });

  test("uses a compact History list instead of the comparison table on mobile", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/owner-preview/history");
    await expect(page.getByRole("heading", { name: "History preview" })).toBeVisible();
    await expectMobileTouchTargets(page);
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(390);
    await expect(page.locator("[data-owner-history-mobile-list]")).toBeVisible();
    await expect(page.locator("[data-owner-history-table-scroll]")).toBeHidden();
    await expect(page.getByText("Verified good units", { exact: true }).first()).toBeVisible();
    await page.screenshot({
      path: "e2e-audit/shots/owner-v2-history-mobile.png",
      fullPage: true,
    });
    assertNoConsoleErrors(errors);
  });

  test("keeps the History ledger scrollable with a frozen project column on tablet", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    await page.setViewportSize({ width: 900, height: 900 });
    await page.goto("/owner-preview/history");
    const historyScroll = page.locator("[data-owner-history-table-scroll]");
    await expect(historyScroll).toBeVisible();
    const scrollState = await historyScroll.evaluate((element) => ({
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
    }));
    expect(scrollState.scrollWidth).toBeGreaterThan(scrollState.clientWidth);
    const projectCell = page
      .getByRole("button", { name: /Alvarez Gates/ })
      .locator("..");
    await expect(projectCell).toHaveCSS("position", "sticky");
    await page.screenshot({
      path: "e2e-audit/shots/owner-v2-history-tablet.png",
      fullPage: false,
    });
    assertNoConsoleErrors(errors);
  });

  test("renders empty and unavailable states without inventing operational truth", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/owner-preview/empty");
    await expect(page.getByText("No active projects", { exact: true })).toBeVisible();
    await expect(page.getByText("Pace data unavailable", { exact: true })).toBeVisible();
    await expect(
      page.getByText("Exception monitoring unavailable", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("No stations are configured for this factory.", {
        exact: true,
      }),
    ).toBeVisible();

    await page.goto("/owner-preview/live-truth");
    await expect(page.getByText("DATA DELAY", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Deadline unavailable", { exact: true })).toBeVisible();
    await expect(page.getByText("Unavailable", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Assignment unavailable", { exact: true })).toBeVisible();
    await expect(page.getByText("Camera count unavailable", { exact: true })).toBeVisible();
    await expect(
      page.getByText("Exception monitoring unavailable", { exact: true }),
    ).toBeVisible();

    const verificationAlert = page
      .locator("[data-owner-attention]")
      .getByRole("link", { name: /Verification pending/ });
    await verificationAlert.focus();
    await expect(verificationAlert).toBeFocused();
    await verificationAlert.press("Enter");
    await expect(page).toHaveURL(
      /\/owner-preview\/alerts\?kind=verification$/,
    );
    await expect(
      page.getByRole("heading", { name: "Alerts preview" }),
    ).toBeVisible();

    await page.goto("/owner-preview/unavailable");
    const status = page.locator(
      '[data-owner-surface-status="unavailable"]',
    );
    await expect(status).toHaveText("Data unavailable");
    await expect(status).not.toHaveClass(/text-good|bg-good/);
    assertNoConsoleErrors(errors);
  });

  test("has no serious or critical automated accessibility violations", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1536, height: 1024 });
    await page.goto("/owner-preview");
    const results = await new AxeBuilder({ page })
      .include("body")
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    const severe = results.violations.filter((violation) =>
      violation.impact === "serious" || violation.impact === "critical"
    );
    expect(severe).toEqual([]);

    await page.getByRole("button", { name: "Project", exact: true }).click();
    const drawerResults = await new AxeBuilder({ page })
      .include('[data-testid="new-project-drawer"]')
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    const severeDrawer = drawerResults.violations.filter((violation) =>
      violation.impact === "serious" || violation.impact === "critical"
    );
    expect(severeDrawer).toEqual([]);
  });
});
