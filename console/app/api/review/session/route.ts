import { NextRequest, NextResponse } from "next/server";
import {
  authorizeReviewerAccessToken,
  clearReviewerCookies,
  reviewServerConfig,
  reviewerAccessToken,
  setReviewerCookies,
} from "@/lib/reviewServer";

export const dynamic = "force-dynamic";

type AuthPayload = {
  access_token?: string;
  refresh_token?: string;
  expires_in?: number;
  user?: { id: string; email?: string };
  error_description?: string;
  msg?: string;
};

async function consumeInvitation(
  accessToken: string,
  invitationToken: string,
  config: ReturnType<typeof reviewServerConfig>,
) {
  const response = await fetch(
    `${config.projectUrl}/rest/v1/rpc/worker_accept_reviewer_invitation`,
    {
      method: "POST",
      headers: {
        apikey: config.publishableKey,
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ p_invitation_token: invitationToken }),
      cache: "no-store",
    },
  );
  const result = (await response.json()) as {
    accepted?: boolean;
    reason?: string;
  };
  if (!response.ok || !result.accepted) {
    throw new Error(result.reason ?? "invalid");
  }
}

export async function GET(request: NextRequest) {
  const token = reviewerAccessToken(request);
  if (!token) return Response.json({ user: null });
  const config = reviewServerConfig();
  const response = await fetch(`${config.projectUrl}/auth/v1/user`, {
    headers: {
      apikey: config.publishableKey,
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });
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
  const config = reviewServerConfig();
  const body = (await request.json()) as {
    email?: string;
    password?: string;
    accessToken?: string;
    refreshToken?: string;
    invitationToken?: string;
  };
  if (body.accessToken && body.refreshToken) {
    if (!body.invitationToken) {
      return Response.json(
        { error: "Invitation token is required." },
        { status: 401 },
      );
    }
    const userResponse = await fetch(`${config.projectUrl}/auth/v1/user`, {
      headers: {
        apikey: config.publishableKey,
        Authorization: `Bearer ${body.accessToken}`,
      },
      cache: "no-store",
    });
    if (!userResponse.ok) {
      return Response.json({ error: "Invite session is invalid or expired." }, { status: 401 });
    }
    const user = (await userResponse.json()) as { id: string; email?: string };
    try {
      await consumeInvitation(body.accessToken, body.invitationToken, config);
      if (!(await authorizeReviewerAccessToken(body.accessToken))) {
        throw new Error("SESSION_NOT_AUTHORIZED");
      }
    } catch {
      return Response.json(
        { error: "Invite session is invalid, expired, revoked, or already used." },
        { status: 401 },
      );
    }
    const output = NextResponse.json({
      user: { id: user.id, email: user.email ?? "" },
    });
    setReviewerCookies(request, output, body.accessToken, body.refreshToken, 3600);
    return output;
  }
  const response = await fetch(
    `${config.projectUrl}/auth/v1/token?grant_type=password`,
    {
      method: "POST",
      headers: {
        apikey: config.publishableKey,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email: body.email, password: body.password }),
      cache: "no-store",
    },
  );
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
