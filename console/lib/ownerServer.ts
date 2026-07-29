import { NextRequest, NextResponse } from "next/server";

export const ownerAccessCookie = "fv_owner_access";
export const ownerRefreshCookie = "fv_owner_refresh";

export class OwnerDataError extends Error {
  constructor(
    readonly status: 401 | 403 | 409 | 422 | 503,
    readonly publicCode:
      | "OWNER_AUTH_REQUIRED"
      | "OWNER_ACCESS_DENIED"
      | "OWNER_CONFLICT"
      | "OWNER_DOMAIN_INVALID"
      | "OWNER_DATA_UNAVAILABLE",
    readonly providerCode?: string,
  ) {
    super(publicCode);
  }
}

async function ownerResponseError(response: Response) {
  const payload = (await response.clone().json().catch(() => null)) as {
    code?: string;
  } | null;
  const providerCode = payload?.code;
  if (response.status === 401 || providerCode === "28000") {
    return new OwnerDataError(401, "OWNER_AUTH_REQUIRED", providerCode);
  }
  if (response.status === 403 || providerCode === "42501") {
    return new OwnerDataError(403, "OWNER_ACCESS_DENIED", providerCode);
  }
  if (
    response.status === 409 ||
    providerCode === "23P01" ||
    providerCode === "23505" ||
    providerCode === "55000"
  ) {
    return new OwnerDataError(409, "OWNER_CONFLICT", providerCode);
  }
  if (
    response.status === 400 ||
    response.status === 422 ||
    providerCode === "23514" ||
    providerCode === "22023"
  ) {
    return new OwnerDataError(422, "OWNER_DOMAIN_INVALID", providerCode);
  }
  return new OwnerDataError(503, "OWNER_DATA_UNAVAILABLE", providerCode);
}

export function ownerServerConfig() {
  const projectUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!projectUrl || !publishableKey) {
    throw new Error("Supabase owner configuration is missing.");
  }
  return { projectUrl, publishableKey };
}

export function ownerAccessToken(request: NextRequest) {
  return request.cookies.get(ownerAccessCookie)?.value ?? null;
}

export function ownerRefreshToken(request: NextRequest) {
  return request.cookies.get(ownerRefreshCookie)?.value ?? null;
}

function ownerHeaders(accessToken: string) {
  const config = ownerServerConfig();
  return {
    apikey: config.publishableKey,
    Authorization: `Bearer ${accessToken}`,
    "Content-Type": "application/json",
  };
}

function storageObjectPath(bucket: string, objectPath: string) {
  const parts = [bucket, ...objectPath.split("/")];
  if (
    parts.some(
      (part) => !part || part === "." || part === "..",
    )
  ) {
    throw new OwnerDataError(422, "OWNER_DOMAIN_INVALID");
  }
  return parts
    .map((part) => encodeURIComponent(part))
    .join("/");
}

export async function authorizeOwner(
  request: NextRequest,
  factoryId: string,
) {
  const accessToken = ownerAccessToken(request);
  if (!accessToken) return { authorized: false as const, status: 401 };
  const result = await authorizeOwnerAccessToken(accessToken, factoryId);
  return result.authorized
    ? { authorized: true as const, accessToken, factories: result.factories }
    : { authorized: false as const, status: result.status };
}

export async function authorizeOwnerAccessToken(
  accessToken: string,
  factoryId: string | null = null,
) {
  const config = ownerServerConfig();
  const response = await fetch(
    `${config.projectUrl}/rest/v1/rpc/owner_authorize_session`,
    {
      method: "POST",
      headers: ownerHeaders(accessToken),
      body: JSON.stringify({ p_factory_id: factoryId }),
      cache: "no-store",
    },
  );
  if (!response.ok) {
    if (response.status === 401) {
      return { authorized: false as const, status: 401 as const, factories: [] };
    }
    if (response.status === 403) {
      return { authorized: false as const, status: 403 as const, factories: [] };
    }
    throw await ownerResponseError(response);
  }
  const result = (await response.json()) as {
    authorized?: boolean;
    factories?: unknown[];
  };
  return result.authorized === true
    ? { authorized: true as const, factories: result.factories ?? [] }
    : { authorized: false as const, status: 403 as const, factories: [] };
}

export async function ownerRest<T>(
  accessToken: string,
  path: string,
  init: RequestInit = {},
) {
  const config = ownerServerConfig();
  const response = await fetch(`${config.projectUrl}/rest/v1/${path}`, {
    ...init,
    headers: {
      ...ownerHeaders(accessToken),
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!response.ok) throw await ownerResponseError(response);
  return (await response.json()) as T;
}

export async function ownerRestAll<T>(
  accessToken: string,
  path: string,
  options: {
    pageSize?: number;
    maxRows?: number;
  } = {},
): Promise<T[]> {
  const pageSize = options.pageSize ?? 1_000;
  const maxRows = options.maxRows ?? 100_000;
  if (
    !Number.isInteger(pageSize)
    || pageSize < 1
    || pageSize > 1_000
    || !Number.isInteger(maxRows)
    || maxRows < pageSize
  ) {
    throw new OwnerDataError(422, "OWNER_DOMAIN_INVALID");
  }
  const config = ownerServerConfig();
  const rows: T[] = [];
  let expectedTotal: number | null = null;

  while (rows.length < maxRows) {
    const offset = rows.length;
    const response = await fetch(`${config.projectUrl}/rest/v1/${path}`, {
      headers: {
        ...ownerHeaders(accessToken),
        Prefer: "count=exact",
        Range: `${offset}-${offset + pageSize - 1}`,
        "Range-Unit": "items",
      },
      cache: "no-store",
    });
    if (!response.ok) throw await ownerResponseError(response);
    const payload = await response.json();
    if (!Array.isArray(payload)) {
      throw new OwnerDataError(503, "OWNER_DATA_UNAVAILABLE");
    }
    const contentRange = response.headers.get("content-range");
    const emptyMatch = contentRange?.match(/^\*\/(\d+)$/);
    const rangeMatch = contentRange?.match(/^(\d+)-(\d+)\/(\d+)$/);
    if (!emptyMatch && !rangeMatch) {
      throw new OwnerDataError(503, "OWNER_DATA_UNAVAILABLE");
    }
    const total = Number(emptyMatch?.[1] ?? rangeMatch?.[3]);
    if (
      !Number.isSafeInteger(total)
      || total < 0
      || total > maxRows
      || (expectedTotal !== null && expectedTotal !== total)
    ) {
      throw new OwnerDataError(503, "OWNER_DATA_UNAVAILABLE");
    }
    expectedTotal = total;
    if (rangeMatch) {
      const rangeStart = Number(rangeMatch[1]);
      const rangeEnd = Number(rangeMatch[2]);
      if (
        rangeStart !== offset
        || rangeEnd < rangeStart
        || rangeEnd - rangeStart + 1 !== payload.length
        || payload.length > pageSize
      ) {
        throw new OwnerDataError(503, "OWNER_DATA_UNAVAILABLE");
      }
    } else if (payload.length !== 0 || total !== 0) {
      throw new OwnerDataError(503, "OWNER_DATA_UNAVAILABLE");
    }
    if (rows.length + payload.length > total) {
      throw new OwnerDataError(503, "OWNER_DATA_UNAVAILABLE");
    }
    rows.push(...(payload as T[]));
    if (rows.length === total) return rows;
    if (payload.length === 0) {
      throw new OwnerDataError(503, "OWNER_DATA_UNAVAILABLE");
    }
  }

  throw new OwnerDataError(503, "OWNER_DATA_UNAVAILABLE");
}

export async function ownerRpc<T>(
  accessToken: string,
  functionName: string,
  body: object,
) {
  return ownerRest<T>(accessToken, `rpc/${functionName}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function ownerSignedStorageUrl(
  accessToken: string,
  bucket: string,
  objectPath: string,
  expiresIn = 300,
) {
  const config = ownerServerConfig();
  const response = await fetch(
    `${config.projectUrl}/storage/v1/object/sign/${storageObjectPath(
      bucket,
      objectPath,
    )}`,
    {
      method: "POST",
      headers: ownerHeaders(accessToken),
      body: JSON.stringify({ expiresIn }),
      cache: "no-store",
    },
  );
  if (!response.ok) throw await ownerResponseError(response);
  const result = (await response.json()) as {
    signedURL?: string;
    signedUrl?: string;
  };
  const signedPath = result.signedURL ?? result.signedUrl;
  if (!signedPath) {
    throw new OwnerDataError(503, "OWNER_DATA_UNAVAILABLE");
  }
  const storageSignedPath = signedPath.startsWith("/storage/v1/")
    ? signedPath
    : `/storage/v1/${signedPath.replace(/^\/+/, "")}`;
  return {
    signedUrl: new URL(storageSignedPath, config.projectUrl).toString(),
    expiresIn,
  };
}

export function setOwnerCookies(
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
  response.cookies.set(ownerAccessCookie, accessToken, {
    ...common,
    maxAge: expiresIn,
  });
  response.cookies.set(ownerRefreshCookie, refreshToken, {
    ...common,
    maxAge: 60 * 60 * 24 * 30,
  });
}

export function clearOwnerCookies(
  request: NextRequest,
  response: NextResponse,
) {
  const secure =
    process.env.NODE_ENV === "production" ||
    request.nextUrl.protocol === "https:";
  for (const name of [ownerAccessCookie, ownerRefreshCookie]) {
    response.cookies.set(name, "", {
      httpOnly: true,
      sameSite: "strict",
      secure,
      path: "/",
      maxAge: 0,
    });
  }
}
