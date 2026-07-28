import { createHmac, timingSafeEqual } from "node:crypto";
import type { NextRequest } from "next/server";

export const reviewPreviewCookieName = "factoryvision_review_preview";

function previewSecret() {
  return process.env.REVIEW_PREVIEW_ACCESS_TOKEN?.trim() ?? "";
}

function safelyEqual(left: string, right: string) {
  const leftBytes = Buffer.from(left);
  const rightBytes = Buffer.from(right);
  return (
    leftBytes.length === rightBytes.length &&
    timingSafeEqual(leftBytes, rightBytes)
  );
}

export function validReviewPreviewToken(candidate: string | null) {
  const secret = previewSecret();
  return Boolean(secret && candidate && safelyEqual(candidate, secret));
}

export function reviewPreviewCookieValue() {
  const secret = previewSecret();
  if (!secret) return null;
  return createHmac("sha256", secret)
    .update("factoryvision-review-preview-v1")
    .digest("base64url");
}

export function hasReviewPreviewPass(request: NextRequest) {
  const expected = reviewPreviewCookieValue();
  const actual = request.cookies.get(reviewPreviewCookieName)?.value;
  return Boolean(expected && actual && safelyEqual(actual, expected));
}
