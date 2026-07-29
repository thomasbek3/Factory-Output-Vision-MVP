import { NextRequest, NextResponse } from "next/server";
import {
  authorizeOwnerAccessToken,
  clearOwnerCookies,
  ownerAccessToken,
  ownerRefreshToken,
  ownerServerConfig,
  setOwnerCookies,
} from "@/lib/ownerServer";

export const dynamic = "force-dynamic";

type SupabaseUser = {
  id: string;
  email?: string;
};

async function authenticatedUser(accessToken: string) {
  const config = ownerServerConfig();
  const response = await fetch(`${config.projectUrl}/auth/v1/user`, {
    headers: {
      apikey: config.publishableKey,
      Authorization: `Bearer ${accessToken}`,
    },
    cache: "no-store",
  });
  return response.ok ? ((await response.json()) as SupabaseUser) : null;
}

function safeReturnToValue(
  requested: string | null | undefined,
  origin: string,
) {
  requested ??= "/";
  if (!requested.startsWith("/") || requested.includes("\\")) return "/";
  try {
    const resolved = new URL(requested, origin);
    if (resolved.origin !== origin) return "/";
    return `${resolved.pathname}${resolved.search}`;
  } catch {
    return "/";
  }
}

function safeReturnTo(request: NextRequest) {
  return safeReturnToValue(
    request.nextUrl.searchParams.get("return_to"),
    request.nextUrl.origin,
  );
}

function isSameOrigin(request: NextRequest) {
  return request.headers.get("origin") === request.nextUrl.origin;
}

async function refreshOwnerSession(
  request: NextRequest,
  redirectAfterRefresh: boolean,
) {
  const config = ownerServerConfig();
  const refreshToken = ownerRefreshToken(request);
  if (!refreshToken) {
    if (redirectAfterRefresh) {
      return NextResponse.redirect(new URL("/sign-in", request.url));
    }
    return NextResponse.json(
      { error: "OWNER_SESSION_INVALID" },
      { status: 401 },
    );
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
    !refreshResponse.ok
    || !refreshed?.access_token
    || !refreshed.refresh_token
  ) {
    const output = redirectAfterRefresh
      ? NextResponse.redirect(new URL("/sign-in", request.url))
      : NextResponse.json(
          { error: "OWNER_SESSION_INVALID" },
          { status: 401 },
        );
    clearOwnerCookies(request, output);
    return output;
  }
  const [user, authorization] = await Promise.all([
    authenticatedUser(refreshed.access_token),
    authorizeOwnerAccessToken(refreshed.access_token),
  ]);
  if (!user || !authorization.authorized) {
    const output = redirectAfterRefresh
      ? NextResponse.redirect(new URL("/sign-in", request.url))
      : NextResponse.json(
          {
            error:
              authorization.authorized === false
              && authorization.status === 401
                ? "OWNER_SESSION_INVALID"
                : "OWNER_ACCESS_DENIED",
          },
          {
            status:
              authorization.authorized === false
              && authorization.status === 401
                ? 401
                : 403,
          },
        );
    clearOwnerCookies(request, output);
    return output;
  }
  const output = redirectAfterRefresh
    ? NextResponse.redirect(new URL(safeReturnTo(request), request.url))
    : NextResponse.json({
        user: { id: user.id, email: user.email ?? "" },
        factories: authorization.factories,
      });
  setOwnerCookies(
    request,
    output,
    refreshed.access_token,
    refreshed.refresh_token,
    refreshed.expires_in ?? 3600,
  );
  return output;
}

export async function GET(request: NextRequest) {
  if (request.nextUrl.searchParams.get("action") === "refresh") {
    return refreshOwnerSession(request, true);
  }
  const accessToken = ownerAccessToken(request);
  if (!accessToken) return Response.json({ user: null, factories: [] });
  const [user, authorization] = await Promise.all([
    authenticatedUser(accessToken),
    authorizeOwnerAccessToken(accessToken),
  ]);
  if (!user || !authorization.authorized) {
    const output = NextResponse.json({ user: null, factories: [] });
    clearOwnerCookies(request, output);
    return output;
  }
  return Response.json({
    user: { id: user.id, email: user.email ?? "" },
    factories: authorization.factories,
  });
}

export async function POST(request: NextRequest) {
  const body = (await request.json().catch(() => null)) as {
    action?: "requestPasswordless" | "completePasswordless" | "refresh";
    email?: string;
    accessToken?: string;
    refreshToken?: string;
    expiresIn?: number;
    returnTo?: string;
  } | null;
  if (!body) {
    return Response.json({ error: "OWNER_SESSION_INVALID" }, { status: 400 });
  }
  const config = ownerServerConfig();

  if (body.action === "refresh") {
    if (!isSameOrigin(request)) {
      return Response.json({ error: "OWNER_SESSION_INVALID" }, { status: 403 });
    }
    return refreshOwnerSession(request, false);
  }

  if (body.action === "requestPasswordless") {
    if (!isSameOrigin(request)) {
      return Response.json({ error: "OWNER_SESSION_INVALID" }, { status: 403 });
    }
    const email = body.email?.trim().toLowerCase() ?? "";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return Response.json({ error: "Enter a valid email address." }, { status: 400 });
    }
    const redirectTo = new URL("/sign-in", request.nextUrl.origin);
    redirectTo.searchParams.set(
      "return_to",
      safeReturnToValue(body.returnTo, request.nextUrl.origin),
    );
    const response = await fetch(
      `${config.projectUrl}/auth/v1/otp?redirect_to=${encodeURIComponent(redirectTo.toString())}`,
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
    if (!response.ok && response.status === 429) {
      return Response.json(
        { error: "Please wait before requesting another sign-in link." },
        { status: 429 },
      );
    }
    // Conceal whether an address exists while still surfacing safe rate limits.
    return Response.json({ sent: true });
  }

  if (
    body.action !== "completePasswordless" ||
    !body.accessToken ||
    !body.refreshToken
  ) {
    return Response.json({ error: "OWNER_SESSION_INVALID" }, { status: 400 });
  }
  if (!isSameOrigin(request)) {
    return Response.json({ error: "OWNER_SESSION_INVALID" }, { status: 403 });
  }

  const user = await authenticatedUser(body.accessToken);
  if (!user) {
    return Response.json({ error: "OWNER_SESSION_INVALID" }, { status: 401 });
  }
  const authorization = await authorizeOwnerAccessToken(body.accessToken);
  if (!authorization.authorized) {
    return Response.json(
      {
        error:
          authorization.status === 401
            ? "OWNER_SESSION_INVALID"
            : "OWNER_ACCESS_DENIED",
      },
      { status: authorization.status },
    );
  }

  const output = NextResponse.json({
    user: { id: user.id, email: user.email ?? "" },
    factories: authorization.factories,
  });
  const expiresIn =
    Number.isInteger(body.expiresIn) &&
    (body.expiresIn as number) >= 60 &&
    (body.expiresIn as number) <= 86_400
      ? (body.expiresIn as number)
      : 3600;
  setOwnerCookies(
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
    return Response.json({ error: "OWNER_SESSION_INVALID" }, { status: 403 });
  }
  const output = NextResponse.json({ ok: true });
  clearOwnerCookies(request, output);
  return output;
}
