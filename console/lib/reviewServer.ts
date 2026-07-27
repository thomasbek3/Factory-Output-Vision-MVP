import { NextRequest, NextResponse } from "next/server";

const projectUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

export const reviewAccessCookie = "fv_review_access";
export const reviewRefreshCookie = "fv_review_refresh";

export function reviewServerConfig() {
  if (!projectUrl || !publishableKey) {
    throw new Error("Supabase reviewer configuration is missing.");
  }
  return { projectUrl, publishableKey };
}

export function reviewerAccessToken(request: NextRequest) {
  return request.cookies.get(reviewAccessCookie)?.value ?? null;
}

export function reviewerRefreshToken(request: NextRequest) {
  return request.cookies.get(reviewRefreshCookie)?.value ?? null;
}

export function setReviewerCookies(
  request: NextRequest,
  response: NextResponse,
  accessToken: string,
  refreshToken: string,
  expiresIn: number,
) {
  const common = {
    httpOnly: true,
    sameSite: "strict" as const,
    secure: request.nextUrl.protocol === "https:",
    path: "/",
  };
  response.cookies.set(reviewAccessCookie, accessToken, {
    ...common,
    maxAge: expiresIn,
  });
  response.cookies.set(reviewRefreshCookie, refreshToken, {
    ...common,
    maxAge: 60 * 60 * 24 * 30,
  });
}

export function clearReviewerCookies(request: NextRequest, response: NextResponse) {
  const secure = request.nextUrl.protocol === "https:";
  response.cookies.set(reviewAccessCookie, "", {
    httpOnly: true,
    sameSite: "strict",
    secure,
    path: "/",
    maxAge: 0,
  });
  response.cookies.set(reviewRefreshCookie, "", {
    httpOnly: true,
    sameSite: "strict",
    secure,
    path: "/",
    maxAge: 0,
  });
}
