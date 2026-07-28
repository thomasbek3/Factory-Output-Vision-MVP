import { NextRequest, NextResponse } from "next/server";
import {
  reviewPreviewCookieName,
  reviewPreviewCookieValue,
  validReviewPreviewToken,
} from "@/lib/reviewPreviewPass";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const token = request.nextUrl.searchParams.get("token");
  const cookieValue = reviewPreviewCookieValue();
  if (!validReviewPreviewToken(token) || !cookieValue) {
    return Response.json({ error: "PREVIEW_ACCESS_DENIED" }, { status: 403 });
  }

  const response = NextResponse.redirect(new URL("/review", request.url));
  response.cookies.set(reviewPreviewCookieName, cookieValue, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 60 * 60 * 24 * 30,
    path: "/",
  });
  response.headers.set("Cache-Control", "no-store");
  response.headers.set("Referrer-Policy", "no-referrer");
  return response;
}
