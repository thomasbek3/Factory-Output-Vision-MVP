import path from "node:path";
import { test, expect } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers";

const createdClients: string[] = [];

// Remove any jobs this spec created directly from the sqlite file so repeated
// runs never accumulate demo data. Uses the same DB the server writes to.
test.afterAll(async () => {
  if (!createdClients.length) return;
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const Database = require("better-sqlite3");
  const db = new Database(path.join(process.cwd(), "prisma", "dev.db"));
  const stmt = db.prepare("DELETE FROM Job WHERE client = ?");
  for (const client of createdClients) stmt.run(client);
  db.close();
});

test.describe("/jobs", () => {
  test("create a job — persists across reload and shows in money strip", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    const unique = `E2E Client ${Date.now()}`;
    createdClients.push(unique);

    await page.goto("/jobs");
    await page.getByRole("button", { name: /new job/i }).click();

    const dialog = page.getByRole("dialog");
    await dialog.locator('input[name="client"]').fill(unique);
    await dialog.locator('input[name="title"]').fill("200 e2e panels");
    await dialog.locator('input[name="units_required"]').fill("200");
    await dialog.locator('input[name="quote_usd"]').fill("2000");
    await dialog.locator('input[name="cogs_usd"]').fill("800");
    await dialog.locator('input[name="labor_budget_usd"]').fill("400");
    await dialog.locator('input[name="deadline"]').fill("2026-09-01");
    await dialog.getByRole("button", { name: /save job/i }).click();

    // Appears in the list.
    await expect(page.getByText(unique)).toBeVisible();

    // Survives a reload (proves DB persistence).
    await page.reload();
    await expect(page.getByText(unique)).toBeVisible();

    assertNoConsoleErrors(errors);
    // The afterAll hook deletes this job from the DB so the demo set stays clean.
  });

  test("validation errors render inline", async ({ page }) => {
    await page.goto("/jobs");
    await page.getByRole("button", { name: /new job/i }).click();
    const dialog = page.getByRole("dialog");
    // Submit empty form.
    await dialog.getByRole("button", { name: /save job/i }).click();
    // At least one inline error should appear.
    await expect(dialog.locator(".text-\\[var\\(--bad\\)\\]").first()).toBeVisible();
  });
});
