import { NextRequest, NextResponse } from "next/server";
import {
  authorizeOps,
  clearOpsCookies,
  opsAccessCookie,
  opsRefreshToken,
  opsServerConfig,
  setOpsCookies,
} from "@/lib/opsServer";

export const dynamic = "force-dynamic";

type SupabaseUser = {
  id: string;
  email?: string;
};

async function authenticatedUser(accessToken: string) {
  const config = opsServerConfig();
  const response = await fetch(`${config.projectUrl}/auth/v1/user`, {
    headers: {
      apikey: config.publishableKey,
      Authorization: `Bearer ${accessToken}`,
    },
    cache: "no-store",
  });
  return response.ok ? ((await response.json()) as SupabaseUser) : null;
}

function isSameOrigin(request: NextRequest) {
  return request.headers.get("origin") === request.nextUrl.origin;
}

export async function POST(request: NextRequest) {
  if (!isSameOrigin(request)) {
    return Response.json({ error: "OPS_SESSION_INVALID" }, { status: 403 });
  }
  const body = (await request.json().catch(() => null)) as {
    action?: "requestPasswordless" | "completePasswordless" | "refresh";
    email?: string;
    accessToken?: string;
    refreshToken?: string;
    expiresIn?: number;
  } | null;
  if (!body) {
    return Response.json({ error: "OPS_SESSION_INVALID" }, { status: 400 });
  }
  const config = opsServerConfig();

  if (body.action === "refresh") {
    const refreshToken = opsRefreshToken(request);
    if (!refreshToken) {
      return Response.json({ error: "OPS_SESSION_INVALID" }, { status: 401 });
    }
    const refreshResponse = await fetch(
      `${config.projectUrl}/auth/v1/token?grant_type=refresh_token`,
      {
        method: "POST",
        headers: {
          apikey: config.publishableKey,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
        cache: "no-store",
      },
    );
    const refreshed = (await refreshResponse.json().catch(() => null)) as {
      access_token?: string;
      refresh_token?: string;
      expires_in?: number;
    } | null;
    if (
      !refreshResponse.ok ||
      !refreshed?.access_token ||
      !refreshed.refresh_token
    ) {
      const output = NextResponse.json(
        { error: "OPS_SESSION_INVALID" },
        { status: 401 },
      );
      clearOpsCookies(request, output);
      return output;
    }
    const authRequest = new NextRequest(request.url, {
      headers: { cookie: `${opsAccessCookie}=${refreshed.access_token}` },
    });
    const [user, authorization] = await Promise.all([
      authenticatedUser(refreshed.access_token),
      authorizeOps(authRequest),
    ]);
    if (!user || !authorization.authorized) {
      const output = NextResponse.json(
        { error: "OPS_ACCESS_DENIED" },
        { status: 403 },
      );
      clearOpsCookies(request, output);
      return output;
    }
    const output = NextResponse.json({
      user: { id: user.id, email: user.email ?? "" },
    });
    setOpsCookies(
      request,
      output,
      refreshed.access_token,
      refreshed.refresh_token,
      refreshed.expires_in ?? 3600,
    );
    return output;
  }

  if (body.action === "requestPasswordless") {
    const email = body.email?.trim().toLowerCase() ?? "";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return Response.json(
        { error: "Enter a valid email address." },
        { status: 400 },
      );
    }
    const redirectTo = `${request.nextUrl.origin}/ops/sign-in`;
    const response = await fetch(
      `${config.projectUrl}/auth/v1/otp?redirect_to=${encodeURIComponent(redirectTo)}`,
      {
        method: "POST",
        headers: {
          apikey: config.publishableKey,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email, create_user: false }),
        cache: "no-store",
      },
    );
    if (!response.ok) {
      return Response.json(
        {
          error:
            response.status === 429
              ? "Please wait before requesting another sign-in link."
              : "OPS_SIGN_IN_UNAVAILABLE",
        },
        { status: response.status === 429 ? 429 : 503 },
      );
    }
    return Response.json({ sent: true });
  }

  if (
    body.action !== "completePasswordless" ||
    !body.accessToken ||
    !body.refreshToken
  ) {
    return Response.json({ error: "OPS_SESSION_INVALID" }, { status: 400 });
  }
  const user = await authenticatedUser(body.accessToken);
  if (!user) {
    return Response.json({ error: "OPS_SESSION_INVALID" }, { status: 401 });
  }
  const authRequest = new NextRequest(request.url, {
    headers: { cookie: `${opsAccessCookie}=${body.accessToken}` },
  });
  const authorization = await authorizeOps(authRequest);
  if (!authorization.authorized) {
    return Response.json({ error: "OPS_ACCESS_DENIED" }, { status: 403 });
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
  setOpsCookies(
    request,
    output,
    body.accessToken,
    body.refreshToken,
    expiresIn,
  );
  return output;
}

export async function DELETE(request: NextRequest) {
  if (!isSameOrigin(request)) {
    return Response.json({ error: "OPS_SESSION_INVALID" }, { status: 403 });
  }
  const output = NextResponse.json({ ok: true });
  clearOpsCookies(request, output);
  return output;
}
