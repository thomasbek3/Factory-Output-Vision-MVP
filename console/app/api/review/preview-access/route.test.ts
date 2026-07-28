import { afterEach, describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "@/app/api/review/preview-access/route";
import { reviewPreviewCookieName } from "@/lib/reviewPreviewPass";

describe("review preview access route", () => {
  afterEach(() => {
    delete process.env.REVIEW_PREVIEW_ACCESS_TOKEN;
  });

  it("sets a persistent HttpOnly pass and removes the token from the destination", async () => {
    process.env.REVIEW_PREVIEW_ACCESS_TOKEN = "temporary-preview-secret";
    const response = await GET(
      new NextRequest(
        "https://factoryvision-review.vercel.app/api/review/preview-access?token=temporary-preview-secret",
      ),
    );

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "https://factoryvision-review.vercel.app/review",
    );
    const cookie = response.headers.get("set-cookie") ?? "";
    expect(cookie).toContain(`${reviewPreviewCookieName}=`);
    expect(cookie).toContain("HttpOnly");
    expect(cookie).toContain("SameSite=lax");
    expect(cookie).not.toContain("temporary-preview-secret");
  });

  it("rejects an invalid pass", async () => {
    process.env.REVIEW_PREVIEW_ACCESS_TOKEN = "temporary-preview-secret";
    const response = await GET(
      new NextRequest(
        "https://factoryvision-review.vercel.app/api/review/preview-access?token=wrong",
      ),
    );

    expect(response.status).toBe(403);
    expect(response.headers.get("set-cookie")).toBeNull();
  });
});
