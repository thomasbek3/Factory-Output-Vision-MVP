import { NextRequest, NextResponse } from "next/server";
import { supabaseFetch } from "@/lib/workerPortalServer";

const projectUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

// Config is re-declared locally (instead of imported from workerPortalServer)
// to avoid a circular import; both modules read the same env vars.
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

export async function authorizeReviewerAccessToken(accessToken: string) {
  const response = await supabaseFetch("/rest/v1/rpc/worker_authorize_reviewer_session", {
    method: "POST",
    body: "{}",
    accessToken,
  });
  if (!response.ok) return false;
  const result = (await response.json()) as { authorized?: boolean };
  return result.authorized === true;
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
