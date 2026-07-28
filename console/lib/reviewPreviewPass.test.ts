import { afterEach, describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import {
  hasReviewPreviewPass,
  reviewPreviewCookieName,
  reviewPreviewCookieValue,
  validReviewPreviewToken,
} from "@/lib/reviewPreviewPass";

describe("review preview pass", () => {
  afterEach(() => {
    delete process.env.REVIEW_PREVIEW_ACCESS_TOKEN;
  });

  it("accepts the configured bearer token without storing it in the cookie", () => {
    process.env.REVIEW_PREVIEW_ACCESS_TOKEN = "temporary-preview-secret";

    expect(validReviewPreviewToken("temporary-preview-secret")).toBe(true);
    expect(validReviewPreviewToken("wrong-secret")).toBe(false);
    expect(reviewPreviewCookieValue()).not.toBe("temporary-preview-secret");
  });

  it("recognizes only a correctly signed preview cookie", () => {
    process.env.REVIEW_PREVIEW_ACCESS_TOKEN = "temporary-preview-secret";
    const signed = reviewPreviewCookieValue();
    const request = new NextRequest("https://factoryvision-review.vercel.app/review", {
      headers: {
        cookie: `${reviewPreviewCookieName}=${signed}`,
      },
    });

    expect(hasReviewPreviewPass(request)).toBe(true);
    expect(
      hasReviewPreviewPass(
        new NextRequest("https://factoryvision-review.vercel.app/review"),
      ),
    ).toBe(false);
  });
});
