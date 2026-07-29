import { mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { expect, test as setup } from "@playwright/test";

const required = [
  "FV_OWNER_QA_EMAIL",
  "FV_OWNER_QA_PASSWORD",
  "FV_OWNER_QA_FACTORY_ID",
  "NEXT_PUBLIC_SUPABASE_URL",
  "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
] as const;
const missing = required.filter((name) => !process.env[name]);
const requireLive = process.env.FV_REQUIRE_LIVE_OWNER_QA === "1";
const ownerStorageState = "test-results/.auth/owner.json";

if (requireLive && missing.length) {
  throw new Error(
    `Live owner QA is required, but these variables are missing: ${missing.join(", ")}`,
  );
}

setup.skip(missing.length > 0, "Live owner QA credentials are not configured.");

setup("authenticate the dedicated owner QA identity", async ({
  page,
  baseURL,
}) => {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL as string;
  const publishableKey = process.env
    .NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY as string;
  const tokenResponse = await page.request.post(
    `${supabaseUrl}/auth/v1/token?grant_type=password`,
    {
      headers: {
        apikey: publishableKey,
        "Content-Type": "application/json",
      },
      data: {
        email: process.env.FV_OWNER_QA_EMAIL,
        password: process.env.FV_OWNER_QA_PASSWORD,
      },
    },
  );
  expect(tokenResponse.ok()).toBe(true);
  const token = (await tokenResponse.json()) as {
    access_token: string;
    refresh_token: string;
    expires_in: number;
  };
  const origin = new URL(baseURL as string).origin;
  const sessionResponse = await page.request.post("/api/owner/session", {
    headers: {
      Origin: origin,
      "Content-Type": "application/json",
    },
    data: {
      action: "completePasswordless",
      accessToken: token.access_token,
      refreshToken: token.refresh_token,
      expiresIn: token.expires_in,
    },
  });
  const sessionPayloadText = await sessionResponse.text();
  expect(
    sessionResponse.ok(),
    `Owner session returned ${sessionResponse.status()}: ${sessionPayloadText}`,
  ).toBe(true);

  const authorization = JSON.parse(sessionPayloadText) as {
    factories?: Array<{ id?: string }>;
  };
  expect(
    authorization.factories?.some(
      (factory) => factory.id === process.env.FV_OWNER_QA_FACTORY_ID,
    ),
  ).toBe(true);

  const factoryId = process.env.FV_OWNER_QA_FACTORY_ID as string;
  const factoryResponse = await page.request.get(
    `${supabaseUrl}/rest/v1/factories?id=eq.${encodeURIComponent(factoryId)}&select=id,is_test`,
    {
      headers: {
        apikey: publishableKey,
        Authorization: `Bearer ${token.access_token}`,
      },
    },
  );
  expect(factoryResponse.ok()).toBe(true);
  expect(await factoryResponse.json()).toEqual([
    { id: factoryId, is_test: true },
  ]);

  mkdirSync(dirname(ownerStorageState), { recursive: true });
  await page.context().storageState({ path: ownerStorageState });
});
