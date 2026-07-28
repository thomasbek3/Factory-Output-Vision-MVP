import { describe, expect, it } from "vitest";
import {
  isPlausibleReviewerEmail,
  normalizeReviewerEmail,
  passwordlessPublicBaseUrl,
  passwordlessRedirectUrl,
} from "@/lib/reviewerPasswordless";

describe("reviewer passwordless sign-in", () => {
  it("builds a localized login callback without an invitation token", () => {
    const redirect = new URL(
      passwordlessRedirectUrl("https://factoryvision-review.vercel.app", "es"),
    );
    expect(redirect.pathname).toBe("/review/welcome");
    expect(redirect.searchParams.get("mode")).toBe("login");
    expect(redirect.searchParams.get("lang")).toBe("es");
    expect(redirect.searchParams.has("invitation")).toBe(false);
  });

  it("normalizes and validates reviewer emails", () => {
    expect(normalizeReviewerEmail(" Worker@Example.com ")).toBe(
      "worker@example.com",
    );
    expect(isPlausibleReviewerEmail("worker@example.com")).toBe(true);
    expect(isPlausibleReviewerEmail("not-an-email")).toBe(false);
  });

  it("requires a configured callback origin in production", () => {
    expect(
      passwordlessPublicBaseUrl(
        "https://factoryvision-review.vercel.app/review",
        "https://preview.example",
        true,
      ),
    ).toBe("https://factoryvision-review.vercel.app");
    expect(() =>
      passwordlessPublicBaseUrl(
        undefined,
        "https://forged-host.example",
        true,
      ),
    ).toThrow("REVIEW_PUBLIC_BASE_URL");
  });
});
