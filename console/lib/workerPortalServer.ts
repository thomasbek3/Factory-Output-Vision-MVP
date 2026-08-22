// workerPortalServer: the ONE server-side Supabase transport for the
// worker/ops portal (CP4). Every API route goes through these helpers instead
// of hand-rolling fetch calls, so URL assembly, apikey/Bearer headers,
// no-store caching, and error mapping live in exactly one place.
//
// Planes (ADR-0006): Supabase remains the control + media plane. This module
// only deepens the client seam; it does not move any plane.

import { reviewServerConfig } from "@/lib/reviewServer";

export type SupabaseConfig = ReturnType<typeof reviewServerConfig>;

export type WorkerPortalError = Error & {
  status?: number;
  body?: string;
};

export function workerPortalError(message: string, status?: number, body?: string): WorkerPortalError {
  const error = new Error(message) as WorkerPortalError;
  error.status = status;
  error.body = body;
  return error;
}

type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: string;
  accessToken?: string;
  /** Use SUPABASE_SECRET_KEY as BOTH apikey and Bearer (service-role REST calls). */
  serviceRole?: boolean;
};

/** Core fetch with the canonical Supabase headers and no-store caching. */
export async function supabaseFetch(
  path: string,
  options: RequestOptions = {},
): Promise<Response> {
  const config = reviewServerConfig();
  const headers: Record<string, string> = {
    apikey: config.publishableKey,
    Authorization: `Bearer ${config.publishableKey}`,
  };
  if (options.serviceRole) {
    const secretKey = process.env.SUPABASE_SECRET_KEY;
    if (!secretKey) throw workerPortalError("SUPABASE_SECRET_KEY_MISSING", 500);
    headers.apikey = secretKey;
    headers.Authorization = `Bearer ${secretKey}`;
  } else if (options.accessToken) {
    headers.Authorization = `Bearer ${options.accessToken}`;
  }
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  return fetch(`${config.projectUrl}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body,
    cache: "no-store",
  });
}

/**
 * Call a PostgREST RPC as an authenticated reviewer/service role.
 * Returns parsed JSON (null for empty bodies); throws WorkerPortalError with
 * the upstream status + body on failure.
 */
export async function callWorkerRpc<T>(
  functionName: string,
  body: object,
  options: { accessToken?: string } = {},
): Promise<T> {
  const response = await supabaseFetch(`/rest/v1/rpc/${functionName}`, {
    method: "POST",
    body: JSON.stringify(body),
    accessToken: options.accessToken,
  });
  const text = await response.text();
  if (!response.ok) {
    throw workerPortalError(
      text || `RPC_${functionName}_${response.status}`,
      response.status,
      text,
    );
  }
  return (text ? JSON.parse(text) : null) as T;
}

export type SignedMediaResult = {
  signedUrl: string;
  /** Fully-qualified URL (signedPath is relative to the project origin). */
  mediaUrl: string;
};

/**
 * Sign a storage object URL. `role` picks the credential: reviewer access
 * tokens sign user-readable objects; the service key signs anything ops or
 * practice flows need.
 */
export async function signStorageUrl(
  bucket: string,
  mediaPath: string,
  role: { kind: "reviewer"; token: string } | { kind: "service" },
  expiresInSec: number,
): Promise<SignedMediaResult> {
  const config = reviewServerConfig();
  const objectPath = mediaPath.split("/").map(encodeURIComponent).join("/");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (role.kind === "service") {
    // Original practice/preview signing sent the secret as BOTH apikey and
    // bearer; preserve that exactly.
    const secretKey = process.env.SUPABASE_SECRET_KEY;
    if (!secretKey) throw workerPortalError("SUPABASE_SECRET_KEY_MISSING", 500);
    headers.apikey = secretKey;
    headers.Authorization = `Bearer ${secretKey}`;
  } else {
    headers.apikey = config.publishableKey;
    headers.Authorization = `Bearer ${role.token}`;
  }
  const response = await fetch(
    `${config.projectUrl}/storage/v1/object/sign/${encodeURIComponent(bucket)}/${objectPath}`,
    {
      method: "POST",
      headers,
      body: JSON.stringify({ expiresIn: expiresInSec }),
      cache: "no-store",
    },
  );
  if (!response.ok) {
    throw workerPortalError(
      `MEDIA_SIGNING_FAILED_${response.status}`,
      response.status,
    );
  }
  const result = (await response.json()) as { signedURL?: string; signedUrl?: string };
  const signedPath = result.signedURL ?? result.signedUrl;
  if (!signedPath) throw workerPortalError("MEDIA_URL_MISSING", 502);
  return {
    signedUrl: signedPath,
    mediaUrl: signedPath.startsWith("http")
      ? signedPath
      : `${config.projectUrl}/storage/v1${signedPath}`,
  };
}

/** Auth server fetch (auth/v1/*). Same header discipline as supabaseFetch. */
export async function authFetch(
  path: string,
  options: Omit<RequestOptions, "accessToken"> & {
    bearerToken?: string;
    /** Use SUPABASE_SECRET_KEY for both apikey and Bearer (admin endpoints). */
    serviceRole?: boolean;
  } = {},
): Promise<Response> {
  const config = reviewServerConfig();
  const headers: Record<string, string> = {
    apikey: config.publishableKey,
  };
  if (options.serviceRole) {
    const secretKey = process.env.SUPABASE_SECRET_KEY;
    if (!secretKey) throw workerPortalError("SUPABASE_SECRET_KEY_MISSING", 500);
    headers.apikey = secretKey;
    headers.Authorization = `Bearer ${secretKey}`;
  } else if (options.bearerToken) {
    headers.Authorization = `Bearer ${options.bearerToken}`;
  }
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  return fetch(`${config.projectUrl}/auth/v1${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body,
    cache: "no-store",
  });
}
