import { NextRequest, NextResponse } from "next/server";

export const opsAccessCookie = "fv_ops_access";
export const opsRefreshCookie = "fv_ops_refresh";

export function opsServerConfig() {
  const projectUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!projectUrl || !publishableKey) {
    throw new Error("Supabase ops configuration is missing.");
  }
  return { projectUrl, publishableKey };
}

export function opsAccessToken(request: NextRequest) {
  return request.cookies.get(opsAccessCookie)?.value ?? null;
}

export function opsRefreshToken(request: NextRequest) {
  return request.cookies.get(opsRefreshCookie)?.value ?? null;
}

function opsHeaders(accessToken: string) {
  const config = opsServerConfig();
  return {
    apikey: config.publishableKey,
    Authorization: `Bearer ${accessToken}`,
    "Content-Type": "application/json",
  };
}

async function opsRpcWithToken<T>(
  accessToken: string,
  functionName: string,
  body: object,
) {
  const config = opsServerConfig();
  const response = await fetch(
    `${config.projectUrl}/rest/v1/rpc/${functionName}`,
    {
      method: "POST",
      headers: opsHeaders(accessToken),
      body: JSON.stringify(body),
      cache: "no-store",
    },
  );
  const text = await response.text();
  if (!response.ok) {
    throw new Error(
      response.status === 401 || response.status === 403
        ? "OPS_ACCESS_DENIED"
        : text || `OPS_RPC_${response.status}`,
    );
  }
  return (text ? JSON.parse(text) : null) as T;
}

export async function authorizeOps(
  request: NextRequest,
  factoryId: string | null = null,
) {
  const accessToken = opsAccessToken(request);
  if (!accessToken) return { authorized: false as const, status: 401 as const };
  const result = await authorizeOpsAccessToken(accessToken, factoryId);
  return result.authorized
    ? { authorized: true as const, accessToken }
    : { authorized: false as const, status: 403 as const };
}

export async function authorizeOpsAccessToken(
  accessToken: string,
  factoryId: string | null = null,
) {
  try {
    await opsRpcWithToken<boolean>(accessToken, "ops_assert_access", {
      p_factory_id: factoryId,
    });
    return { authorized: true as const };
  } catch (error) {
    if (error instanceof Error && error.message === "OPS_ACCESS_DENIED") {
      return { authorized: false as const, status: 403 as const };
    }
    throw error;
  }
}

export async function opsRpc<T>(
  request: NextRequest,
  functionName: string,
  body: object,
) {
  const accessToken = opsAccessToken(request);
  if (!accessToken) throw new Error("OPS_AUTH_REQUIRED");
  return opsRpcWithToken<T>(accessToken, functionName, body);
}

export function setOpsCookies(
  request: NextRequest,
  response: NextResponse,
  accessToken: string,
  refreshToken: string,
  expiresIn: number,
) {
  const common = {
    httpOnly: true,
    sameSite: "strict" as const,
    secure:
      process.env.NODE_ENV === "production" ||
      request.nextUrl.protocol === "https:",
    path: "/",
  };
  response.cookies.set(opsAccessCookie, accessToken, {
    ...common,
    maxAge: expiresIn,
  });
  response.cookies.set(opsRefreshCookie, refreshToken, {
    ...common,
    maxAge: 60 * 60 * 24 * 30,
  });
}

export function clearOpsCookies(
  request: NextRequest,
  response: NextResponse,
) {
  const common = {
    httpOnly: true,
    sameSite: "strict" as const,
    secure:
      process.env.NODE_ENV === "production" ||
      request.nextUrl.protocol === "https:",
    path: "/",
    maxAge: 0,
  };
  response.cookies.set(opsAccessCookie, "", common);
  response.cookies.set(opsRefreshCookie, "", common);
}
