import { defineConfig, devices } from "@playwright/test";

/**
 * E2E config for the FactoryVision console.
 *
 * Reuses the already-running production server on 127.0.0.1:3000 (the
 * launchd-supervised `next start`). If nothing is listening, it starts one via
 * scripts/serve.sh. reuseExistingServer keeps the harness fast and means these
 * specs test the SAME artifact the owner hits through the funnel.
 */
const PORT = process.env.FV_CONSOLE_PORT ?? "3000";
const BASE_URL = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: [["list"]],
  timeout: 30_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    video: "off",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "bash scripts/serve.sh",
    url: BASE_URL,
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
