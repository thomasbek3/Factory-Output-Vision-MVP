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
const BASE_URL = `http://localhost:${PORT}`;
const OWNER_LIVE_ENV = [
  "FV_OWNER_QA_EMAIL",
  "FV_OWNER_QA_PASSWORD",
  "FV_OWNER_QA_FACTORY_ID",
  "NEXT_PUBLIC_SUPABASE_URL",
  "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
] as const;
const OWNER_LIVE_CONFIGURED = OWNER_LIVE_ENV.every(
  (name) => Boolean(process.env[name]),
);
const OWNER_STORAGE_STATE = "test-results/.auth/owner.json";

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
      testIgnore: [
        /owner-v2-live\.setup\.ts/,
        /owner-v2-live\.spec\.ts/,
      ],
    },
    {
      name: "owner-auth-setup",
      testMatch: /owner-v2-live\.setup\.ts/,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "owner-live",
      testMatch: /owner-v2-live\.spec\.ts/,
      dependencies: ["owner-auth-setup"],
      use: {
        ...devices["Desktop Chrome"],
        storageState: OWNER_LIVE_CONFIGURED
          ? OWNER_STORAGE_STATE
          : undefined,
      },
    },
  ],
  webServer: {
    command: "bash scripts/serve.sh",
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
