import { createHash } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import {
  authorizeReviewerAccessToken,
  clearReviewerCookies,
  reviewerAccessToken,
  setReviewerCookies,
} from "@/lib/reviewServer";
import { authFetch, callWorkerRpc, supabaseFetch } from "@/lib/workerPortalServer";
import {
  isPlausibleReviewerEmail,
  normalizeReviewerEmail,
  passwordlessPublicBaseUrl,
  passwordlessRedirectUrl,
  type PasswordlessLanguage,
} from "@/lib/reviewerPasswordless";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type AuthPayload = {
  access_token?: string;
  refresh_token?: string;
  expires_in?: number;
  user?: { id: string; email?: string };
  error_description?: string;
  msg?: string;
};

async function consumeInvitation(accessToken: string, invitationToken: string) {
  const result = (await callWorkerRpc(
    "worker_accept_reviewer_invitation",
    { p_invitation_token: invitationToken },
    { accessToken },
  )) as { accepted?: boolean; reason?: string } | null;
  if (!result?.accepted) {
    throw new Error(result?.reason ?? "invalid");
  }
}

function requestIp(request: NextRequest) {
  return (
    request.headers.get("x-vercel-forwarded-for") ??
    request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ??
    "unknown"
  );
}

function sha256(value: string) {
  return createHash("sha256").update(value).digest("hex");
}

async function passwordlessRequestAllowed(request: NextRequest, email: string) {
  // Rate-limit RPC is anonymous (no bearer): plain Supabase POST.
  const response = await supabaseFetch("/rest/v1/rpc/check_passwordless_login_rate", {
    method: "POST",
    body: JSON.stringify({
      p_email_hash: sha256(email),
      p_ip_hash: sha256(requestIp(request)),
    }),
  });
  if (!response.ok) throw new Error("PASSWORDLESS_RATE_LIMIT_UNAVAILABLE");
  return (await response.json()) === true;
}

export async function GET(request: NextRequest) {
  const token = reviewerAccessToken(request);
  if (!token) return Response.json({ user: null });
  const response = await authFetch("/user", { bearerToken: token });
  if (!response.ok) return Response.json({ user: null });
  const user = (await response.json()) as { id: string; email?: string };
  if (!(await authorizeReviewerAccessToken(token))) {
    const output = NextResponse.json({ user: null });
    clearReviewerCookies(request, output);
    return output;
  }
  return Response.json({ user: { id: user.id, email: user.email ?? "" } });
}

export async function POST(request: NextRequest) {
  const body = (await request.json()) as {
    action?: "requestPasswordless" | "completePasswordless";
    email?: string;
    password?: string;
    language?: PasswordlessLanguage;
    expiresIn?: number;
    accessToken?: string;
    refreshToken?: string;
    invitationToken?: string;
  };
  if (body.action === "requestPasswordless") {
    const email = normalizeReviewerEmail(body.email ?? "");
    if (!isPlausibleReviewerEmail(email)) {
      return Response.json(
        { error: "Enter a valid email address." },
        { status: 400 },
      );
    }
    let allowed = false;
    try {
      allowed = await passwordlessRequestAllowed(request, email);
    } catch {
      return Response.json(
        { error: "Sign-in is temporarily unavailable." },
        { status: 503 },
      );
    }
    if (!allowed) {
      return Response.json(
        { error: "Please wait before requesting another sign-in link." },
        { status: 429 },
      );
    }
    const redirectTo = passwordlessRedirectUrl(
      passwordlessPublicBaseUrl(
        process.env.REVIEW_PUBLIC_BASE_URL,
        request.nextUrl.origin,
        process.env.NODE_ENV === "production",
      ),
      body.language === "es" ? "es" : "en",
    );
    const response = await authFetch(
      `/otp?redirect_to=${encodeURIComponent(redirectTo)}`,
      {
        method: "POST",
        body: JSON.stringify({
          email,
          data: {},
          create_user: false,
        }),
      },
    );
    if (!response.ok) {
      if (response.status === 429) {
        return Response.json(
          { error: "Please wait before requesting another sign-in link." },
          { status: 429 },
        );
      }
      console.error("Supabase passwordless request failed", response.status);
    }
    return Response.json({ sent: true });
  }
  if (body.accessToken && body.refreshToken) {
    const completingPasswordless = body.action === "completePasswordless";
    if (!completingPasswordless && !body.invitationToken) {
      return Response.json(
        { error: "Invitation token is required." },
        { status: 401 },
      );
    }
    const userResponse = await authFetch("/user", { bearerToken: body.accessToken });
    if (!userResponse.ok) {
      return Response.json(
        {
          error: completingPasswordless
            ? "Sign-in link is invalid or expired."
            : "Invite session is invalid or expired.",
        },
        { status: 401 },
      );
    }
    const user = (await userResponse.json()) as { id: string; email?: string };
    try {
      if (!completingPasswordless) {
        await consumeInvitation(body.accessToken, body.invitationToken as string);
      }
      if (!(await authorizeReviewerAccessToken(body.accessToken))) {
        throw new Error("SESSION_NOT_AUTHORIZED");
      }
    } catch {
      return Response.json(
        {
          error: completingPasswordless
            ? "Sign-in link is invalid, expired, or not authorized."
            : "Invite session is invalid, expired, revoked, or already used.",
        },
        { status: 401 },
      );
    }
    const output = NextResponse.json({
      user: { id: user.id, email: user.email ?? "" },
    });
    const expiresIn =
      Number.isInteger(body.expiresIn) &&
      (body.expiresIn as number) >= 60 &&
      (body.expiresIn as number) <= 86_400
        ? (body.expiresIn as number)
        : 3600;
    setReviewerCookies(
      request,
      output,
      body.accessToken,
      body.refreshToken,
      expiresIn,
    );
    return output;
  }
  const response = await authFetch("/token?grant_type=password", {
    method: "POST",
    body: JSON.stringify({ email: body.email, password: body.password }),
  });
  const result = (await response.json()) as AuthPayload;
  if (
    !response.ok ||
    !result.access_token ||
    !result.refresh_token ||
    !result.expires_in ||
    !result.user
  ) {
    return Response.json(
      { error: result.error_description ?? result.msg ?? "Sign in failed." },
      { status: 401 },
    );
  }
  if (!(await authorizeReviewerAccessToken(result.access_token))) {
    return Response.json(
      { error: "This account does not have an accepted FactoryVision invitation." },
      { status: 403 },
    );
  }
  const output = NextResponse.json({
    user: { id: result.user.id, email: result.user.email ?? "" },
  });
  setReviewerCookies(
    request,
    output,
    result.access_token,
    result.refresh_token,
    result.expires_in,
  );
  return output;
}

export async function DELETE(request: NextRequest) {
  const output = NextResponse.json({ ok: true });
  clearReviewerCookies(request, output);
  return output;
}
